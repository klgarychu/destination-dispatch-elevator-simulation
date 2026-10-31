"""Static PNG charts from saved statistics. Fixed order, and nothing is ranked or highlighted.

The colours pass a colour-blindness check with every pair in play, as scatter charts need. Two of
them have low contrast against the background, so report.md is the table view of every chart.
"""

import csv
import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # the backend must be set first
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator, FuncFormatter, LogLocator, NullLocator

from elevator_sim.config import ALGORITHMS, ConfigError
from elevator_sim.metrics import nearest_rank
from elevator_sim.workload import LOADS, PATTERNS

COLOURS = {
    "round_robin": "#2a78d6",
    "nearest_car": "#eb6834",
    "zone_based": "#1baf7a",
    "eta": "#56b4e9",
    "marginal_insertion": "#b5179e",
}
MARKERS = {
    "round_robin": "o",
    "nearest_car": "s",
    "zone_based": "^",
    "eta": "D",
    "marginal_insertion": "P",
}
TITLES = {
    "algorithm_comparison": "Mean total time per passenger, by algorithm",
    "distributions": "Wait and total time distributions, by algorithm",
    "fairness_vs_efficiency": "Fairness against efficiency, by algorithm",
    "load_response": "Mean total time as load rises, by algorithm",
    "car_movement": "Car movement over the first 200 ticks, by algorithm",
}
FIXED_DISTANCE_NOTE = "Total time is wait time plus a fixed distance."
_SPREAD_NOTE = "Lines show the range across seeds. Gaps smaller than that range are noise."

_SURFACE = "#fcfcfb"
_INK = "#0b0b0b"
_SECONDARY_INK = "#52514e"
_GRID = "#e1e0d9"
_AXIS = "#c3c2b7"
_SAMPLE_INPUT = "up_peak_heavy_s1"
_CAR_MOVEMENT_TICKS = 200
_WHOLE_TICKS = FuncFormatter(lambda value, _: f"{value:,.0f}")


def fixed_order(algorithms: Iterable[str]) -> list[str]:
    present = set(algorithms)
    return [name for name in ALGORITHMS if name in present]


def _in_order(values: Iterable[str], order: Sequence[str]) -> list[str]:
    present = dict.fromkeys(values)
    listed = [value for value in order if value in present]
    return listed + [value for value in present if value not in order]


def _style_axes(axes: Axes) -> None:
    axes.set_facecolor(_SURFACE)
    axes.grid(axis="y", color=_GRID, linewidth=0.8)
    axes.set_axisbelow(True)
    for side in ("top", "right", "left"):
        axes.spines[side].set_visible(False)
    axes.spines["bottom"].set_color(_AXIS)
    axes.tick_params(colors=_SECONDARY_INK, labelsize=8, length=0)


def _figure(rows: int, columns: int, width: float, height: float) -> tuple[Figure, Any]:
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    figure, axes = plt.subplots(
        rows, columns, figsize=(width, height), squeeze=False, sharey="row", facecolor=_SURFACE
    )
    for axis in axes.flat:
        _style_axes(axis)
    return figure, axes


def _finish(
    figure: Figure, path: Path, title: str, notes: Sequence[str], algorithms: Sequence[str]
) -> None:
    """Title and notes at the top left, with the legend below them."""
    height = figure.get_figheight()
    figure.text(0.02, 1 - 0.14 / height, title, fontsize=13, weight="bold", color=_INK)
    figure.text(
        0.02, 1 - 0.36 / height, " ".join(notes), fontsize=9, color=_SECONDARY_INK, va="center"
    )
    handles = [
        Line2D(
            [],
            [],
            color=COLOURS[name],
            marker=MARKERS[name],
            markersize=6,
            linewidth=2,
            label=name,
        )
        for name in algorithms
    ]
    if handles:
        figure.legend(
            handles=handles,
            loc="upper left",
            bbox_to_anchor=(0.015, 1 - 0.46 / height),
            ncols=len(handles),
            frameon=False,
            fontsize=9,
            labelcolor=_SECONDARY_INK,
        )
    figure.tight_layout(rect=(0, 0, 1, 1 - 0.8 / height))
    figure.savefig(path, dpi=150, facecolor=_SURFACE, metadata={"Software": None})
    plt.close(figure)


def _read_aggregates(stats: Path) -> list[dict[str, str]]:
    path = stats / "aggregate_stats.csv"
    if not path.exists():
        raise ConfigError(f"no statistics found at {path}")
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def _algorithm(row: dict[str, str]) -> str:
    return row["config_id"].split("__")[0]


def _panel_label(axes: Axes, text: str) -> None:
    axes.set_title(text, fontsize=9, color=_SECONDARY_INK, loc="left")


def _pick(rows: Sequence[dict[str, str]], pattern: str, load: str) -> list[dict[str, str]]:
    return [row for row in rows if row["pattern"] == pattern and row["load"] == load]


def _algorithm_comparison(rows: Sequence[dict[str, str]], path: Path) -> None:
    patterns = _in_order((row["pattern"] for row in rows), list(PATTERNS))
    loads = _in_order((row["load"] for row in rows), list(LOADS))
    algorithms = fixed_order(_algorithm(row) for row in rows)
    figure, axes = _figure(
        len(loads), len(patterns), 2.6 * len(patterns) + 0.6, 2.0 * len(loads) + 1.0
    )
    for row_index, load in enumerate(loads):
        for column, pattern in enumerate(patterns):
            axis = axes[row_index][column]
            _panel_label(axis, f"{pattern}, {load}")
            axis.set_xticks([])
            axis.set_xlim(-0.6, len(algorithms) - 0.4)
            for row in _pick(rows, pattern, load):
                name = _algorithm(row)
                place = algorithms.index(name)
                axis.plot(
                    [place, place],
                    [float(row["total_mean_min"]), float(row["total_mean_max"])],
                    color=COLOURS[name],
                    linewidth=2,
                    solid_capstyle="round",
                )
                axis.plot(
                    place,
                    float(row["total_mean_mean"]),
                    marker=MARKERS[name],
                    color=COLOURS[name],
                    markersize=6,
                    markeredgecolor=_SURFACE,
                    markeredgewidth=1,
                )
        top = max(float(row["total_mean_max"]) for row in rows if row["load"] == load)
        axes[row_index][0].set_ylim(0, top * 1.08)
        axes[row_index][0].set_ylabel("Ticks", fontsize=8, color=_SECONDARY_INK)
    _finish(
        figure,
        path,
        TITLES["algorithm_comparison"],
        [FIXED_DISTANCE_NOTE, _SPREAD_NOTE, "Each row shares an axis."],
        algorithms,
    )


def _pooled_times(stats: Path, building: str) -> dict[tuple[str, str], dict[str, list[int]]]:
    pooled: dict[tuple[str, str], dict[str, list[int]]] = {}
    for path in sorted((stats / "runs").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record["building"] != building:
            continue
        key = (record["load"], record["settings"]["algorithm"])
        times = pooled.setdefault(key, {"wait": [], "total": []})
        times["wait"].extend(record["waits"])
        times["total"].extend(record["totals"])
    return pooled


def _box(values: Sequence[int], label: str) -> dict[str, Any]:
    """The middle 90% of passengers, so that a few extreme waits can't hide the rest."""
    return {
        "label": label,
        "whislo": nearest_rank(values, 5),
        "q1": nearest_rank(values, 25),
        "med": nearest_rank(values, 50),
        "q3": nearest_rank(values, 75),
        "whishi": nearest_rank(values, 95),
        "fliers": [],
    }


def _distributions(stats: Path, building: str, path: Path) -> None:
    pooled = _pooled_times(stats, building)
    loads = _in_order((load for load, _ in pooled), list(LOADS))
    algorithms = fixed_order(name for _, name in pooled)
    figure, axes = _distribution_figure(len(loads))
    for column, load in enumerate(loads):
        for row_index, measure in enumerate(("wait", "total")):
            axis = axes[row_index][column]
            _style_axes(axis)
            _panel_label(axis, f"{measure} time, {load}")
            boxes = [
                _box(pooled[(load, name)][measure], name)
                for name in algorithms
                if pooled[(load, name)][measure]
            ]
            if not boxes:
                continue
            drawn = axis.bxp(
                boxes,
                positions=range(len(boxes)),
                widths=0.35,
                patch_artist=True,
                showfliers=False,
                medianprops={"color": _INK, "linewidth": 1.2},
                whiskerprops={"color": _AXIS, "linewidth": 1.2},
                showcaps=False,
                boxprops={"linewidth": 0},
            )
            for box, name in zip(drawn["boxes"], algorithms, strict=True):
                box.set_facecolor(COLOURS[name])
            axis.set_xticks([])
            axis.set_yscale("symlog", linthresh=10)
            axis.yaxis.set_major_locator(FixedLocator([0, 5, 10, 100, 1000, 10000]))
            axis.yaxis.set_major_formatter(_WHOLE_TICKS)
            axis.yaxis.set_minor_locator(NullLocator())
    for row_index in range(2):
        axes[row_index][0].set_ylabel("Ticks", fontsize=8, color=_SECONDARY_INK)
    _finish(
        figure,
        path,
        TITLES["distributions"],
        [
            "Boxes: 25th to 75th percentile. Bar: median. Lines: 5th to 95th.",
            "Patterns and seeds are pooled. The axis is log above 10.",
            FIXED_DISTANCE_NOTE,
        ],
        algorithms,
    )


def _distribution_figure(loads: int) -> tuple[Figure, Any]:
    """Two rows, sharing one axis, so that every load can be compared directly."""
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    return plt.subplots(
        2, loads, figsize=(2.8 * loads + 0.8, 6.4), squeeze=False, sharey=True, facecolor=_SURFACE
    )


def _fairness_vs_efficiency(rows: Sequence[dict[str, str]], path: Path) -> None:
    patterns = _in_order((row["pattern"] for row in rows), list(PATTERNS))
    loads = _in_order((row["load"] for row in rows), list(LOADS))
    algorithms = fixed_order(_algorithm(row) for row in rows)
    figure, axes = _figure(
        len(loads), len(patterns), 2.6 * len(patterns) + 0.6, 2.2 * len(loads) + 1.0
    )
    for row_index, load in enumerate(loads):
        for column, pattern in enumerate(patterns):
            axis = axes[row_index][column]
            _panel_label(axis, f"{pattern}, {load}")
            axis.grid(axis="x", color=_GRID, linewidth=0.8)
            for row in _pick(rows, pattern, load):
                name = _algorithm(row)
                x, y = float(row["total_mean_mean"]), float(row["wait_p95_mean"])
                axis.plot(
                    [float(row["total_mean_min"]), float(row["total_mean_max"])],
                    [y, y],
                    color=COLOURS[name],
                    linewidth=1,
                )
                axis.plot(
                    [x, x],
                    [float(row["wait_p95_min"]), float(row["wait_p95_max"])],
                    color=COLOURS[name],
                    linewidth=1,
                )
                axis.plot(
                    x,
                    y,
                    marker=MARKERS[name],
                    color=COLOURS[name],
                    markersize=6,
                    markeredgecolor=_SURFACE,
                    markeredgewidth=1,
                )
            axis.tick_params(axis="x", labelbottom=True)
            axis.set_xlabel("Mean total time (ticks)", fontsize=8, color=_SECONDARY_INK)
        axes[row_index][0].set_ylabel("p95 wait (ticks)", fontsize=8, color=_SECONDARY_INK)
    _finish(
        figure,
        path,
        TITLES["fairness_vs_efficiency"],
        ["Further left is less total time, and lower down is a shorter long wait.", _SPREAD_NOTE],
        algorithms,
    )


def _load_response(rows: Sequence[dict[str, str]], path: Path) -> None:
    patterns = _in_order((row["pattern"] for row in rows), list(PATTERNS))
    loads = _in_order((row["load"] for row in rows), list(LOADS))
    algorithms = fixed_order(_algorithm(row) for row in rows)
    figure, axes = _figure(1, len(patterns), 3.0 * len(patterns) + 0.6, 4.4)
    for column, pattern in enumerate(patterns):
        axis = axes[0][column]
        _panel_label(axis, pattern)
        axis.set_yscale("log")
        axis.yaxis.set_major_locator(LogLocator(base=10, subs=(1, 2, 5)))
        axis.yaxis.set_major_formatter(_WHOLE_TICKS)
        axis.yaxis.set_minor_locator(NullLocator())
        for name in algorithms:
            series = {
                row["load"]: row
                for row in rows
                if row["pattern"] == pattern and _algorithm(row) == name
            }
            places = [index for index, load in enumerate(loads) if load in series]
            members = [series[loads[index]] for index in places]
            axis.fill_between(
                places,
                [float(row["total_mean_min"]) for row in members],
                [float(row["total_mean_max"]) for row in members],
                color=COLOURS[name],
                alpha=0.1,
                linewidth=0,
            )
            axis.plot(
                places,
                [float(row["total_mean_mean"]) for row in members],
                color=COLOURS[name],
                marker=MARKERS[name],
                markersize=6,
                markeredgecolor=_SURFACE,
                markeredgewidth=1,
                linewidth=2,
            )
        axis.set_xticks(range(len(loads)), loads)
    axes[0][0].set_ylabel("Mean total time (ticks, log scale)", fontsize=8, color=_SECONDARY_INK)
    _finish(
        figure,
        path,
        TITLES["load_response"],
        [
            "The axis is a log scale, so that all loads fit.",
            "Shading shows the range across seeds.",
        ],
        algorithms,
    )


def _car_movement(stats: Path, building: str, path: Path) -> None:
    sample = stats / "samples" / f"{building}_{_SAMPLE_INPUT}"
    if not sample.exists():
        return
    runs = {folder.name.split("__")[0]: folder for folder in sample.iterdir()}
    algorithms = fixed_order(runs)
    figure, axes = _figure(len(algorithms), 1, 10.0, 1.7 * len(algorithms) + 1.0)
    for row_index, name in enumerate(algorithms):
        with (runs[name] / "positions.csv").open(encoding="utf-8", newline="") as file:
            table = list(csv.reader(file))
        ticks = [int(row[0]) for row in table[1 : _CAR_MOVEMENT_TICKS + 2]]
        axis = axes[row_index][0]
        _panel_label(axis, name)
        for column in range(1, len(table[0])):
            floors = [int(row[column]) for row in table[1 : _CAR_MOVEMENT_TICKS + 2]]
            axis.plot(ticks, floors, color=COLOURS[name], linewidth=1, alpha=0.85)
        axis.set_ylabel("Floor", fontsize=8, color=_SECONDARY_INK)
    axes[-1][0].set_xlabel("Tick", fontsize=8, color=_SECONDARY_INK)
    _finish(
        figure,
        path,
        TITLES["car_movement"],
        [f"One line per car, on the input {building}_{_SAMPLE_INPUT}."],
        [],
    )


def write_charts(stats: Path, out: Path) -> list[Path]:
    rows = _read_aggregates(stats)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for building in dict.fromkeys(row["building"] for row in rows):
        members = [row for row in rows if row["building"] == building]
        for name, draw in (
            ("algorithm_comparison", _algorithm_comparison),
            ("fairness_vs_efficiency", _fairness_vs_efficiency),
            ("load_response", _load_response),
        ):
            target = out / f"{name}_{building}.png"
            draw(members, target)
            written.append(target)
        target = out / f"distributions_{building}.png"
        _distributions(stats, building, target)
        written.append(target)
        target = out / f"car_movement_{building}.png"
        _car_movement(stats, building, target)
        if target.exists():
            written.append(target)
    return written
