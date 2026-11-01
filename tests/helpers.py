"""Checks and fixtures shared by the tests."""

from collections.abc import Sequence

from elevator_sim.boarding.behaviours import make_behaviour
from elevator_sim.elevators.base import Elevator
from elevator_sim.elevators.express import ExpressElevator
from elevator_sim.elevators.normal import NormalElevator
from elevator_sim.engine import SimulationResult
from elevator_sim.forecast import Forecaster
from elevator_sim.requests import Direction, Passenger, Request
from elevator_sim.schedulers.base import FleetView, fleet_view


def assert_rules_hold(result: SimulationResult, capacity: int, floors: int) -> None:
    """Assert the TST-09 rules on a finished run, using only its public results."""
    positions = result.positions
    for tick in range(1, len(positions)):
        for before, after in zip(positions[tick - 1], positions[tick], strict=True):
            assert abs(after - before) <= 1, f"car moved more than one floor at tick {tick}"
    assert all(1 <= floor <= floors for row in positions for floor in row)

    load: dict[tuple[int, int], int] = {}
    for passenger in result.passengers:
        request = passenger.request
        board, dropoff = passenger.board_tick, passenger.dropoff_tick
        assert board is not None, f"{request.id} never boarded"
        assert dropoff is not None, f"{request.id} never arrived"
        assert request.time <= board < dropoff
        assert dropoff - board == abs(request.dest - request.source)

        car = passenger.car_id - 1
        assert positions[board][car] == request.source
        assert positions[dropoff][car] == request.dest
        for tick in range(board, dropoff):
            assert positions[tick + 1][car] - positions[tick][car] == request.direction
            load[(car, tick)] = load.get((car, tick), 0) + 1

    assert all(riders <= capacity for riders in load.values())


def requests_at(*rows: tuple[int, int, int]) -> list[Request]:
    """Build requests from (time, source, dest) rows, with ids in order."""
    return [Request(t, f"p{i + 1}", source, dest) for i, (t, source, dest) in enumerate(rows)]


def car_at(
    car_id: int,
    position: int,
    direction: Direction = Direction.IDLE,
    riders: Sequence[int] = (),
    waiting: Sequence[tuple[str, int, int]] = (),
    floors: int = 10,
    capacity: int = 6,
) -> NormalElevator:
    """A car placed mid-journey. `riders` are destinations, `waiting` is (id, source, dest)."""
    car = NormalElevator(car_id, floors, capacity, position, make_behaviour("min_time"))
    car.direction = direction
    for index, dest in enumerate(riders):
        source = position if dest != position else position - 1
        request = Request(0, f"rider{car_id}.{index}", source, dest)
        car.riders.append(Passenger(request, index, car_id, board_tick=0))
    for index, (name, source, dest) in enumerate(waiting):
        car.assign(Passenger(Request(0, name, source, dest), 50 + index, car_id))
    return car


def express_at(
    car_id: int, position: int, served: Sequence[int], floors: int = 10, capacity: int = 6
) -> ExpressElevator:
    """An idle express car at a floor it serves."""
    behaviour = make_behaviour("min_time")
    return ExpressElevator(car_id, floors, capacity, position, behaviour, served)


def view_of(*cars: Elevator, now: int = 0, floors: int = 10, capacity: int = 6) -> FleetView:
    return fleet_view(list(cars), now, floors, capacity, Forecaster(list(cars), next_order=100))
