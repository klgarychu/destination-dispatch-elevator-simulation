"""The Elevator base class: LOOK movement and boarding, shared by every kind of car."""

import copy
from abc import ABC, abstractmethod
from bisect import bisect_left, bisect_right, insort

from elevator_sim.boarding.behaviours import Behaviour
from elevator_sim.requests import Direction, Passenger


class Elevator(ABC):
    def __init__(
        self, car_id: int, floors: int, capacity: int, start_floor: int, behaviour: Behaviour
    ) -> None:
        self.car_id = car_id
        self.floors = floors
        self.capacity = capacity
        self.position = start_floor
        self.direction = Direction.IDLE
        self.behaviour = behaviour
        self.riders: list[Passenger] = []
        # Waiting passengers by floor, in request order. Queues can hold hundreds of passengers
        # in overload, and every stop needs them by floor, so avoid scanning the whole queue.
        self._waiting: dict[int, list[Passenger]] = {}
        self._waiting_floors: list[int] = []
        self.moves = 0
        self.empty_moves = 0
        self.rider_moves = 0

    @abstractmethod
    def serves(self, floor: int) -> bool:
        """Return whether this car stops at the floor."""

    def can_serve(self, source: int, dest: int) -> bool:
        return self.serves(source) and self.serves(dest)

    @property
    def has_passengers(self) -> bool:
        return bool(self.riders or self._waiting)

    @property
    def passengers(self) -> list[Passenger]:
        """Riders first, then waiting passengers by floor."""
        waiting = [p for floor in self._waiting_floors for p in self._waiting[floor]]
        return [*self.riders, *waiting]

    @property
    def waiting_count(self) -> int:
        return sum(len(queue) for queue in self._waiting.values())

    def assign(self, passenger: Passenger) -> None:
        floor = passenger.request.source
        if floor not in self._waiting:
            self._waiting[floor] = []
            insort(self._waiting_floors, floor)
        self._waiting[floor].append(passenger)

    def exchange(self, tick: int) -> None:
        """Drop off, set the direction, then board (spec section 7.2)."""
        self._drop_off(tick)
        self._resolve_direction()
        self._board(tick)

    def move(self, idle_target: int | None = None) -> None:
        if self.direction != Direction.IDLE:
            step = int(self.direction)
        elif idle_target is None or idle_target == self.position:
            return
        else:
            step = 1 if idle_target > self.position else -1
        self.position += step
        self.moves += 1
        self.rider_moves += len(self.riders)
        if not self.riders:
            self.empty_moves += 1

    def clone(self) -> Elevator:
        """Copy the car and its passengers, so that a forecast can't touch the real ones."""
        twin = copy.copy(self)
        twin.riders = [rider.clone() for rider in self.riders]
        twin._waiting = {
            floor: [p.clone() for p in queue] for floor, queue in self._waiting.items()
        }
        twin._waiting_floors = list(self._waiting_floors)
        return twin

    def distance_to_next_event(self) -> int:
        """Floors to the next stop with a rider or waiting passenger, in the car's direction.

        Passing any other floor changes nothing, so a forecast can jump straight there.
        """
        floors = self._waiting_floors
        if self.direction == Direction.UP:
            index = bisect_right(floors, self.position)
            nearest = [floors[index]] if index < len(floors) else []
            nearest += [r.request.dest for r in self.riders]
            return min(nearest) - self.position
        index = bisect_left(floors, self.position) - 1
        nearest = [floors[index]] if index >= 0 else []
        nearest += [r.request.dest for r in self.riders]
        return self.position - max(nearest)

    def jump(self, floors: int) -> None:
        """Move several floors at once. Forecasts only, as it logs no ticks."""
        self.position += floors * int(self.direction)

    def _drop_off(self, tick: int) -> None:
        staying = []
        for rider in self.riders:
            if rider.request.dest == self.position:
                rider.dropoff_tick = tick
            else:
                staying.append(rider)
        self.riders = staying

    def _resolve_direction(self) -> None:
        if self.direction != Direction.IDLE:
            ahead = self.direction
            behind = Direction(-ahead)
            if not (self.riders or self._work_ahead(ahead) or self._waiting_here(ahead)):
                if self._work_ahead(behind) or self._waiting_here(behind):
                    self.direction = behind
                else:
                    self.direction = Direction.IDLE
        if self.direction == Direction.IDLE and self._waiting:
            oldest = min((queue[0] for queue in self._waiting.values()), key=lambda p: p.order)
            if oldest.request.source == self.position:
                self.direction = oldest.request.direction
            elif oldest.request.source > self.position:
                self.direction = Direction.UP
            else:
                self.direction = Direction.DOWN

    def _work_ahead(self, direction: Direction) -> bool:
        floors = self._waiting_floors
        if direction == Direction.UP:
            if floors and floors[-1] > self.position:
                return True
            return any(r.request.dest > self.position for r in self.riders)
        if floors and floors[0] < self.position:
            return True
        return any(r.request.dest < self.position for r in self.riders)

    def _waiting_here(self, direction: Direction) -> bool:
        queue = self._waiting.get(self.position, ())
        return any(p.request.direction == direction for p in queue)

    def _board(self, tick: int) -> None:
        queue = self._waiting.get(self.position)
        if not queue or self.direction == Direction.IDLE:
            return
        going = [p for p in queue if p.request.direction == self.direction]
        if not going:
            return
        seats = self.capacity - len(self.riders)
        ordered = self.behaviour.order(going)
        boarding = ordered[:seats]
        for passenger in boarding:
            passenger.board_tick = tick
            self.riders.append(passenger)
        for passenger in ordered[seats:]:
            passenger.times_left_behind += 1
        queue[:] = [p for p in queue if p.board_tick is None]
        if not queue:
            del self._waiting[self.position]
            self._waiting_floors.remove(self.position)
