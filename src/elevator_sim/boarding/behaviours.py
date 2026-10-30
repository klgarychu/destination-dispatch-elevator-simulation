"""Seat behaviours: the priority order for passengers waiting at a stop."""

from collections.abc import Sequence
from typing import Protocol

from elevator_sim.requests import Passenger


class Behaviour(Protocol):
    name: str

    def order(self, passengers: Sequence[Passenger]) -> list[Passenger]:
        """Return the passengers in seat priority order."""
        ...


class MinTime:
    """Shortest ride first, because freeing seats fastest favours the average (D12)."""

    name = "min_time"

    def order(self, passengers: Sequence[Passenger]) -> list[Passenger]:
        return sorted(passengers, key=lambda p: (p.request.ride_length, p.order))


_BEHAVIOURS: dict[str, Behaviour] = {"min_time": MinTime()}


def make_behaviour(name: str) -> Behaviour:
    return _BEHAVIOURS[name]
