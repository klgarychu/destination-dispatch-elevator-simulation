"""Simulation settings, TOML loading and validation."""

import re
import tomllib
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

# The fixed display order (G4). Phase 1 compared the first five, so its suite stays on those.
ALGORITHMS = ("round_robin", "nearest_car", "zone_based", "eta", "marginal_insertion")
ALL_ALGORITHMS = (*ALGORITHMS, "rush_express")
BEHAVIOURS = ("min_time",)

# Settings the design defines but this phase doesn't build. Accepting them silently would let a
# reader believe a guard was active when it wasn't (M12).
_LATER_SETTINGS = {
    "fairness_weight": 3,
    "guard": 4,
    "skip_limit": 4,
    "wait_limit": 4,
    "seat_hold": 4,
    "assignment_rule": 5,
}
_LATER_BEHAVIOURS = {"strict": 3, "weighted": 3}

_BUILDING_KEYS = {"floors", "elevators", "capacity", "start_floor"}
_DISPATCH_KEYS = {"algorithm", "behaviour"}
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
        if self.behaviour in _LATER_BEHAVIOURS:
            phase = _LATER_BEHAVIOURS[self.behaviour]
            raise ConfigError(f"behaviour {self.behaviour!r} arrives in Phase {phase}")
        if self.behaviour not in BEHAVIOURS:
            raise ConfigError(f"unknown behaviour {self.behaviour!r}: use {', '.join(BEHAVIOURS)}")
        if self.max_ticks is not None and self.max_ticks < 1:
            raise ConfigError(f"max_ticks must be at least 1, not {self.max_ticks}")
        self._check_express()

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


def config_id(config: SimConfig) -> str:
    """A readable id with four stable parts: algorithm, behaviour, guard and assignment rule."""
    return f"{config.algorithm}__{config.behaviour}__none__none"


def settings_record(config: SimConfig) -> dict[str, str | float | bool | None]:
    """All dispatch settings by name. Fields for later phases hold their off value."""
    return {
        "algorithm": config.algorithm,
        "behaviour": config.behaviour,
        "fairness_weight": None,
        "guard": "none",
        "guard_value": None,
        "seat_hold": False,
        "assignment_rule": "none",
        "rule_value": None,
        "unguarded": True,
    }


def _read_section(data: dict[str, Any], name: str, allowed: set[str]) -> dict[str, Any]:
    section = data.pop(name, {})
    if not isinstance(section, dict):
        raise ConfigError(f"{name} must be a [{name}] section, not {section!r}")
    for key in section:
        if key in _LATER_SETTINGS:
            raise ConfigError(f"setting {key!r} arrives in Phase {_LATER_SETTINGS[key]}")
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
