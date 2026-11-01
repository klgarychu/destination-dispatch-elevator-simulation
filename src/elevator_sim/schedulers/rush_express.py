"""Express by dispatch: run ordinary cars as express only while the lobby is in a rush (M31).

Stops take no time here, so an express car gains nothing by skipping floors. Its gain comes from
separating traffic: a car kept to the low floors has a shorter round trip, so it carries more
people. Wiring that split into the cars costs a great deal in other traffic, because a trip across
the middle of the building then has few cars to use. This rule makes the split only while recent
requests show a lobby rush, and otherwise behaves exactly as marginal_insertion.

It looks only at requests already made, so it can't peek ahead, and it asks cars what they serve,
so it also works on a building with express cars.
"""

from collections import deque

from elevator_sim.requests import Request
from elevator_sim.schedulers.base import CarView, FleetView
from elevator_sim.schedulers.marginal_insertion import MarginalInsertion

LOBBY = 1
# Thirty requests is long enough that lunch traffic, 40% from the lobby, doesn't look like a rush
# by chance. Up-peak is 85% from the lobby, so 70% separates them (M31).
WINDOW = 30
RUSH_SHARE = 0.7
# Cars take turns: one serves every floor, the next the low floors, the next the high floors.
_ANY_FLOOR, _LOW_RISE, _HIGH_RISE = range(3)


def in_band(role: int, request: Request, floors: int) -> bool:
    """Whether a car with this role takes this trip during a rush."""
    trip = (request.source, request.dest)
    middle = floors // 2
    if role == _LOW_RISE:
        return all(floor <= middle for floor in trip)
    if role == _HIGH_RISE:
        return all(floor == LOBBY or floor > middle for floor in trip)
    return True


class RushExpress(MarginalInsertion):
    name = "rush_express"

    def __init__(self) -> None:
        self._recent: deque[bool] = deque(maxlen=WINDOW)

    def _in_rush(self) -> bool:
        return len(self._recent) == WINDOW and sum(self._recent) >= RUSH_SHARE * WINDOW

    def _candidates(self, request: Request, view: FleetView) -> tuple[CarView, ...]:
        eligible = view.eligible(request)
        if not self._in_rush():
            return eligible
        roles = {car.car_id: index % 3 for index, car in enumerate(view.cars)}
        banded = tuple(car for car in eligible if in_band(roles[car.car_id], request, view.floors))
        return banded or eligible

    def assign(self, request: Request, view: FleetView) -> int:
        self._recent.append(request.source == LOBBY)
        costs = self.costs(request, view, self._candidates(request, view))
        return min(costs, key=lambda car_id: (costs[car_id], car_id))
