"""Rewrite the golden outputs: `python tests/update_golden.py`.

Run this only when a phase is meant to change results, and say why in the commit (M8).
"""

import tempfile
from pathlib import Path

from elevator_sim.config import ALGORITHMS, SimConfig, config_id
from elevator_sim.engine import SimulationResult, simulate
from elevator_sim.output import write_run
from elevator_sim.workload import generate_requests

GOLDEN_DIR = Path(__file__).parent / "golden"

# Short, busy inputs, so that seats run short and passengers get left behind.
CASES = {
    "3car-10floor-6cap": (SimConfig(floors=10, elevators=3, capacity=6), 2.5),
    "6car-60floor-6cap": (SimConfig(floors=60, elevators=6, capacity=6), 1.5),
}


def golden_path(building: str, algorithm: str) -> Path:
    return GOLDEN_DIR / f"{building}__{algorithm}.csv"


def render_case(building: str, algorithm: str, scratch: Path) -> tuple[SimulationResult, bytes]:
    building_config, rate = CASES[building]
    config = SimConfig(
        floors=building_config.floors,
        elevators=building_config.elevators,
        capacity=building_config.capacity,
        algorithm=algorithm,
    )
    requests = generate_requests("lunch", rate, 120, 2024, config.floors)
    result = simulate(requests, config)
    out = scratch / config_id(config) / building
    write_run(result, out)
    return result, (out / "passengers.csv").read_bytes()


def main() -> None:
    GOLDEN_DIR.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        for building in CASES:
            for algorithm in ALGORITHMS:
                _, text = render_case(building, algorithm, Path(scratch))
                golden_path(building, algorithm).write_bytes(text)


if __name__ == "__main__":
    main()
