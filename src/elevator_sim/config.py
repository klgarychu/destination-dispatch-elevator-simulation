"""Simulation settings, TOML loading and validation."""

import math
import re
import tomllib
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

# The fixed display order (G4). Phase 1 compared the first five, so its suite stays on those.
ALGORITHMS = ("round_robin", "nearest_car", "zone_based", "eta", "marginal_insertion")
ALL_ALGORITHMS = (*ALGORITHMS, "rush_express")
BEHAVIOURS = ("strict", "min_time", "weighted")
DEFAULT_WEIGHT = 1.0
GUARDS = ("none", "skip_limit", "wait_expiry")
DEFAULT_GUARD = "skip_limit"

# Settings the design defines but this version doesn't build. Accepting them silently would let a
# reader believe a rule was active when it wasn't (M12).
_NOT_BUILT = {"assignment_rule"}

_BUILDING_KEYS = {"floors", "elevators", "capacity", "start_floor"}
_DISPATCH_KEYS = {
    "algorithm",
    "behaviour",
    "fairness_weight",
    "guard",
    "skip_limit",
    "wait_limit",
    "seat_hold",
}
_EXPRESS_KEYS = {"car", "serves"}
_INTEGER_KEYS = ("floors", "elevators", "capacity", "start_floor")


class ConfigError(ValueError):
    """Invalid settings."""


def is_whole_number(value: object) -> bool:
    """True for an int, but not for True or False, which Python also counts as ints."""
    return isinstance(value, int) and not isinstance(value, bool)


def check_workers(workers: int) -> None:
    if not is_whole_number(workers) or workers < 1:
        raise ConfigError(f"workers must be at least 1, not {workers!r}")


def _require_whole_number(name: str, value: object) -> None:
    if not is_whole_number(value):
        raise ConfigError(f"{name} must be a whole number, not {value!r}")


def _require_text(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise ConfigError(f"{name} must be text, not {value!r}")


def parse_serves(text: str) -> tuple[int, ...]:
    """The floors in a list such as "1,31-60", in order."""
    floors: set[int] = set()
    for part in text.split(","):
        match = re.fullmatch(r"\s*(\d+)(?:-(\d+))?\s*", part)
        if match is None:
            raise ConfigError(f"serves must list floors such as '1,31-60', not {text!r}")
        low = int(match[1])
        high = int(match[2]) if match[2] else low
        if high < low:
            raise ConfigError(f"serves has a range that runs backwards in {text!r}")
        floors.update(range(low, high + 1))
    return tuple(sorted(floors))


def format_serves(floors: tuple[int, ...]) -> str:
    """Floors in order as `parse_serves` reads them, with each run of floors as a range."""
    runs: list[list[int]] = []
    for floor in floors:
        if runs and floor == runs[-1][-1] + 1:
            runs[-1].append(floor)
        else:
            runs.append([floor])
    return ",".join(str(run[0]) if len(run) == 1 else f"{run[0]}-{run[-1]}" for run in runs)


@dataclass(frozen=True, slots=True)
class ExpressCar:
    """A car that serves only these floors. Every other car is normal (B5)."""

    car: int
    serves: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class SimConfig:
    floors: int = 10
    elevators: int = 3
    capacity: int = 6
    start_floor: int = 1
    algorithm: str = "marginal_insertion"
    behaviour: str = "min_time"
    max_ticks: int | None = None
    express: tuple[ExpressCar, ...] = ()
    fairness_weight: float | None = None
    guard: str = DEFAULT_GUARD
    skip_limit: int = 2
    # Ticks, or whole round trips written as "2rt".
    wait_limit: int | str = "2rt"
    seat_hold: bool = True

    @property
    def weight(self) -> float:
        """The fairness weight in force, which is 0 for every behaviour but `weighted`."""
        if self.behaviour != "weighted":
            return 0.0
        return DEFAULT_WEIGHT if self.fairness_weight is None else self.fairness_weight

    @property
    def guard_in_force(self) -> str:
        """The guard that runs. `strict` meets "no passenger waits forever" by itself (D24)."""
        return "none" if self.behaviour == "strict" else self.guard

    @property
    def round_trip(self) -> int:
        """Ticks to travel from floor 1 to the top and back."""
        return 2 * (self.floors - 1)

    @property
    def wait_limit_ticks(self) -> int:
        if isinstance(self.wait_limit, str):
            return int(self.wait_limit.removesuffix("rt")) * self.round_trip
        return self.wait_limit

    def __post_init__(self) -> None:
        for name in _INTEGER_KEYS:
            _require_whole_number(name, getattr(self, name))
        if self.max_ticks is not None:
            _require_whole_number("max_ticks", self.max_ticks)
        _require_text("algorithm", self.algorithm)
        _require_text("behaviour", self.behaviour)
        if self.floors < 2:
            raise ConfigError(f"floors must be at least 2, not {self.floors}")
        if self.elevators < 1:
            raise ConfigError(f"elevators must be at least 1, not {self.elevators}")
        if self.capacity < 1:
            raise ConfigError(f"capacity must be at least 1, not {self.capacity}")
        if not 1 <= self.start_floor <= self.floors:
            raise ConfigError(f"start_floor {self.start_floor} is outside 1..{self.floors}")
        if self.algorithm not in ALL_ALGORITHMS:
            names = ", ".join(ALL_ALGORITHMS)
            raise ConfigError(f"unknown algorithm {self.algorithm!r}: use {names}")
        if self.behaviour not in BEHAVIOURS:
            raise ConfigError(f"unknown behaviour {self.behaviour!r}: use {', '.join(BEHAVIOURS)}")
        if self.max_ticks is not None and self.max_ticks < 1:
            raise ConfigError(f"max_ticks must be at least 1, not {self.max_ticks}")
        self._check_weight()
        self._check_guard()
        self._check_express()

    def _check_weight(self) -> None:
        weight = self.fairness_weight
        if weight is None:
            return
        # Accepting a weight that does nothing would let a reader believe it had an effect (M12).
        if self.behaviour != "weighted":
            raise ConfigError(f"fairness_weight applies only to weighted, not {self.behaviour}")
        if isinstance(weight, bool) or not isinstance(weight, int | float):
            raise ConfigError(f"fairness_weight must be a number, not {weight!r}")
        if not 0 <= weight < math.inf:
            raise ConfigError(f"fairness_weight must be 0 or more and finite, not {weight!r}")

    def _check_guard(self) -> None:
        _require_text("guard", self.guard)
        if self.guard not in GUARDS:
            raise ConfigError(f"unknown guard {self.guard!r}: use {', '.join(GUARDS)}")
        _require_whole_number("skip_limit", self.skip_limit)
        if self.skip_limit < 1:
            raise ConfigError(f"skip_limit must be at least 1, not {self.skip_limit}")
        if not isinstance(self.seat_hold, bool):
            raise ConfigError(f"seat_hold must be true or false, not {self.seat_hold!r}")
        limit = self.wait_limit
        if isinstance(limit, str):
            if re.fullmatch(r"[1-9]\d*rt", limit) is None:
                raise ConfigError(
                    f"wait_limit must be ticks or round trips such as '2rt', not {limit!r}"
                )
        elif not is_whole_number(limit) or limit < 1:
            raise ConfigError(f"wait_limit must be at least 1 tick, not {limit!r}")

    def _check_express(self) -> None:
        cars = [car.car for car in self.express]
        for express in self.express:
            if not 1 <= express.car <= self.elevators:
                raise ConfigError(f"express car {express.car} is outside 1..{self.elevators}")
            if cars.count(express.car) > 1:
                raise ConfigError(f"express car {express.car} is listed twice")
            if len(express.serves) < 2:
                raise ConfigError(f"express car {express.car} must serve at least 2 floors")
            for floor in express.serves:
                if not 1 <= floor <= self.floors:
                    raise ConfigError(
                        f"express car {express.car} lists floor {floor}, outside 1..{self.floors}"
                    )
        # One normal car serves every pair of floors, so only an all-express fleet needs checking.
        if len(self.express) == self.elevators:
            served = [set(car.serves) for car in self.express]
            for low, high in combinations(range(1, self.floors + 1), 2):
                if not any(low in floors and high in floors for floors in served):
                    raise ConfigError(f"no car serves both floors {low} and {high} (B8)")


def guard_value(config: SimConfig) -> int | str | None:
    """The limit of the guard in force, as it was set: S, or W in ticks or round trips."""
    guard = config.guard_in_force
    if guard == "skip_limit":
        return config.skip_limit
    if guard == "wait_expiry":
        return config.wait_limit
    return None


def holds_seats(config: SimConfig) -> bool:
    """Seat hold keeps seats only for flagged passengers, so with no guard it does nothing."""
    return config.seat_hold and config.guard_in_force != "none"


def config_id(config: SimConfig) -> str:
    """A readable id with four stable parts: algorithm, behaviour, guard and assignment rule."""
    behaviour = config.behaviour
    if behaviour == "weighted":
        behaviour = f"weighted-{config.weight:g}"
    guard = config.guard_in_force
    if guard != "none":
        guard = f"{guard}-{guard_value(config)}-{'hold' if config.seat_hold else 'nohold'}"
    return f"{config.algorithm}__{behaviour}__{guard}__none"


def settings_record(config: SimConfig) -> dict[str, str | int | float | bool | None]:
    """All dispatch settings by name. Assignment rules aren't built, so hold their off value."""
    guard = config.guard_in_force
    return {
        "algorithm": config.algorithm,
        "behaviour": config.behaviour,
        "fairness_weight": config.weight if config.behaviour == "weighted" else None,
        "guard": guard,
        "guard_value": guard_value(config),
        "seat_hold": holds_seats(config),
        "assignment_rule": "none",
        "rule_value": None,
        # Strict meets "no passenger waits forever" by itself, so it needs no guard (D24).
        "unguarded": guard == "none" and config.behaviour != "strict",
    }


def building_record(config: SimConfig) -> dict[str, Any]:
    """All building settings by name, as a config file sets them, so a run can be repeated."""
    return {
        "floors": config.floors,
        "elevators": config.elevators,
        "capacity": config.capacity,
        "start_floor": config.start_floor,
        # None when the engine's formula sets the limit (spec section 7.5).
        "max_ticks": config.max_ticks,
        "express": [
            {"car": car.car, "serves": format_serves(car.serves)} for car in config.express
        ],
    }


def _read_section(data: dict[str, Any], name: str, allowed: set[str]) -> dict[str, Any]:
    section = data.pop(name, {})
    if not isinstance(section, dict):
        raise ConfigError(f"{name} must be a [{name}] section, not {section!r}")
    for key in section:
        if key in _NOT_BUILT:
            raise ConfigError(f"setting {key!r} isn't built in this version")
        if key not in allowed:
            raise ConfigError(f"unknown setting {key!r} in [{name}]")
    return section


def _read_express(data: dict[str, Any]) -> tuple[ExpressCar, ...]:
    entries = data.pop("express", [])
    if not isinstance(entries, list):
        raise ConfigError("express cars must be [[express]] tables")
    cars = []
    for entry in entries:
        for key in entry:
            if key not in _EXPRESS_KEYS:
                raise ConfigError(f"unknown setting {key!r} in [[express]]")
        if "car" not in entry or "serves" not in entry:
            raise ConfigError("[[express]] needs both car and serves")
        _require_whole_number("car", entry["car"])
        _require_text("serves", entry["serves"])
        cars.append(ExpressCar(entry["car"], parse_serves(entry["serves"])))
    return tuple(cars)


def load_config(path: Path) -> SimConfig:
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}") from None
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise ConfigError(f"{path}: {error}") from None

    building = _read_section(data, "building", _BUILDING_KEYS)
    dispatch = _read_section(data, "dispatch", _DISPATCH_KEYS)
    express = _read_express(data)
    for table in data:
        raise ConfigError(f"unknown section {table!r} in {path}")
    return SimConfig(**building, **dispatch, express=express)
