"""Measuring the saturation rates that set each load level (spec section 12.4)."""

import statistics
from collections.abc import Callable, Mapping
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

from elevator_sim.config import ConfigError, SimConfig, check_workers
from elevator_sim.engine import SimulationResult, simulate
from elevator_sim.workload import (
    ARRIVAL_TICKS,
    LOADS,
    MAX_GENERATED_REQUESTS,
    PATTERNS,
    RATES_FILE,
    generate_requests,
    input_seed,
    load_rates,
)

CALIBRATION_SEEDS = (1, 2, 3)


def backlog_at(result: SimulationResult, tick: int) -> int:
    """Passengers who have made their request but haven't been delivered by this tick."""
    return sum(
        1
        for p in result.passengers
        if p.request.time <= tick and (p.dropoff_tick is None or p.dropoff_tick > tick)
    )


def backlog_growth(result: SimulationResult) -> int:
    """How much the backlog grew over the second half of the arrivals."""
    return backlog_at(result, ARRIVAL_TICKS) - backlog_at(result, ARRIVAL_TICKS // 2)


def find_rate_boundary(passes: Callable[[float], bool]) -> float:
    """Find a passing rate, in whole hundredths, where one hundredth more fails.

    Close to saturation, passing isn't strictly monotonic: a few rates can pass just above one that
    fails. So this finds one edge of a narrow band, not a single true limit (M23).
    """
    if not passes(0.01):
        raise ConfigError("calibration found no passing rate: even 0.01 per tick fails")
    low, high = 1, 2
    while passes(high / 100):
        low, high = high, high * 2
        if high / 100 > MAX_GENERATED_REQUESTS / ARRIVAL_TICKS:
            raise ConfigError(f"calibration found no failing rate, up to {low / 100} per tick")
    while high - low > 1:
        middle = (low + high) // 2
        if passes(middle / 100):
            low = middle
        else:
            high = middle
    return low / 100


def check_load_levels(rate: float, passes: Callable[[float], bool]) -> None:
    """Confirm the rate puts heavy load below the boundary and overload above it.

    That is what the rate is for, and the search can't show it, because passing isn't strictly
    monotonic near the boundary (M23).
    """
    if not passes(rate * LOADS["heavy"]):
        raise ConfigError(f"calibrated rate {rate}: the fleet doesn't keep up with heavy load")
    if passes(rate * LOADS["overload"]):
        raise ConfigError(f"calibrated rate {rate}: the fleet keeps up with overload")


def saturation_rate(
    building: str,
    pattern: str,
    config: SimConfig,
    algorithm: str = "marginal_insertion",
    guard: str = "none",
) -> float:
    """A measured saturation rate. Without a guard by default, so the frozen rates reproduce (M6).

    A saturated fleet is one whose backlog keeps growing. The size of the backlog at one tick
    can't show that, because it includes everyone simply in transit (G15). This is a working
    measure from short runs on three seeds, not a proof of long-run capacity (M23).
    """
    target = replace(config, algorithm=algorithm, behaviour="min_time", guard=guard)

    def passes(rate: float) -> bool:
        growth = []
        for seed in CALIBRATION_SEEDS:
            run_seed = input_seed(building, pattern, "calibration", seed)
            requests = generate_requests(pattern, rate, ARRIVAL_TICKS, run_seed, target.floors)
            growth.append(backlog_growth(simulate(requests, target)))
        return statistics.fmean(growth) <= target.elevators * target.capacity

    rate = find_rate_boundary(passes)
    check_load_levels(rate, passes)
    return rate


def _calibrate_pair(job: tuple[str, str, SimConfig, str, str]) -> tuple[str, str, float]:
    building, pattern, config, algorithm, guard = job
    return building, pattern, saturation_rate(building, pattern, config, algorithm, guard)


def write_rates(path: Path, rates: dict[str, dict[str, float]]) -> None:
    lines = ["# Measured saturation arrival rates, in passengers per tick (spec section 12.4, M6)."]
    for building in sorted(rates):
        lines.append(f"\n[{building}]")
        lines.extend(f"{pattern} = {rates[building][pattern]}" for pattern in PATTERNS)
    with path.open("w", encoding="utf-8", newline="") as file:
        file.write("\n".join(lines) + "\n")


def calibrate(
    buildings: Mapping[str, SimConfig],
    workers: int,
    out: Path = RATES_FILE,
    algorithm: str = "marginal_insertion",
    guard: str = "none",
) -> None:
    """Measure rates for these buildings, keeping any others already in the file."""
    check_workers(workers)
    rates = load_rates(out) if out.exists() else {}
    jobs = [
        (name, pattern, config, algorithm, guard)
        for name, config in buildings.items()
        for pattern in PATTERNS
    ]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for building, pattern, rate in pool.map(_calibrate_pair, jobs):
            rates.setdefault(building, {})[pattern] = rate
    write_rates(out, rates)
