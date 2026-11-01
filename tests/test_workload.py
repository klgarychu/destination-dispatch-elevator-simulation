"""TST-15: the generator is repeatable, and traffic mix and rates are within tolerance."""

import random
from pathlib import Path

import pytest

from elevator_sim.config import ConfigError
from elevator_sim.requests import Request, load_requests
from elevator_sim.workload import (
    InputSpec,
    building_config,
    ensure_inputs,
    generate_requests,
    input_name,
    input_requests,
    input_seed,
    load_rates,
    suite_inputs,
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


def test_ensure_inputs_writes_missing_files_and_accepts_ones_that_match_the_rates(
    tmp_path: Path,
) -> None:
    ensure_inputs(tmp_path, (1,))
    written = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    ensure_inputs(tmp_path, (1,))

    assert len(written) == 64
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == written


def test_ensure_inputs_stops_on_a_file_that_no_longer_matches_the_rates(tmp_path: Path) -> None:
    stale = tmp_path / next(suite_inputs((1,))).name
    stale.write_text("time,id,source,dest\n0,only,1,2\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="generate --suite"):
        ensure_inputs(tmp_path, (1,))

    assert stale.read_text(encoding="utf-8") == "time,id,source,dest\n0,only,1,2\n"


def test_patterns_need_three_floors_for_interfloor_trips() -> None:
    with pytest.raises(ConfigError, match="3 floors"):
        generate_requests("lunch", 1.0, 100, 1, 2)


def test_an_unknown_pattern_is_rejected() -> None:
    with pytest.raises(ConfigError, match="pattern"):
        generate_requests("rush", 1.0, 100, 1, 10)


def test_a_rate_must_be_positive() -> None:
    with pytest.raises(ConfigError, match="rate"):
        generate_requests("uniform", 0, 100, 1, 10)


@pytest.fixture
def bounded_generator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turns a generator loop that would never end into a quick test failure."""

    class Bounded(random.Random):
        calls = 0

        def expovariate(self, lambd: float = 1.0) -> float:
            Bounded.calls += 1
            assert Bounded.calls < 1000, "the generator is not stopping"
            return super().expovariate(lambd)

    monkeypatch.setattr("elevator_sim.workload.random.Random", Bounded)


@pytest.mark.usefixtures("bounded_generator")
@pytest.mark.parametrize(
    ("rate", "ticks", "floors", "named"),
    [
        (float("nan"), 10, 3, "rate"),
        (float("inf"), 10, 3, "rate"),
        (-1.0, 10, 3, "rate"),
        ("fast", 10, 3, "rate"),
        (True, 10, 3, "rate"),
        (1.0, 0, 3, "ticks"),
        (1.0, -10, 3, "ticks"),
        (1.0, 1.5, 3, "ticks"),
        (1.0, 10, 1, "floors"),
        (1.0, 10, 2.5, "floors"),
        (1e9, 1000, 3, "requests"),
    ],
)
def test_the_generator_refuses_what_it_cannot_honour(
    rate: object, ticks: object, floors: object, named: str
) -> None:
    with pytest.raises(ConfigError, match=named):
        generate_requests("uniform", rate, ticks, 1, floors)  # type: ignore[arg-type]  # bad values


@pytest.mark.usefixtures("bounded_generator")
def test_the_generator_limit_is_on_the_expected_number_of_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("elevator_sim.workload.MAX_GENERATED_REQUESTS", 100)

    assert generate_requests("uniform", 1.0, 100, 1, 3)
    with pytest.raises(ConfigError, match="requests"):
        generate_requests("uniform", 1.0, 101, 1, 3)


def test_a_rates_file_that_is_not_toml_is_refused(tmp_path: Path) -> None:
    file = tmp_path / "rates.toml"
    file.write_text("[baseline\n", encoding="utf-8")

    with pytest.raises(ConfigError, match=r"rates\.toml"):
        load_rates(file)


def test_a_rates_file_that_is_not_utf_8_is_refused(tmp_path: Path) -> None:
    file = tmp_path / "rates.toml"
    file.write_bytes(b'[baseline]\nnote = "caf\xe9"\n')

    with pytest.raises(ConfigError, match=r"rates\.toml"):
        load_rates(file)


@pytest.mark.parametrize(
    "rates",
    [{}, {"baseline": 3}, {"baseline": {}}, {"baseline": {"lunch": "fast"}}],
)
def test_a_missing_or_unusable_rate_is_refused(rates: dict[str, dict[str, float]]) -> None:
    with pytest.raises(ConfigError, match="baseline lunch"):
        input_requests(InputSpec("baseline", "lunch", "light", 1), rates)


def test_simple_is_one_car_in_the_baseline_building() -> None:
    simple, baseline = building_config("simple"), building_config("baseline")

    assert (simple.floors, simple.elevators) == (baseline.floors, 1)
    assert (simple.capacity, simple.start_floor) == (baseline.capacity, baseline.start_floor)


def test_bridge_is_the_baseline_building_with_the_floors_of_tall() -> None:
    bridge, baseline, tall = (building_config(name) for name in ("bridge", "baseline", "tall"))

    assert bridge.floors == tall.floors
    assert (bridge.elevators, bridge.capacity) == (baseline.elevators, baseline.capacity)
    assert bridge.start_floor == baseline.start_floor


def test_every_suite_building_has_a_rate_for_every_pattern() -> None:
    rates = load_rates()

    for spec in suite_inputs():
        assert rates[spec.building][spec.pattern] > 0
