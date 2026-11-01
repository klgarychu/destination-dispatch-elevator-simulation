"""TST-11: each algorithm chooses the expected car. Scores and costs are worked by hand."""

from dataclasses import replace

import pytest

from elevator_sim.boarding.behaviours import make_behaviour
from elevator_sim.config import ALGORITHMS, SimConfig
from elevator_sim.elevators.normal import NormalElevator
from elevator_sim.engine import simulate
from elevator_sim.forecast import PredictedTrip
from elevator_sim.metrics import wait_time
from elevator_sim.requests import Direction, Request
from elevator_sim.schedulers.eta import Eta
from elevator_sim.schedulers.marginal_insertion import MarginalInsertion, marginal_cost
from elevator_sim.schedulers.nearest_car import NearestCar, suitability
from elevator_sim.schedulers.registry import make_scheduler
from elevator_sim.schedulers.round_robin import RoundRobin
from elevator_sim.schedulers.zone_based import ZoneBased, zone_bounds
from helpers import car_at, view_of

UP, DOWN = Direction.UP, Direction.DOWN


def request(source: int, dest: int, name: str = "new", time: int = 0) -> Request:
    return Request(time, name, source, dest)


def wrong_way_fleet() -> tuple[NormalElevator, ...]:
    """The closest car passes the floor going down, so it can't take an upward passenger yet."""
    return (
        car_at(1, 6, DOWN, riders=[1]),
        car_at(2, 9),
        car_at(3, 2, DOWN, riders=[1]),
    )


def full_car_fleet(*car_one_riders: int) -> tuple[NormalElevator, ...]:
    return (
        car_at(1, 3, UP, riders=car_one_riders),
        car_at(2, 10),
        car_at(3, 9, DOWN, riders=[7]),
    )


def test_tst11_round_robin_takes_cars_in_turn() -> None:
    scheduler = RoundRobin()
    view = view_of(car_at(1, 1), car_at(2, 1), car_at(3, 1))

    picks = [scheduler.assign(request(1, 2), view) for _ in range(4)]

    assert picks == [1, 2, 3, 1]


# nearest_car: with 10 floors, N = 9.


def test_tst11_nearest_car_scores_follow_the_figure_of_suitability() -> None:
    new = request(5, 9)
    view = view_of(*wrong_way_fleet())

    scores = [suitability(car, new, view.floors) for car in view.cars]

    assert scores == [9, 7, 1]


def test_tst11_nearest_car_scores_a_car_coming_the_passengers_way_highest() -> None:
    view = view_of(car_at(1, 3, UP, riders=[8]), car_at(2, 10))

    assert [suitability(car, request(5, 8), view.floors) for car in view.cars] == [9, 6]


def test_tst11_nearest_car_treats_a_car_on_the_source_floor_as_moving_toward_it() -> None:
    view = view_of(car_at(1, 5, DOWN, riders=[1]))

    assert suitability(view.cars[0], request(5, 9), view.floors) == 10


def test_tst11_nearest_car_picks_the_highest_score_even_when_it_is_a_poor_choice() -> None:
    assert NearestCar().assign(request(5, 9), view_of(*wrong_way_fleet())) == 1


def test_tst11_nearest_car_breaks_ties_on_the_lowest_car_number() -> None:
    assert NearestCar().assign(request(5, 8), view_of(car_at(1, 3), car_at(2, 7))) == 1


# zone_based: zones 1-4, 5-7 and 8-10, with idle floors 2, 6 and 9.


def test_tst11_zones_are_as_equal_as_possible_with_extra_floors_going_lowest() -> None:
    assert zone_bounds(10, 3) == [(1, 4), (5, 7), (8, 10)]
    assert zone_bounds(10, 4) == [(1, 3), (4, 6), (7, 8), (9, 10)]
    assert zone_bounds(60, 6)[4] == (41, 50)
    assert zone_bounds(2, 3) == [(1, 1), (2, 2)]


@pytest.mark.parametrize(
    ("source", "dest", "car"),
    [
        (6, 9, 2),  # the source floor decides
        (9, 1, 3),
        (3, 8, 1),  # the destination's zone doesn't matter
        (1, 8, 3),  # from the lobby, the destination decides
        (1, 3, 1),
    ],
)
def test_tst11_zone_based_picks_the_car_that_owns_the_zone_floor(
    source: int, dest: int, car: int
) -> None:
    view = view_of(car_at(1, 1), car_at(2, 1), car_at(3, 1))

    assert ZoneBased().assign(request(source, dest), view) == car


def test_tst11_zone_based_ignores_where_the_cars_are() -> None:
    view = view_of(car_at(1, 8), car_at(2, 1), car_at(3, 8))

    assert ZoneBased().assign(request(7, 2), view) == 2


ONE_CAR = SimConfig(floors=10, elevators=1, capacity=6)
ONE_CAR_REQUESTS = [
    Request(0, "a", 1, 8),
    Request(0, "b", 1, 3),
    Request(2, "c", 9, 2),
    Request(2, "d", 4, 7),
    Request(5, "e", 6, 1),
    Request(40, "f", 3, 5),
]


@pytest.mark.parametrize("algorithm", ["nearest_car", "eta", "marginal_insertion"])
def test_tst11_one_car_leaves_the_algorithm_nothing_to_choose(algorithm: str) -> None:
    reference = simulate(ONE_CAR_REQUESTS, replace(ONE_CAR, algorithm="round_robin"))

    result = simulate(ONE_CAR_REQUESTS, replace(ONE_CAR, algorithm=algorithm))

    assert result.positions == reference.positions
    assert result.passengers == reference.passengers


@pytest.mark.parametrize(
    ("algorithm", "second_wait"),
    [
        # The car stops at floor 3 by tick 2, so at tick 6 it is 5 floors from floor 8.
        ("round_robin", 5),
        # It carries on to floor 5, the middle of its zone, by tick 4: 3 floors from floor 8.
        ("zone_based", 3),
    ],
)
def test_tst11_with_one_car_zone_based_differs_only_by_parking(
    algorithm: str, second_wait: int
) -> None:
    requests = [Request(0, "a", 1, 3), Request(6, "b", 8, 10)]

    result = simulate(requests, replace(ONE_CAR, algorithm=algorithm))

    assert [wait_time(p) for p in result.passengers] == [0, second_wait]


def test_tst11_zone_based_parks_idle_cars_mid_zone_rounded_down() -> None:
    view = view_of(car_at(1, 1), car_at(2, 1), car_at(3, 1))

    assert [ZoneBased().idle_target(car, view) for car in view.cars] == [2, 6, 9]


def test_tst11_a_car_with_no_zone_stays_where_it_is() -> None:
    view = view_of(car_at(1, 1, floors=2), car_at(2, 1, floors=2), car_at(3, 1, floors=2), floors=2)

    assert ZoneBased().idle_target(view.cars[2], view) is None


# eta: the lowest predicted wait for the new passenger only.


def test_tst11_eta_waits_for_a_wrong_way_car_include_the_turn_back() -> None:
    new = request(5, 9)

    assert Eta().waits(new, view_of(*wrong_way_fleet())) == {1: 9, 2: 4, 3: 5}


def test_tst11_eta_avoids_the_wrong_way_car() -> None:
    assert Eta().assign(request(5, 9), view_of(*wrong_way_fleet())) == 2


def test_tst11_eta_avoids_a_car_that_arrives_full() -> None:
    new = request(5, 8)
    view = view_of(*full_car_fleet(10, 10, 10, 10, 10, 10))

    assert Eta().waits(new, view) == {1: 12, 2: 5, 3: 4}
    assert Eta().assign(new, view) == 3


def test_tst11_eta_chooses_a_full_car_when_a_seat_frees_up_in_time() -> None:
    new = request(5, 8)
    view = view_of(*full_car_fleet(4, 10, 10, 10, 10, 10))

    assert Eta().waits(new, view) == {1: 2, 2: 5, 3: 4}
    assert Eta().assign(new, view) == 1


def test_tst11_eta_measures_wait_from_the_request_tick() -> None:
    new = request(5, 9, time=20)
    view = view_of(car_at(1, 3), now=20)

    assert Eta().waits(new, view) == {1: 2}


def test_tst11_eta_breaks_ties_on_the_lowest_car_number() -> None:
    assert Eta().assign(request(5, 8), view_of(car_at(1, 3), car_at(2, 7))) == 1


# marginal_insertion: the new passenger's total time plus the delay to everyone else on the car.


def test_tst11_marginal_insertion_trip_inside_a_sweep_costs_only_its_own_time() -> None:
    new = request(4, 7)
    view = view_of(car_at(1, 2, UP, riders=[9]), car_at(2, 8), car_at(3, 10))

    assert MarginalInsertion().costs(new, view) == {1: 5, 2: 7, 3: 9}
    assert MarginalInsertion().assign(new, view) == 1


def delayed_passenger_fleet() -> tuple[NormalElevator, ...]:
    return (
        car_at(1, 5, DOWN, waiting=[("A", 3, 8)]),
        car_at(2, 6),
        car_at(3, 9),
    )


def test_tst11_marginal_insertion_counts_the_delay_to_a_waiting_passenger() -> None:
    new = request(1, 2, "B")
    view = view_of(*delayed_passenger_fleet())

    # Car 1 now passes A to fetch B: B totals 5 and A's drop-off moves from 7 to 11.
    assert MarginalInsertion().costs(new, view) == {1: 9, 2: 6, 3: 9}
    assert MarginalInsertion().assign(new, view) == 2


def test_tst11_eta_ignores_that_delay_and_picks_the_car_marginal_insertion_rejects() -> None:
    assert Eta().assign(request(1, 2, "B"), view_of(*delayed_passenger_fleet())) == 1


def test_tst11_marginal_insertion_counts_every_passenger_delayed() -> None:
    new = request(1, 2, "B")
    trio = [("A1", 3, 8), ("A2", 3, 8), ("A3", 3, 8)]
    view = view_of(car_at(1, 5, DOWN, waiting=trio), car_at(2, 6), car_at(3, 9))

    assert MarginalInsertion().costs(new, view)[1] == 17


def test_tst11_marginal_insertion_sees_a_taken_seat_as_a_long_delay() -> None:
    new = request(2, 8, "B")
    view = view_of(
        car_at(1, 1, UP, riders=[10] * 5, waiting=[("A", 4, 9)]),
        car_at(2, 9),
        car_at(3, 10),
    )

    # B takes the last seat, so A misses the sweep: B totals 7 and A's drop-off moves from 8 to 20.
    assert MarginalInsertion().costs(new, view) == {1: 19, 2: 13, 3: 14}
    assert MarginalInsertion().assign(new, view) == 2
    assert Eta().assign(new, view) == 1


def test_tst11_marginal_insertion_breaks_ties_on_the_lowest_car_number() -> None:
    new = request(5, 8)
    view = view_of(car_at(1, 3, UP, riders=[9]), car_at(2, 7), car_at(3, 1))

    assert MarginalInsertion().costs(new, view) == {1: 5, 2: 5, 3: 7}
    assert MarginalInsertion().assign(new, view) == 1


def test_tst11_marginal_cost_is_the_new_passengers_time_plus_each_delay() -> None:
    baseline = {"a": PredictedTrip(0, 1, 10), "b": PredictedTrip(2, 3, 20)}
    candidate = {
        "a": PredictedTrip(0, 1, 13),
        "b": PredictedTrip(2, 3, 20),
        "new": PredictedTrip(5, 7, 12),
    }

    # The new passenger totals 7, a arrives 3 ticks later, and b isn't delayed.
    assert marginal_cost(Request(5, "new", 1, 6), baseline, candidate) == 10


@pytest.mark.parametrize(
    "baseline",
    [
        {},
        {"a": PredictedTrip(0, 1, 10), "delivered": PredictedTrip(0, 1, 5)},
    ],
)
def test_tst11_marginal_cost_refuses_forecasts_of_different_passengers(
    baseline: dict[str, PredictedTrip],
) -> None:
    candidate = {"a": PredictedTrip(0, 1, 10), "new": PredictedTrip(5, 7, 12)}

    with pytest.raises(AssertionError, match="different people"):
        marginal_cost(Request(5, "new", 1, 6), baseline, candidate)


def test_tst11_marginal_insertion_ignores_a_passenger_already_delivered() -> None:
    requests = [Request(0, "a", 1, 10), Request(10, "b", 1, 2)]

    result = simulate(requests, SimConfig(floors=10, elevators=2))

    # a leaves car 1 on floor 10 at tick 9. Car 2 is still idle on floor 1, so b boards at once.
    b = result.passengers[1]
    assert (b.car_id, b.board_tick, b.dropoff_tick) == (2, 10, 11)


def test_tst11_marginal_insertion_ignores_a_delivered_passenger_while_another_rides() -> None:
    requests = [Request(0, "x", 1, 20), Request(0, "y", 1, 10), Request(10, "z", 14, 13)]

    result = simulate(requests, SimConfig(floors=20, elevators=2))

    # y has left car 1, but x rides on to floor 20 at tick 19, so car 1 reaches z at tick 25 and
    # costs 16. Car 2 climbs straight from floor 1, reaches z at tick 23, and costs 14.
    z = result.passengers[2]
    assert (z.car_id, z.board_tick, z.dropoff_tick) == (2, 23, 24)


def test_every_algorithm_is_registered_under_its_own_name() -> None:
    assert [make_scheduler(name).name for name in ALGORITHMS] == list(ALGORITHMS)


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_tst01_every_algorithm_reproduces_the_one_car_pdf_sample(algorithm: str) -> None:
    requests = [
        Request(0, "passenger1", 1, 51),
        Request(0, "passenger2", 1, 37),
        Request(10, "passenger3", 20, 1),
    ]
    config = SimConfig(floors=60, elevators=1, capacity=6, algorithm=algorithm)

    result = simulate(requests, config)

    assert [(p.board_tick, p.dropoff_tick) for p in result.passengers] == [
        (0, 50),
        (0, 36),
        (81, 100),
    ]


def test_car_at_builds_cars_with_the_shared_behaviour() -> None:
    assert car_at(1, 1).behaviour is make_behaviour("min_time")
