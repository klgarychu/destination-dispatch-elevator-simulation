# Elevator scheduling simulation

A discrete-time Python simulation of a destination-dispatch elevator system. A passenger gives their origin and destination when they make a request, and the system immediately assigns them to one car. The project compares dispatch algorithms under simulated traffic.

> **Status: work in progress.** This version has six algorithms, normal and express elevators, three seat behaviours, and guards against long waits. The assignment rules in the design are not built. **Results so far are interim**, until the final suite runs.

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

`run` writes `positions.csv` (every car's floor at every tick), `passengers.csv` and `summary.json`, and prints the summary. It also accepts `--floors`, `--elevators`, `--capacity`, `--algorithm`, `--behaviour`, `--weight`, `--guard`, `--skip-limit`, `--wait-limit`, `--seat-hold` or `--no-seat-hold`, and `--max-ticks`. It defaults to `marginal_insertion` with `min_time` and the default guard, which is a convenience and not a judgement.

Simulated inputs:

```powershell
python -m elevator_sim generate --suite --out data/generated
python -m elevator_sim generate --pattern up_peak --rate 0.5 --ticks 1000 --seed 1 --config configs/3car-10floor-6cap.toml --out data/one.csv
```

Compare algorithms on one file, or run the whole suite:

```powershell
python -m elevator_sim compare --requests data/one.csv --config configs/3car-10floor-6cap.toml --out results/one
python -m elevator_sim compare --suite --out results/phase4
python -m elevator_sim charts --stats results/phase4 --out results/phase4/charts
```

`compare --suite` runs two stages on `3car-10floor-6cap`, `3car-60floor-6cap` and `3car-60floor-6cap-overlap`. Stage 1 runs every algorithm under every seat behaviour with the default guard. Stage 2 runs `marginal_insertion` under `min_time` and `weighted` at 1 with each guard setting in turn, including none, at medium, heavy and overload. `--stage 1` or `--stage 2` runs one of them. A run in both stages runs once and has a row in each. `--phase 1`, `--phase 2` and `--phase 3` run the earlier suites, which had no guards. Phase 1 has eight cases named after their buildings, each at four loads set from its own measured limit, and each on the same arrivals as `3car-60floor-6cap`. Phase 2 has five express layouts of `3car-60floor-6cap` and one of `6car-60floor-6cap`, each on the same passengers as the building it changes.

To measure how much traffic a layout can carry under another algorithm, add `--algorithm` to `generate --calibrate`, with `--out` naming a separate file. The rates in `configs/load_rates.toml` are measured with `marginal_insertion` and no guard, and `--guard` measures them with one.

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
| `rush_express` | As `marginal_insertion`, except that in a lobby rush one car serves every floor, one the low floors and one the high floors. A rush is when 70% of the last 30 requests came from the lobby |

Stops take no time in this model, so an express car saves nothing by skipping a floor. Express cars, set with `[[express]]` tables in a config file, can only help by separating traffic.

## Seat behaviours

When a car stops and seats are short, the behaviour decides who boards.

| Name | Who boards first |
| --- | --- |
| `strict` | The earliest request, and a seat is kept for any earlier passenger further along the car's sweep |
| `min_time` | The shortest ride |
| `weighted` | The highest (1 + weight × ticks waited ÷ floors) ÷ ride length. Weight 0 matches `min_time`. `marginal_insertion` and `rush_express` also count a delay for more the longer that passenger has waited |

## Guards against long waits

`min_time` and `weighted` can leave a passenger behind again and again. A guard flags such a passenger, and flagged passengers board first, oldest first. `strict` needs no guard, because it boards in request order.

| Guard | A passenger is flagged once they have |
| --- | --- |
| `skip_limit` | Been left behind S times. The default, with S = 2 |
| `wait_expiry` | Waited W ticks, set in ticks such as `36` or in round trips such as `2rt` |
| `none` | Never. For measurement only, and such runs are labelled unguarded |

With seat hold, which is on by default, a car also keeps a seat free for a flagged passenger further along its way. Without it, a flag helps only at the passenger's own floor, which does nothing if the car arrives full. These rules are our adaptation: no published elevator method was found for them.

With `skip_limit` and seat hold, a flagged passenger boards on the car's next pass in their direction, as long as no more passengers are flagged in that direction than the car has seats. There is no fixed time limit: requests can't be refused, so in overload queues still grow.

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
