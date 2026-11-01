"""Target: the lowest rise in total passenger time on the car (D7, D16).

LOOK fixes the route for any set of passengers, so there is no insertion position to search, only
a car to choose. Each car is simulated with and without the new passenger, and always re-simulated,
because a small insertion can change a schedule's structure: one taken seat can push a passenger
onto the next sweep.
"""

from collections.abc import Iterable

from elevator_sim.forecast import Forecast
from elevator_sim.requests import Request
from elevator_sim.schedulers.base import CarView, FleetView, Scheduler


def marginal_cost(request: Request, baseline: Forecast, candidate: Forecast) -> int:
    """The new passenger's total time, plus the delay to each passenger already on the car."""
    assert candidate.keys() - {request.id} == baseline.keys(), "forecasts cover different people"
    delays = (
        trip.dropoff_tick - baseline[name].dropoff_tick
        for name, trip in candidate.items()
        if name != request.id
    )
    return candidate[request.id].dropoff_tick - request.time + sum(delays)


class MarginalInsertion(Scheduler):
    name = "marginal_insertion"

    def costs(
        self, request: Request, view: FleetView, cars: Iterable[CarView] | None = None
    ) -> dict[int, int]:
        """The cost of each car, from all eligible cars unless a narrower choice is given."""
        return {
            car.car_id: marginal_cost(
                request,
                view.baseline_forecast(car.car_id),
                view.candidate_forecast(car.car_id, request),
            )
            for car in (view.eligible(request) if cars is None else cars)
        }

    def assign(self, request: Request, view: FleetView) -> int:
        costs = self.costs(request, view)
        return min(costs, key=lambda car_id: (costs[car_id], car_id))
