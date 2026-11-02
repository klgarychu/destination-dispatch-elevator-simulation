# Elevator scheduling simulation

A discrete-time Python simulation of a destination-dispatch elevator system. A passenger gives their origin and destination when they make a request, and the system immediately assigns them to one car. The project compares six dispatch algorithms, three seat behaviours and two guards against long waits, under simulated traffic.

The software presents statistics and charts in a fixed order, and never ranks results or names a winner. A person reads them and decides. The author's conclusion is in [Conclusion](#conclusion).

## Requirements

**Python 3.15 or later.** The simulator uses only the standard library. Charts need `matplotlib`, and the tests need `pytest`, `hypothesis`, `ruff` and `mypy`. It was built and tested on Windows 11. Other systems weren't tried.

## Install

```powershell
py -3.15 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev,charts]"
```

Run the commands below from the project root, with the virtual environment's Python. They are shown as `python -m elevator_sim`.

## Quick start: the sample from the assignment

The sample reaches floor 51, so it needs its own config. With the default 10 floors it gives a validation error.

```powershell
python -m elevator_sim run --requests examples/pdf_sample.csv --config configs/pdf_sample.toml --out results/sample
```

`run` writes three files and prints the summary:

| File | Contents |
| --- | --- |
| `positions.csv` | Every car's floor at every tick, from tick 0 to the last drop-off |
| `passengers.csv` | Each passenger's car, board and drop-off ticks, wait, travel and total time, and times left behind |
| `summary.json` | The settings, and the minimum, mean, maximum, p95 and standard deviation of wait and total time |

Exit codes are 0 for success, 2 for invalid input or settings, and 3 for reaching `max_ticks`. Errors go to stderr, with every bad input row listed.

## Your own building and settings

**1. Describe the building in a TOML file.** Anything left out takes its default.

```toml
[building]
floors = 20          # default 10
elevators = 4        # default 3
capacity = 8         # default 6
start_floor = 1      # default 1

[[express]]          # optional, one table per express car
car = 4
serves = "1,11-20"

[dispatch]
algorithm = "eta"         # round_robin, nearest_car, zone_based, eta, marginal_insertion (default), rush_express
behaviour = "weighted"    # strict, min_time (default), weighted
fairness_weight = 0.5     # weighted only, default 1
guard = "wait_expiry"     # none, skip_limit (default), wait_expiry
skip_limit = 2            # S, default 2
wait_limit = "1rt"        # ticks such as 36, or round trips such as "2rt" (default)
seat_hold = true          # default true
```

**2. Get requests.** Use your own CSV with the header `time,id,source,dest`, or generate one:

```powershell
python -m elevator_sim generate --pattern lunch --rate 0.8 --ticks 300 --seed 7 --config my_building.toml --out requests.csv
```

Patterns are `uniform`, `up_peak`, `down_peak` and `lunch`, and the rate is passengers per tick.

**3. Run one configuration:**

```powershell
python -m elevator_sim run --requests requests.csv --config my_building.toml --out results/my_run
```

Any setting can also be given on the command line, where it replaces the file's: `--floors`, `--elevators`, `--capacity`, `--algorithm`, `--behaviour`, `--weight`, `--guard`, `--skip-limit`, `--wait-limit`, `--seat-hold` or `--no-seat-hold`, and `--max-ticks`. A `--behaviour` there also replaces the file's weight, unless `--weight` is given too. With no config file, `run` uses `marginal_insertion`, `min_time` and the default guard. That is a convenience, not a judgement.

**4. Compare every algorithm and seat behaviour on the same requests,** with the file's building and guard settings. That is 6 algorithms × 5 seat settings = 30 runs:

```powershell
python -m elevator_sim compare --requests requests.csv --config my_building.toml --out results/my_compare
python -m elevator_sim charts --stats results/my_compare --out results/my_compare/charts
```

To find how much traffic a building can carry, run `generate --calibrate --config my_building.toml --out my_rates.toml`. It can take tens of minutes, and `--algorithm` and `--guard` measure the limit under other settings.

## Reproducing the results

```powershell
python -m elevator_sim generate --suite --out data/generated
python -m elevator_sim compare --suite --out results
python -m elevator_sim charts --stats results --out results/charts
python -m elevator_sim compare --suite --phase 1 --guard skip_limit --out results/cases
python -m elevator_sim charts --stats results/cases --out results/cases/charts
python -m elevator_sim compare --suite --phase 2 --guard skip_limit --out results/express
python -m elevator_sim charts --stats results/express --out results/express/charts
```

- **`generate --suite`** writes the simulated inputs from the frozen rates in `configs/load_rates.toml`, and refuses to overwrite an input that no longer matches them.
- **`compare --suite`** runs the main experiment, in two stages on `3car-10floor-6cap`, `3car-60floor-6cap` and the `3car-60floor-6cap-overlap` express layout:
  - Stage 1 runs every algorithm under every seat setting with the default guard.
  - Stage 2 runs `marginal_insertion` under `min_time` and `weighted` at 1 with each guard setting in turn, including none, at medium, heavy and overload traffic.
  - `--stage 1` or `--stage 2` runs one stage. A run in both stages runs once and has a row in each.
- **`--phase 1`** runs eight building cases, each named after its building, from 1 to 9 cars, 10 to 60 floors and 6 to 12 seats. Floors, cars and seats each change alone around `3car-60floor-6cap`, and `1car-10floor-6cap` is a control with no car to choose. Each case runs at its own load levels, and again on the same arrivals as `3car-60floor-6cap`.
- **`--phase 2`** runs five express layouts of `3car-60floor-6cap`, and one of `6car-60floor-6cap`, each on the same passengers as the building it changes.
- **`--guard skip_limit`** runs those case studies with the default guard. Without it they run with no guard, as they did when first built.

Each folder gets `simulation_stats.csv` (one row per run), `aggregate_stats.csv` (the mean, minimum and maximum across seeds), `report.md` (summary tables) and the charts. It also gets full logs for two sample inputs per building in `samples/`. A restarted `compare` reuses saved runs whose input, settings and code are unchanged. The same input and settings give byte-identical files on the same Python version and operating system.

On the development PC, a Windows 11 machine with 16 logical processors, with 8 workers and nothing else running: the main experiment takes about 50 minutes, the eight buildings about 9, and the express layouts about 13. `--workers` sets the number of processes.

The charts are in [results/charts/](results/charts/), [results/cases/charts/](results/cases/charts/) and [results/express/charts/](results/express/charts/), with each folder's `report.md` beside them as a table view.

## How the simulation works

- **Time.** One tick is one floor of travel. Each tick: new requests are assigned in input order; each car drops off, then boards; positions are logged; then each car moves at most one floor. Stops take no time.
- **Assignment.** Each passenger is assigned to one car in the tick of their request, and the assignment never changes. Algorithms see only requests already made.
- **Movement.** Every car follows the same rule, LOOK. A car keeps its direction until nothing is left ahead to drop off or pick up, and a passenger boards only if the car is going their way or is idle. So algorithms differ only in which car they choose.
- **Capacity.** Capacity is never exceeded. A passenger can be left behind by a full car, and waits for a later pass.
- **Times.** `wait_time` is the board tick minus the request tick. `travel_time` is the drop-off tick minus the board tick. `total_time` is their sum.

## Algorithms

| Name | Chooses |
| --- | --- |
| `round_robin` | The next car in turn |
| `nearest_car` | The highest figure of suitability, a distance score that accounts for direction. The formula comes from a public description crediting Barney's handbook, which wasn't read, and treating an idle car as already moving towards the call is our choice |
| `zone_based` | The car that owns the request's block of floors, from the source floor, or from the destination for trips from floor 1. Idle cars return to the middle of their zone |
| `eta` | The car with the lowest predicted wait for the new passenger only |
| `marginal_insertion` | The car whose total passenger time rises least, counting the delay to everyone already assigned. Under LOOK a car's route is fixed by its passengers, so "insertion" means simulating each car forward with and without the new passenger |
| `rush_express` | Our adaptation of `marginal_insertion`. While 70% of the last 30 requests came from the lobby, cars take turns as any-floor, low-rise and high-rise. The values were chosen on seeds 1 to 10 and checked once on seeds 11 to 15 |

Ties go to the lowest car number. Express cars, set with `[[express]]` tables, are chosen only for trips they can serve. Stops take no time here, so an express car saves nothing by skipping floors, and can help only by separating traffic.

## Seat behaviours

When a car stops and seats are short, the behaviour decides who boards.

| Name | Who boards first |
| --- | --- |
| `strict` | The earliest request. A later passenger boards only if that still leaves a seat for every earlier one further along the car's way |
| `min_time` | The shortest ride, which frees seats fastest |
| `weighted` | The highest (1 + weight × ticks waited ÷ floors) ÷ ride length. Weight 0 matches `min_time`, and larger weights move towards request order. `marginal_insertion` and `rush_express` also weigh a delay more the longer that passenger has waited |

Request order is kept per car and direction. A later passenger on another car, or going the other way, can still board first. No published elevator source was found for shortest-ride-first boarding or for keeping seats across floors: both are our adaptations.

## Guards against long waits

`min_time` and `weighted` can leave a passenger behind again and again. A guard flags such a passenger, and flagged passengers board first, oldest first. `strict` needs no guard and runs none.

| Guard | A passenger is flagged once they have |
| --- | --- |
| `skip_limit` | Been left behind S times. The default, with S = 2 |
| `wait_expiry` | Waited W ticks, set in ticks or in round trips of the building |
| `none` | Never. For measurement only, and such runs are labelled unguarded |

With seat hold, which is on by default, a car keeps a seat free for a flagged passenger further along its way. Without it, a flag helps only at the passenger's own floor, which does nothing if the car arrives full. Seat hold and skip counts at boarding are our adaptations.

**What is guaranteed.** Every passenger is always served. With `skip_limit` and seat hold, a flagged passenger boards on the car's next pass in their direction, as long as no more passengers are flagged in that direction than the car has seats. That held in every test on one car, and in heavy traffic the condition often fails. Requests can't be refused, so there is no fixed time limit: in overload, queues grow.

## Simulated traffic

| Item | Values |
| --- | --- |
| Patterns, as incoming, outgoing and between-floor trips | `uniform` 0/0/100, `up_peak` 85/10/5, `down_peak` 10/85/5, `lunch` 40/40/20 |
| Loads | `light`, `medium`, `heavy` and `overload`: 30%, 60%, 90% and 120% of a measured limit |
| Arrivals | Random, over 1,000 ticks, with seeds 1 to 5 |
| Limit | For each building and pattern, the highest rate, in hundredths of a passenger per tick, at which the number of unfinished passengers grows by no more than one fleet's seats over the second half of the arrivals. Measured with `marginal_insertion`, `min_time` and no guard, on three seeds |

The limits are frozen, so every experiment uses the same passengers. Measured with the default guard, the limits of the main experiment's two buildings fall by up to 17%. So on 4 of their 8 building and pattern pairs, `heavy` traffic is past the limit when guards run. Part of a guard's cost at heavy traffic is that lost capacity.

## Assumptions, simplifications and trade-offs

- **Stops take no time.** So a passenger's travel time always equals the distance, and total time differs between configurations only through waiting. Published gains from grouping passengers to save stops can't appear here, so published figures shouldn't be compared with these results.
- **Floors are numbered from 1**, with no basement. All cars start on floor 1 by default, and an express car starts at its lowest served floor if needed.
- **Every pair of floors needs a car serving both,** or the settings are refused. A building with one normal car always passes.
- **Each row of input is one trip,** because the assignment calls `id` a unique passenger id. Unsorted rows are sorted by time, keeping file order for ties. Any invalid row stops the run, and all bad rows are listed.
- **A passenger whose car is already at their floor,** idle or going their way, waits 0 ticks.
- **The run ends at the last drop-off,** and every passenger counts. Nothing is trimmed from the start or end.
- **Idle cars stay where they are,** except under `zone_based`. An idle car with work heads for its oldest waiting passenger.
- **"Best" is the owner's call.** The assignment's measure is mean total time per passenger, and the software reports it beside the fairness measures without choosing.
- **Five seeds** per input. Published practice is often ten, so charts show the range across seeds, which describes the spread and isn't a significance test. Configurations run the same passengers, so compare them seed by seed.
- **Assignment rules aren't built.** The design included five rules that change how `marginal_insertion` chooses a car, such as a predicted wait limit, and they were left out of scope. Setting `assignment_rule` is refused.
- **The 60-floor buildings are taller than any found in the published studies read,** so there are no published results to check them against.
- **Defaults are our suggestions,** not published values: 10 floors, 3 cars, 6 seats, and the guard at S = 2 with seat hold.

## What I'd improve with more time

- Give stops a time cost, so that grouping passengers and skipping floors with express cars can show their real-world value.
- Build the assignment rules, and compare them with the guards.
- Run ten seeds, and give the differences confidence intervals.
- Find out why the guards cost so much more on the 10-floor building, and why `eta` with `strict` improved every measure at medium traffic in testing.
- Speed up forecasts in long overload queues, which dominate the run time.

## Conclusion

These figures come from the final results, with `min_time` and the default guard unless stated.

**`marginal_insertion` looks like the strongest all-round algorithm.** Unlike `eta`, it counts the delay to passengers already assigned, not just the new one. On every building with more than one car, it had the lowest average total time, p95 wait and longest wait at light and medium traffic. At heavy traffic on `uniform`, `down_peak` and `lunch`, its average was 35% to 65% below the next algorithm's, and its p95 and longest waits stayed the lowest almost everywhere. The exception is the morning rush: at `up_peak` in heavy traffic and overload, `zone_based` had a lower average on 13 of 14 building and level pairs.

**Other factors help most in particular situations:**

- **Express cars, at the morning rush.** `rush_express` gives the cars any-floor, low-rise and high-rise roles only while most requests come from the lobby. At `up_peak` on `3car-60floor-6cap`, it cut the average by 27% at heavy traffic and 36% in overload against `marginal_insertion`, and beat `zone_based` too. At other times it changed nothing. Fixed express layouts also helped at `up_peak`, by up to 30% at heavy traffic, but every one of them cost time under `uniform` traffic.
- **The guard, for fairness.** It roughly halved the longest wait, by 47% at both heavy traffic and overload, for 10% and 32% more average time. The most times one passenger was left behind fell from 6.5 to 2.5 at heavy traffic. Seat hold does most of that work.
- **Seat behaviour, when no guard runs.** At heavy traffic with no guard, `weighted` at weight 1 cut the longest wait by 39% for 9% more average time, and `strict` by 49% for 32%. With the guard on, they add little.

The guard and seat figures are for `marginal_insertion` on `3car-60floor-6cap`, averaged over the four patterns and five seeds.

**This is not academic research.** It's a take-home exercise in a simplified model. Stops take no time, the traffic is simulated, and there are five seeds and no significance tests. Several rules are our own adaptations with no published source, and the 60-floor buildings are taller than any in the studies I read. The results compare options within this model. They don't predict how a real building will perform.

## Time spent

| Activity | Hours |
| --- | ---: |
| Research | 3 |
| Instructing the agentic planning, design and development workflow | 2 |
| Reviewing and improving the code, design and plan | 7 |
| Preparing the presentation | 2 |
| Agentic work by Claude Code | 20 |
| **Total** | **34** |

## AI assistance

This project was built with AI assistance (Claude Code).
