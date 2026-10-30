"""The tick loop, tested through simulate(). Expected values are worked by hand."""

import pytest

from elevator_sim.config import SimConfig
from elevator_sim.engine import SchedulerError, SimulationStalledError, simulate
from elevator_sim.requests import InputValidationError, Passenger, Request
from elevator_sim.schedulers.base import CarView, FleetView, Scheduler
from helpers import requests_at

PDF_SAMPLE = [
    Request(0, "passenger1", 1, 51),
    Request(0, "passenger2", 1, 37),
    Request(10, "passenger3", 20, 1),
]
ONE_CAR = SimConfig(floors=60, elevators=1, capacity=6, algorithm="round_robin")


def by_id(passengers: list[Passenger]) -> dict[str, tuple[int | None, int | None]]:
    return {p.request.id: (p.board_tick, p.dropoff_tick) for p in passengers}


def test_tst01_pdf_sample_gives_the_hand_calculated_times() -> None:
    result = simulate(PDF_SAMPLE, ONE_CAR)

    assert by_id(result.passengers) == {
        "passenger1": (0, 50),
        "passenger2": (0, 36),
        "passenger3": (81, 100),
    }


def test_tst01_pdf_sample_logs_101_rows_and_passes_floor_20_without_boarding() -> None:
    result = simulate(PDF_SAMPLE, ONE_CAR)

    assert len(result.positions) == 101
    assert result.positions[19] == (20,)
    assert result.positions[50] == (51,)
    assert result.positions[100] == (1,)


def test_tst02_request_at_the_cars_floor_boards_with_zero_wait() -> None:
    result = simulate(requests_at((0, 1, 3)), SimConfig(algorithm="round_robin", elevators=1))

    assert result.passengers[0].board_tick == 0


def test_tst02_idle_ticks_pass_one_at_a_time_and_are_logged() -> None:
    result = simulate(requests_at((5, 1, 3)), SimConfig(algorithm="round_robin", elevators=1))

    assert result.positions == [(1,), (1,), (1,), (1,), (1,), (1,), (2,), (3,)]
    assert by_id(result.passengers) == {"p1": (5, 7)}


def test_tst02_drop_off_happens_before_boarding_in_the_same_tick() -> None:
    config = SimConfig(floors=5, elevators=1, capacity=1, algorithm="round_robin")

    result = simulate(requests_at((0, 1, 3), (0, 3, 5)), config)

    assert by_id(result.passengers) == {"p1": (0, 2), "p2": (2, 4)}


def test_tst02_requests_in_one_tick_are_assigned_in_input_order() -> None:
    config = SimConfig(floors=5, elevators=2, algorithm="round_robin")

    result = simulate(requests_at((0, 1, 2), (0, 1, 3), (0, 1, 4)), config)

    assert [p.car_id for p in result.passengers] == [1, 2, 1]


def test_tst04_run_ends_at_the_last_drop_off() -> None:
    result = simulate(requests_at((0, 1, 2), (0, 1, 9)), SimConfig(algorithm="round_robin"))

    assert result.ticks == 8
    assert len(result.positions) == 9


def test_i5_empty_input_gives_one_position_row() -> None:
    result = simulate([], SimConfig(algorithm="round_robin"))

    assert result.positions == [(1, 1, 1)]
    assert result.passengers == []


def test_tst03_simulate_validates_like_the_csv_loader() -> None:
    with pytest.raises(InputValidationError, match="dest"):
        simulate([Request(0, "a", 1, 11)], SimConfig(algorithm="round_robin"))


def test_tst03_simulate_sorts_unsorted_requests() -> None:
    requests = [Request(4, "late", 2, 1), Request(0, "early", 1, 3)]

    result = simulate(requests, SimConfig(algorithm="round_robin", elevators=1))

    assert [p.request.id for p in result.passengers] == ["early", "late"]
    assert [p.order for p in result.passengers] == [0, 1]


def test_o4_reaching_max_ticks_reports_the_tick_and_unfinished_passengers() -> None:
    config = SimConfig(algorithm="round_robin", elevators=1, max_ticks=3)

    with pytest.raises(SimulationStalledError, match=r"tick 3.*1 passenger"):
        simulate(requests_at((0, 1, 9)), config)


def test_o6_default_max_ticks_allows_a_full_run() -> None:
    config = SimConfig(floors=5, elevators=1, capacity=1, algorithm="round_robin")
    rows = [(0, 5, 1)] * 20

    assert len(simulate(requests_at(*rows), config).passengers) == 20


class WrongCar(Scheduler):
    name = "wrong_car"

    def assign(self, request: Request, view: FleetView) -> int:
        return 99


def test_engine_rejects_a_scheduler_that_picks_an_ineligible_car() -> None:
    with pytest.raises(SchedulerError, match="99"):
        simulate(requests_at((0, 1, 2)), SimConfig(), scheduler=WrongCar())


class Recorder(Scheduler):
    """Remembers what a scheduler is shown, to test the read-only view."""

    name = "recorder"

    def __init__(self) -> None:
        self.seen: list[tuple[int, tuple[CarView, ...]]] = []

    def assign(self, request: Request, view: FleetView) -> int:
        self.seen.append((view.now, view.cars))
        return view.eligible(request)[0].car_id


def test_tst02_earlier_assignments_in_a_tick_are_visible_to_later_ones() -> None:
    recorder = Recorder()

    simulate(requests_at((0, 1, 2), (0, 1, 3)), SimConfig(), scheduler=recorder)

    (_, first), (_, second) = recorder.seen
    assert first[0].waiting_count == 0
    assert second[0].waiting_count == 1


def test_view_shows_a_car_snapshot_that_a_scheduler_cannot_change() -> None:
    recorder = Recorder()

    simulate(requests_at((0, 1, 2)), SimConfig(), scheduler=recorder)

    car = recorder.seen[0][1][0]
    with pytest.raises(AttributeError):
        car.position = 5  # type: ignore[misc]  # the point of the test
