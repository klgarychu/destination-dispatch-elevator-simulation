"""Seat behaviours: the priority order for passengers waiting at a stop."""

from collections.abc import Sequence
from typing import Protocol

from elevator_sim.requests import Passenger


class Behaviour(Protocol):
    name: str
    # Whether earlier passengers further along this sweep keep a seat (D11).
    protects_earlier: bool

    def order(self, passengers: Sequence[Passenger], tick: int) -> list[Passenger]:
        """Return the passengers in seat priority order."""
        ...


class Strict:
    """Request order, with seats kept for earlier passengers further along (D11)."""

    name = "strict"
    protects_earlier = True

    def order(self, passengers: Sequence[Passenger], tick: int) -> list[Passenger]:
        return sorted(passengers, key=lambda p: p.order)


class MinTime:
    """Shortest ride first, because freeing seats fastest favours the average (D12)."""

    name = "min_time"
    protects_earlier = False

    def order(self, passengers: Sequence[Passenger], tick: int) -> list[Passenger]:
        return sorted(passengers, key=lambda p: (p.request.ride_length, p.order))


class Weighted:
    """Short rides first, moving towards request order as the wait and the weight grow (D14)."""

    name = "weighted"
    protects_earlier = False

    def __init__(self, weight: float, floors: int) -> None:
        self.weight = weight
        self.floors = floors

    def _score(self, passenger: Passenger, tick: int) -> float:
        waited = tick - passenger.request.time
        return (1 + self.weight * waited / self.floors) / passenger.request.ride_length

    def order(self, passengers: Sequence[Passenger], tick: int) -> list[Passenger]:
        return sorted(passengers, key=lambda p: (-self._score(p, tick), p.order))


_FIXED: dict[str, Behaviour] = {"strict": Strict(), "min_time": MinTime()}


def make_behaviour(name: str, weight: float = 0.0, floors: int = 1) -> Behaviour:
    return Weighted(weight, floors) if name == "weighted" else _FIXED[name]
