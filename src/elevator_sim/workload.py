"""Simulated requests and the suite's input files (spec section 12)."""

import csv
import math
import random
import tomllib
import zlib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
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

BUILDINGS = (
    "1car-10floor-6cap",
    "3car-10floor-6cap",
    "3car-35floor-6cap",
    "3car-60floor-6cap",
    "6car-60floor-6cap",
    "9car-60floor-6cap",
    "3car-60floor-9cap",
    "3car-60floor-12cap",
)
# Phase 2 (M30). Each express case runs on the passengers of the building it changes, so that a
# difference comes from the express cars and not the traffic. EXPRESS_OWN_LIMIT also runs at its own
# limits, which repeats Phase 1's runs and gives the 6-car express building its own traffic.
EXPRESS_BUILDINGS = {
    "3car-60floor-6cap-1high31": "3car-60floor-6cap",
    "3car-60floor-6cap-1high41": "3car-60floor-6cap",
    "3car-60floor-6cap-2high31": "3car-60floor-6cap",
    "3car-60floor-6cap-split30": "3car-60floor-6cap",
    "3car-60floor-6cap-overlap": "3car-60floor-6cap",
    "6car-60floor-6cap-express": "6car-60floor-6cap",
}
EXPRESS_OWN_LIMIT = (
    "3car-10floor-6cap",
    "3car-60floor-6cap",
    "6car-60floor-6cap",
    "6car-60floor-6cap-express",
)
# Seeds keep the name each case first had, so renaming a case changes no request (M27).
_FIRST_NAMES = {
    "1car-10floor-6cap": "simple",
    "3car-10floor-6cap": "baseline",
    "3car-60floor-6cap": "bridge",
}
# Incoming, outgoing and interfloor percentages. None draws both floors from the whole building.
PATTERNS: dict[str, tuple[int, int, int] | None] = {
    "uniform": None,
    "up_peak": (85, 10, 5),
    "down_peak": (10, 85, 5),
    "lunch": (40, 40, 20),
}
LOADS = {"light": 0.3, "medium": 0.6, "heavy": 0.9, "overload": 1.2}
# Own limit sets each case's load from its own saturation rate. Fixed gives every case the same
# arrivals, so that a difference between cases comes from the case and not its traffic (M28).
OWN_LIMIT = "own_limit"
FIXED = "fixed"
# The case that sets the fixed load. It has the lowest limits, so every case can carry that load.
FIXED_LOAD_CASE = "3car-60floor-6cap"
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
    fixed: bool = False

    @property
    def name(self) -> str:
        source = _fixed_load_source(self.building) if self.fixed else self.building
        return input_name(source, self.pattern, self.load, self.seed)


def _fixed_load_source(building: str) -> str:
    """What a case's fixed-load file is named after. Cases of one height share a file."""
    floors = building_config(building).floors
    if floors == building_config(FIXED_LOAD_CASE).floors:
        return FIXED_LOAD_CASE
    return f"fixed-{floors}floor"


def input_name(building: str, pattern: str, load: str, seed: int) -> str:
    return f"{building}_{pattern}_{load}_s{seed}.csv"


def input_seed(building: str, pattern: str, load: str, seed: int) -> int:
    """A seed per file, so inputs are independent and repeatable."""
    first_name = _FIRST_NAMES.get(building, building)
    return zlib.crc32(f"{first_name}|{pattern}|{load}|{seed}".encode())


def suite_inputs(
    seeds: Sequence[int] = SEEDS, buildings: Sequence[str] = BUILDINGS
) -> Iterator[InputSpec]:
    for building in buildings:
        for pattern in PATTERNS:
            for load in LOADS:
                for seed in seeds:
                    yield InputSpec(building, pattern, load, seed)


def fixed_inputs(seeds: Sequence[int] = SEEDS) -> Iterator[InputSpec]:
    """The fixed load on every other case, because that case's own runs already are that load."""
    for spec in suite_inputs(seeds):
        if spec.building != FIXED_LOAD_CASE:
            yield replace(spec, fixed=True)


def _input_files(seeds: Sequence[int]) -> dict[str, InputSpec]:
    """One spec per file, because cases can share a fixed-load file."""
    specs = [*suite_inputs(seeds), *fixed_inputs(seeds), *suite_inputs(seeds, EXPRESS_OWN_LIMIT)]
    return {spec.name: spec for spec in specs}


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


def _fixed_requests(spec: InputSpec, rates: dict[str, dict[str, float]]) -> list[Request]:
    """The fixed-load case's arrivals, with their floors redrawn if this case's height differs."""
    arrivals = input_requests(replace(spec, building=FIXED_LOAD_CASE, fixed=False), rates)
    floors = building_config(spec.building).floors
    if floors == building_config(FIXED_LOAD_CASE).floors:
        return arrivals
    source = _fixed_load_source(spec.building)
    rng = random.Random(input_seed(source, spec.pattern, spec.load, spec.seed))
    mix = PATTERNS[spec.pattern]
    return [Request(r.time, r.id, *_trip(rng, mix, floors)) for r in arrivals]


def input_requests(spec: InputSpec, rates: dict[str, dict[str, float]]) -> list[Request]:
    if spec.fixed:
        return _fixed_requests(spec, rates)
    config = building_config(spec.building)
    rate = _rate_for(spec, rates) * LOADS[spec.load]
    seed = input_seed(spec.building, spec.pattern, spec.load, spec.seed)
    return generate_requests(spec.pattern, rate, ARRIVAL_TICKS, seed, config.floors)


def write_suite(out: Path, seeds: Sequence[int] = SEEDS) -> int:
    rates = load_rates()
    files = _input_files(seeds)
    for name, spec in files.items():
        write_requests(out / name, input_requests(spec, rates))
    return len(files)


def ensure_inputs(out: Path, seeds: Sequence[int] = SEEDS) -> None:
    """Write any missing suite inputs, and stop at one that no longer matches the rates."""
    rates = load_rates()
    for name, spec in _input_files(seeds).items():
        path = out / name
        requests = input_requests(spec, rates)
        if not path.exists():
            write_requests(path, requests)
        elif load_requests(path, building_config(spec.building).floors) != requests:
            raise ConfigError(f"{path} doesn't match the current rates: run generate --suite")
