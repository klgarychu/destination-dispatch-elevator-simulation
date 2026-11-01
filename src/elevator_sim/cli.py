"""The command line: `python -m elevator_sim run|generate|compare|charts`."""

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path

from elevator_sim.calibration import calibrate
from elevator_sim.config import ConfigError, SimConfig, load_config
from elevator_sim.engine import SimulationStalledError, simulate
from elevator_sim.experiment import express_tasks, file_tasks, run_suite, suite_tasks
from elevator_sim.output import format_summary, summary_data, write_run
from elevator_sim.requests import InputValidationError, load_requests
from elevator_sim.workload import (
    BUILDINGS,
    RATES_FILE,
    SEEDS,
    building_config,
    ensure_inputs,
    generate_requests,
    write_requests,
    write_suite,
)

EXIT_OK = 0
EXIT_INVALID = 2
EXIT_STALLED = 3


def _config_from(args: argparse.Namespace) -> SimConfig:
    config = load_config(args.config) if args.config else SimConfig()
    overrides = {
        name: value
        for name in ("floors", "elevators", "capacity", "algorithm", "behaviour", "max_ticks")
        if (value := getattr(args, name, None)) is not None
    }
    return replace(config, **overrides)


def _run(args: argparse.Namespace) -> int:
    config = _config_from(args)
    result = simulate(load_requests(args.requests, config.floors), config)
    write_run(result, args.out)
    print(format_summary(summary_data(result)))
    return EXIT_OK


def _generate(args: argparse.Namespace) -> int:
    if args.calibrate:
        if args.config:
            buildings = {args.config.stem: load_config(args.config)}
        else:
            buildings = {name: building_config(name) for name in BUILDINGS}
        calibrate(buildings, args.workers, args.out or RATES_FILE, args.algorithm)
    elif args.suite:
        if args.out is None:
            raise ConfigError("generate --suite needs --out")
        print(f"Wrote {write_suite(args.out)} input files to {args.out}")
    else:
        if args.pattern is None or args.rate is None or args.out is None:
            raise ConfigError("generate needs --pattern, --rate and --out, or --suite")
        floors = _config_from(args).floors
        requests = generate_requests(args.pattern, args.rate, args.ticks, args.seed, floors)
        write_requests(args.out, requests)
        print(f"Wrote {len(requests)} requests to {args.out}")
    return EXIT_OK


def _compare(args: argparse.Namespace) -> int:
    if args.suite:
        if args.stage not in ("all", "1"):
            raise ConfigError("Stage 2 arrives in Phase 4")
        ensure_inputs(args.inputs, (SEEDS[0],) if args.quick else SEEDS)
        tasks = (suite_tasks if args.phase == 1 else express_tasks)(args.inputs, args.quick)
    elif args.requests:
        config = load_config(args.config) if args.config else SimConfig()
        building = args.config.stem if args.config else "custom"
        tasks = file_tasks(args.requests, config, building)
    else:
        raise ConfigError("compare needs --suite, or --requests with a file")
    outcome = run_suite(tasks, args.out, args.workers)
    finished = len(tasks) - len(outcome.stalled)
    counts = f"{finished - outcome.reused} run, {outcome.reused} reused"
    print(f"Finished {finished} of {len(tasks)} runs ({counts}). Results are in {args.out}")
    if outcome.stalled:
        print(f"error: {len(outcome.stalled)} runs reached max_ticks", file=sys.stderr)
        return EXIT_STALLED
    return EXIT_OK


def _charts(args: argparse.Namespace) -> int:
    # Imported here because the simulator must run without matplotlib installed.
    from elevator_sim.charts import write_charts

    written = write_charts(args.stats, args.out)
    if written:
        print(f"Wrote {len(written)} charts to {args.out}")
    else:
        print("Wrote no charts: this comparison has no passengers")
    return EXIT_OK


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="elevator_sim")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="run one request file")
    run.add_argument("--requests", type=Path, required=True)
    run.add_argument("--config", type=Path)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--floors", type=int)
    run.add_argument("--elevators", type=int)
    run.add_argument("--capacity", type=int)
    run.add_argument("--algorithm")
    run.add_argument("--behaviour")
    run.add_argument("--max-ticks", dest="max_ticks", type=int)
    run.set_defaults(handler=_run)

    generate = commands.add_parser("generate", help="make simulated request files")
    generate.add_argument("--suite", action="store_true")
    generate.add_argument("--calibrate", action="store_true")
    generate.add_argument("--pattern")
    generate.add_argument("--rate", type=float)
    generate.add_argument("--ticks", type=int, default=1000)
    generate.add_argument("--seed", type=int, default=1)
    generate.add_argument("--config", type=Path)
    generate.add_argument("--out", type=Path)
    generate.add_argument("--workers", type=int, default=8)
    generate.add_argument("--algorithm", default="marginal_insertion")
    generate.set_defaults(handler=_generate)

    compare = commands.add_parser("compare", help="run every configuration")
    compare.add_argument("--suite", action="store_true")
    compare.add_argument("--requests", type=Path)
    compare.add_argument("--config", type=Path)
    compare.add_argument("--stage", default="all")
    compare.add_argument("--phase", type=int, choices=(1, 2), default=2)
    compare.add_argument("--quick", action="store_true")
    compare.add_argument("--inputs", type=Path, default=Path("data/generated"))
    compare.add_argument("--workers", type=int, default=8)
    compare.add_argument("--out", type=Path, required=True)
    compare.set_defaults(handler=_compare)

    charts = commands.add_parser("charts", help="draw charts from saved statistics")
    charts.add_argument("--stats", type=Path, required=True)
    charts.add_argument("--out", type=Path, required=True)
    charts.set_defaults(handler=_charts)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    handler: Callable[[argparse.Namespace], int] = args.handler
    try:
        return handler(args)
    except (ConfigError, InputValidationError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_INVALID
    except SimulationStalledError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_STALLED
