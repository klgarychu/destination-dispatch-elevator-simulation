"""The simulation suite: parallel runs, resuming, and the statistics files.

Each run saves its own JSON as it finishes, with a fingerprint of its input, settings and code, so
a restarted suite reuses only runs that still match. Statistics are built afterwards in fixed task
order, so they don't depend on the order runs finished in, and a manifest lists exactly which runs
they cover, because `runs/` can also hold runs from other comparisons. Wall-clock times go only to
suite_log.csv, because every other file must stay byte-identical.
"""

import csv
import hashlib
import json
import shutil
import statistics
import time
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from elevator_sim.config import (
    ALGORITHMS,
    ALL_ALGORITHMS,
    SimConfig,
    check_workers,
    config_id,
    settings_record,
)
from elevator_sim.engine import SimulationStalledError, simulate
from elevator_sim.metrics import run_stats, total_time, wait_time
from elevator_sim.output import (
    MANIFEST_FILE,
    Manifest,
    RunRecord,
    read_run_record,
    run_file,
    write_csv,
    write_manifest,
    write_run,
    write_run_record,
)
from elevator_sim.report import render_report
from elevator_sim.requests import load_requests
from elevator_sim.workload import (
    BEHAVIOUR_OWN_LIMIT,
    BEHAVIOUR_SHARED,
    EXPRESS_BUILDINGS,
    EXPRESS_OWN_LIMIT,
    FIXED,
    OWN_LIMIT,
    SEEDS,
    InputSpec,
    building_config,
    fixed_inputs,
    input_name,
    suite_inputs,
)

_IDENTITY_COLUMNS = [
    "run_id",
    "config_id",
    "stage",
    "building",
    "pattern",
    "load",
    "load_basis",
    "seed",
]
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

# Assignment rules aren't built (M34), so their statistic holds its off value.
_NOT_BUILT = {"fallback_count": 0}
_SAMPLES = {("up_peak", "heavy", 1), ("lunch", "overload", 1)}
SEAT_SETTINGS: tuple[tuple[str, float | None], ...] = (
    ("strict", None),
    ("min_time", None),
    ("weighted", 0.5),
    ("weighted", 1.0),
    ("weighted", 2.0),
)
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
    load_basis: str = OWN_LIMIT


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
    """Phase 1: every algorithm on every input, in fixed order, with no guard as it was run."""
    samples = sample_inputs()
    seeds = (SEEDS[0],) if quick else SEEDS
    tasks = []
    for spec in (*suite_inputs(seeds), *fixed_inputs(seeds)):
        building = building_config(spec.building)
        path = inputs / spec.name
        # Cases can share a fixed-load file, so those run ids name the case as well.
        label = f"{spec.building}__{FIXED}_{path.stem}" if spec.fixed else path.stem
        for algorithm in ALGORITHMS:
            config = replace(building, algorithm=algorithm, guard="none")
            tasks.append(
                Task(
                    f"{config_id(config)}__{label}",
                    config,
                    1,
                    spec.building,
                    spec.pattern,
                    spec.load,
                    spec.seed,
                    path,
                    not spec.fixed
                    and (spec.building, spec.pattern, spec.load, spec.seed) in samples,
                    FIXED if spec.fixed else OWN_LIMIT,
                )
            )
    return tasks


def _samples_this(spec: InputSpec) -> bool:
    return (spec.pattern, spec.load, spec.seed) in _SAMPLES


def _case_tasks(
    inputs: Path,
    quick: bool,
    own_limit: Sequence[str],
    shared: Mapping[str, str],
    seat_settings: Sequence[tuple[str, float | None]],
    guard: str,
) -> list[Task]:
    """Every algorithm and seat setting on each case's own limit, then on shared passengers."""
    seeds = (SEEDS[0],) if quick else SEEDS

    def configs(case: str) -> list[SimConfig]:
        building = replace(building_config(case), guard=guard)
        return [
            replace(building, algorithm=algorithm, behaviour=behaviour, fairness_weight=weight)
            for behaviour, weight in seat_settings
            for algorithm in ALL_ALGORITHMS
        ]

    tasks = []
    for spec in suite_inputs(seeds, own_limit):
        path = inputs / spec.name
        for config in configs(spec.building):
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
                    _samples_this(spec),
                )
            )
    for case, base in shared.items():
        for spec in suite_inputs(seeds, (base,)):
            path = inputs / input_name(base, spec.pattern, spec.load, spec.seed)
            for config in configs(case):
                tasks.append(
                    Task(
                        f"{config_id(config)}__{case}__{FIXED}_{path.stem}",
                        config,
                        1,
                        case,
                        spec.pattern,
                        spec.load,
                        spec.seed,
                        path,
                        _samples_this(spec),
                        FIXED,
                    )
                )
    return tasks


def express_tasks(inputs: Path, quick: bool = False) -> list[Task]:
    """Phase 2 (M30): the express cases, all on `min_time` with no guard, as they were run."""
    only_min_time = (("min_time", None),)
    return _case_tasks(inputs, quick, EXPRESS_OWN_LIMIT, EXPRESS_BUILDINGS, only_min_time, "none")


def behaviour_tasks(inputs: Path, quick: bool = False) -> list[Task]:
    """Phase 3 (M32): every seat setting on every algorithm, with no guard, as they were run."""
    return _case_tasks(inputs, quick, BEHAVIOUR_OWN_LIMIT, BEHAVIOUR_SHARED, SEAT_SETTINGS, "none")


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
            load_basis="custom",
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


def _sample_dir(task: Task) -> str:
    """Where a run's full logs go, relative to the results folder."""
    # Cases can share a fixed-load file, so those folders name the case as well.
    stem = task.input_path.stem
    name = f"{task.building}__{stem}" if task.load_basis == FIXED else stem
    return f"samples/{name}/{config_id(task.config)}"


def _is_current(task: Task, fingerprint: str, out: Path) -> bool:
    """Whether a run is saved, and can be shown to come from this input, settings and code."""
    saved = read_run_record(out, task.run_id)
    return saved is not None and saved.fingerprint == fingerprint


def _discard(task: Task, out: Path) -> None:
    """Remove a stale result first, so a run that then stalls can't leave it on show."""
    run_file(out, task.run_id).unlink(missing_ok=True)
    # A run outside the sample may share its input file with a sample run, and so this folder.
    if task.sample:
        shutil.rmtree(out / _sample_dir(task), ignore_errors=True)


def run_task(task: Task, fingerprint: str, out: Path) -> tuple[str, str, float]:
    """Run one task, returning its id, status and seconds."""
    started = time.perf_counter()
    try:
        result = simulate(load_requests(task.input_path, task.config.floors), task.config)
    except SimulationStalledError as error:
        return task.run_id, f"stalled: {error}", time.perf_counter() - started
    sample_dir = _sample_dir(task) if task.sample else None
    if sample_dir is not None:
        write_run(result, out / sample_dir)
    stats = {key: _rounded(value) for key, value in run_stats(result).items()}
    record = RunRecord(
        run_id=task.run_id,
        fingerprint=fingerprint,
        config_id=config_id(task.config),
        stage=task.stage,
        building=task.building,
        pattern=task.pattern,
        load=task.load,
        load_basis=task.load_basis,
        seed=task.seed,
        settings=settings_record(task.config),
        stats=stats | _NOT_BUILT,
        waits=[wait_time(p) for p in result.passengers],
        totals=[total_time(p) for p in result.passengers],
        sample_dir=sample_dir,
    )
    write_run_record(out, record)
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
        record = read_run_record(out, task.run_id)
        if record is not None:
            identity = {key: getattr(record, key) for key in _IDENTITY_COLUMNS}
            rows.append(identity | record.settings | record.stats)
    return rows


def aggregate(rows: Sequence[dict[str, Any]], keys: Sequence[str]) -> list[dict[str, Any]]:
    """Mean, min and max of each statistic across seeds, per configuration and input group."""
    groups: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        group = (
            row["config_id"],
            row["building"],
            row["pattern"],
            row["load"],
            row["load_basis"],
        )
        groups.setdefault(group, []).append(row)

    aggregated = []
    for (config, building, pattern, load, load_basis), members in groups.items():
        entry: dict[str, Any] = {
            "config_id": config,
            "algorithm": members[0]["algorithm"],
            "behaviour": members[0]["behaviour"],
            "fairness_weight": members[0]["fairness_weight"],
            "building": building,
            "pattern": pattern,
            "load": load,
            "load_basis": load_basis,
            "seeds": len(members),
        }
        for key in keys:
            values = [member[key] for member in members if member[key] is not None]
            entry[f"{key}_mean"] = round(statistics.fmean(values), 4) if values else None
            entry[f"{key}_min"] = min(values, default=None)
            entry[f"{key}_max"] = max(values, default=None)
        aggregated.append(entry)
    return aggregated


def write_statistics(
    rows: Sequence[dict[str, Any]], out: Path, not_finished: Sequence[str] = ()
) -> None:
    write_csv(
        out / "simulation_stats.csv",
        STATS_COLUMNS,
        [[row[column] for column in STATS_COLUMNS] for row in rows],
    )

    aggregated = aggregate(rows, AGGREGATE_KEYS)
    columns = [
        "config_id",
        "algorithm",
        "behaviour",
        "fairness_weight",
        "building",
        "pattern",
        "load",
        "load_basis",
        "seeds",
    ]
    columns += [f"{key}_{part}" for key in AGGREGATE_KEYS for part in ("mean", "min", "max")]
    write_csv(
        out / "aggregate_stats.csv",
        columns,
        [[entry[column] for column in columns] for entry in aggregated],
    )

    (out / "by_config").mkdir(exist_ok=True)
    for earlier in (out / "by_config").glob("*.csv"):
        earlier.unlink()
    configs = dict.fromkeys(row["config_id"] for row in rows)
    for config in configs:
        members = [row for row in rows if row["config_id"] == config]
        write_csv(
            out / "by_config" / f"{config}.csv",
            STATS_COLUMNS,
            [[row[column] for column in STATS_COLUMNS] for row in members],
        )

    with (out / "report.md").open("w", encoding="utf-8", newline="") as file:
        file.write(render_report(rows, not_finished))


def run_suite(tasks: Sequence[Task], out: Path, workers: int) -> SuiteOutcome:
    check_workers(workers)
    out.mkdir(parents=True, exist_ok=True)
    # Removed first and written last, so an interrupted suite can't leave it beside changed runs.
    (out / MANIFEST_FILE).unlink(missing_ok=True)
    outcome = run_tasks(tasks, out, workers)
    rows = load_rows(tasks, out)
    finished = [row["run_id"] for row in rows]
    done = set(finished)
    # In task order, not the order runs stalled in, so the files stay byte-identical.
    not_finished = [task.run_id for task in tasks if task.run_id not in done]
    write_statistics(rows, out, not_finished)
    samples = [task.run_id for task in tasks if task.sample and task.run_id in done]
    write_manifest(out, Manifest(finished, not_finished, samples))
    return outcome
