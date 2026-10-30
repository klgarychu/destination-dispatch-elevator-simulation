"""Target: the lowest rise in total passenger time on the car (D7, D16).

LOOK fixes the route for any set of passengers, so there is no insertion position to search, only
a car to choose. Each car is simulated with and without the new passenger, and always re-simulated,
because a small insertion can change a schedule's structure: one taken seat can push a passenger
onto the next sweep.
"""

from elevator_sim.forecast import Forecast
from elevator_sim.requests import Request
from elevator_sim.schedulers.base import FleetView, Scheduler


def _passenger_time(forecast: Forecast) -> int:
    """Total time for everyone in a forecast, measured from each request tick."""
    return sum(trip.dropoff_tick - trip.request_time for trip in forecast.values())


class MarginalInsertion(Scheduler):
    name = "marginal_insertion"

    def costs(self, request: Request, view: FleetView) -> dict[int, int]:
        return {
            car.car_id: _passenger_time(view.forecast(car.car_id, request))
            - _passenger_time(view.forecast(car.car_id))
            for car in view.eligible(request)
        }

    def assign(self, request: Request, view: FleetView) -> int:
        costs = self.costs(request, view)
        return min(costs, key=lambda car_id: (costs[car_id], car_id))
