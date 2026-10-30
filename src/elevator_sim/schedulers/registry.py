"""Builds a scheduler by name. A new instance per run keeps runs independent."""

from elevator_sim.schedulers.base import Scheduler
from elevator_sim.schedulers.round_robin import RoundRobin


def make_scheduler(name: str) -> Scheduler:
    schedulers: dict[str, type[Scheduler]] = {"round_robin": RoundRobin}
    return schedulers[name]()
