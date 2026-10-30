"""Checks shared by the property, golden and scenario tests."""

from elevator_sim.engine import SimulationResult
from elevator_sim.requests import Request


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
