# Implementation Plan: Elevator Scheduling Simulation

| Item | Detail |
| --- | --- |
| Status | **Complete.** Every gate is decided, and Gate 6 was approved on 2026-11-02 and tagged `phase-6` (section 13). Phase 5 was skipped at Gate 3 (M34). Section 14 records the work since Gate 6 |
| Date | 2026-10-30, last updated 2026-11-03 |
| Design | [spec.md](spec.md). This plan says when things are built. The spec says how they work |
| Decision log | [assumptions_made.md](assumptions_made.md). M1 to M43 come from this plan, its code reviews, its gates and the owner's later requests |
| Approver | The project owner |
| Replaces | The phase table in spec section 18 (M1), which M41 then removed from the spec |

## 1. Overview

The project is built in six phases. Phase 1 is a working MVP, and each later phase adds more variables and configurations until the full design in the spec is reached.

Every phase ends the same way: tests pass, a simulation produces statistics, charts and logs, and a person approves before the next phase starts.

| Phase | Adds | Buildings | Behaviours | Guards | Configurations | Inputs | Runs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1. MVP | Simulator, 5 algorithms, normal cars, all commands | The eight cases in section 4.4 | `min_time` | None | 5 | 800 | 6,000 |
| 2. Express cars | `ExpressElevator`, `rush_express`, five express layouts (M30) | 9 cases, in section 5.3 | `min_time` | None | 6 | 320 | 4,800 |
| 3. Seat behaviours | `strict`, `weighted`, weights, seat reservation | All 3 | All 3 | None | 30 | 240 | 7,200 |
| 4. Guards | `skip_limit`, `wait_expiry`, seat hold, Stage 2 rows 1 to 4 | All 3 | All 3 | All | 30 + 18 | 240 + 180 | 10,440 |
| 5. Assignment rules | Skipped by the owner at Gate 3 (M34) | | | | | | |
| 6. Final | Clean full suite, the eight Phase 1 cases and Phase 2's express layouts again on final settings, README, presentation, handover | All 3 | All 3 | All | 30 + 18 | 240 + 180 | 10,440 rows + 6,000 + 4,800 |

"All 3" means `3car-10floor-6cap`, `3car-60floor-6cap` and `3car-60floor-6cap-overlap` (Gate 2). Run counts follow the spec's method. Phases 4 and 6 include 360 runs that appear in both stages, so 10,440 rows come from 10,080 executions (section 12, PC4). Phases 1 to 3 are not the spec's Stage 1, because Stage 1 needs guards (section 12, PC3).

## 2. Rules for every phase

1. **Stop at every gate.** Finishing a phase doesn't authorise the next one. Only an approval recorded in section 13 does. Ask and wait, even if the next phase looks small (M3).
2. **Run the whole matrix.** Each phase runs every configuration in its row of the table above, not only what's new.
3. **Keep older tests passing.** Every test from earlier phases runs in every later phase.
4. **Don't let results drift.** A configuration that exists in two phases must give identical results on the same input, unless the phase is meant to change it (M8).
5. **Reject what isn't built yet.** A setting from a later phase stops with a validation error and exit code 2. It is never accepted and ignored, because a reader could believe a guard was active when it wasn't (M12).
6. **Never rank.** Reports, charts and phase reviews show statistics in fixed order, with no rank, winner, "best" label or highlight of the lowest value (R-31).
7. **Record assumptions.** Add anything new to `assumptions_made.md`, and list it in the phase review.
8. **Agree any cut.** Dropping scope, seeds or test values needs the approver's agreement (G17).
9. **Don't change the interpreter mid-project.** Stay on Python 3.15.2, because byte-identical results depend on it (C27).
10. **Commit as you go.** Commit each finished piece of work to `main` with a clear message, at least once per work package, so the history shows how the project was built. The whole history is published when the owner pushes, so never commit secrets or anything `.gitignore` keeps local, such as `docs/` and the review files in `project_docs/` (M14, M42).

## 3. What every phase produces

### 3.1 Commands

Each phase finishes by running these inside `.venv`:

```powershell
python -m pytest
python -m ruff format --check .
python -m ruff check .
python -m mypy --strict src
python -m elevator_sim generate --suite --out data/generated
python -m elevator_sim compare --suite --stage all --workers 8 --out results/phaseN
python -m elevator_sim charts --stats results/phaseN --out results/phaseN/charts
```

`--stage all` means every run defined so far. The suite definition in `experiment.py` grows each phase, so no new flags are needed.

### 3.2 Review pack

Each phase has its own folder, so results from different code versions never mix (M7). `.gitignore` keeps `docs/`, every `project_docs/` file except the five core documents, `data/generated/` and every results folder local, and lists by name the files that are published (M40, M42, spec section 14.1). Only the final suite writes directly to `results/`.

```text
results/phaseN/
├── phase_review.md            # the approver's summary
├── report.md                  # summary tables, spec section 14.2
├── simulation_stats.csv       # one row per run
├── aggregate_stats.csv        # one row per configuration, building, pattern and load
├── by_config/<config_id>.csv  # one file per configuration
├── charts/                    # PNGs
├── samples/                   # logs from sample runs
├── runs/<run_id>.json         # saved results, used to resume a suite
├── run_manifest.json          # the runs these files and charts cover (M20)
└── suite_log.csv              # one row per run: run_id, status, seconds
```

- **Logs.** `samples/` holds `positions.csv`, `passengers.csv` and `summary.json` for every configuration on two inputs per building: `up_peak` at heavy load and `lunch` at overload, both seed 1.
- **Timing.** `suite_log.csv` is the only file with wall-clock times. Keep them out of every other file, or byte-identical output (TST-14) will fail.
- **Stable columns.** `simulation_stats.csv` has every column in spec section 14.1 from Phase 1. Columns for features not built yet hold their "off" value, so the format never changes between phases.
- **Stable names.** `config_id` always has four parts, for example `round_robin__min_time__none__none` in Phase 1.

### 3.3 Phase review

`phase_review.md` has these sections:

| Section | Contents |
| --- | --- |
| Delivered | What was planned, what was built, and any difference |
| Tests | Counts from `pytest`, including hypothesis and fixed scenarios, plus `ruff` and `mypy` results |
| Simulation | Inputs, configurations, runs finished and failed, and which runs were `unguarded` |
| Results | Links to charts and tables, in fixed order, with no conclusion on which option is best |
| Regression | How many shared rows were compared with the previous phase, and how many changed |
| Run time | Measured time for this phase, and the projection for the full suite |
| Changes | New assumptions, deviations from the spec, and open questions |
| Version | Git commit hash and Python version |
| Decisions needed | The gate questions for this phase |

### 3.4 Approval gate

The approver reads the review pack and gives one of these decisions, which is recorded in section 13:

| Decision | Meaning |
| --- | --- |
| Approve | Tag the commit `phase-N` and start the next phase |
| Approve with changes | Update this plan and `assumptions_made.md`, then start the next phase |
| Rework | Fix what's listed, re-run the phase, and present it again |
| Stop | End the work here |

An approval covers the next phase only. The gate confirms that a phase is complete and sound. It doesn't choose the best algorithm, which is the owner's separate decision after Phase 6 (C2).

## 4. Phase 1: MVP

**Goal:** a working simulator that runs simulated input files through all five algorithms, with unit tests and full outputs. This phase covers the PDF's core simulator, input and output requirements and its algorithms bonus item. Every passenger is served, but D19's limits on long waits don't apply yet (PC1).

### 4.1 Scope

| In | Out, and the phase it arrives in |
| --- | --- |
| Tick loop, LOOK, capacity, end of run, `max_ticks` | `ExpressElevator`, `[[express]]` settings (Phase 2) |
| `Elevator` base class, `NormalElevator`, factory | `strict`, `weighted`, `fairness_weight` (Phase 3) |
| `min_time` boarding, with no reservation | `boarding/seats.py`, seat reservation (Phase 3) |
| Forecast: `board_tick` and `dropoff_tick`, exact, fast and cached | Guards and seat hold (Phase 4) |
| `round_robin`, `nearest_car`, `zone_based`, `eta`, `marginal_insertion` | Assignment rules, `passes_to_board`, `peak_demand` (Phase 5) |
| `run`, `compare`, `generate`, `charts` | Stage 2 (Phases 4 and 5) |
| Calibration for the eight cases | Final README (Phase 6) |
| Statistics, report, charts, logs | |

MVP boarding is the spec's section 9.1 procedure with nothing flagged and nothing protected:

```text
board(t):
    order = waiting passengers here going this way,
            shortest ride first, ties by request order
    for p in order:
        if no seats are free: stop
        board p, recording board_tick = t
    add 1 to times_left_behind for everyone here going this way who did not board
```

`times_left_behind` is recorded from Phase 1, so the MVP shows how much passengers are skipped when nothing protects them.

### 4.2 Build these seams now

Later phases should add code here without reworking the core:

- Schedulers choose only from `view.eligible(request)`, and cars expose `serves` and `can_serve`, even though every car serves every floor in Phase 1.
- `boarding/behaviours.py` holds each behaviour as a named priority rule, so `board()` gets its order from one place.
- `forecast.py` calls the real `exchange` code. It must not contain a second model of movement or boarding, so later boarding rules reach forecasts automatically.
- `marginal_insertion` calculates its cost through one function, so weights and rules can change it later.

### 4.3 Work packages

Write the hand-calculated fixtures in spec section 15.2 before the code they test.

| WP | Work | Main files | Tests |
| --- | --- | --- | --- |
| 1.1 Setup | Install Python 3.15.2 from python.org. Create `.venv` with `py -3.15 -m venv .venv`. Confirm the commit name and email with the owner (PC11), run `git init -b main`, and commit `.gitignore` first. Add a stub `README.md`, and `pyproject.toml` from the starter in `CLAUDE.md`. It sets `requires-python = ">=3.15"`, the `dev` and `charts` extras, and the versions in spec section 18, which are now in `CLAUDE.md` | `pyproject.toml`, `.gitignore`, `README.md` | `pytest`, `ruff` and `mypy` run on an empty package. `git status` doesn't list `docs/` or `project_docs/` |
| 1.2 Input and settings | `Request`, CSV loader, validation, sorting, `SimConfig`, TOML loading | `requests.py`, `config.py` | TST-03, TST-12 (settings) |
| 1.3 Cars | `Elevator`, `NormalElevator`, factory, LOOK, `exchange`, `move`, `min_time` boarding | `elevators/`, `boarding/behaviours.py` | TST-02, TST-07, TST-08 (`min_time`) |
| 1.4 Engine | Tick loop, `simulate()`, `FleetView`, `round_robin`, statistics, output files | `engine.py`, `schedulers/base.py`, `schedulers/round_robin.py`, `metrics.py`, `output.py` | TST-01, TST-04, TST-05, TST-09, TST-14 |
| 1.5 Algorithms | Forecast first, then `nearest_car`, `zone_based`, `eta`, `marginal_insertion` | `forecast.py`, `schedulers/` | TST-06, TST-10, TST-11 |
| 1.6 Commands and inputs | `run` and `generate`, traffic patterns, calibration, config files, PDF sample | `cli.py`, `workload.py`, `configs/`, `examples/` | TST-15, TST-17 |
| 1.7 Suite and reporting | `compare`, `charts`, parallel runs, resuming, statistics files, report, sample logs, suite log, golden outputs | `experiment.py`, `report.py`, `charts.py`, `tests/golden/` | TST-16, TST-17, TST-18 |
| 1.8 Phase run | Calibrate, check the load levels, run the matrix, write the README draft and review pack | `configs/load_rates.toml`, `README.md` | TST-13 (overload ramp, seats-not-short bound), TST-19 |
| 1.9 Cases | Eight cases named after their buildings, seeds that keep first names, five calibrated rates (M27) | `workload.py`, `configs/` | TST-15, M8 golden files |
| 1.10 Fixed load | The same arrivals on every case, `load_basis`, report sections, charts on the own limit only (M28) | `workload.py`, `experiment.py`, `output.py`, `report.py`, `charts.py` | TST-15, TST-16, TST-17, TST-18 |

The README draft holds how to run the project, what's built so far, and a clear note that results are interim and unguarded. The hours stay a placeholder.

### 4.4 Simulation

| Dimension | Values | Count |
| --- | --- | --- |
| Buildings | `1car-10floor-6cap`, `3car-10floor-6cap`, `3car-35floor-6cap`, `3car-60floor-6cap`, `6car-60floor-6cap`, `9car-60floor-6cap`, `3car-60floor-9cap`, `3car-60floor-12cap`, chosen by the owner (M27) | 8 |
| Patterns | `uniform`, `up_peak`, `down_peak`, `lunch` | 4 |
| Loads | Light, medium, heavy, and overload as the stress load (M4) | 4 |
| Seeds | 1 to 5 | 5 |
| Load bases | Own limit on all eight, and the fixed load on the other seven, which adds 160 inputs (M28) | 2 |
| **Inputs** | | **800** |
| Algorithms | All five, on `min_time` with no guard | 5 |
| **Runs** | 3,200 at own limit and 2,800 at fixed load | **6,000** |

Calibration uses `marginal_insertion` with `min_time` and no guard, because the default guard doesn't exist yet. The rates are then frozen (M6).

All runs are labelled `unguarded`, and `report.md` says so.

### 4.5 Charts

Phase 1 produces all charts in spec section 14.3 except Anti-starvation methods: Algorithm comparison, Distributions, Fairness vs efficiency (one point per algorithm), Load response and Car movement.

### 4.6 Exit criteria

- WP 1.1 to 1.10 are complete, and every test in Phase 1's column of section 10 passes.
- The PDF sample gives the results in spec section 15.2, using `configs/pdf_sample.toml`.
- All 6,000 runs finish, with no `max_ticks` error.
- `compare` produces every file in section 3.2, and `report.md` passes TST-18.
- Overload is past capacity, and heavy traffic produces left-behind passengers, for each building and pattern (spec section 12.4). If not, say so in the review.
- `suite_log.csv` gives a measured run time, including the 100 `9car-60floor-6cap` overload runs, and a projection for the full suite (M9).

### 4.7 Gate 1 questions

1. Do the statistics, charts and logs look right, and are they what you want from every later phase?
2. Is overload really past capacity on every building, or should calibration change before the rates are frozen?
3. Is the projected run time acceptable, or should anything be cut?
4. Do you accept that all MVP results are unguarded and interim (PC1, PC3)?
5. Do you want to push this first version to GitHub (section 12, PC8)? It's optional.

## 5. Phase 2: Express elevators

**Goal, set by the owner at Gate 1 (M30):** show what express cars improve, under what conditions and in what layout, on the reference case `3car-60floor-6cap`, and identify an express algorithm to compare with the other five. Phase 1's results must not change.

### 5.1 Work

| WP | Work | Main files |
| --- | --- | --- |
| 2.1 Express car | `ExpressElevator`, `[[express]]` settings, validation, coverage check (B8), start floor rule (B9), `zone_based` fallback and parking (D27) | `elevators/express.py`, `config.py`, `schedulers/zone_based.py` |
| 2.2 Express algorithm | `rush_express` (M31) | `schedulers/rush_express.py` |
| 2.3 Express suite | Five layouts of the reference case and the 6-car express building, on shared passengers, plus the regression cases. Report minimums and maximums, and calibration under a named algorithm | `workload.py`, `experiment.py`, `report.py`, `calibration.py`, `configs/` |
| 2.4 Calibration and forecasts | Calibrate `6car-60floor-6cap-express` only. The existing rates must not change. Measure each layout's limit into `results/phase2/`, not the frozen rates. Add express cars to the forecast tests | `configs/load_rates.toml`, `tests/test_forecast.py` |
| 2.5 Phase run | Run the matrix, update the README draft, write the review pack and presentation | |

The earlier WP 2.0, which narrowed the suite, is replaced by `--phase`, because the owner decided at Gate 1 that the eight cases stay for Phase 6.

### 5.2 Tests

- TST-12 in full: skipped floors, eligibility, coverage failure, start floor, settings validation.
- TST-09 and TST-10 on buildings that include express cars.
- TST-11: `round_robin` skip, `zone_based` fallback and parking, as defined in spec section 8.3, and `rush_express`.
- TST-06 on `rush_express`, which keeps a history of requests.
- TST-15 for the express cases.

### 5.3 Simulation

| Cases | Load | Inputs | Runs, with 6 algorithms |
| --- | --- | --- | --- |
| `3car-10floor-6cap`, `3car-60floor-6cap`, `6car-60floor-6cap`, `6car-60floor-6cap-express` | Own limit | 320 | 1,920 |
| The five layouts of `3car-60floor-6cap` | Its passengers | Shared | 2,400 |
| `6car-60floor-6cap-express` | The passengers of `6car-60floor-6cap` | Shared | 480 |
| **Total** | | **320** | **4,800** |

All are `unguarded`.

### 5.4 Exit criteria

- Every test in Phase 2's column of section 10 passes.
- All 4,800 runs finish.
- The 1,200 rows that repeat Phase 1 match it exactly, and a full re-run of Phase 1 on the final code gives byte-identical statistics and sample logs.
- `results/phase1/` is unchanged.
- Overload is past capacity on `6car-60floor-6cap-express`.

### 5.5 Gate 2 questions

1. Do the express results look credible, and do they answer the aim?
2. Should `rush_express` join later phases?
3. Should later phases use `3car-60floor-6cap` as their reference, in place of `6car-60floor-6cap` and its express building?
4. Should the remaining code review items wait again?
5. Is the updated run time projection still acceptable?
6. Do you approve Phase 2?

## 6. Phase 3: Seat behaviours

**Goal, set by the owner at Gate 2 (M32):** measure and improve fairness against overall total time, comparing the seat behaviours under a fixed case for each algorithm from Phases 1 and 2. A person reviews and approves the results before Phase 4.

### 6.1 Work

| WP | Work | Main files |
| --- | --- | --- |
| 3.0 Wording | Stop calling the seed range noise (Gate 2, code review item 15) | `report.py`, `charts.py` |
| 3.1 Behaviours | Seat reservation (spec section 9.3, D25), `strict` with earlier passengers protected (D11) and a blocked passenger stopping boarding (D28), `weighted` with `fairness_weight` and `--weight` (D14), weighted delays in `marginal_insertion` and `rush_express`, and a hand-worked `weighted` case | `boarding/`, `elevators/base.py`, `config.py`, `cli.py`, `schedulers/marginal_insertion.py`, `tests/` |
| 3.2 Suite | Every seat setting on every algorithm, the report in a fixed order, and the fairness chart | `experiment.py`, `report.py`, `charts.py` |
| 3.3 Phase run | Run the matrix, update the README draft, write the review pack and presentation | |

### 6.2 Tests

- TST-08 for all three behaviours.
- TST-09, TST-10 and TST-14 under all behaviours.
- TST-11 for `marginal_insertion` with weighted delays.
- TST-13: seat starvation under `strict` with one car, and the `strict` bound in spec section 9.6.
- `weighted` at weight 0 gives the same results as `min_time` (spec section 9.2).

### 6.3 Simulation

6 algorithms × 5 behaviour settings (`strict`, `min_time`, `weighted` at 0.5, 1 and 2) × 240 inputs = 7,200 runs. The fixed case is `3car-60floor-6cap`. `3car-10floor-6cap` and `3car-60floor-6cap-overlap` also run, the latter on the reference passengers.

`min_time` and `weighted` runs are still `unguarded`. `strict` isn't, because it meets D10 by itself (D24).

### 6.4 Exit criteria

- Every test in Phase 3's column of section 10 passes.
- All 7,200 runs finish.
- The 1,440 `min_time` rows match Phase 2 exactly, and `results/phase1/` and `results/phase2/` are unchanged.
- The Fairness vs efficiency chart shows every configuration and weight.

### 6.5 Gate 3 questions

1. Do behaviours differ where seats run short, and match closely in light traffic, as spec section 9.2 expects?
2. Do you accept the two statistic definitions proposed for Phase 4 (section 7.2)?
3. Do the fairness results look right, and which measure of fairness should Phase 4 aim at?
4. Do you approve Phase 3?

## 7. Phase 4: Guards

**Goal:** make "no passenger waits forever" real, complete the spec's Stage 1, and test the boarding methods in Stage 2. Following Gate 3, the results aim at the longest wait and `times_left_behind`, with average total time as the cost (M34).

### 7.1 Work

| WP | Work | Main files |
| --- | --- | --- |
| 4.1 Guards | `skip_limit`, `wait_expiry`, `none`, and flag re-evaluation at each exchange | `boarding/guards.py` |
| 4.2 Seat hold | Flagged passengers board first, and become protected in the seat reservation check | `boarding/guards.py`, `boarding/seats.py` |
| 4.3 Settings | `--guard`, `skip_limit`, `wait_limit` in ticks or round trips, `seat_hold`. `strict` ignores guards and records `none` (D24) | `config.py`, `cli.py` |
| 4.4 Forecast | Copy guard state into forecasts, so that they stay exact | `forecast.py` |
| 4.5 New default | Change the default to `skip_limit` with S = 2 and seat hold on (D18). `none` stays available and labelled `unguarded` | `config.py` |
| 4.6 Statistics and charts | `flagged_passengers`, `held_seat_ticks`, `share_above_wait_limit`, the Anti-starvation methods chart. Seat hold made forecasting runs up to 6 times slower, so the seat check was sped up without changing a result (M35) | `metrics.py`, `charts.py`, `boarding/seats.py` |
| 4.7 Stage 2 | Stage 2 rows 1 to 4, and the handling of overlapping runs (PC4, M36). Rows 5 to 10 are skipped with Phase 5 (M34) | `experiment.py`, `report.py` |
| 4.8 Calibration check | Calibrate again with the default guard and write the rates to `results/phase4/calibration_check.toml`. Don't change `load_rates.toml` (M6) | `workload.py` |
| 4.9 Phase run | Run the matrix, update the README draft, write the review pack | |

### 7.2 Spec gap to close first

Spec section 14.1 lists two columns without defining them. The proposed definitions are below (M13), and Gate 3 asks the approver to accept them:

- `held_seat_ticks`: seats kept empty for a flagged passenger, summed over the ticks until each seat is used.
- `share_above_wait_limit`: the share of passengers whose wait is above W, using the run's `wait_limit`, or 2 RT if it has none.

### 7.3 Tests

- Unit tests for each guard: when it flags, how flags are re-evaluated, and how flagged passengers board.
- TST-13: seat starvation with seat hold on one car, same-floor starvation, and the bounds in spec section 9.6.
- TST-09, TST-10 and TST-14 under each guard.
- TST-16 for Stage 2 rows, and TST-17 for the new default and flags.

### 7.4 Simulation

| Part | Configurations | Inputs | Runs |
| --- | --- | --- | --- |
| Stage 1 with the default guard | 30 | 240 | 7,200 |
| Stage 2 rows 1 to 4, on `min_time` and `weighted` at 1 | 18 | 180 | 3,240 |
| **Total** | | | **10,440 rows, 10,080 executions** |

Stage 2 uses `marginal_insertion` only, at medium, heavy and overload load.

### 7.5 Exit criteria

- Every test in Phase 4's column of section 10 passes.
- All 10,440 rows finish, with no `max_ticks` error.
- The 1,440 `strict` rows match Phase 3, and the 360 no-guard rows match Phase 3, comparing every column except `stage`.
- Wait limits actually trigger on the 60-floor buildings (spec section 13.3, C19).
- The calibration check shows the gap between frozen and guarded rates.

### 7.6 Gate 4 questions

1. Do guards reduce the worst waits, and at what cost to mean total time?
2. Should the frozen load rates stay, given the calibration check? Changing them would make Phase 1 to 3 results incomparable.
3. Is the run time still acceptable for the final suite?
4. Do you approve Phase 4, so that Phase 6 can start? Phase 5 is skipped (M34)

## 8. Phase 5: Assignment rules

**Skipped by the owner at Gate 3 (M34).** Nothing in this section is built. It stays as a record of what was planned.

**Goal:** finish the anti-starvation scope with the rules that change how `marginal_insertion` chooses a car.

### 8.1 Work

| WP | Work | Main files |
| --- | --- | --- |
| 5.1 Forecast outputs | `passes_to_board` and `peak_demand` | `forecast.py` |
| 5.2 Filters | `predicted_wait_limit`, `round_trip_cap`, `seat_headroom`, and fallback with `fallback_count` (D19) | `schedulers/assignment_rules.py` |
| 5.3 Cost rules | `convex_cost`, `lowest_worst_wait`, and its tie-break order | `schedulers/assignment_rules.py` |
| 5.4 Settings | `assignment_rule`, `rule_value`. Using a rule with any other algorithm is a configuration error | `config.py` |
| 5.5 Stage 2 | Stage 2 rows 5 to 10, and the rule results in the Anti-starvation methods chart | `experiment.py`, `charts.py` |
| 5.6 Phase run | Run the matrix, update the README draft, write the review pack | |

### 8.2 Tests

- TST-11 for each rule in a hand-built case.
- Each filter rejects only when the car would newly break the limit, and a rejected fleet falls back to the lowest-cost car and adds to `fallback_count`.
- TST-10 for `passes_to_board` and `peak_demand`.
- TST-06 with rules active.
- TST-13: seat starvation with several cars, checking whether rules steer the flood away.
- A rule set with any other algorithm exits with code 2.

### 8.3 Simulation

12 settings × 2 base behaviours × 180 inputs = 4,320 runs, on `marginal_insertion` only.

### 8.4 Exit criteria

- Every test in Phase 5's column of section 10 passes.
- All 4,320 runs finish.
- Golden outputs are unchanged. This phase shares no configuration with earlier phases, so they are the regression check here.
- `fallback_count` is reported for each filter.

### 8.5 Gate 5 questions

1. Are all anti-starvation methods tested in a way you can compare from the charts?
2. Does anything need to change before the final suite and README?

## 9. Phase 6: Final suite and README

**Goal:** reproduce everything from clean code and finish the deliverables.

### 9.1 Work

| WP | Work |
| --- | --- |
| 6.0 Ad hoc runs | `compare --requests` runs every Stage 1 configuration, a `--behaviour` override replaces the file's weight, and `--guard` runs the earlier suites on the final settings (M38) |
| 6.1 Final suite | Run `compare --suite --stage all --out results`, then `charts --stats results --out results/charts`. Run the eight Phase 1 cases again with `compare --suite --phase 1 --guard skip_limit --out results/cases`, and Phase 2's express cases with `--phase 2 --guard skip_limit --out results/express`, so the final presentation uses final settings throughout (M38) |
| 6.2 Reproduction check | Compare final rows with Phase 4. All 10,440 must match, except `stage` where the run appears in both stages |
| 6.3 README | Everything listed under "README contents" in spec section 18, with the hours as a placeholder (R4) |
| 6.4 Assumptions | Carry `assumptions_made.md` into the README (R6), including M-entries that affect results, such as frozen load rates |
| 6.5 Final review | Check spec section 15.3, and list every requirement as met or as a known limit in spec section 16 |

### 9.2 Exit criteria

- Spec section 15.3 is met in full.
- `git ls-files` lists nothing from `docs/` or `project_docs/` (C26), no `results/phase*` files, and neither `AGENTS.md` nor `CLAUDE.md`.
- The README contains no conclusion on which option is best. That's written by the owner (C2).

### 9.3 Gate 6 questions

1. Is the project ready to hand over?
2. Are any known limits unacceptable for submission?

After Gate 6, the owner's actions in spec section 17 remain: check the company's AI rules, supply the hours, write the conclusion, and create the public repo and push.

## 10. Test plan by phase

Every test reruns in every later phase. A blank cell means no new work beyond that rerun.

| Test | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 |
| --- | --- | --- | --- | --- | --- |
| TST-01 PDF sample | Full | | | | |
| TST-02 Tick order | Full | | | | |
| TST-03 Invalid input | Full | | | | |
| TST-04 Position log | Full | | | | |
| TST-05 Statistics | Full | | | Guard columns | `fallback_count` |
| TST-06 No peeking | All 5 algorithms | | | | With rules |
| TST-07 LOOK scenarios | Full | | | | |
| TST-08 Seat shortage | `min_time` | | `strict`, `weighted` | | |
| TST-09 Random-input rules | Normal cars | Express cars | All behaviours | Each guard | Each rule |
| TST-10 Forecast accuracy | Normal cars | Express cars | All behaviours | Each guard | New outputs |
| TST-11 Expected car | All 5 algorithms | Skip, fallback, parking | Weighted delays | | Each rule |
| TST-12 Cars and settings | Settings, start floor | Full | | | |
| TST-13 Starvation scenarios | Overload ramp, seats-not-short bound | | Seat starvation, `strict` bound | Same-floor, seat hold, guard bounds | Several cars |
| TST-14 Determinism | Full | Express cars | All behaviours | Each guard | Each rule |
| TST-15 Generator | All eight cases, fixed load | `6car-60floor-6cap-express` | | | |
| TST-16 Separate statistics | Full | | | Stage 2 rows | Stage 2 rows |
| TST-17 Commands | Full | `[[express]]` | `--weight` | `--guard`, new default | `assignment_rule` |
| TST-18 No ranking | Full | | | New chart | |
| TST-19 `ruff`, `mypy --strict` | Every phase | Every phase | Every phase | Every phase | Every phase |
| Golden outputs (M8) | New | Extend | Extend | Extend | Extend |
| Later settings rejected (M12) | New | Update | Update | Update | Remove |

Golden outputs are stored in `tests/golden/`: `passengers.csv` for short inputs, one per building and configuration kind. They catch drift on every test run, without running a suite.

## 11. Requirement coverage

| Phase | Requirements completed | Requirements started |
| --- | --- | --- |
| 1 | R-02 to R-23, R-26, R-30 to R-32 | R-01 (all served, not yet protected), R-27 (one behaviour), R-29 (800 inputs), R-33, R-36 |
| 2 | R-24 | |
| 3 | R-25, R-27 | |
| 4 | R-01 | R-28 (guards and seat hold) |
| 5 | Skipped (M34). R-28's assignment rules become a known limit | |
| 6 | R-29, R-33, R-36, R-35 except the hours | |
| Owner | The hours in R-35, supplied by the owner (M39) | R-34: pushed to the private repo at the owner's request (M39). It is met when the owner makes the repo public |

Spec section 5 gives each requirement's current status, and spec section 16.5 the rules the code doesn't meet yet.

## 12. Areas of concern

Each "What remains" starts with **Resolved** or **Open**. Resolved concerns keep their first text as a record.

| ID | Concern | What this plan does | What remains |
| --- | --- | --- | --- |
| PC1 | **The MVP conflicts with D18 and D10.** D18 says a no-guard run can never be a default, and D10 says no passenger may wait forever. The MVP has only unguarded `min_time`, as you directed | Allowed as a temporary exception until Phase 4 (M5). All such runs are labelled `unguarded` | **Resolved in Phase 4,** which added the guards and made `skip_limit` the default. Every final run has a guard except Stage 2's control and `strict`, which needs none. First text: **Until Phase 4, D10's protection isn't met.** Every passenger is still served, because inputs are finite, but a long ride can be skipped repeatedly. The spec's default of `run` isn't met until Phase 4 |
| PC2 | **G15 can't be followed in Phase 1.** It calibrates with the default guard, which doesn't exist yet | Calibrate without a guard, and freeze the rates so inputs stay identical across phases (M6). Phase 4 reports the gap | **Resolved at Gate 4:** the frozen rates stay, and the README and presentation say heavy means 90% of the limit without a guard. First text: if the gap is large, Gate 4 chooses between keeping the frozen rates and recalibrating. Recalibrating changes the inputs, so earlier phases would no longer be comparable |
| PC3 | **Phases 1 to 3 aren't the spec's Stage 1.** Stage 1 runs `min_time` and `weighted` with the default guard | Those phases are labelled interim | **Resolved:** the README and the final presentation quote Phase 6 results only (M38). Don't quote earlier phases' results in them |
| PC4 | **The spec counts 360 runs twice.** Stage 2 row 2 at S = 2 is the same configuration as Stage 1's `marginal_insertion` on `min_time` and `weighted` at 1, on the same 180 inputs. Because `run_id` comes from the configuration and input, they collide | Run them once, and write a row for each stage (M11). This kept the designed 13,560 rows from 13,200 executions. After M34 it is 10,440 rows from 10,080 runs (spec section 13.1) | **Resolved,** as built in Phase 4 (M36). `simulation_stats.csv` holds two rows with one `run_id`, separated by `stage` |
| PC5 | **Run time is still unmeasured, and phases multiply it.** All phases together were planned as 53,520 runs, before Gates 1 to 3 changed the phases | Phase 1 measures run time on real overload runs, and every gate reviews the projection (M9) | **Resolved:** every gate accepted the run time, and the final 20,880 runs took about 71 minutes (spec section 13.5). Any cut would still need the approver's agreement |
| PC6 | **"Stress load" isn't a term in the spec** | Read as the overload level at 120% of saturation, plus the TST-13 overload ramp (M4) | **Resolved at Gate 0:** it stands as written |
| PC7 | **Two gaps in the spec.** Two statistic columns have no definition, and there's no worked `weighted` example | Definitions proposed in section 7.2 (M13). The example is in WP 3.1 | **Resolved at Gate 3,** which accepted the definitions |
| PC8 | **Pushing early changes what the public sees.** R1 planned the push for the end | Allowed after any approved gate (M10). The README must state what's missing at that point | **Resolved by M39:** the agent pushed the complete project once, at the owner's request. The checks still apply to any later push: `git ls-files` shows nothing `.gitignore` keeps local, and `git push -u origin main --tags` sends the tags too. Pushed history stays public |
| PC9 | **Python 3.15 isn't installed.** `python` on this PC is 3.12.10, and `py` lists only 3.11 and 3.12 (C24) | WP 1.1 installs it. Always use `.venv` | **Resolved in WP 1.1,** which installed 3.15.2 |
| PC10 | **This plan's folders and checks go beyond the spec.** Phase folders, golden outputs, phase comparisons and `suite_log.csv` support your gate and logging requirements. They are not product features | Kept small, and none is a simulation setting | **Resolved at Gate 0:** they stand as written |
| PC11 | **Commit details become public.** Every commit stores the author's name and email, the time and the message. This PC's Git identity uses a personal email address, and commits made with an AI assistant carry a co-author line | WP 1.1 confirms the name and email before the first commit (M14) | **Resolved at Gate 6:** the history is published as it is, with the author email `klgarychu@gmail.com` on every commit (M39). **Open:** the owner checks the company's rules on AI use, because the co-author line is public evidence of it (C25) |
| PC12 | **The spec's calibration stopped below saturation.** It counted passengers in transit, so most pairs at the overload level had no growing queue. Found in Phase 1 | **Resolved at Gate 1.** The owner chose a backlog-growth test (G15). The rates rose on all 8 pairs, and Phase 1 was re-run. The forecast fix (PC13) then raised them again, by the owner's decision, in `1b74e23` | **Resolved.** Rates are now frozen (M6). Earlier runs are kept in `results/phase1_first_run/` and `results/phase1_before_p1_fixes/` for comparison only |
| PC13 | **`eta` and `marginal_insertion` differed at light load, against C14.** On `tall lunch` light, mean total was 43.1 against 57.2. Found in Phase 1 | **Resolved: this was a bug, not a real effect as first reported.** Cached forecasts kept delivered passengers, so `marginal_insertion` under-costed cars that had finished trips (code review item 1). Fixed in `forecast.py`, and TST-10 and TST-11 now reach the stale case | **Resolved,** except that the `tall uniform` gap below wasn't investigated. On the re-run, `tall lunch` light is 42.3 against 41.2. `tall uniform` light still differs, at 44.6 against 33.1, with `eta` varying widely across seeds, and that isn't investigated. How the README describes the target (C13) follows the final figures |
| PC14 | **Charts of one pattern are too narrow.** A chart's width follows its number of patterns, so a chart from `compare --requests` has its title, notes and legend cut off, and only 3 of the 5 algorithm names show. Found in Phase 1, while checking code review item 5 | **Resolved in `c1a205b`.** Charts with long notes have a minimum width of 11 inches, measured against the wider fallback font | **Resolved.** Suite charts are byte-identical |
| PC15 | **Input errors from a worker lose their text.** `InputValidationError` doesn't survive the move between processes, so with 2 or more workers, and the default was then 12, `compare` on a bad file prints its error one letter per line. The exit code is still 2. Found in Phase 1, while checking code review item 6 | **Resolved in `04d1b9d`.** The error now keeps its problem list between processes | **Resolved.** None |
| PC16 | **Which cases later phases run.** The eight cases and the fixed load were added for Phase 1 (M27, M28) | **Resolved by the owner:** they are for Phase 1 only. `--phase` keeps each phase's suite, which replaced WP 2.0 (section 5.1), so "All 3" and the run counts for Phases 2 to 6 hold | **Resolved.** Taking all eight forward would have tripled those phases' 34,320 runs. Phase 6 re-ran them once as a case study (M38) |
| PC17 | **Phase 1 suggests two limits on Phase 4.** Both are estimates from unguarded runs under `marginal_insertion`. At overload, one car and direction has more passengers past 2 round trips than it has seats for 64% to 93% of the time any such passenger is waiting, so "boards on the next pass" (spec section 9.6) can't hold there. At medium load, at most 0.02% of the 10-floor and earlier 6-car, capacity-10 passengers are left behind twice, so Stage 2's 1,080 medium-load guard runs may show almost no effect | Recorded in `results/phase1/study/`. Nothing changed: the spec already says flagged passengers then board in order, and Stage 2 still includes medium | **Resolved.** Stage 2 kept medium. Phase 4 found the guard almost never acts there on `marginal_insertion`, as predicted (`results/phase4/phase_review.md`). First text: Phase 4 should check both with guards on. The owner can drop medium from Stage 2's guard rows at Gate 3 or Gate 4 |
| PC18 | **Spec section 9.2 says behaviours differ only when seats run short, but WP 3.1 goes further.** `weighted` also multiplies delays in `marginal_insertion`, so it can change car choice when seats aren't short | Recorded. Nothing changed | **Resolved at Gate 3,** whose first question allowed for this |
| PC19 | **Load levels aren't equally far from the limit on every building.** Calibration's tolerance is one fleet's seats, an absolute number, which was 1% to 2% of the arrivals in its test window on `3car-10floor-6cap` and 5% to 12% on the 60-floor cases measured then. At 90% of the rate, over 10 seeds on `marginal_insertion`, the backlog was flat on `3car-10floor-6cap` and grew by 5 to 9 passengers on `3car-60floor-6cap`. The tolerance now reaches 54 on `9car-60floor-6cap`. So heavy sits closer to the limit on 60 floors | Recorded in the review pack. The rates are unchanged, and overload is past capacity on all 40 pairs, by at least 1.17 times a fleet's seats | **Resolved at Gate 1:** the rates stay. First text: the owner decides at Gate 1. Keeping the rates only needs care when comparing heavy load across buildings at their own limits, and the fixed load doesn't depend on them for other cases. A tolerance in proportion to arrivals would change every rate and result |
| PC20 | **The presentation quotes interim results.** PC3 says to quote Phase 6 results in a presentation, and the owner has asked for one now | Every slide carries an interim label, and the last slide says what isn't built yet | **Resolved:** the final presentation uses Phase 6 results throughout, and is published (M38, M40). First text: the owner decides whether to present these numbers or wait for Phase 6, which adds guards and will change them |
| PC21 | **Express gains here leave out the main real-world one.** Stops take no time (Q36), so a car saves nothing by skipping a floor. In a real building, fewer stops are the main reason to run express cars | Every express result here comes from separating traffic, and the presentation says so | **Open, as a known limit** accepted at Gate 6. Treat these results as a lower bound on what express cars do for ride time, and don't compare them with published figures |
| PC22 | **Later phases' buildings and algorithms.** The plan's later phases used `6car-60floor-6cap` and had no `rush_express` | **Resolved at Gate 2:** `rush_express` joins them, and they use `3car-10floor-6cap`, `3car-60floor-6cap` and `3car-60floor-6cap-overlap` | **Resolved.** Stage 1 grows from 25 to 30 configurations |
| PC23 | **Skipping Phase 5 leaves part of R-28 unbuilt.** R-28 asks for every method in D17, and the five assignment rules are in D17 | The owner skipped Phase 5 at Gate 3 (M34). `assignment_rule` stays refused, Stage 2 is rows 1 to 4, and the Anti-starvation methods chart shows guards and seat hold only | **Open, as a known limit** accepted at Gate 6. The README and spec section 16 list the assignment rules as a known limit. The spec's 14,760-row suite becomes 10,440 rows |
| PC24 | **The documents fell behind the decisions.** After Gate 6 a review found superseded rules still reading as current in the spec, the plan and the agent files, and two agreed rules the code doesn't meet | Section 14 reconciles the documents (M41). The spec marks every rule the code doesn't meet as Open (spec section 16.5) | **Open:** whether to fix the six Open rules, C29 to C34, is the owner's decision. Some fixes change code behind published files |

## 13. Approval log

Record each decision here. A phase can't start until the gate before it says Approve or Approve with changes.

| Gate | Unlocks | Approver | Date | Decision | Conditions |
| --- | --- | --- | --- | --- | --- |
| 0. This plan | Phase 1 | Project owner | 2026-10-30 | Approve | Owner said to start Phase 1. PC6 (stress load) and PC10 (extra checks) stand as written, and PC11 (commit email) is still open: it must be settled before any push |
| 1. MVP | Phase 2 | Project owner | 2026-11-01 | Approve | Approved at commit `698dfab`, tagged `phase-1`. Conditions: `report.md` gains min wait, min total and max total from Phase 2 on. Suites use 8 workers. Results stay interim and are presented with that label. Pushing waits until the end. The remaining code review items wait until after Phase 2. The rates stay as they are (PC19). Phase 2 also runs express cars on the same passengers as the building without them. Phase 6 re-runs the eight cases once on the final settings, so the code stays. The owner also reset Phase 2's aim, and said Phase 1's results must not change (M30) |
| 2. Express cars | Phase 3 | Project owner | 2026-11-02 | Approve | Approved at commit `d60ef92`, tagged `phase-2`. Conditions: `rush_express` joins later phases. Later phases use `3car-10floor-6cap`, `3car-60floor-6cap` and `3car-60floor-6cap-overlap`, in place of the 6-car buildings. The 'noise' wording is fixed before Phase 3, and the other open code review items wait again. The run time is accepted. The owner set Phase 3's target: measure and improve fairness against overall total time, comparing seat behaviours under a fixed case for each algorithm, with human review before Phase 4 (M32) |
| 3. Seat behaviours | Phase 4 | Project owner | 2026-11-02 | Approve with changes | Approved at commit `7e025b7`, tagged `phase-3`. Yes to all four questions as recommended: behaviours differ where seats run short and match in light traffic; the M13 definitions are accepted; Phase 4 aims at the longest wait and `times_left_behind`, with average total time as the cost. Changes: the owner skips Phase 5, so Gate 4 unlocks Phase 6, the final presentation, and the owner then publishes to a real GitHub repo (M34). Phase 4 needs human review and approval |
| 4. Guards | Phase 6 (Phase 5 skipped, M34) | Project owner | 2026-11-02 | Approve | Approved at commit `9df8235`, tagged `phase-4`. Yes to all six questions as recommended: the default guard stays `skip_limit` at S = 2 with seat hold; the frozen load rates stay, and the README and presentation say heavy means 90% of the limit without a guard; the run time is accepted; Phase 6 is the final suite, the eight Phase 1 cases on the default guard, the README except the hours and conclusion, and a final presentation on the final results; the owner checks the company's rules on AI assistance before publishing. The owner also asked whether the program runs a user's own configuration ad hoc |
| 5. Assignment rules | Skipped | Project owner | 2026-11-02 | Skipped | The owner skips Phase 5 (M34) |
| 6. Final | Owner's handover steps | Project owner | 2026-11-02 | Approve | Approved at commit `4622d05`, tagged `phase-6`. Final runs at commit `c7712cc`, and the later commits add the published charts, reports, README, and the owner's conclusion and time spent. Yes to all four questions as recommended: the project is ready to hand over; the known limits are accepted, as the README states them; the presentation stays local, which the owner later reversed (M40, section 14); Phase 6 is approved. Before the gate, the owner had the agent push `main` with its full history and the tags `phase-1` to `phase-4` to the private repo `klgarychu/destination-dispatch-elevator-simulation`. The owner makes it public after their own check. That settles PC11: the history is published as it is, with the author email `klgarychu@gmail.com` on every commit (M39) |

## 14. After Gate 6

Every gate is decided, so no phase is unlocked. Work now comes only from the owner's requests, each recorded in `assumptions_made.md` before or as it is done.

| Date | Work | Decision | Commit |
| --- | --- | --- | --- |
| 2026-11-02 | Publish the PDF sample run, each final folder's statistics, per-configuration files, sample logs and suite log, and the final presentation | M40 | `6203861` |
| 2026-11-02 | Link the final presentation from the top of the README | Owner's request | `0393f52` |
| 2026-11-03 | Reconcile `intent.md`, the spec, this plan, the research report, the decision log, `AGENTS.md` and `CLAUDE.md` with the decisions and the code, after a review of them. The spec marks six agreed rules the code doesn't meet as Open (spec section 16.5). No code, test or result changed | M41 | `baffcd3` |
| 2026-11-03 | Publish `AGENTS.md`, `CLAUDE.md` and the five core documents in `project_docs/`, committed locally for the owner to check before pushing | M42 | `baffcd3` |
| 2026-11-03 | Rename `sdlc/` to `project_docs/` | M43 | The commit that adds this row |

The open items are the owner's: push the rename commit (M43), make the repo public (R-34), check the company's rules on AI use (C25), and decide whether to fix C29 to C34 (PC24).
