"""Simulated requests and the suite's input files (spec section 12)."""

import csv
import math
import random
import tomllib
import zlib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from elevator_sim.config import (
    ConfigError,
    SimConfig,
    is_whole_number,
    load_config,
)
from elevator_sim.requests import CSV_HEADER, Request, load_requests

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
# The most requests the generator will expect to make. The PDF sets no limit, but a high enough
# rate never finishes: 1e9 per tick for 1,000 ticks would need a trillion requests. This value only
# has to stop runaway settings, so it is about 2,200 times the largest suite input (4,548 requests),
# and it still fits on the development PC, at about 1.5 GB and 30 seconds (M21).
MAX_GENERATED_REQUESTS = 10_000_000


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


def _check_generation(pattern: str, rate: float, ticks: int, floors: int) -> None:
    if pattern not in PATTERNS:
        raise ConfigError(f"unknown pattern {pattern!r}: use {', '.join(PATTERNS)}")
    if isinstance(rate, bool) or not isinstance(rate, int | float) or not 0 < rate < math.inf:
        raise ConfigError(f"rate must be a positive finite number, not {rate!r}")
    if not is_whole_number(ticks) or ticks < 1:
        raise ConfigError(f"ticks must be a whole number of at least 1, not {ticks!r}")
    if not is_whole_number(floors) or floors < 2:
        raise ConfigError(f"floors must be a whole number of at least 2, not {floors!r}")
    if ticks > MAX_GENERATED_REQUESTS / rate:
        limit = f"{MAX_GENERATED_REQUESTS:,}"
        raise ConfigError(f"rate {rate} for {ticks} ticks expects more than {limit} requests")
    if PATTERNS[pattern] is not None and floors < 3:
        raise ConfigError(f"pattern {pattern!r} needs at least 3 floors for interfloor trips")


def generate_requests(
    pattern: str, rate: float, ticks: int, seed: int, floors: int
) -> list[Request]:
    """Poisson arrivals: exponential gaps, with the running time rounded down to a tick."""
    _check_generation(pattern, rate, ticks, floors)
    mix = PATTERNS[pattern]
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
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise ConfigError(f"{path}: {error}") from None


def _rate_for(spec: InputSpec, rates: dict[str, dict[str, float]]) -> float:
    table = rates.get(spec.building)
    rate = table.get(spec.pattern) if isinstance(table, dict) else None
    if isinstance(rate, bool) or not isinstance(rate, int | float):
        name = f"{spec.building} {spec.pattern}"
        raise ConfigError(f"no usable rate for {name}: run generate --calibrate")
    return rate


def input_requests(spec: InputSpec, rates: dict[str, dict[str, float]]) -> list[Request]:
    config = building_config(spec.building)
    rate = _rate_for(spec, rates) * LOADS[spec.load]
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
    """Write any missing suite inputs, and stop at one that no longer matches the rates."""
    rates = load_rates()
    for spec in suite_inputs(seeds):
        path = out / spec.name
        requests = input_requests(spec, rates)
        if not path.exists():
            write_requests(path, requests)
        elif load_requests(path, building_config(spec.building).floors) != requests:
            raise ConfigError(f"{path} doesn't match the current rates: run generate --suite")
