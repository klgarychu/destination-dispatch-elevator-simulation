"""The seat reservation check (spec section 9.3): would boarding take a seat someone needs ahead?"""

from collections import Counter, defaultdict
from collections.abc import Sequence

from elevator_sim.requests import Direction, Passenger


def takes_reserved_seat(
    candidate: Passenger,
    riders: Sequence[Passenger],
    protected: Sequence[Passenger],
    position: int,
    direction: Direction,
    capacity: int,
) -> bool:
    """Whether the car would be over capacity with this passenger still aboard.

    Walks the floors ahead in sweep order. A passenger who gets off first takes no seat from anyone
    further along (D25), so the walk ends at their floor.
    """
    leaving = Counter(rider.request.dest for rider in riders)
    leaving[candidate.request.dest] += 1
    leaving.update(person.request.dest for person in protected)
    joining: defaultdict[int, int] = defaultdict(int)
    for person in protected:
        joining[person.request.source] += 1

    aboard = len(riders) + 1
    step = int(direction)
    for floor in sorted({*leaving, *joining}, key=lambda floor: floor * step):
        if (floor - position) * step <= 0:
            continue
        aboard -= leaving[floor]
        if floor == candidate.request.dest:
            return False
        aboard += joining[floor]
        if aboard > capacity:
            return True
    return False
