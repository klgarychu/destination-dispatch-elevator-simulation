"""Simulated requests and load calibration (spec section 12)."""

import csv
import random
import statistics
import tomllib
import zlib
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path

from elevator_sim.config import ConfigError, SimConfig, load_config
from elevator_sim.engine import SimulationResult, simulate
from elevator_sim.requests import CSV_HEADER, Request

CONFIG_DIR = Path("configs")
RATES_FILE = CONFIG_DIR / "load_rates.toml"

BUILDINGS = ("baseline", "tall")
# Incoming, outgoing and interfloor percentages. None draws both floors from the whole building.
PATTERNS: dict[str, tuple[int, int, int] | None] = {
    "uniform": None,
    "up_peak": (85, 10, 5),
    "down_peak": (10, 85, 5),
    "lunch": (40, 40, 20),
}
LOADS = {"light": 0.3, "medium": 0.6, "heavy": 0.9, "overload": 1.2}
SEEDS = (1, 2, 3, 4, 5)
ARRIVAL_TICKS = 1000
CALIBRATION_SEEDS = (1, 2, 3)


@dataclass(frozen=True, slots=True)
class InputSpec:
    building: str
    pattern: str
    load: str
    seed: int

    @property
    def name(self) -> str:
        return input_name(self.building, self.pattern, self.load, self.seed)


def input_name(building: str, pattern: str, load: str, seed: int) -> str:
    return f"{building}_{pattern}_{load}_s{seed}.csv"


def input_seed(building: str, pattern: str, load: str, seed: int) -> int:
    """A seed per file, so inputs are independent and repeatable."""
    return zlib.crc32(f"{building}|{pattern}|{load}|{seed}".encode())


def suite_inputs(seeds: Sequence[int] = SEEDS) -> Iterator[InputSpec]:
    for building in BUILDINGS:
        for pattern in PATTERNS:
            for load in LOADS:
                for seed in seeds:
                    yield InputSpec(building, pattern, load, seed)


def _trip(rng: random.Random, mix: tuple[int, int, int] | None, floors: int) -> tuple[int, int]:
    if mix is None:
        source, dest = rng.sample(range(1, floors + 1), 2)
        return source, dest
    incoming, outgoing, _ = mix
    roll = rng.randrange(100)
    if roll < incoming:
        return 1, rng.randint(2, floors)
    if roll < incoming + outgoing:
        return rng.randint(2, floors), 1
    source, dest = rng.sample(range(2, floors + 1), 2)
    return source, dest


def generate_requests(
    pattern: str, rate: float, ticks: int, seed: int, floors: int
) -> list[Request]:
    """Poisson arrivals: exponential gaps, with the running time rounded down to a tick."""
    if pattern not in PATTERNS:
        raise ConfigError(f"unknown pattern {pattern!r}: use {', '.join(PATTERNS)}")
    if rate <= 0:
        raise ConfigError(f"rate must be positive, not {rate}")
    mix = PATTERNS[pattern]
    if mix is not None and floors < 3:
        raise ConfigError(f"pattern {pattern!r} needs at least 3 floors for interfloor trips")

    rng = random.Random(seed)
    requests: list[Request] = []
    clock = rng.expovariate(rate)
    while clock < ticks:
        source, dest = _trip(rng, mix, floors)
        requests.append(Request(int(clock), f"p{len(requests) + 1:06d}", source, dest))
        clock += rng.expovariate(rate)
    return requests


def write_requests(path: Path, requests: Sequence[Request]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(CSV_HEADER)
        writer.writerows((r.time, r.id, r.source, r.dest) for r in requests)


def building_config(building: str) -> SimConfig:
    return load_config(CONFIG_DIR / f"{building}.toml")


def load_rates(path: Path = RATES_FILE) -> dict[str, dict[str, float]]:
    try:
        with path.open("rb") as file:
            return tomllib.load(file)
    except FileNotFoundError:
        raise ConfigError(f"{path} not found: run generate --calibrate first") from None


def input_requests(spec: InputSpec, rates: dict[str, dict[str, float]]) -> list[Request]:
    config = building_config(spec.building)
    rate = rates[spec.building][spec.pattern] * LOADS[spec.load]
    seed = input_seed(spec.building, spec.pattern, spec.load, spec.seed)
    return generate_requests(spec.pattern, rate, ARRIVAL_TICKS, seed, config.floors)


def write_suite(out: Path, seeds: Sequence[int] = SEEDS) -> int:
    rates = load_rates()
    count = 0
    for spec in suite_inputs(seeds):
        write_requests(out / spec.name, input_requests(spec, rates))
        count += 1
    return count


def ensure_inputs(out: Path, seeds: Sequence[int] = SEEDS) -> None:
    """Write any suite inputs that are missing, without touching the ones already there."""
    rates = load_rates()
    for spec in suite_inputs(seeds):
        if not (out / spec.name).exists():
            write_requests(out / spec.name, input_requests(spec, rates))


def undelivered_at(result: SimulationResult, tick: int) -> int:
    return sum(1 for p in result.passengers if p.dropoff_tick is None or p.dropoff_tick > tick)


def bisect_highest_rate(passes: Callable[[float], bool]) -> float:
    """Find the highest passing rate to two decimals, working in whole hundredths."""
    low, high = 1, 2
    while passes(high / 100):
        low, high = high, high * 2
    while high - low > 1:
        middle = (low + high) // 2
        if passes(middle / 100):
            low = middle
        else:
            high = middle
    return low / 100


def saturation_rate(building: str, pattern: str) -> float:
    """Calibrate without a guard, so that inputs stay identical across phases (M6)."""
    config = replace(
        building_config(building), algorithm="marginal_insertion", behaviour="min_time"
    )

    def passes(rate: float) -> bool:
        undelivered = []
        for seed in CALIBRATION_SEEDS:
            run_seed = input_seed(building, pattern, "calibration", seed)
            requests = generate_requests(pattern, rate, ARRIVAL_TICKS, run_seed, config.floors)
            undelivered.append(undelivered_at(simulate(requests, config), ARRIVAL_TICKS))
        return statistics.fmean(undelivered) <= config.elevators * config.capacity

    return bisect_highest_rate(passes)


def _calibrate_pair(pair: tuple[str, str]) -> tuple[str, str, float]:
    building, pattern = pair
    return building, pattern, saturation_rate(building, pattern)


def write_rates(path: Path, rates: dict[str, dict[str, float]]) -> None:
    lines = ["# Measured saturation arrival rates, in passengers per tick (spec section 12.4, M6)."]
    for building in sorted(rates):
        lines.append(f"\n[{building}]")
        lines.extend(f"{pattern} = {rates[building][pattern]}" for pattern in PATTERNS)
    with path.open("w", encoding="utf-8", newline="") as file:
        file.write("\n".join(lines) + "\n")


def calibrate(buildings: Sequence[str], workers: int, out: Path = RATES_FILE) -> None:
    """Measure rates for these buildings, keeping any others already in the file."""
    rates = load_rates(out) if out.exists() else {}
    pairs = [(building, pattern) for building in buildings for pattern in PATTERNS]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for building, pattern, rate in pool.map(_calibrate_pair, pairs):
            rates.setdefault(building, {})[pattern] = rate
    write_rates(out, rates)
