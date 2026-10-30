"""LOOK and boarding, tested through Elevator.exchange and Elevator.move.

Expected ticks are worked by hand from spec sections 7.1 and 7.2. A car at position p at tick t
exchanges passengers first, then moves one floor, so it reaches floor f in abs(f - p) ticks.
"""

from elevator_sim.boarding.behaviours import make_behaviour
from elevator_sim.config import SimConfig
from elevator_sim.elevators.base import Elevator
from elevator_sim.elevators.factory import build_fleet
from elevator_sim.elevators.normal import NormalElevator
from elevator_sim.requests import Direction, Passenger, Request


def car(floors: int = 10, capacity: int = 6, start_floor: int = 1) -> NormalElevator:
    return NormalElevator(1, floors, capacity, start_floor, make_behaviour("min_time"))


def passenger(order: int, source: int, dest: int, time: int = 0) -> Passenger:
    return Passenger(Request(time, f"p{order}", source, dest), order, car_id=1)


def run(elevator: Elevator, *assigned: Passenger, start: int = 0, limit: int = 200) -> int:
    """Run one car until its passengers are delivered, assigning each at its request time."""
    pending = sorted(assigned, key=lambda p: p.order)
    tick = start
    while tick < limit:
        while pending and pending[0].request.time == tick:
            elevator.assign(pending.pop(0))
        elevator.exchange(tick)
        if not pending and not elevator.has_passengers:
            return tick
        elevator.move()
        tick += 1
    raise AssertionError("car did not finish")


def test_tst07_car_reverses_at_the_furthest_pickup_even_if_going_the_other_way() -> None:
    near, far = passenger(0, 5, 2), passenger(1, 8, 3)

    run(car(), near, far)

    # Passes floor 5 at tick 4, turns at floor 8 at tick 7, then floors 5, 3, 2.
    assert (far.board_tick, far.dropoff_tick) == (7, 12)
    assert (near.board_tick, near.dropoff_tick) == (10, 13)


def test_tst07_opposite_direction_passenger_is_not_boarded_on_the_way_past() -> None:
    rider, against = passenger(0, 1, 9), passenger(1, 5, 2)

    run(car(), rider, against)

    # Up to floor 9 by tick 8, then back down to floor 5 by tick 12, and floor 2 by tick 15.
    assert (rider.board_tick, rider.dropoff_tick) == (0, 8)
    assert (against.board_tick, against.dropoff_tick) == (12, 15)
    assert against.times_left_behind == 0


def test_tst07_passenger_going_the_other_way_boards_after_the_car_reverses() -> None:
    going_up, going_down = passenger(0, 5, 8), passenger(1, 5, 2)

    run(car(start_floor=5), going_up, going_down)

    assert (going_up.board_tick, going_up.dropoff_tick) == (0, 3)
    assert (going_down.board_tick, going_down.dropoff_tick) == (6, 9)


def test_tst07_idle_car_heads_for_its_oldest_passenger() -> None:
    oldest, newer = passenger(0, 2, 3), passenger(1, 8, 9)

    run(car(start_floor=5), oldest, newer)

    # Goes down to floor 2 first, turns, and carries oldest up, reaching floor 8 at tick 9.
    assert (oldest.board_tick, oldest.dropoff_tick) == (3, 4)
    assert (newer.board_tick, newer.dropoff_tick) == (9, 10)


def test_tst07_passenger_on_the_car_floor_boards_as_the_car_leaves_their_way() -> None:
    oldest, here = passenger(0, 8, 9), passenger(1, 3, 5)

    run(car(start_floor=3), oldest, here)

    assert (here.board_tick, here.dropoff_tick) == (0, 2)
    assert (oldest.board_tick, oldest.dropoff_tick) == (5, 6)


def test_tst07_car_turns_for_a_passenger_who_is_on_its_final_floor_going_the_other_way() -> None:
    rider, here = passenger(0, 1, 5), passenger(1, 5, 2)

    run(car(), rider, here)

    assert rider.dropoff_tick == 4
    assert (here.board_tick, here.dropoff_tick) == (4, 7)


def test_tst07_car_stops_as_idle_when_nothing_is_left() -> None:
    elevator = car()

    run(elevator, passenger(0, 1, 3))

    assert elevator.direction == Direction.IDLE
    assert elevator.position == 3


def test_tst07_passenger_on_a_full_car_floor_is_left_behind_and_counted() -> None:
    rider, waiting = passenger(0, 1, 9), passenger(1, 5, 7)

    run(car(capacity=1), rider, waiting)

    # Passes floor 5 full at tick 4, turns at floor 9 at tick 8, reaches floor 5 at tick 12.
    assert waiting.times_left_behind == 1
    assert (waiting.board_tick, waiting.dropoff_tick) == (12, 14)


def test_tst08_min_time_gives_a_scarce_seat_to_the_shortest_ride() -> None:
    # Spec section 15.2: 1 car, capacity 1, 5 floors.
    a, b = passenger(0, 1, 3), passenger(1, 1, 2)

    run(car(floors=5, capacity=1), a, b)

    assert (b.board_tick, b.dropoff_tick) == (0, 1)
    assert (a.board_tick, a.dropoff_tick) == (2, 4)
    assert a.times_left_behind == 1


def test_tst08_min_time_breaks_ride_length_ties_by_request_order() -> None:
    first, second = passenger(0, 1, 3), passenger(1, 1, 3)

    run(car(floors=5, capacity=1), first, second)

    assert first.board_tick == 0
    assert second.board_tick == 4


def test_tst08_car_never_boards_past_capacity() -> None:
    elevator = car(capacity=2)
    for order in range(3):
        elevator.assign(passenger(order, 1, 2 + order))

    elevator.exchange(0)

    assert len(elevator.riders) == 2


def test_tst12_a_normal_car_serves_every_floor() -> None:
    elevator = car(floors=10)

    assert all(elevator.serves(floor) for floor in range(1, 11))
    assert not elevator.serves(11)
    assert elevator.can_serve(1, 10)


def test_tst12_fleet_cars_are_numbered_from_one_and_start_on_the_start_floor() -> None:
    fleet = build_fleet(SimConfig(elevators=3, start_floor=4))

    assert [elevator.car_id for elevator in fleet] == [1, 2, 3]
    assert [elevator.position for elevator in fleet] == [4, 4, 4]


def test_idle_car_steps_towards_its_idle_target_and_stays_there() -> None:
    elevator = car(start_floor=1)

    positions = []
    for tick in range(4):
        elevator.exchange(tick)
        elevator.move(idle_target=3)
        positions.append(elevator.position)

    assert positions == [2, 3, 3, 3]


def test_car_with_work_ignores_an_idle_target() -> None:
    elevator = car(start_floor=5)
    elevator.assign(passenger(0, 8, 9))

    elevator.exchange(0)
    elevator.move(idle_target=1)

    assert elevator.position == 6


def test_car_counts_its_moves_with_and_without_riders() -> None:
    elevator = car(start_floor=3)

    run(elevator, passenger(0, 1, 2))

    # Two empty moves down to floor 1, then one loaded move up to floor 2.
    assert (elevator.moves, elevator.empty_moves, elevator.rider_moves) == (3, 2, 1)
