"""The simulation suite: parallel runs, resuming, and the statistics files.

Each run saves its own JSON as it finishes, with a fingerprint of its input, settings and code, so
a restarted suite reuses only runs that still match. Statistics are built afterwards in fixed task
order, so they don't depend on the order runs finished in. Wall-clock times go only to
suite_log.csv, because every other file must stay byte-identical.
"""

import csv
import hashlib
import json
import shutil
import statistics
import time
from collections.abc import Iterable, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from elevator_sim.config import ALGORITHMS, SimConfig, config_id, settings_record
from elevator_sim.engine import SimulationStalledError, simulate
from elevator_sim.metrics import run_stats, total_time, wait_time
from elevator_sim.output import write_csv, write_json, write_run
from elevator_sim.report import render_report
from elevator_sim.requests import load_requests
from elevator_sim.workload import SEEDS, building_config, suite_inputs

_IDENTITY_COLUMNS = ["run_id", "config_id", "stage", "building", "pattern", "load", "seed"]
_SETTINGS_COLUMNS = [
    "algorithm",
    "behaviour",
    "fairness_weight",
    "guard",
    "guard_value",
    "seat_hold",
    "assignment_rule",
    "rule_value",
    "unguarded",
]
AGGREGATE_KEYS = [
    "passengers",
    "ticks",
    "passengers_per_tick",
    "wait_min",
    "wait_mean",
    "wait_max",
    "wait_p95",
    "wait_stdev",
    "total_min",
    "total_mean",
    "total_max",
    "total_p95",
    "total_stdev",
    "avg_car_load",
    "empty_travel_share",
    "jain_wait",
    "jain_total",
    "times_left_behind",
    "max_left_behind_one_passenger",
    "flagged_passengers",
    "fallback_count",
    "held_seat_ticks",
    "share_above_wait_limit",
]
STATS_COLUMNS = _IDENTITY_COLUMNS + _SETTINGS_COLUMNS + AGGREGATE_KEYS

# Off values for statistics that arrive with guards and assignment rules.
_NOT_BUILT_YET = {
    "flagged_passengers": 0,
    "fallback_count": 0,
    "held_seat_ticks": 0,
    "share_above_wait_limit": None,
}
_SAMPLES = {("up_peak", "heavy", 1), ("lunch", "overload", 1)}
PACKAGE_DIR = Path(__file__).parent


@dataclass(frozen=True, slots=True)
class Task:
    run_id: str
    config: SimConfig
    stage: int
    building: str
    pattern: str
    load: str
    seed: int
    input_path: Path
    sample: bool = False


@dataclass(frozen=True, slots=True)
class SuiteOutcome:
    stalled: list[str]
    reused: int


def sample_inputs() -> set[tuple[str, str, str, int]]:
    """The inputs that keep full run logs, two per building."""
    return {
        (spec.building, spec.pattern, spec.load, spec.seed)
        for spec in suite_inputs()
        if (spec.pattern, spec.load, spec.seed) in _SAMPLES
    }


def suite_tasks(inputs: Path, quick: bool = False) -> list[Task]:
    """Stage 1 as far as it is built: every algorithm on every input, in fixed order."""
    samples = sample_inputs()
    tasks = []
    for spec in suite_inputs((SEEDS[0],) if quick else SEEDS):
        building = building_config(spec.building)
        path = inputs / spec.name
        for algorithm in ALGORITHMS:
            config = replace(building, algorithm=algorithm)
            tasks.append(
                Task(
                    f"{config_id(config)}__{path.stem}",
                    config,
                    1,
                    spec.building,
                    spec.pattern,
                    spec.load,
                    spec.seed,
                    path,
                    (spec.building, spec.pattern, spec.load, spec.seed) in samples,
                )
            )
    return tasks


def file_tasks(requests: Path, building: SimConfig, building_name: str) -> list[Task]:
    """Every configuration on one request file."""
    return [
        Task(
            f"{config_id(config)}__{requests.stem}",
            config,
            1,
            building_name,
            "custom",
            "custom",
            0,
            requests,
        )
        for config in (replace(building, algorithm=algorithm) for algorithm in ALGORITHMS)
    ]


def source_fingerprint(package: Path = PACKAGE_DIR) -> str:
    """A hash of every source file, so a run saved by different code is never reused."""
    digest = hashlib.sha256()
    for path in sorted(package.rglob("*.py"), key=lambda path: path.as_posix()):
        digest.update(path.relative_to(package).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def run_fingerprint(task: Task, source: str) -> str:
    """Everything a saved run depends on, except where its input file is kept."""
    contents = hashlib.sha256(task.input_path.read_bytes()).hexdigest()
    identity = asdict(task) | {"input_path": contents, "source": source}
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def _rounded(value: int | float | None) -> int | float | None:
    return round(value, 4) if isinstance(value, float) else value


def _run_file(task: Task, out: Path) -> Path:
    return out / "runs" / f"{task.run_id}.json"


def _sample_dir(task: Task, out: Path) -> Path:
    return out / "samples" / task.input_path.stem / config_id(task.config)


def _is_current(task: Task, fingerprint: str, out: Path) -> bool:
    """Whether a run is saved, and can be shown to come from this input, settings and code."""
    try:
        record: dict[str, Any] = json.loads(_run_file(task, out).read_text(encoding="utf-8"))
    except FileNotFoundError, json.JSONDecodeError:
        return False
    return record.get("fingerprint") == fingerprint


def _discard(task: Task, out: Path) -> None:
    """Remove a stale result first, so a run that then stalls can't leave it on show."""
    _run_file(task, out).unlink(missing_ok=True)
    shutil.rmtree(_sample_dir(task, out), ignore_errors=True)


def run_task(task: Task, fingerprint: str, out: Path) -> tuple[str, str, float]:
    """Run one task, returning its id, status and seconds."""
    started = time.perf_counter()
    try:
        result = simulate(load_requests(task.input_path, task.config.floors), task.config)
    except SimulationStalledError as error:
        return task.run_id, f"stalled: {error}", time.perf_counter() - started
    if task.sample:
        write_run(result, _sample_dir(task, out))
    record = {
        "run_id": task.run_id,
        "fingerprint": fingerprint,
        "config_id": config_id(task.config),
        "stage": task.stage,
        "building": task.building,
        "pattern": task.pattern,
        "load": task.load,
        "seed": task.seed,
        "settings": settings_record(task.config),
        "stats": {key: _rounded(value) for key, value in run_stats(result).items()}
        | _NOT_BUILT_YET,
        "waits": [wait_time(p) for p in result.passengers],
        "totals": [total_time(p) for p in result.passengers],
    }
    # Written then renamed, so an interrupted suite can't leave half a result to resume from.
    partial = out / "runs" / f"{task.run_id}.partial"
    write_json(partial, record)
    partial.replace(_run_file(task, out))
    return task.run_id, "ok", time.perf_counter() - started


def _log_writer(path: Path) -> Any:
    is_new = not path.exists()
    file = path.open("a", encoding="utf-8", newline="")
    if is_new:
        file.write("run_id,status,seconds\n")
    return file


def run_tasks(tasks: Sequence[Task], out: Path, workers: int) -> SuiteOutcome:
    """Run every task without a current saved result, and reuse the rest."""
    (out / "runs").mkdir(parents=True, exist_ok=True)
    source = source_fingerprint()
    todo = []
    for task in tasks:
        fingerprint = run_fingerprint(task, source)
        if not _is_current(task, fingerprint, out):
            _discard(task, out)
            todo.append((task, fingerprint))
    stalled: list[str] = []
    with _log_writer(out / "suite_log.csv") as log:

        def record(run_id: str, status: str, seconds: float) -> None:
            writer = csv.writer(log, lineterminator="\n")
            writer.writerow([run_id, status, f"{seconds:.3f}"])
            log.flush()
            if status != "ok":
                stalled.append(run_id)

        if workers == 1:
            for task, fingerprint in todo:
                record(*run_task(task, fingerprint, out))
        else:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(run_task, task, mark, out) for task, mark in todo]
                for future in as_completed(futures):
                    record(*future.result())
    return SuiteOutcome(stalled, len(tasks) - len(todo))


def load_rows(tasks: Iterable[Task], out: Path) -> list[dict[str, Any]]:
    """One flat row per finished run, in task order."""
    rows = []
    for task in tasks:
        path = _run_file(task, out)
        if path.exists():
            record = json.loads(path.read_text(encoding="utf-8"))
            identity = {key: record[key] for key in _IDENTITY_COLUMNS}
            rows.append(identity | record["settings"] | record["stats"])
    return rows


def aggregate(rows: Sequence[dict[str, Any]], keys: Sequence[str]) -> list[dict[str, Any]]:
    """Mean, min and max of each statistic across seeds, per configuration and input group."""
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        group = (row["config_id"], row["building"], row["pattern"], row["load"])
        groups.setdefault(group, []).append(row)

    aggregated = []
    for (config, building, pattern, load), members in groups.items():
        entry: dict[str, Any] = {
            "config_id": config,
            "building": building,
            "pattern": pattern,
            "load": load,
            "seeds": len(members),
        }
        for key in keys:
            values = [member[key] for member in members if member[key] is not None]
            entry[f"{key}_mean"] = round(statistics.fmean(values), 4) if values else None
            entry[f"{key}_min"] = min(values, default=None)
            entry[f"{key}_max"] = max(values, default=None)
        aggregated.append(entry)
    return aggregated


def write_statistics(rows: Sequence[dict[str, Any]], out: Path) -> None:
    write_csv(
        out / "simulation_stats.csv",
        STATS_COLUMNS,
        [[row[column] for column in STATS_COLUMNS] for row in rows],
    )

    aggregated = aggregate(rows, AGGREGATE_KEYS)
    columns = ["config_id", "building", "pattern", "load", "seeds"]
    columns += [f"{key}_{part}" for key in AGGREGATE_KEYS for part in ("mean", "min", "max")]
    write_csv(
        out / "aggregate_stats.csv",
        columns,
        [[entry[column] for column in columns] for entry in aggregated],
    )

    (out / "by_config").mkdir(exist_ok=True)
    configs = dict.fromkeys(row["config_id"] for row in rows)
    for config in configs:
        members = [row for row in rows if row["config_id"] == config]
        write_csv(
            out / "by_config" / f"{config}.csv",
            STATS_COLUMNS,
            [[row[column] for column in STATS_COLUMNS] for row in members],
        )

    with (out / "report.md").open("w", encoding="utf-8", newline="") as file:
        file.write(render_report(rows))


def run_suite(tasks: Sequence[Task], out: Path, workers: int) -> SuiteOutcome:
    out.mkdir(parents=True, exist_ok=True)
    outcome = run_tasks(tasks, out, workers)
    write_statistics(load_rows(tasks, out), out)
    return outcome
