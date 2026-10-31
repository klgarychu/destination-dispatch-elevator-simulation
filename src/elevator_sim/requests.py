"""Requests, passengers, and input validation."""

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

from elevator_sim.config import is_whole_number

CSV_HEADER = ["time", "id", "source", "dest"]


class InputValidationError(ValueError):
    """Invalid requests. `problems` lists every bad row, not just the first."""

    def __init__(self, problems: Sequence[str]) -> None:
        self.problems = tuple(problems)
        super().__init__("invalid requests:\n  " + "\n  ".join(self.problems))

    def __reduce__(self) -> tuple[object, ...]:
        """Rebuild from the problems, not the message, when a worker process sends this back."""
        return type(self), (self.problems,)


class Direction(IntEnum):
    DOWN = -1
    IDLE = 0
    UP = 1


@dataclass(frozen=True, slots=True)
class Request:
    time: int
    id: str
    source: int
    dest: int

    @property
    def direction(self) -> Direction:
        return Direction.UP if self.dest > self.source else Direction.DOWN

    @property
    def ride_length(self) -> int:
        return abs(self.dest - self.source)


@dataclass(slots=True)
class Passenger:
    request: Request
    order: int  # position in sorted input: the request order
    car_id: int
    board_tick: int | None = None
    dropoff_tick: int | None = None
    times_left_behind: int = 0

    def clone(self) -> Passenger:
        return Passenger(
            self.request,
            self.order,
            self.car_id,
            self.board_tick,
            self.dropoff_tick,
            self.times_left_behind,
        )


def _problems_with(request: Request, floors: int) -> list[str]:
    problems = []
    if not is_whole_number(request.time):
        problems.append(f"time {request.time!r} is not a whole number")
    elif request.time < 0:
        problems.append(f"time {request.time} is negative")
    if not isinstance(request.id, str):
        problems.append(f"id {request.id!r} is not text")
    elif not request.id:
        problems.append("id is empty")
    for name, floor in (("source", request.source), ("dest", request.dest)):
        if not is_whole_number(floor):
            problems.append(f"{name} {floor!r} is not a whole number")
        elif not 1 <= floor <= floors:
            problems.append(f"{name} {floor} is outside floors 1..{floors}")
    if request.source == request.dest:
        problems.append(f"source and dest are both {request.source}")
    return problems


def validate_requests(requests: Sequence[Request], floors: int) -> list[Request]:
    """Return the requests sorted by time, keeping input order for ties, or raise."""
    labelled = [(f"request {index + 1}", request) for index, request in enumerate(requests)]
    return _validated(labelled, [], floors)


def _validated(
    labelled: Sequence[tuple[str, Request]], problems: list[tuple[str, str]], floors: int
) -> list[Request]:
    found = list(problems)
    seen: set[str] = set()
    for label, request in labelled:
        found.extend((label, problem) for problem in _problems_with(request, floors))
        if not isinstance(request.id, str):
            continue
        if request.id and request.id in seen:
            found.append((label, f"duplicate id {request.id!r}"))
        seen.add(request.id)
    if found:
        raise InputValidationError([f"{label}: {problem}" for label, problem in found])
    return sorted((request for _, request in labelled), key=lambda request: request.time)


def _parse_int(name: str, text: str, problems: list[str]) -> int | None:
    try:
        return int(text)
    except ValueError:
        problems.append(f"{name} {text!r} is not an integer")
        return None


def load_requests(path: Path, floors: int) -> list[Request]:
    """Read and validate a CSV of requests. Row numbers count the header as row 1."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.reader(file))
    except (UnicodeDecodeError, csv.Error) as error:
        raise InputValidationError([f"{path}: {error}"]) from None
    if not rows or rows[0] != CSV_HEADER:
        raise InputValidationError([f"{path}: header must be {','.join(CSV_HEADER)}"])

    labelled: list[tuple[str, Request]] = []
    problems: list[tuple[str, str]] = []
    for number, row in enumerate(rows[1:], start=2):
        label = f"row {number}"
        if len(row) != len(CSV_HEADER):
            problems.append((label, f"expected {len(CSV_HEADER)} fields, found {len(row)}"))
            continue
        parse_problems: list[str] = []
        time = _parse_int("time", row[0], parse_problems)
        source = _parse_int("source", row[2], parse_problems)
        dest = _parse_int("dest", row[3], parse_problems)
        if time is None or source is None or dest is None:
            problems.extend((label, problem) for problem in parse_problems)
            continue
        labelled.append((label, Request(time, row[1], source, dest)))
    return _validated(labelled, problems, floors)
