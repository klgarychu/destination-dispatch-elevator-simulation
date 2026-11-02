"""report.md: summary tables in fixed order. It states numbers and passes no judgement (R-31)."""

import statistics
from collections.abc import Sequence
from typing import Any

from elevator_sim.config import ALL_ALGORITHMS
from elevator_sim.workload import BUILDINGS, EXPRESS_BUILDINGS, FIXED, LOADS, OWN_LIMIT, PATTERNS

_COLUMNS = (
    ("Min total", "total_min"),
    ("Mean total", "total_mean"),
    ("Max total", "total_max"),
    ("Min wait", "wait_min"),
    ("Mean wait", "wait_mean"),
    ("p95 wait", "wait_p95"),
    ("Max wait", "wait_max"),
    ("Jain (wait)", "jain_wait"),
    ("Left behind", "times_left_behind"),
)


def _place(options: Sequence[str], value: str) -> int:
    """A value's fixed display position. Anything unlisted, such as custom input, goes last."""
    return options.index(value) if value in options else len(options)


def _group_key(row: dict[str, Any]) -> tuple[int, int, str, int, str, int, str]:
    building, pattern, load = row["building"], row["pattern"], row["load"]
    return (
        _place((OWN_LIMIT, FIXED), row["load_basis"]),
        _place((*BUILDINGS, *EXPRESS_BUILDINGS), building),
        building,
        _place(list(PATTERNS), pattern),
        pattern,
        _place(list(LOADS), load),
        load,
    )


def _cell(values: Sequence[float]) -> str:
    return f"{statistics.fmean(values):.2f} ({min(values):.2f} to {max(values):.2f})"


def _table(rows: Sequence[dict[str, Any]]) -> list[str]:
    headers = ["Algorithm", "Behaviour", "Seeds", *[title for title, _ in _COLUMNS]]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    configs = dict.fromkeys(row["config_id"] for row in rows)
    ordered = sorted(
        configs,
        key=lambda config: _place(
            ALL_ALGORITHMS, next(r["algorithm"] for r in rows if r["config_id"] == config)
        ),
    )
    for config in ordered:
        members = [row for row in rows if row["config_id"] == config]
        cells = [
            f"`{members[0]['algorithm']}`",
            f"`{members[0]['behaviour']}`",
            str(len(members)),
        ]
        for _, key in _COLUMNS:
            values = [member[key] for member in members if member[key] is not None]
            cells.append(_cell(values) if values else "no passengers")
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def _incomplete_notice(finished: int, not_finished: Sequence[str]) -> list[str]:
    if not not_finished:
        return []
    names = ", ".join(f"`{run_id}`" for run_id in not_finished)
    return [
        f"**Incomplete comparison: {len(not_finished)} of {finished + len(not_finished)} runs "
        "didn't finish, so the configurations below may not have run the same inputs.** "
        f"Missing: {names}.",
        "",
    ]


def render_report(rows: Sequence[dict[str, Any]], not_finished: Sequence[str] = ()) -> str:
    pairs = {(r["load_basis"], r["building"], r["pattern"], r["load"], r["seed"]) for r in rows}
    seeds = sorted({r["seed"] for r in rows})
    unguarded = sum(1 for r in rows if r["unguarded"])
    lines = [
        "# Simulation report",
        "",
        *_incomplete_notice(len(rows), not_finished),
        f"Runs: {len(rows)}. Case and input pairs: {len(pairs)}. "
        f"Configurations: {len({r['config_id'] for r in rows})}. "
        f"Seeds: {', '.join(str(seed) for seed in seeds)}.",
        "",
        f"Unguarded runs: {unguarded} of {len(rows)}. Unguarded runs have no protection against "
        "long waits beyond the inputs being finite.",
        "",
        "Configurations appear in a fixed order. This report makes no judgement between them: "
        "a person reads the tables and charts and decides.",
        "",
        "Each cell shows the mean across seeds, then the range across seeds in brackets. "
        "That range describes spread and isn't a significance test: configurations run the same "
        "inputs, so compare them seed by seed.",
        "",
        "Total time is wait time plus a fixed distance, so differences in mean total time are "
        "exactly the differences in mean wait time.",
    ]
    if any(r["load_basis"] == FIXED for r in rows):
        lines += [
            "",
            "Sections marked fixed load give a case the same arrivals as the building it is "
            "compared with, whose own sections are that load. Cases of another height keep the "
            "arrival ticks, with floors drawn for their height.",
        ]
    groups: dict[tuple[int, int, str, int, str, int, str], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(_group_key(row), []).append(row)
    for key in sorted(groups):
        members = groups[key]
        first = members[0]
        label = ", fixed load" if first["load_basis"] == FIXED else ""
        lines += [
            "",
            f"## {first['building']}, {first['pattern']}, {first['load']}{label}",
            "",
            *_table(members),
        ]
    return "\n".join(lines) + "\n"
