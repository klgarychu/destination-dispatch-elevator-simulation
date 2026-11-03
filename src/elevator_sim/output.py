"""Files and console text for one run: positions.csv, passengers.csv, summary.json."""

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from elevator_sim.config import ConfigError, building_record, settings_record
from elevator_sim.engine import SimulationResult
from elevator_sim.metrics import (
    TimeStats,
    observations,
    time_stats,
    total_time,
    wait_time,
)

MANIFEST_FILE = "run_manifest.json"
PASSENGER_COLUMNS = [
    "id",
    "time",
    "source",
    "dest",
    "elevator",
    "board_time",
    "dropoff_time",
    "wait_time",
    "travel_time",
    "total_time",
    "times_left_behind",
]


def write_csv(path: Path, header: list[str], rows: list[list[Any]]) -> None:
    """Write a CSV with LF line endings, so the bytes are the same on every run."""
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def write_json(path: Path, data: object) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        file.write(json.dumps(data, indent=2) + "\n")


@dataclass(frozen=True, slots=True)
class RunRecord:
    """One finished run, as saved in runs/<run_id>.json."""

    run_id: str
    fingerprint: str
    config_id: str
    stage: int
    building: str
    pattern: str
    load: str
    load_basis: str
    seed: int
    settings: dict[str, Any]
    building_settings: dict[str, Any]
    stats: dict[str, Any]
    waits: list[int]
    totals: list[int]
    sample_dir: str | None


def run_file(out: Path, run_id: str) -> Path:
    return out / "runs" / f"{run_id}.json"


def write_run_record(out: Path, record: RunRecord) -> None:
    """Written then renamed, so an interrupted suite can't leave half a result to resume from."""
    partial = out / "runs" / f"{record.run_id}.partial"
    write_json(partial, asdict(record))
    partial.replace(run_file(out, record.run_id))


def read_run_record(out: Path, run_id: str) -> RunRecord | None:
    """A saved run, or None if it's missing or was saved in another format."""
    try:
        return RunRecord(**json.loads(run_file(out, run_id).read_text(encoding="utf-8")))
    except FileNotFoundError, json.JSONDecodeError, TypeError:
        return None


@dataclass(frozen=True, slots=True)
class Manifest:
    """The runs a folder's statistics cover, any that didn't finish, and those with full logs."""

    runs: list[str]
    not_finished: list[str]
    samples: list[str]


def write_manifest(out: Path, manifest: Manifest) -> None:
    write_json(out / MANIFEST_FILE, asdict(manifest))


def read_manifest(out: Path) -> Manifest:
    path = out / MANIFEST_FILE
    if not path.exists():
        raise ConfigError(f"no finished comparison at {path}: run compare first")
    try:
        return Manifest(**json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError, TypeError:
        raise ConfigError(f"can't read {path}: run compare again") from None


def _rounded(stats: TimeStats | None) -> dict[str, float | int] | None:
    if stats is None:
        return None
    return {
        "min": stats.min,
        "mean": round(stats.mean, 2),
        "max": stats.max,
        "p95": stats.p95,
        "stdev": round(stats.stdev, 2),
    }


def summary_data(result: SimulationResult) -> dict[str, Any]:
    config = result.config
    return {
        "config": settings_record(config),
        "building": building_record(config),
        "passengers": len(result.passengers),
        "ticks": result.ticks,
        "wait_time": _rounded(time_stats([wait_time(p) for p in result.passengers])),
        "total_time": _rounded(time_stats([total_time(p) for p in result.passengers])),
        "observations": observations(result),
    }


def write_run(result: SimulationResult, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    cars = len(result.positions[0])
    write_csv(
        out / "positions.csv",
        ["time"] + [f"elevator_{number}" for number in range(1, cars + 1)],
        [[tick, *row] for tick, row in enumerate(result.positions)],
    )
    write_csv(
        out / "passengers.csv",
        PASSENGER_COLUMNS,
        [
            [
                p.request.id,
                p.request.time,
                p.request.source,
                p.request.dest,
                p.car_id,
                p.board_tick,
                p.dropoff_tick,
                wait_time(p),
                total_time(p) - wait_time(p),
                total_time(p),
                p.times_left_behind,
            ]
            for p in result.passengers
        ],
    )
    write_json(out / "summary.json", summary_data(result))


def format_summary(summary: dict[str, Any]) -> str:
    lines = [f"Passengers: {summary['passengers']}", f"Ticks: {summary['ticks']}"]
    for label, key in (("wait", "wait_time"), ("total", "total_time")):
        stats = summary[key]
        if stats is None:
            lines.append(f"{label}: no passengers")
        else:
            lines.append(
                f"{label}: min {stats['min']}, mean {stats['mean']}, max {stats['max']}, "
                f"p95 {stats['p95']}, stdev {stats['stdev']}"
            )
    lines.extend(summary["observations"])
    return "\n".join(lines)
