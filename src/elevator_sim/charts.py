"""Static PNG charts from saved statistics. Fixed order, and nothing is ranked or highlighted.

Charts show each case against its own limit, so the fixed-load runs are left out of them. Most show
one line per algorithm, so when several seat behaviours ran they use `min_time`. The fairness chart
shows every behaviour and weight.

The colours pass a colour-blindness check with every pair in play, as scatter charts need. Two of
them have low contrast against the background, so report.md is the table view of every chart.
"""

import csv
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

from elevator_sim.config import ALL_ALGORITHMS, ConfigError
from elevator_sim.metrics import nearest_rank
from elevator_sim.output import RunRecord, read_manifest, read_run_record
from elevator_sim.workload import FIXED, LOADS, PATTERNS, input_name

COLOURS = {
    "round_robin": "#2a78d6",
    "nearest_car": "#eb6834",
    "zone_based": "#1baf7a",
    "eta": "#56b4e9",
    "marginal_insertion": "#b5179e",
    "rush_express": "#7d5a00",
}
MARKERS = {
    "round_robin": "o",
    "nearest_car": "s",
    "zone_based": "^",
    "eta": "D",
    "marginal_insertion": "P",
    "rush_express": "X",
}
SETTING_MARKERS = {
    "strict": "s",
    "min_time": "o",
    "weighted 0.5": "^",
    "weighted 1": "D",
    "weighted 2": "v",
}
TITLES = {
    "algorithm_comparison": "Mean total time per passenger, by algorithm",
    "distributions": "Wait and total time distributions, by algorithm",
    "fairness_vs_efficiency": "Fairness against efficiency, by algorithm",
    "load_response": "Mean total time as load rises, by algorithm",
    "car_movement": "Car movement over the first 200 ticks, by algorithm",
}
FONTS = ["Segoe UI", "DejaVu Sans"]
FIXED_DISTANCE_NOTE = "Total time is wait time plus a fixed distance."
SPREAD_NOTE = "Lines show the range across seeds, which isn't a significance test."

_SURFACE = "#fcfcfb"
_INK = "#0b0b0b"
_SECONDARY_INK = "#52514e"
_GRID = "#e1e0d9"
_AXIS = "#c3c2b7"
_SAMPLE_RUN = ("up_peak", "heavy", 1)
_CAR_MOVEMENT_TICKS = 200
# Room for the longest note, which ends at about 10.9 inches in the wider fallback font. Below this
# a chart of one input loses its notes and legend. The narrowest suite chart held to this is exactly
# 11 inches wide, so suite charts keep their size. The car movement chart isn't held to it, because
# its notes are short and it is 10 inches wide.
_MIN_WIDTH = 11.0
_WHOLE_TICKS = FuncFormatter(lambda value, _: f"{value:,.0f}")


def fixed_order(algorithms: Iterable[str]) -> list[str]:
    present = set(algorithms)
    return [name for name in ALL_ALGORITHMS if name in present]


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
    plt.rcParams["font.family"] = FONTS
    figure, axes = plt.subplots(
        rows, columns, figsize=(width, height), squeeze=False, sharey="row", facecolor=_SURFACE
    )
    for axis in axes.flat:
        _style_axes(axis)
    return figure, axes


def _setting(row: dict[str, str]) -> str:
    weight = row["fairness_weight"]
    return f"{row['behaviour']} {float(weight):g}" if weight else row["behaviour"]


def _finish(
    figure: Figure,
    path: Path,
    title: str,
    notes: Sequence[str],
    algorithms: Sequence[str],
    settings: Sequence[str] = (),
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
            marker=None if settings else MARKERS[name],
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
    if settings:
        shapes = [
            Line2D(
                [],
                [],
                color=_SECONDARY_INK,
                marker=SETTING_MARKERS[name],
                markersize=6,
                linewidth=0,
                label=name,
            )
            for name in settings
        ]
        figure.legend(
            handles=shapes,
            loc="upper left",
            bbox_to_anchor=(0.015, 1 - 0.74 / height),
            ncols=len(shapes),
            frameon=False,
            fontsize=9,
            labelcolor=_SECONDARY_INK,
        )
    figure.tight_layout(rect=(0, 0, 1, 1 - (1.05 if settings else 0.8) / height))
    figure.savefig(path, dpi=150, facecolor=_SURFACE, metadata={"Software": None})
    plt.close(figure)


def _read_aggregates(stats: Path) -> list[dict[str, str]]:
    path = stats / "aggregate_stats.csv"
    if not path.exists():
        raise ConfigError(f"no statistics found at {path}")
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def _panel_label(axes: Axes, text: str) -> None:
    axes.set_title(text, fontsize=9, color=_SECONDARY_INK, loc="left")


def _has_passengers(row: dict[str, str]) -> bool:
    """An input with no passengers has no statistics, which leave these cells blank."""
    return bool(row["total_mean_mean"])


def _no_passengers(axes: Axes) -> None:
    axes.text(
        0.5,
        0.5,
        "no passengers",
        transform=axes.transAxes,
        ha="center",
        va="center",
        fontsize=9,
        color=_SECONDARY_INK,
    )


def _pick(rows: Sequence[dict[str, str]], pattern: str, load: str) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if row["pattern"] == pattern and row["load"] == load and _has_passengers(row)
    ]


def _algorithm_comparison(rows: Sequence[dict[str, str]], path: Path) -> None:
    patterns = _in_order((row["pattern"] for row in rows), list(PATTERNS))
    loads = _in_order((row["load"] for row in rows), list(LOADS))
    algorithms = fixed_order(row["algorithm"] for row in rows)
    width = max(2.6 * len(patterns) + 0.6, _MIN_WIDTH)
    figure, axes = _figure(len(loads), len(patterns), width, 2.0 * len(loads) + 1.0)
    for row_index, load in enumerate(loads):
        for column, pattern in enumerate(patterns):
            axis = axes[row_index][column]
            _panel_label(axis, f"{pattern}, {load}")
            axis.set_xticks([])
            axis.set_xlim(-0.6, len(algorithms) - 0.4)
            picked = _pick(rows, pattern, load)
            if not picked:
                _no_passengers(axis)
            for row in picked:
                name = row["algorithm"]
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
        top = max(
            (
                float(row["total_mean_max"])
                for row in rows
                if row["load"] == load and _has_passengers(row)
            ),
            default=1.0,
        )
        axes[row_index][0].set_ylim(0, top * 1.08)
        axes[row_index][0].set_ylabel("Ticks", fontsize=8, color=_SECONDARY_INK)
    _finish(
        figure,
        path,
        TITLES["algorithm_comparison"],
        [FIXED_DISTANCE_NOTE, SPREAD_NOTE, "Each row shares an axis."],
        algorithms,
    )


def _saved_run(stats: Path, run_id: str) -> RunRecord:
    record = read_run_record(stats, run_id)
    if record is None:
        raise ConfigError(f"can't read run {run_id} in {stats}: run compare again")
    return record


def pooled_times(
    stats: Path, run_ids: Sequence[str], building: str, behaviour: str | None = None
) -> dict[tuple[str, str], dict[str, list[int]]]:
    pooled: dict[tuple[str, str], dict[str, list[int]]] = {}
    for run_id in run_ids:
        record = _saved_run(stats, run_id)
        if record.building != building or record.load_basis == FIXED:
            continue
        if behaviour is not None and record.settings["behaviour"] != behaviour:
            continue
        key = (record.load, record.settings["algorithm"])
        times = pooled.setdefault(key, {"wait": [], "total": []})
        times["wait"].extend(record.waits)
        times["total"].extend(record.totals)
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


def _distributions(
    stats: Path, run_ids: Sequence[str], building: str, path: Path, behaviour: str | None
) -> None:
    pooled = pooled_times(stats, run_ids, building, behaviour)
    loads = _in_order((load for load, _ in pooled), list(LOADS))
    algorithms = fixed_order(name for _, name in pooled)
    figure, axes = _distribution_figure(len(loads))
    for column, load in enumerate(loads):
        for row_index, measure in enumerate(("wait", "total")):
            axis = axes[row_index][column]
            _style_axes(axis)
            _panel_label(axis, f"{measure} time, {load}")
            present = [name for name in algorithms if pooled.get((load, name), {}).get(measure)]
            if not present:
                axis.set_xticks([])
                _no_passengers(axis)
                continue
            drawn = axis.bxp(
                [_box(pooled[(load, name)][measure], name) for name in present],
                positions=[algorithms.index(name) for name in present],
                widths=0.35,
                patch_artist=True,
                showfliers=False,
                medianprops={"color": _INK, "linewidth": 1.2},
                whiskerprops={"color": _AXIS, "linewidth": 1.2},
                showcaps=False,
                boxprops={"linewidth": 0},
            )
            for box, name in zip(drawn["boxes"], present, strict=True):
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
    plt.rcParams["font.family"] = FONTS
    width = max(2.8 * loads + 0.8, _MIN_WIDTH)
    return plt.subplots(
        2, loads, figsize=(width, 6.4), squeeze=False, sharey=True, facecolor=_SURFACE
    )


def _fairness_vs_efficiency(rows: Sequence[dict[str, str]], path: Path) -> None:
    patterns = _in_order((row["pattern"] for row in rows), list(PATTERNS))
    loads = _in_order((row["load"] for row in rows), list(LOADS))
    algorithms = fixed_order(row["algorithm"] for row in rows)
    settings = _in_order((_setting(row) for row in rows), list(SETTING_MARKERS))
    several = len(settings) > 1
    width = max(2.6 * len(patterns) + 0.6, _MIN_WIDTH)
    figure, axes = _figure(len(loads), len(patterns), width, 2.2 * len(loads) + 1.0)
    for row_index, load in enumerate(loads):
        for column, pattern in enumerate(patterns):
            axis = axes[row_index][column]
            _panel_label(axis, f"{pattern}, {load}")
            axis.grid(axis="x", color=_GRID, linewidth=0.8)
            picked = _pick(rows, pattern, load)
            if not picked:
                _no_passengers(axis)
            for row in picked:
                name = row["algorithm"]
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
                    marker=SETTING_MARKERS[_setting(row)] if several else MARKERS[name],
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
        ["Further left is less total time, and lower down is a shorter long wait.", SPREAD_NOTE],
        algorithms,
        settings if several else (),
    )


def _load_response(rows: Sequence[dict[str, str]], path: Path) -> None:
    patterns = _in_order((row["pattern"] for row in rows), list(PATTERNS))
    loads = _in_order((row["load"] for row in rows), list(LOADS))
    algorithms = fixed_order(row["algorithm"] for row in rows)
    figure, axes = _figure(1, len(patterns), max(3.0 * len(patterns) + 0.6, _MIN_WIDTH), 4.4)
    for column, pattern in enumerate(patterns):
        axis = axes[0][column]
        _panel_label(axis, pattern)
        axis.set_yscale("log")
        axis.yaxis.set_major_locator(LogLocator(base=10, subs=(1, 2, 5)))
        axis.yaxis.set_major_formatter(_WHOLE_TICKS)
        axis.yaxis.set_minor_locator(NullLocator())
        if not any(row["pattern"] == pattern and _has_passengers(row) for row in rows):
            _no_passengers(axis)
        for name in algorithms:
            series = {
                row["load"]: row
                for row in rows
                if row["pattern"] == pattern and row["algorithm"] == name and _has_passengers(row)
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


def _car_movement(
    stats: Path, sample_ids: Sequence[str], building: str, path: Path, behaviour: str | None
) -> None:
    runs: dict[str, Path] = {}
    for run_id in sample_ids:
        record = _saved_run(stats, run_id)
        run = (record.pattern, record.load, record.seed)
        if behaviour is not None and record.settings["behaviour"] != behaviour:
            continue
        if record.building == building and run == _SAMPLE_RUN and record.sample_dir:
            runs[record.settings["algorithm"]] = stats / record.sample_dir
    if not runs:
        return
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
        [f"One line per car, on the input {Path(input_name(building, *_SAMPLE_RUN)).stem}."],
        [],
    )


def write_charts(stats: Path, out: Path) -> list[Path]:
    """Draw every chart from the same runs as the statistics, replacing any earlier charts.

    An incomplete comparison is refused, not drawn with gaps. Stalled runs tend to be the hardest
    ones, so a partial chart would flatter the algorithm that stalled.
    """
    rows = [row for row in _read_aggregates(stats) if row["load_basis"] != FIXED]
    manifest = read_manifest(stats)
    if manifest.not_finished:
        count = len(manifest.not_finished)
        names = ", ".join(manifest.not_finished[:5])
        raise ConfigError(
            f"charts need a complete comparison, but runs in {stats} didn't finish ({count} in "
            f"all, including {names}). See report.md"
        )
    run_ids = manifest.runs
    out.mkdir(parents=True, exist_ok=True)
    for name in TITLES:
        for earlier in out.glob(f"{name}_*.png"):
            earlier.unlink()
    if not any(_has_passengers(row) for row in rows):
        return []
    written = []
    behaviour = "min_time" if len({_setting(row) for row in rows}) > 1 else None
    for building in dict.fromkeys(row["building"] for row in rows):
        members = [row for row in rows if row["building"] == building]
        one_line_each = [r for r in members if behaviour is None or r["behaviour"] == behaviour]
        for name, draw, drawn_rows in (
            ("algorithm_comparison", _algorithm_comparison, one_line_each),
            ("fairness_vs_efficiency", _fairness_vs_efficiency, members),
            ("load_response", _load_response, one_line_each),
        ):
            target = out / f"{name}_{building}.png"
            draw(drawn_rows, target)
            written.append(target)
        target = out / f"distributions_{building}.png"
        _distributions(stats, run_ids, building, target, behaviour)
        written.append(target)
        target = out / f"car_movement_{building}.png"
        _car_movement(stats, manifest.samples, building, target, behaviour)
        if target.exists():
            written.append(target)
    return written
