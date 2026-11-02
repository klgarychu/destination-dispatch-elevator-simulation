"""Guards: when a waiting passenger is flagged, and so boards first (spec section 9.4)."""

from dataclasses import dataclass

from elevator_sim.config import SimConfig
from elevator_sim.requests import Passenger


@dataclass(frozen=True, slots=True)
class Guard:
    """Flags a passenger left behind `limit` times, or waiting `limit` ticks. `none` never flags.

    With `seat_hold`, a flagged passenger further along the sweep also keeps a seat.
    """

    kind: str = "none"
    limit: int = 0
    seat_hold: bool = False

    def flags(self, passenger: Passenger, tick: int) -> bool:
        """Whether the passenger is flagged at this tick. Once true, it stays true."""
        if self.kind == "skip_limit":
            return passenger.times_left_behind >= self.limit
        if self.kind == "wait_expiry":
            return tick - passenger.request.time >= self.limit
        return False


NO_GUARD = Guard()


def make_guard(config: SimConfig) -> Guard:
    kind = config.guard_in_force
    if kind == "skip_limit":
        return Guard(kind, config.skip_limit, config.seat_hold)
    if kind == "wait_expiry":
        return Guard(kind, config.wait_limit_ticks, config.seat_hold)
    return NO_GUARD
