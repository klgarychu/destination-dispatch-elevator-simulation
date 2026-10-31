"""TST-15: the generator is repeatable, and traffic mix and rates are within tolerance."""

from pathlib import Path

import pytest

from elevator_sim.config import ConfigError, SimConfig
from elevator_sim.engine import simulate
from elevator_sim.requests import Request, load_requests
from elevator_sim.workload import (
    backlog_at,
    backlog_growth,
    bisect_highest_rate,
    generate_requests,
    input_name,
    input_seed,
    write_requests,
)


def mix(requests: list[Request]) -> tuple[float, float, float]:
    incoming = sum(1 for r in requests if r.source == 1) / len(requests)
    outgoing = sum(1 for r in requests if r.dest == 1) / len(requests)
    return incoming, outgoing, 1 - incoming - outgoing


def test_tst15_same_seed_gives_the_same_requests() -> None:
    assert generate_requests("lunch", 0.5, 200, 7, 10) == generate_requests(
        "lunch", 0.5, 200, 7, 10
    )


def test_tst15_a_different_seed_gives_different_requests() -> None:
    assert generate_requests("lunch", 0.5, 200, 7, 10) != generate_requests(
        "lunch", 0.5, 200, 8, 10
    )


def test_tst15_arrival_count_is_within_four_standard_deviations_of_the_rate() -> None:
    # Poisson with rate 0.5 over 2,000 ticks has mean 1,000 and standard deviation about 32.
    requests = generate_requests("uniform", 0.5, 2000, 1, 10)

    assert 870 <= len(requests) <= 1130


@pytest.mark.parametrize(
    ("pattern", "expected"),
    [
        ("up_peak", (0.85, 0.10, 0.05)),
        ("down_peak", (0.10, 0.85, 0.05)),
        ("lunch", (0.40, 0.40, 0.20)),
    ],
)
def test_tst15_traffic_mix_is_within_tolerance(
    pattern: str, expected: tuple[float, float, float]
) -> None:
    requests = generate_requests(pattern, 2.0, 5000, 3, 60)

    assert mix(requests) == pytest.approx(expected, abs=0.02)


def test_tst15_uniform_traffic_draws_both_floors_from_the_whole_building() -> None:
    requests = generate_requests("uniform", 2.0, 5000, 3, 10)

    assert {r.source for r in requests} == set(range(1, 11))
    assert {r.dest for r in requests} == set(range(1, 11))
    # Each floor is the source of about 1 in 10 trips.
    assert sum(1 for r in requests if r.source == 1) / len(requests) == pytest.approx(0.1, abs=0.02)


def test_tst15_requests_are_valid_sorted_and_inside_the_arrival_window() -> None:
    requests = generate_requests("up_peak", 1.0, 300, 5, 10)

    assert [r.time for r in requests] == sorted(r.time for r in requests)
    assert all(0 <= r.time < 300 for r in requests)
    assert all(r.source != r.dest for r in requests)
    assert all(1 <= r.source <= 10 and 1 <= r.dest <= 10 for r in requests)


def test_tst15_passenger_ids_are_numbered_from_one() -> None:
    requests = generate_requests("uniform", 1.0, 20, 5, 10)

    assert [r.id for r in requests[:2]] == ["p000001", "p000002"]


def test_tst15_input_seed_is_a_crc32_of_all_four_parts() -> None:
    # zlib.crc32(b"baseline|up_peak|heavy|1"), worked out separately from the code under test.
    assert input_seed("baseline", "up_peak", "heavy", 1) == 647343489


def test_tst15_each_part_of_the_name_changes_the_seed() -> None:
    seeds = {
        input_seed("baseline", "up_peak", "heavy", 1),
        input_seed("tall", "up_peak", "heavy", 1),
        input_seed("baseline", "lunch", "heavy", 1),
        input_seed("baseline", "up_peak", "light", 1),
        input_seed("baseline", "up_peak", "heavy", 2),
    }

    assert len(seeds) == 5


def test_tst15_input_files_follow_the_naming_rule() -> None:
    assert input_name("tall", "down_peak", "overload", 3) == "tall_down_peak_overload_s3.csv"


def test_tst15_a_written_file_loads_back_the_same(tmp_path: Path) -> None:
    requests = generate_requests("lunch", 0.5, 100, 2, 10)
    file = tmp_path / "input.csv"

    write_requests(file, requests)

    assert load_requests(file, floors=10) == requests


def test_patterns_need_three_floors_for_interfloor_trips() -> None:
    with pytest.raises(ConfigError, match="3 floors"):
        generate_requests("lunch", 1.0, 100, 1, 2)


def test_an_unknown_pattern_is_rejected() -> None:
    with pytest.raises(ConfigError, match="pattern"):
        generate_requests("rush", 1.0, 100, 1, 10)


def test_a_rate_must_be_positive() -> None:
    with pytest.raises(ConfigError, match="rate"):
        generate_requests("uniform", 0, 100, 1, 10)


def test_backlog_counts_passengers_still_travelling_at_the_tick() -> None:
    requests = [Request(0, "a", 1, 3), Request(0, "b", 1, 9)]
    result = simulate(requests, SimConfig(elevators=1, algorithm="round_robin"))

    assert backlog_at(result, 1) == 2
    assert backlog_at(result, 2) == 1
    assert backlog_at(result, 8) == 0


def test_backlog_leaves_out_passengers_who_have_not_requested_yet() -> None:
    # a is delivered at tick 2. b requests at tick 5, and the car fetches them from floor 3.
    requests = [Request(0, "a", 1, 3), Request(5, "b", 1, 2)]
    result = simulate(requests, SimConfig(elevators=1, algorithm="round_robin"))

    assert backlog_at(result, 1) == 1
    assert backlog_at(result, 3) == 0
    assert backlog_at(result, 6) == 1
    assert backlog_at(result, 8) == 0


def test_a_flooded_car_shows_a_growing_backlog_and_a_quiet_car_does_not() -> None:
    # min_time favours short hops, so one seat carries under 0.5 passengers a tick. At 1.0 arrivals
    # a tick, about 500 arrive between ticks 500 and 1,000 and at most about 250 leave, so the
    # backlog must grow by well over 150. At 0.02 a tick the car keeps up.
    config = SimConfig(elevators=1, capacity=1, algorithm="round_robin")

    quiet = simulate(generate_requests("uniform", 0.02, 1000, 1, 10), config)
    flooded = simulate(generate_requests("uniform", 1.0, 1000, 1, 10), config)

    assert -2 <= backlog_growth(quiet) <= 2
    assert backlog_growth(flooded) > 150


def test_bisection_finds_the_highest_passing_rate_to_two_decimals() -> None:
    assert bisect_highest_rate(lambda rate: rate <= 0.37) == pytest.approx(0.37)
    assert bisect_highest_rate(lambda rate: rate <= 2.91) == pytest.approx(2.91)


def test_bisection_stops_at_the_lowest_rate_if_nothing_passes() -> None:
    assert bisect_highest_rate(lambda rate: False) == pytest.approx(0.01)
