# Elevator scheduling simulation

A discrete-time Python simulation of a destination-dispatch elevator system. A passenger gives their origin and destination when they make a request, and the system immediately assigns them to one car. The project compares dispatch algorithms under simulated traffic.

> **Status: first version (MVP).** This version has five algorithms, normal elevators and one seat behaviour (`min_time`). Express elevators, other seat behaviours and protection against long waits are not built yet, so **all results so far are interim and unguarded**: every passenger is served, but a long ride can be skipped repeatedly.

The software presents statistics and charts, and never ranks results or names a winner. A person reads them and decides.

## Requirements

**Python 3.15 or later.** The simulator uses only the standard library. Charts need `matplotlib`, and the tests need `pytest`, `hypothesis`, `ruff` and `mypy`.

## Install

```powershell
py -3.15 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev,charts]"
```

## Run

Run the commands below from the project root, using the virtual environment's Python.

The PDF sample reaches floor 51, so it needs its own config. With the default 10 floors it gives a validation error.

```powershell
python -m elevator_sim run --requests examples/pdf_sample.csv --config configs/pdf_sample.toml --out results/sample
```

`run` writes `positions.csv` (every car's floor at every tick), `passengers.csv` and `summary.json`, and prints the summary. It also accepts `--floors`, `--elevators`, `--capacity`, `--algorithm`, `--behaviour` and `--max-ticks`.

Simulated inputs:

```powershell
python -m elevator_sim generate --suite --out data/generated
python -m elevator_sim generate --pattern up_peak --rate 0.5 --ticks 1000 --seed 1 --config configs/3car-10floor-6cap.toml --out data/one.csv
```

Compare algorithms on one file, or run the whole suite:

```powershell
python -m elevator_sim compare --requests data/one.csv --config configs/3car-10floor-6cap.toml --out results/one
python -m elevator_sim compare --suite --stage all --workers 12 --out results/phase1
python -m elevator_sim charts --stats results/phase1 --out results/phase1/charts
```

The suite has eight cases, each named after its building, such as `3car-60floor-6cap`. Every case runs four loads set from its own measured limit, which shows how it behaves near that limit. Every case also runs the same arrivals as `3car-60floor-6cap`, so a difference between cases comes from the building and not its traffic.

Exit codes are 0 for success, 2 for invalid input or settings, and 3 for reaching `max_ticks`.

## Algorithms

Every algorithm only chooses a car. All cars move by the same rule, LOOK: a car keeps its direction until nothing is left ahead to drop off or pick up.

| Name | Choice |
| --- | --- |
| `round_robin` | The next car in turn |
| `nearest_car` | The highest figure of suitability, a distance score that accounts for direction |
| `zone_based` | The car that owns the request's block of floors |
| `eta` | The lowest predicted wait for the new passenger only |
| `marginal_insertion` | The lowest rise in total passenger time on the car, counting the delay to everyone else |

## Tests

```powershell
python -m pytest
python -m ruff format --check .
python -m ruff check .
python -m mypy --strict src
```

## Key assumptions

- One tick is one floor of travel, and stops take no time. So a passenger's travel time is always the distance between their floors, and total time differs between algorithms only through wait time.
- `wait_time` is the boarding tick minus the request tick. `total_time` is wait time plus travel time.
- Each passenger is assigned once, in the tick of their request, and the assignment never changes.
- Schedulers see only requests already made.
- Capacity is never exceeded, so a passenger can be left behind by a full car and wait for a later pass.
- Floors are numbered from 1, and all cars start on floor 1 by default. The defaults are 10 floors, 3 elevators and a capacity of 6.

The full list will be added here in the final version.

## Time spent

To be filled in by the author.

## AI assistance

This project was built with AI assistance (Claude Code).
