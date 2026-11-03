# CLAUDE.md

@AGENTS.md

Python setup and engineering standards for this project. `pyproject.toml` is the source of truth for versions and tool settings, and the table below copies it.

## Versions

| Tool | Version | Use |
| --- | --- | --- |
| Python | 3.14 or later | Interpreter, with `requires-python = ">=3.14"`. The final results were produced on 3.15.2, which byte-identical reproduction needs (M44) |
| `matplotlib` | 3.11.2 | `charts` extra, imported only by `charts.py` |
| `pytest` | 9.2.0 | Unit, scenario and integration tests |
| `hypothesis` | 6.170.14 | Property tests |
| `ruff` | 0.17.3 | Formatter and linter |
| `mypy` | 2.4.1 | Strict type checking |

The simulator imports only the standard library. Any new package needs the owner's agreement (S3).

## Environment

`python` on this PC is the system Python outside `.venv`, and shell state doesn't persist between tool calls. Call the virtual environment's interpreter by path, every time:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev,charts]"
```

`.gitignore` also covers `__pycache__/`, `*.egg-info/`, `.hypothesis/`, `.mypy_cache/`, `.pytest_cache/` and `.ruff_cache/`.

## Checks

Run these before every commit, and fix what they report:

```powershell
.venv\Scripts\python.exe -m ruff format .
.venv\Scripts\python.exe -m ruff check --fix .
.venv\Scripts\python.exe -m mypy --strict src
.venv\Scripts\python.exe -m pytest
```

During a review, run `ruff format --check .` and `ruff check .` in their place, because a review changes no file.

Run `compare --suite` and calibration in the background, because they can outlast the 10-minute foreground limit.

`compare` reuses a saved run only if its input, settings and code are unchanged, and `compare --suite` stops if an input no longer matches the rates. After recalibrating, run `generate --suite`.

## Code

- **Typed.** Annotate everything, using `X | None` and built-in generics. An interface is an abstract base class when its subclasses share code, as `Elevator` and `Scheduler` do, and a `Protocol` otherwise. Use `@dataclass(frozen=True, slots=True)` for values and `slots=True` for mutable records. A `# type: ignore` needs a comment giving the reason.
- **Validated.** Check types and shapes at every public boundary: config files, CLI options, the Python API and saved JSON, because dataclass annotations check nothing at run time. Refuse an option or setting that doesn't apply with a named error (M12). A configuration derived from another, by an override or a mode, must pass the same validation, so reset the settings that depend on what changed, such as `fairness_weight` with `behaviour`.
- **Reproducible.** Save the complete effective settings, the input's identity and the code's identity with every result, so a run can be repeated from its outputs (spec section 11.3).
- **Deterministic.** The same input gives the same bytes (TST-14). Pass `random.Random(seed)` explicitly, iterate lists or sorted keys rather than sets, and keep wall-clock time out of every file except `suite_log.csv`.
- **Stable files.** Write text with `encoding="utf-8"` and `newline=""`, and give `csv.writer` `lineterminator="\n"`, because its default `\r\n` would change the bytes. Read input CSVs with `encoding="utf-8-sig"` to accept a byte order mark (I4).
- **Layered.** `simulate()` returns data and writes no files. `output.py` writes files, and `cli.py` alone prints and sets exit codes. Failures are named exceptions, which the CLI turns into stderr messages with no traceback.
- **One vocabulary.** Use the spec's glossary and British spelling in names, such as `behaviour`, so code, documents and output columns match.
- **Hot path.** `forecast.py` runs once per car per request. Keep it exact first, and profile with `cProfile` before optimising.
- **Small parts.** Use plain functions and dataclasses, and add an abstraction only for a need the code has today, because the owner has to explain this design in a meeting.

## Tests

- **Layout.** Use `tests/test_<module>.py`, with golden outputs in `tests/golden/`. Put the test ID in the name, such as `test_tst07_reversal_at_furthest_pickup`, so plan section 10 traces to code.
- **Red first.** Write the test, watch it fail, then write the code. Fixtures in spec section 15.2 come before the code they check.
- **Hand-calculated.** Expected values in hand-calculated tests come from working the example through by hand, never from running the code.
- **Public behaviour.** Test through `simulate()`, `Elevator.exchange` and the CLI, so refactors leave tests valid.
- **Property tests.** Use `hypothesis` for TST-06, TST-09 and TST-10. Pin each failure it finds with `@example`, so the case stays in the suite.
- **Reference.** Check an optimised path against a plain reference implementation over varied inputs, as TST-10 checks cached forecasts against `Forecaster.fresh`.
- **Boundaries.** A test of a threshold, cache, guard or rolling window crosses the point where its state changes, and asserts that it did, such as a run long enough for `rush_express` to enter and leave a rush.
- **Meaning.** Test a chart through the data it draws: which runs, their labels and units, and an observed zero against no data. That the PNG exists proves little.
- **Golden outputs.** Update them with `tests/update_golden.py`, only when a phase is meant to change results, and say why in the commit (M8).
- **Tight.** Compare means and standard deviations with `pytest.approx`. Full suites run through `compare`, and only the small suite in TST-17 runs inside `pytest`.

## Git

Commit each finished change the owner asked for to `main`, staging files by name, and leave `.vscode/` and `tmp/` unstaged (M14). Use a subject such as `WP 1.3: add LOOK movement`, and explain why in the body when the reason isn't obvious. Push only when the owner asks, each time (M39).

## Skills

- `mattpocock-skills:tdd`: building a feature or fixing a bug.
- `mattpocock-skills:diagnosing-bugs`: a test failure or run time you can't explain.
- `dataviz`: before writing or changing `charts.py`.
