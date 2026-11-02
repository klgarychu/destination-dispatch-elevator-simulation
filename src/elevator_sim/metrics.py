"""Statistics for one run. Plain facts only: nothing here compares configurations (R-31)."""

import math
import statistics
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from elevator_sim.boarding.guards import make_guard
from elevator_sim.engine import SimulationResult
from elevator_sim.requests import Passenger


@dataclass(frozen=True, slots=True)
class TimeStats:
    min: int
    mean: float
    max: int
    p95: int
    stdev: float


def nearest_rank(values: Sequence[int], percent: int) -> int:
    ordered = sorted(values)
    return ordered[math.ceil(percent / 100 * len(ordered)) - 1]


def time_stats(values: Sequence[int]) -> TimeStats | None:
    if not values:
        return None
    return TimeStats(
        min(values),
        statistics.fmean(values),
        max(values),
        nearest_rank(values, 95),
        statistics.pstdev(values),
    )


def jain_index(values: Sequence[int]) -> float:
    """A 0 to 1 score of how evenly time is shared. All zeros count as perfectly even."""
    squares = sum(value * value for value in values)
    if squares == 0:
        return 1.0
    return float(sum(values) ** 2 / (len(values) * squares))


def wait_time(passenger: Passenger) -> int:
    assert passenger.board_tick is not None
    return passenger.board_tick - passenger.request.time


def total_time(passenger: Passenger) -> int:
    assert passenger.dropoff_tick is not None
    return passenger.dropoff_tick - passenger.request.time


def run_stats(result: SimulationResult) -> dict[str, int | float | None]:
    """The Size, Wait, Total, Cars, Fairness and Guards columns of one simulation_stats.csv row."""
    waits = [wait_time(p) for p in result.passengers]
    totals = [total_time(p) for p in result.passengers]
    left_behind = [p.times_left_behind for p in result.passengers]
    row: dict[str, int | float | None] = {
        "passengers": len(result.passengers),
        "ticks": result.ticks,
        "passengers_per_tick": len(result.passengers) / result.ticks if result.ticks else None,
    }
    for name, stats in (("wait", time_stats(waits)), ("total", time_stats(totals))):
        row[f"{name}_min"] = stats.min if stats else None
        row[f"{name}_mean"] = stats.mean if stats else None
        row[f"{name}_max"] = stats.max if stats else None
        row[f"{name}_p95"] = stats.p95 if stats else None
        row[f"{name}_stdev"] = stats.stdev if stats else None
    moves = result.moves
    row["avg_car_load"] = result.rider_moves / moves if moves else None
    row["empty_travel_share"] = result.empty_moves / moves if moves else None
    row["jain_wait"] = jain_index(waits) if waits else None
    row["jain_total"] = jain_index(totals) if totals else None
    row["times_left_behind"] = sum(left_behind)
    row["max_left_behind_one_passenger"] = max(left_behind, default=0)
    # Flags only ever turn on, so a passenger ever flagged is flagged as they board.
    guard = make_guard(result.config)
    row["flagged_passengers"] = sum(
        1 for p in result.passengers if p.board_tick is not None and guard.flags(p, p.board_tick)
    )
    row["held_seat_ticks"] = result.held_seat_ticks
    limit = result.config.wait_limit_ticks
    row["share_above_wait_limit"] = (
        sum(1 for wait in waits if wait > limit) / len(waits) if waits else None
    )
    return row


def _peak_waiting(passengers: Sequence[Passenger]) -> int:
    """The most passengers waiting at the end of any tick."""
    change: Counter[int] = Counter()
    for passenger in passengers:
        if wait_time(passenger):
            change[passenger.request.time] += 1
            assert passenger.board_tick is not None
            change[passenger.board_tick] -= 1
    waiting = peak = 0
    for tick in sorted(change):
        waiting += change[tick]
        peak = max(peak, waiting)
    return peak


def observations(result: SimulationResult) -> list[str]:
    """Plain facts about one run (R-20)."""
    passengers = result.passengers
    if not passengers:
        return []
    longest = max(passengers, key=wait_time)
    sources = Counter(p.request.source for p in passengers)
    busiest = min(sources, key=lambda floor: (-sources[floor], floor))
    zero_share = sum(1 for p in passengers if wait_time(p) == 0) / len(passengers)
    return [
        f"Longest wait: {longest.request.id} at {wait_time(longest)} ticks",
        f"Busiest source floor: {busiest} with {sources[busiest]} passengers",
        f"Peak passengers waiting: {_peak_waiting(passengers)}",
        f"Share with zero wait: {zero_share:.1%}",
        f"Times left behind: {sum(p.times_left_behind for p in passengers)}",
    ]
