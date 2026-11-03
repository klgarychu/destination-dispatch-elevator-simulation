# Elevator Scheduling Simulation: Requirements and Design Specification

| Item | Detail |
| --- | --- |
| Status | Delivered. Gate 6 approved on 2026-11-02, and this spec reconciled with the code on 2026-11-03 (M41) |
| Date | 2026-10-30, last updated 2026-11-03 |
| Project | New Python project, built locally in this folder |
| Code | `main` at `0393f52`. Section 5 gives each requirement's status, and a rule the code doesn't meet yet is marked **Open** where it is stated |
| Decision log | [assumptions_made.md](assumptions_made.md). IDs such as D11 or G6 in this spec point to it |
| Research | [algorithm_research.md](algorithm_research.md). Numbers such as [9] point to its references |

## 1. Summary

We are building a discrete-time Python simulation of a destination-dispatch elevator system, as set out in the take-home assessment `docs/Take_home_Elevator.pdf`. A passenger gives their origin and destination when they make a request, and the system immediately assigns them to one car.

The project delivers:

- a tick-by-tick simulator that meets every requirement in the PDF
- six dispatch algorithms, including the target, online capacity-aware pickup/drop-off insertion minimising marginal total passenger time, and `rush_express`, its variant for lobby rushes (M31)
- three seat behaviours (strict order, minimum time, weighted fairness), and guards with seat hold against starvation. The assignment rules were designed and not built (M34)
- normal and express elevators
- simulated suites: the main experiment of 240 inputs and 10,080 runs, written as 10,440 rows, and two case studies (section 13.1)
- statistics, logs, reports, charts and a presentation, so that a person can judge which option is best

**The software never ranks results or names a winner** (G3). It presents statistics and charts, and a person decides.

Several requirements conflict. Section 16 says what was decided and what can't be fully met.

## 2. Sources and precedence

When sources disagree, the higher one wins:

1. `docs/Take_home_Elevator.pdf`. The intent says to follow it strictly.
2. Decisions in `assumptions_made.md` marked PDF, Confirmed, Accepted, Derived, Owner's request or Owner's decision. These cover what the PDF leaves undefined. An entry marked Superseded holds only where the entry that replaced it is silent.
3. This specification.
4. `assumptions_made.md` entries marked Spec decision or Plan decision, which engineers may raise for review.
5. `algorithm_research.md`, which is background. The table at its top lists the findings that later decisions replaced, such as stop time (T4).

When a decision changes behaviour or scope, the sections of this spec it affects are updated at the same time, so that no superseded rule reads as current (M41).

Do not add features the PDF doesn't ask for unless a decision in `assumptions_made.md` says so. The stop-time setting was removed for that reason (T4).

## 3. Scope

### 3.1 In scope

- All PDF requirements, all three bonus items, the README, and presentation charts (P2).
- Simulated inputs, statistics and charts for comparing algorithms and settings.
- What the owner added after the spec review, each recorded in `assumptions_made.md`: the case studies, `rush_express`, ad hoc comparisons, the presentation and the published results (M24 to M40).

### 3.2 Out of scope

- Sky lobbies and passenger transfers (P3). They appear only in the PDF's background section, and a transfer would break "assigns them to a specific elevator".
- Non-zero stop time (T4).
- The assignment rules of section 9.5. The owner skipped them at Gate 3 (M34).
- Ranking or naming a winner in software (G3).
- Animation or interactive UI (O5).
- GitHub Actions (S6).
- Publishing without the owner's request. The agent pushed to the private repo at the owner's request (M39, M40), and making it public is the owner's step.

## 4. Glossary

| Term | Meaning |
| --- | --- |
| Tick | One unit of simulated time, equal to one floor of travel |
| Car | One elevator |
| Request | One input row: `time, id, source, dest` |
| Rider | A passenger who has boarded a car |
| Waiting passenger | A passenger assigned to a car who has not boarded yet |
| LOOK | The movement rule in section 7.2. Also called collective control |
| Sweep | A car's continuous travel in one direction |
| RT | The longest LOOK round trip, `2 × (floors − 1)` ticks. 18 for 10 floors, 118 for 60 |
| Algorithm, scheduler | The logic that picks a car for a new request |
| Behaviour | The rule for who gets a seat when there aren't enough: `strict`, `min_time` or `weighted` |
| Guard | A boarding rule that protects a passenger who has waited too long |
| Flagged | A passenger a guard has marked for priority. Once flagged, always flagged (section 9.4) |
| Protected | A waiting passenger whose seat the reservation check keeps: earlier passengers under `strict`, and flagged ones under seat hold (section 9.3) |
| Assignment rule | **Not built** (M34). A designed change to how `marginal_insertion` chooses a car, for anti-starvation testing (section 9.5) |
| Forecast | A forward simulation of one car, using only passengers already known |
| Left behind | A passenger whose car stopped at their floor going their way, but who did not board |
| Case | A building in the suites, named after its cars, floors and capacity (section 12.1) |
| Input | One simulated request file |
| Load basis | Where a run's arrival rate comes from: `own_limit`, a share of the case's own saturation rate; `fixed`, another case's passengers (section 12.5); or `custom`, a file given to `compare --requests` |
| Configuration | One combination of algorithm, behaviour, weight and guard. Its assignment rule is always `none` (M34) |
| Run | One configuration on one input |
| Stage | Stage 1 compares algorithms and seat behaviours. Stage 2 compares guard settings on `marginal_insertion` (section 13) |
| Row | One line of `simulation_stats.csv`. A run in both stages runs once and is written as a row for each (M11) |

## 5. Requirements

Each requirement lists its source, the test that verifies it (section 15), with the worked example from section 15.2 where there is one, and its status at `0393f52`:

- **Met:** built and tested.
- **Met with a limit:** met as far as section 16 says it can be.
- **Partly met:** some of it isn't built, by the owner's decision.
- **Owner's step:** only the owner can finish it.

A rule elsewhere in this spec that the code doesn't meet yet is marked **Open** where it is stated, and section 16.5 lists them all. A broad test name doesn't prove full coverage, so an Open rule stays Open until a test checks that rule itself.

### 5.1 Core system

| ID | Requirement | Source | Test | Status |
| --- | --- | --- | --- | --- |
| R-01 | Serve every request. No passenger waits indefinitely to be picked up or dropped off | PDF, D10, D19 | TST-09, TST-13 | Met with a limit: bounds are in round trips, with no fixed time (C3) |
| R-02 | Aim to minimise total time per passenger, where `total_time = wait_time + travel_time` | PDF | TST-05 | Met |
| R-03 | Honour capacity and direction logic, with direction logic meaning LOOK | PDF, D3 | TST-07, TST-09 | Met |
| R-04 | A passenger gives both origin and destination at request time | PDF | TST-03 | Met |
| R-05 | Assign each passenger to one specific car in the tick of their request | PDF, D1 | TST-09 | Met |
| R-06 | A passenger's destination can't change after assignment, and the controller never moves them to another car | PDF, D2 | TST-09 | Met |
| R-07 | Model time in discrete ticks, where one tick is one floor of travel, with no link to real clock time | PDF | TST-09 | Met |
| R-08 | Advance one tick at a time, even when requests skip ahead | PDF, T1 | TST-02 | Met |
| R-09 | Configurable number of elevators, with no fixed maximum | PDF, B3 | TST-12 | Met |
| R-10 | Configurable number of floors, numbered 1 to n | PDF, B1 | TST-12 | Met |
| R-11 | Configurable maximum passengers per elevator | PDF | TST-08, seat shortage | Met |
| R-12 | Defaults: 10 floors, 3 elevators, capacity 6, all overridable | B10 | TST-17 | Met |

### 5.2 Input

| ID | Requirement | Source | Test | Status |
| --- | --- | --- | --- | --- |
| R-13 | Provide a function that accepts a list of requests with fields `time`, `id`, `source`, `dest` | PDF, I1 | TST-01, PDF sample | Met |
| R-14 | Provide a CSV loader on top of that function | I1 | TST-03 | Met |
| R-15 | Never let a scheduler see a request before its `time` | PDF, D4 | TST-06 | Met |
| R-16 | Reject invalid input before the run starts, listing every bad row | I2 | TST-03 | Met |
| R-17 | Sort unsorted rows by time, keeping file order for ties | I3 | TST-03 | Met |

### 5.3 Output

| ID | Requirement | Source | Test | Status |
| --- | --- | --- | --- | --- |
| R-18 | Log every elevator's position for every tick, starting at 0, to a file with one row per tick | PDF, O2 | TST-04, PDF sample | Met |
| R-19 | On completion, output minimum, maximum and average wait time and total time | PDF, O3 | TST-05, PDF sample | Met. The saved settings beside them are Open (C31) |
| R-20 | Output other notable observations about time distributions or system behaviour | PDF | TST-05 | Met |
| R-21 | End the run at the last drop-off | O1 | TST-04 | Met |
| R-22 | Abort with a clear error if `max_ticks` is reached | O4 | TST-17 | Met |

### 5.4 Bonus items

| ID | Requirement | Source | Test | Status |
| --- | --- | --- | --- | --- |
| R-23 | Implement different elevator algorithms | PDF, D15 | TST-11 | Met: six (M31) |
| R-24 | Simulate express elevators that skip certain floors, with normal and express elevators separate in the code | PDF, B5, B6 | TST-12 | Met. Type checks on express settings are Open (C29) |
| R-25 | Explore fairness vs efficiency trade-offs | PDF, D9 | TST-08, TST-16 | Met |

### 5.5 Added by the project owner

| ID | Requirement | Source | Test | Status |
| --- | --- | --- | --- | --- |
| R-26 | Implement `marginal_insertion` as the target algorithm | D7, D16 | TST-10, TST-11 | Met |
| R-27 | Make seat behaviour a setting with three options | D9 | TST-08, seat shortage | Met |
| R-28 | Make starvation prevention configurable, covering every method in D17 | D13, D17 | TST-13 | Partly met: guards and seat hold only. The assignment rules aren't built (C28, M34) |
| R-29 | Simulate the inputs in section 12 and the runs in section 13 | G5 to G7 | TST-15, TST-16 | Met as amended: Stage 2 is rows 1 to 4 (M34), plus the case studies. Calibrating from a `weighted` config file is Open (C32) |
| R-30 | Keep statistics separate for each algorithm, configuration, setting and weight | G9 | TST-16 | Met |
| R-31 | Present results as charts and statistics only, with no ranking or winner, in a fixed order | G3, G4 | TST-18 | Met |
| R-32 | Run as `python -m elevator_sim` with `run`, `compare`, `generate` and `charts` | S5 | TST-17 | Met. Refusing options that don't apply is Open (C30) |
| R-33 | Keep every assumption in `assumptions_made.md` and carry them into the README | User, R6 | Review | Met |

### 5.6 Deliverables

| ID | Requirement | Source | Test | Status |
| --- | --- | --- | --- | --- |
| R-34 | Public GitHub repository containing the Python code | PDF | Manual, section 16 C6 | Owner's step: the repo is pushed and private, and the owner makes it public (M39) |
| R-35 | `README.md` with how to run, time spent, assumptions, simplifications and trade-offs, and what you'd improve | PDF | Review | Met, with the owner's hours and conclusion (M39) |
| R-36 | Visualisations and statistics for the follow-up presentation | PDF, O5 | TST-17 | Met, and published (M40). Two chart rules are Open (C33, C34) |

## 6. Architecture

### 6.1 Repository layout

```text
elevator_sim_claude/
├── pyproject.toml
├── README.md
├── AGENTS.md                   # rules for any agent
├── CLAUDE.md                   # Python setup and standards for Claude Code
├── .gitignore                  # keeps docs/, run data and the other project_docs/ files local (M40, M42)
├── project_docs/                       # intent, this spec, plan, research and decision log (M42)
├── configs/
│   ├── 3car-10floor-6cap.toml  # one file per case in section 12.1
│   ├── 6car-60floor-6cap-express.toml  # 60 floors, 6 cars, 2 of them express
│   ├── pdf_sample.toml         # enough floors for the PDF sample
│   └── load_rates.toml         # calibrated arrival rates
├── examples/
│   └── pdf_sample.csv
├── src/elevator_sim/
│   ├── __init__.py             # exports simulate()
│   ├── __main__.py
│   ├── cli.py
│   ├── config.py               # settings, TOML loading, validation
│   ├── requests.py             # Request, CSV loading, input validation
│   ├── engine.py               # simulate(): the tick loop
│   ├── elevators/
│   │   ├── base.py             # Elevator: movement, boarding
│   │   ├── normal.py           # NormalElevator
│   │   ├── express.py          # ExpressElevator
│   │   └── factory.py          # builds the fleet from settings
│   ├── boarding/
│   │   ├── behaviours.py       # strict, min_time, weighted
│   │   ├── guards.py           # skip_limit, wait_expiry, seat hold
│   │   └── seats.py            # the seat reservation check
│   ├── forecast.py             # forward simulation of one car
│   ├── schedulers/
│   │   ├── base.py             # Scheduler base class, CarView, FleetView
│   │   ├── registry.py         # builds a scheduler by name
│   │   ├── round_robin.py
│   │   ├── nearest_car.py
│   │   ├── zone_based.py
│   │   ├── eta.py
│   │   ├── marginal_insertion.py
│   │   └── rush_express.py
│   ├── metrics.py              # statistics
│   ├── output.py               # positions.csv, passengers.csv, summary.json
│   ├── workload.py             # simulated requests, suite input files
│   ├── calibration.py          # saturation rates
│   ├── experiment.py           # the suite, parallel runs, resuming
│   ├── report.py               # report.md
│   └── charts.py
├── results/                    # the published final results (section 14.1)
└── tests/
    ├── golden/                 # golden outputs (M8)
    └── update_golden.py
```

There is no `assignment_rules.py`, because the assignment rules weren't built (M34).

### 6.2 Data flow

```text
CSV or simulated requests
        │
        ▼
 requests.py: validate ───── any bad row ──► error listing all bad rows
        │
        ▼
 engine.simulate(requests, config)
   ├── keeps unreleased requests private
   ├── scheduler.assign(request, view) ──► forecast.py (read-only copies of cars)
   ├── elevators: exchange passengers, move by LOOK
   └── records positions and passenger times
        │
        ▼
 SimulationResult ──► metrics.py ──► output.py        (one run)
                                 └─► experiment.py ──► report.py, charts.py  (many runs)
```

### 6.3 Module rules

- `engine.py` is the only module that holds requests not yet released. It passes schedulers one request and a read-only view, so a scheduler has no way to reach future requests (R-15).
- Schedulers only choose a car (D5). They never move a car or decide who boards.
- Schedulers call `car.can_serve(source, dest)` and never check the car type (B6).
- `forecast.py` uses the same exchange code as the real step. It must not contain a second model of movement or boarding.
- `metrics.py`, `report.py` and `charts.py` must not produce a rank, a winner or results sorted by value (R-31).
- The simulator imports only the standard library. Only `charts.py` imports `matplotlib`.

### 6.4 Core types

```python
class Direction(IntEnum):
    DOWN = -1
    IDLE = 0
    UP = 1


@dataclass(frozen=True, slots=True)
class Request:
    time: int
    id: str
    source: int
    dest: int


@dataclass(slots=True)
class Passenger:
    request: Request
    order: int  # position in sorted input: the request order
    car_id: int
    board_tick: int | None = None
    dropoff_tick: int | None = None
    times_left_behind: int = 0


class Elevator(ABC):
    def serves(self, floor: int) -> bool: ...  # subclass-specific
    def can_serve(self, source: int, dest: int) -> bool:
        return self.serves(source) and self.serves(dest)

    def exchange(self, tick: int) -> None: ...  # drop off, set direction, board
    def move(self) -> None: ...


class NormalElevator(Elevator): ...  # serves every floor


class ExpressElevator(Elevator): ...  # serves a configured set of floors
```

### 6.5 Public API

```python
def simulate(requests: Sequence[Request], config: SimConfig) -> SimulationResult: ...
```

`SimulationResult` holds the position history, one record per passenger, and run counters. `simulate` validates its input in the same way as the CSV loader. It writes no files, so tests can call it directly.

## 7. Simulation behaviour

### 7.1 Tick loop

```text
t = 0
loop:
    release requests with time == t, in request order
        for each: assign it to a car, immediately and finally
    for each car in number order: car.exchange(t)
    log every car's position for tick t
    if every request is released and every passenger delivered: stop
    if t >= max_ticks: raise SimulationStalledError
    for each car: car.move()
    t = t + 1
```

Consequences:

- A request at tick `t` can board at tick `t` if its car is already there and is idle or going their way, giving a wait of 0 (T5).
- Stops take no time, so a car can drop off, board and leave within one tick (T4).
- Ticks pass one at a time even when nothing is happening, and every tick is logged (T1).
- Earlier assignments in a tick are visible to later ones in the same tick.
- Cars don't interact, so their processing order doesn't change results.
- Every run keeps the invariants listed under TST-09 in section 15.1.

Time definitions (T3):

```text
wait_time   = board_tick − request.time
travel_time = dropoff_tick − board_tick
total_time  = wait_time + travel_time
```

### 7.2 Movement: the LOOK rule

Every algorithm uses this rule, which matches published collective control [7], [17].

```text
exchange(t):
    drop off riders whose dest == position, recording dropoff_tick = t
    resolve_direction()
    board(t)                                     # section 9

resolve_direction():
    if direction is UP or DOWN:
        d = direction
        if riders, or work_ahead(d), or passengers here going d: keep d
        else if work_ahead(−d), or passengers here going −d: reverse to −d
        else: become IDLE
    if direction is IDLE and the car has waiting passengers:
        oldest = its oldest waiting passenger
        if oldest is on this floor: direction = oldest's direction
        else: direction = towards oldest's floor

work_ahead(d):
    any rider's dest is beyond position in direction d, or
    any waiting passenger's source is beyond position in direction d,
    whichever way that passenger is going

move():
    if direction is UP or DOWN: position += direction
    else if the scheduler gives an idle target: step one floor towards it
```

Rules that follow:

- A car with riders never reverses, because riders are always going the car's way.
- A car goes to the furthest pickup ahead before reversing, even if that passenger is going the other way.
- A passenger boards only when the car's direction matches theirs, after `resolve_direction`.
- A reversing car is empty, so each sweep starts with all seats free.

### 7.3 Travel time is fixed

A car with a rider always has work ahead, never reverses and never pauses. So for every passenger, under every algorithm:

```text
travel_time = abs(dest − source)
total_time  = wait_time + abs(dest − source)
```

The second term depends only on the input. **Differences in mean `total_time` between configurations are therefore exactly the differences in mean `wait_time`.** Engineers should treat this as an invariant and test it (TST-09). Section 16 lists what it means for the results.

### 7.4 Normal and express elevators

`Elevator` holds all movement and boarding. The two subclasses differ only in `serves(floor)` (B6).

| Rule | Detail |
| --- | --- |
| Normal | Serves every floor. This is the default for every car (B4) |
| Express | Serves a configured set of floors, and passes the others without stopping (B5). Passing a floor still takes one tick |
| Count | Express cars count toward the elevator total. `elevators = 6` with 2 express means 4 normal (B7) |
| Capacity | Shared by all cars (B7) |
| Eligibility | A car may be chosen only if it serves both source and destination (B8) |
| Coverage | Startup stops with an error if any pair of floors has no shared car. It checks all floor pairs from settings alone, so it looks at no requests. A building with one normal car always passes (B8) |
| Start floor | If the start floor isn't served, the car starts at its lowest served floor (B9) |

An express car stops only at served floors without any special logic, because it is only assigned passengers whose floors it serves.

### 7.5 End of run

The run ends after logging the tick of the last drop-off (O1). Idle cars heading to a parking floor never extend it.

- An empty request list gives one position row at tick 0, and statistics of `null` (I5).
- `max_ticks` defaults to `last request time + 4 × (passengers + 1) × (floors − 1)` (O6). Reaching it raises `SimulationStalledError`, reporting the tick and how many passengers are unfinished.

## 8. Algorithms

### 8.1 Scheduler interface

```python
class Scheduler(ABC):
    name: str

    @abstractmethod
    def assign(self, request: Request, view: FleetView) -> int: ...  # returns a car id
    def idle_target(self, car: CarView, view: FleetView) -> int | None:
        return None


@dataclass(frozen=True, slots=True)
class CarView:  # read-only snapshot
    car_id: int
    position: int
    direction: Direction
    rider_count: int
    waiting_count: int
    can_serve: Callable[[int, int], bool]


@dataclass(frozen=True, slots=True)
class FleetView:
    now: int
    floors: int
    capacity: int
    cars: tuple[CarView, ...]
    forecaster: Forecaster  # cached forecasts
    fairness_weight: float = 0.0  # 0 unless weighted

    def eligible(self, request: Request) -> tuple[CarView, ...]: ...  # cars that can serve it
    def baseline_forecast(self, car_id: int) -> Forecast: ...
    def candidate_forecast(self, car_id: int, request: Request) -> Forecast: ...
```

- `Scheduler` is an abstract base class rather than a Protocol, because every scheduler shares its `idle_target`.
- `assign` must return a car from `view.eligible(request)`. The engine checks this and raises an error otherwise.
- `idle_target` returns `None` by default, meaning the car stays where it is (D8). Only `zone_based` overrides it.
- Ties go to the lowest car number (D22).

### 8.2 Forecast

`view.baseline_forecast(car_id)` copies the car and simulates it until all its passengers are delivered. `view.candidate_forecast(car_id, request)` does the same with one new request added. It ignores future requests, because it can't see them, and it uses the real `exchange` code and the same behaviour and guard settings.

It returns a `Forecast`, which maps each request id on that car to a `PredictedTrip`:

```python
@dataclass(frozen=True, slots=True)
class PredictedTrip:
    request_time: int
    board_tick: int
    dropoff_tick: int
```

The design also had `passes_to_board`, how many times the car reaches a passenger's floor going their way before they board, and `peak_demand`, the highest count of riders plus passengers left behind during the new passenger's trip. Only the assignment rules used them, so neither was built (M34).

Requirements:

- **Exact.** If the car gets no new passengers, the forecast must equal what actually happens (TST-10). A car's plan changes only when it gets a new passenger [11].
- **Fast.** Move directly to the next floor where a rider gets off or a passenger is waiting, instead of ticking floor by floor.
- **Cached.** Keep each car's baseline, and invalidate it only when that car gets a new passenger. After an assignment, the candidate that included the new passenger becomes the new baseline. A baseline covers only the car's unfinished passengers, so anyone delivered since it was cached is left out when it is read. Every cached forecast must equal a fresh simulation (TST-10).

### 8.3 The six algorithms

The order below is the fixed display order (G4).

| Name | Role | Choice | Source |
| --- | --- | --- | --- |
| `round_robin` | Baseline | Next car in turn, skipping cars that can't serve the trip | PDF |
| `nearest_car` | Baseline | Highest figure of suitability | PDF, [19] |
| `zone_based` | Baseline | The car that owns the request's zone | PDF, [18] |
| `eta` | Comparator | Lowest predicted wait for the new passenger only | [1], [4] |
| `marginal_insertion` | Target | Lowest rise in total passenger time on the car | [1], [8], [9] |
| `rush_express` | Variant of the target | `marginal_insertion` among low-rise, high-rise and any-floor cars during a lobby rush | Our design (M31) |

**`nearest_car`.** With `N = floors − 1` and `d = abs(car position − source)`:

| Car state | Score |
| --- | --- |
| Idle, or moving toward the source in the passenger's direction | `(N + 2) − d` |
| Moving toward the source against the passenger's direction | `(N + 1) − d` |
| Moving away from the source | `1` |

A car on the source floor counts as moving toward it. The formula comes from a public README crediting Barney's handbook, and the idle row is our suggestion (D23, E2).

**`zone_based`** (D21):

- Split floors 1 to n into contiguous zones, one per car and as equal as possible. Lower-numbered cars take lower floors, and any extra floors go to the lowest zones.
- The zone floor is `source`, or `dest` when `source == 1`.
- If the zone's car can't serve the trip, choose the eligible car with the lowest `abs(car position − source)`.
- `idle_target` returns the middle floor of the car's zone, rounded down. An express car uses the nearest floor it serves, with ties going to the lower floor (D8, D27).

**`eta`.** For each eligible car, take `candidate_forecast(car, request)` and use the new passenger's predicted wait as the cost.

**`marginal_insertion`.** LOOK fixes the route for any set of passengers [7], so there is no insertion position to choose, only a car (D16). For each eligible car *e*, with `P_e` its unfinished passengers, new request *r*, and `D_k` the predicted drop-off tick:

```text
cost(e, r) = sum over k in P_e + {r} of  g(D_k with r    − t_k)
           − sum over k in P_e       of  g(D_k without r − t_k)
```

With `g(x) = x`, this is the new passenger's total time plus the delay to everyone else on that car, which is the published ETD cost [1]. Pick the lowest cost.

- Measure from each passenger's request tick, not from now [7].
- Do not estimate the change with a local shortcut. A small insertion can change a schedule's structure, so always re-simulate [8], [9].
- Capacity is hard at boarding and soft at assignment, because every passenger must be assigned. A predicted seat shortage shows up as a longer predicted time, with no separate penalty.
- Expect ties when a passenger's trip falls inside a car's current sweep. They go to the lowest car number, which may noticeably affect results (section 16, C17).

When the behaviour is `weighted`, each delay is multiplied by that passenger's weight (D14):

```text
weight_k = 1 + fairness_weight × (ticks passenger k has waited, or waited in total if riding) ÷ floors
```

**`rush_express`** (M31). Added in Phase 2. It is `marginal_insertion` with a narrower choice of cars during a lobby rush. Stops take no time here, so an express car can't gain by skipping floors. It can only help by separating traffic, because a car kept to the low floors has a shorter round trip.

- It keeps the origin of the last 30 requests, including the new one, so it sees only requests already made. A rush is when the window is full and at least 70% of them started at floor 1.
- In a rush, cars take turns by position in the fleet: any floor, low-rise, high-rise. Low-rise takes trips within floors 1 to n ÷ 2, rounded down. High-rise takes trips within floor 1 and the floors above that.
- If no eligible car takes the trip in a rush, every eligible car is considered.
- It chooses among those cars by `marginal_insertion`'s cost. Outside a rush it makes the same choices as `marginal_insertion`.

### 8.4 Excluded algorithms

These are excluded on the evidence in `algorithm_research.md`, section 2.

| Excluded | Reason |
| --- | --- |
| Genetic algorithms, MILP, exact reoptimisation | Under immediate assignment only one passenger is open, so trying each car is already exact. A published comparison found waits "almost identical" [9] |
| Reinforcement learning | Controls stops instead of assignment, and needs long training [14] |
| Dynamic sectoring | Designed for calls with no known destination. Forecasts use more information |
| Longest queue first, highest unanswered floor first | Control car stops, which D5 rules out |
| SSTF | Reverses with work ahead, which breaks LOOK |
| Collective control, SCAN, LOOK | Already the movement rule, so not dispatchers |

## 9. Seat behaviours and starvation prevention

### 9.1 Boarding procedure

Every behaviour uses this procedure at a stop, for waiting passengers on this car, on this floor, going the car's way:

```text
board(t):
    order = flagged passengers first, oldest first
            then the behaviour's priority order
    for p in order:
        if no seats are free: stop
        if boarding p would take a seat needed by a protected passenger ahead:
            leave p behind
            under strict: stop                     # D28
            otherwise: continue
        board p, recording board_tick = t
    add 1 to times_left_behind for everyone here going this way who did not board
```

### 9.2 Behaviours

| Name | Priority when seats are short | Protected passengers |
| --- | --- | --- |
| `strict` | Request order | Earlier passengers waiting ahead on this car and direction (D11) |
| `min_time` | Shortest ride first, ties by request order | Flagged passengers, if seat hold is on |
| `weighted` | Highest `(1 + fairness_weight × ticks waited ÷ floors) ÷ ride length`, ties by request order. The weight defaults to 1, and setting it on another behaviour is an error | Flagged passengers, if seat hold is on |

- Behaviours differ only when seats run short, so expect near-identical results in light traffic.
- Request order is absolute only within one car and direction. Section 16, C4 explains why.
- `weighted` with weight 0 matches `min_time`. Larger weights move towards request order (D14).
- `strict` ignores guard settings, because it satisfies R-01 alone. Outputs record its guard as `none` (D24).
- `min_time` rests on an analogy to Smith's rule, not an elevator study (D12).

### 9.3 Seat reservation check

A protected passenger *q* is one waiting on this car, going this way, on a floor still ahead on this sweep.

To test whether *p* may board, walk the floors ahead in sweep order, starting from the current riders plus everyone boarded at this stop plus *p*:

```text
at each floor ahead:
    remove riders whose dest is this floor
    add protected passengers whose source is this floor
    if the load exceeds capacity while p is still aboard: p is blocked
```

A passenger who gets off before a protected passenger's floor doesn't take their seat (D25). With no protected passengers ahead, nobody is blocked.

### 9.4 Guards

Guards apply to `min_time` and `weighted`.

| Guard | A passenger is flagged when | Default | Test values |
| --- | --- | --- | --- |
| `skip_limit` | `times_left_behind >= S` | S = 2 | 1, 2, 3 |
| `wait_expiry` | `tick − request.time >= W` | W = 2 RT | 1, 2, 3 RT |
| `none` | Never. Measurement only | Not a default | |

`seat_hold` (default on) makes flagged passengers protected, so seats stay free for them on the sweep that reaches them. Without it, a flag gives top priority only at the passenger's own floor, which doesn't help if the car arrives full.

The default is `skip_limit` with S = 2 and seat hold on (D18). All defaults are our suggestion, not published values.

Flags are re-evaluated at each exchange. With more flagged passengers than seats on a sweep, they board in order, up to capacity per sweep.

As built in Phase 4 (M35):

- A flag depends only on the passenger's own count and wait, which only grow, so once flagged a passenger stays flagged.
- Under seat hold, a flagged passenger waiting ahead keeps a seat from anyone who would board after them: every passenger not flagged, and younger flagged ones. A blocked passenger is passed over, and boarding continues. Only `strict` stops (D28).
- Without seat hold there is no seat check at all.
- `wait_limit` is whole ticks, or whole round trips written as `2rt`. A round trip is `2(n − 1)` ticks for every car.

### 9.5 Assignment rules (not built)

**Not built.** The owner skipped them at Gate 3 (M34). An `assignment_rule` setting is refused with exit code 2 (M12), and `fallback_count` is always 0. The design below is kept as a record, and the README lists it as a known limit.

These apply only to `marginal_insertion`. Setting one with another algorithm is a configuration error.

| Name | Type | Definition | Test values |
| --- | --- | --- | --- |
| `predicted_wait_limit` | Filter | Reject a car if adding *r* pushes anyone's predicted wait past W when it wasn't before | 1, 2, 3 RT |
| `round_trip_cap` | Filter | Reject a car if adding *r* makes anyone's `passes_to_board` exceed R when it didn't before | 1, 2, 3 |
| `seat_headroom` | Filter | Reject a car if `peak_demand` exceeds `share × capacity` | 100%, 80% |
| `convex_cost` | Cost | Replace `g` with `wait^p`, using predicted waits | p = 2, 3 |
| `lowest_worst_wait` | Cost | Cost is the highest predicted wait on the car with *r* added. Ties go to the plain cost, then the lowest car number | None |

When a filter rejects every eligible car, use the lowest-cost car anyway and add 1 to `fallback_count` (D19). Every passenger must be assigned.

A "wait counted 3× transit" setting was considered and dropped. Transit never changes (section 7.3), so it would make exactly the same choices as the plain cost (G13).

### 9.6 What "no passenger waits forever" guarantees

This is the definition agreed in D19.

| Situation | Guarantee |
| --- | --- |
| Every run | Every passenger is served. Inputs are finite, and after the last request each car carries at least one waiting passenger per round trip |
| Seats not short | Wait is under `2(n − 1)` ticks, and total time under `3(n − 1)` ticks |
| `strict` | Wait is limited to about `(rank ÷ capacity + 1)` round trips, where rank is the passenger's place among earlier passengers on that car, even in overload |
| Guard with seat hold | A flagged passenger boards on the next pass if at most `capacity` are flagged per direction. Otherwise they board in order. Tested on one car: with `skip_limit`, nobody is left behind more than S times, and with `wait_expiry` no wait exceeds W + 3(n − 1), because a passenger flagged mid-sweep can miss that sweep |
| Assignment rules alone | Not built (M34). As designed: soft, or holds only while no fallback occurs |
| `none` | No protection beyond finite inputs. Measurement only |

**There is no fixed maximum time.** Requests can't be refused, so overload always makes queues grow. These bounds are our derivations and not published results, so they must be tested (TST-13). Report them as bounds in round trips, and don't claim a time limit in the README or presentation.

### 9.7 Excluded methods

| Excluded | Reason |
| --- | --- |
| Rejecting requests, hard time windows | Every passenger must be served |
| Moving a passenger, sending a second car | Breaks final assignment (D2) |
| Jumping a car to an overdue passenger | Breaks LOOK (D3) |
| Earliest deadline first | With one wait limit for everyone, this is request order |
| FSCAN, N-step SCAN | A car would pass waiting passengers with free seats, against D3 |
| Batch priority | Seat hold is the targeted form of this |
| Raw overtake cap | Counts harmless overtakes. `skip_limit` counts real harm |

## 10. Configuration and commands

### 10.1 Config file

Settings use TOML, read with the standard library's `tomllib`. Command-line flags override the file, and defaults apply otherwise.

```toml
[building]
floors = 60
elevators = 6
capacity = 6
start_floor = 1

[[express]]
car = 5
serves = "1,31-60"

[[express]]
car = 6
serves = "1,31-60"

[dispatch]
algorithm = "marginal_insertion"
behaviour = "min_time"
guard = "skip_limit"
skip_limit = 2
wait_limit = "2rt"
seat_hold = true
```

This is `configs/6car-60floor-6cap-express.toml` with the `[dispatch]` defaults written out.

| Setting | Type | Valid values | Default |
| --- | --- | --- | --- |
| `floors` | Whole number | 2 or more | 10 |
| `elevators` | Whole number | 1 or more | 3 |
| `capacity` | Whole number | 1 or more | 6 |
| `start_floor` | Whole number | 1 to `floors` | 1 |
| `[[express]]` `car` | Whole number | 1 to `elevators`, each car once | No express cars |
| `[[express]]` `serves` | Text of floors and ranges, such as `"1,31-60"` | At least 2 distinct floors, each within 1 to `floors` | |
| `algorithm` | Name | The six in section 8.3 | `marginal_insertion` |
| `behaviour` | Name | `strict`, `min_time`, `weighted` | `min_time` |
| `fairness_weight` | Number | 0 or more and finite. Only with `weighted` (M33) | 1 under `weighted` |
| `guard` | Name | `none`, `skip_limit`, `wait_expiry` | `skip_limit` |
| `skip_limit` | Whole number | 1 or more | 2 |
| `wait_limit` | Whole ticks, such as `36`, or round trips, such as `"2rt"` | 1 or more | `"2rt"` |
| `seat_hold` | `true` or `false` | | `true` |
| `max_ticks` | Whole number, on the command line and the Python API only | 1 or more | The formula in section 7.5 (O6) |

- Express cars are defined only in the file. Cars not listed are normal.
- `assignment_rule` is refused with exit code 2, because it isn't built (M12, M34).
- Validation stops the run with a named error for a value of the wrong type or outside its range, an unknown or repeated express car, a failed coverage check, an unknown name or an unknown setting. Whole-number settings refuse `true` and `false`, and a file that isn't UTF-8 is invalid (I7).
- The same checks apply to a `SimConfig` built through the Python API, and to every configuration the code derives from another, such as calibration's.
- **Open (C29):** an `[[express]]` entry that isn't a table, such as `express = [1]`, raises an uncaught `TypeError`. Through the Python API, an express car number or served floor that isn't a whole number is accepted: car 1.5 matches no car, so every car is built as normal. A served-floor tuple that repeats a floor also counts it twice.

### 10.2 Commands

```powershell
# One run
python -m elevator_sim run --requests examples/pdf_sample.csv --config configs/pdf_sample.toml --out results/sample

# Simulated inputs for the suite, or one custom file
python -m elevator_sim generate --suite --out data/generated
python -m elevator_sim generate --pattern up_peak --rate 0.5 --ticks 1000 --seed 1 --config configs/3car-10floor-6cap.toml --out data/one.csv

# Measure saturation rates and update configs/load_rates.toml
python -m elevator_sim generate --calibrate

# Compare all Stage 1 configurations on one file, or run the suite
python -m elevator_sim compare --requests data/one.csv --config configs/3car-10floor-6cap.toml --out results/one
python -m elevator_sim compare --suite --stage all --out results
python -m elevator_sim compare --suite --phase 1 --out results/phase1
python -m elevator_sim compare --suite --quick --out results/quick

# Charts and report from saved statistics
python -m elevator_sim charts --stats results --out results/charts
```

Each command and mode takes these options. Options in the same row are optional unless marked required.

| Command and mode | Options and defaults |
| --- | --- |
| `run` | `--requests` and `--out` required. `--config`, then `--floors`, `--elevators`, `--capacity`, `--algorithm`, `--behaviour`, `--weight` (sets `fairness_weight`), `--guard`, `--skip-limit`, `--wait-limit`, `--seat-hold` or `--no-seat-hold`, and `--max-ticks`, which override the file. A `--behaviour` also clears the file's weight, unless `--weight` is given too (M38) |
| `generate`, one file | `--pattern`, `--rate` and `--out` required. `--ticks` 1000, `--seed` 1, and `--config` for the floors |
| `generate --suite` | `--out` required. Writes every suite input from the frozen rates |
| `generate --calibrate` | `--config` for one building, otherwise every case in `BUILDINGS`. `--algorithm` `marginal_insertion`, `--guard` `none`, `--workers` 8, and `--out` `configs/load_rates.toml`. Calibration runs no guard unless asked, so the frozen rates reproduce (M6) |
| `compare --suite` | `--out` required. `--phase` 1 to 4, default 4. `--stage` `all`, `1` or `2`, default `all`, and Stage 2 only in Phase 4. `--guard` only with phases 1 to 3, default `none` (M38). `--quick` runs seed 1 only. `--inputs` `data/generated`, `--workers` 8 |
| `compare --requests` | The file and `--out` required. `--config` for the building and guard, `--workers` 8. Runs every Stage 1 configuration as Stage 1 rows, with load basis `custom` (M38) |
| `charts` | `--stats` and `--out` required |

- `run` defaults to `marginal_insertion` with `min_time` and the default guard. This is a convenience, not a judgement that it is best (G10).
- `--workers` must be at least 1 (M21).
- An option that doesn't apply to the command and mode given is refused with exit code 2 and a message naming it, as M12 does for settings, so it can't seem to have had an effect. **Open (C30):** this isn't enforced. `compare --requests` accepts `--guard`, `--stage`, `--phase`, `--quick` and `--inputs`, and ignores them, so `--stage 2` still writes Stage 1 rows. Other modes ignore options too, such as `--workers` with `generate --suite`.

Exit codes: 0 for success, 2 for invalid input, settings or options, or a file that can't be read, and 3 for reaching `max_ticks`. `compare` finishes the other runs before it returns 3. `charts` returns 2 for an incomplete comparison, and 0 with no charts for a comparison with no passengers (M22). Errors go to stderr with no traceback.

## 11. Run outputs

`run` writes these to `--out`, and prints the summary to the console.

### 11.1 `positions.csv`

```csv
time,elevator_1,elevator_2,elevator_3
0,1,1,1
1,2,1,1
```

One row per tick from 0 to the last tick, positions only (O2). Cars are numbered from 1.

### 11.2 `passengers.csv`

```csv
id,time,source,dest,elevator,board_time,dropoff_time,wait_time,travel_time,total_time,times_left_behind
```

One row per passenger, in request order.

### 11.3 `summary.json`

```json
{
  "config": {"algorithm": "marginal_insertion", "behaviour": "min_time"},
  "building": {"floors": 60, "elevators": 1, "capacity": 6, "express_cars": []},
  "passengers": 3,
  "ticks": 100,
  "wait_time": {"min": 0, "mean": 23.67, "max": 71, "p95": 71, "stdev": 33.47},
  "total_time": {"min": 36, "mean": 58.67, "max": 90, "p95": 90, "stdev": 22.88},
  "observations": ["Longest wait: passenger3 at 71 ticks"]
}
```

This example is the PDF sample from section 15.2 as the code writes it now, with `config` shortened. The keys hold:

| Key | Contents |
| --- | --- |
| `config` | The dispatch settings in force: `algorithm`, `behaviour`, `fairness_weight` (`null` unless `weighted`), `guard` (`none` under `strict`, D24), `guard_value`, `seat_hold` (`false` with no guard), `assignment_rule` (always `none`), `rule_value` (`null`) and `unguarded` |
| `building` | `floors`, `elevators`, `capacity`, `start_floor`, `max_ticks` as set (`null` for the formula in section 7.5), and each express car with the floors it serves |
| `passengers`, `ticks` | Counts for the run |
| `wait_time`, `total_time` | `min`, `mean`, `max`, `p95` and `stdev`, with the mean and standard deviation rounded to 2 decimals (M18). `null` with no passengers (I5) |
| `observations` | Plain facts about the run, below |

Together with the input file, `config` and `building` must be enough to repeat the run. **Open (C31):** `building` holds only `express_cars`, the express car numbers, and leaves out `start_floor`, `max_ticks` and the floors each express car serves. Saved runs in `results/runs/` have the same gap: they store the dispatch settings, and their fingerprint is a hash, which can't be turned back into the settings.

`observations` meets R-20. It holds plain facts about one run: the longest-waiting passenger, the busiest source floor, peak passengers waiting, share with zero wait, and times left behind. It must not compare configurations.

## 12. Simulated inputs

### 12.1 Buildings

| Name | Floors | Cars | Capacity | Express | Why |
| --- | --- | --- | --- | --- | --- |
| `1car-10floor-6cap` | 10 | 1 | 6 | None | A control: with one car, no algorithm has a car to choose (M24) |
| `3car-10floor-6cap` | 10 | 3 | 6 | None | The project default (B10) |
| `3car-35floor-6cap` | 35 | 3 | 6 | None | The middle height (M27) |
| `3car-60floor-6cap` | 60 | 3 | 6 | None | Floors, cars and capacity each change alone from here (M26, M27) |
| `6car-60floor-6cap` | 60 | 6 | 6 | None | Twice the cars. Includes the PDF's floor 51 (M27) |
| `9car-60floor-6cap` | 60 | 9 | 6 | None | Three times the cars (M27) |
| `3car-60floor-9cap` | 60 | 3 | 9 | None | Half as many seats again per car (M27) |
| `3car-60floor-12cap` | 60 | 3 | 12 | None | Twice the seats per car, and the same 36 seats as `6car-60floor-6cap` (M27) |
| `3car-60floor-6cap-1high31` | 60 | 3 | 6 | Car 3 serves floors 1 and 31–60 | One express car for the top half (M30) |
| `3car-60floor-6cap-1high41` | 60 | 3 | 6 | Car 3 serves floors 1 and 41–60 | One express car for the top third (M30) |
| `3car-60floor-6cap-2high31` | 60 | 3 | 6 | Cars 2 and 3 serve floors 1 and 31–60 | Two express cars, leaving one car for the rest (M30) |
| `3car-60floor-6cap-split30` | 60 | 3 | 6 | Car 2 serves floors 1–30, and car 3 serves floors 1 and 31–60 | Low-rise and high-rise cars (M30) |
| `3car-60floor-6cap-overlap` | 60 | 3 | 6 | Car 2 serves floors 1–40, and car 3 serves floors 1 and 21–60 | Low-rise and high-rise cars that overlap (M30) |
| `6car-60floor-6cap-express` | 60 | 6 | 6 | Cars 5 and 6 serve floors 1 and 31–60 | Tests express cars |

Case names state the cars, floors and capacity, so a name can't drift from its building. Seeds keep the name a case first had, so that renaming it changes no request (M27).

Which suite runs which cases:

| Suite | Cases |
| --- | --- |
| Main experiment (Phases 3, 4 and 6) | `3car-10floor-6cap` and `3car-60floor-6cap` at their own limits, and `3car-60floor-6cap-overlap` on the passengers of `3car-60floor-6cap` (M32) |
| Eight buildings (Phase 1, re-run in Phase 6) | The first eight cases, at their own limits and at the fixed load (M27, M28) |
| Express layouts (Phase 2, re-run in Phase 6) | `3car-10floor-6cap`, `3car-60floor-6cap`, `6car-60floor-6cap` and `6car-60floor-6cap-express` at their own limits, and the express cases on the passengers of the building each changes (M30) |

### 12.2 Traffic patterns

Passengers are incoming (from floor 1), outgoing (to floor 1) or interfloor (between other floors).

| Name | Incoming | Outgoing | Interfloor | Source |
| --- | --- | --- | --- | --- |
| `uniform` | 0 | 0 | 100 | Both floors chosen evenly from 1..n |
| `up_peak` | 85 | 10 | 5 | CIBSE modern office [5] |
| `down_peak` | 10 | 85 | 5 | Mirror of up-peak (our choice) |
| `lunch` | 40 | 40 | 20 | [1], [6], [7] |

Non-lobby floors are chosen evenly from 2..n, with source and destination always different.

### 12.3 Arrivals and load

- Arrivals are Poisson [7], [14]. Draw exponential gaps with `random.Random(seed)`, and round the running time down to a tick.
- The generator refuses a rate that isn't positive and finite, and anything expected to make more than 10 million requests (M21).
- Each input covers 1,000 ticks of arrivals.
- Load levels are light, medium, heavy and overload: 30%, 60%, 90% and 120% of a measured saturation rate (G15).
- Passenger ids are `p000001`, `p000002` and so on.
- Files are named `{building}_{pattern}_{load}_s{seed}.csv`, using seeds 1 to 5.
- The seed for each file comes from `zlib.crc32` of the building, pattern, load and seed number, so inputs are independent and repeatable.
- Inputs are generated on demand and not committed.

### 12.4 Calibration

Saturation depends on the building, the pattern and the configuration, so measure it instead of guessing.

For each building and pattern, use bisection to find an arrival rate, to two decimal places, at which `marginal_insertion` with `min_time` and no guard (M6) lets the backlog grow by no more than `cars × capacity` passengers between ticks 500 and 1,000, averaged over seeds 1 to 3, and at which one hundredth more doesn't. The backlog at a tick is the passengers who have made their request and haven't been delivered.

Measure growth, not the backlog's size at one tick. That size includes everyone simply in transit, so it stops below true saturation (G15).

Calibration replaces the configuration's algorithm, behaviour and guard, and the derived configuration must pass the same validation as any other (section 10.1). **Open (C32):** it keeps the original `fairness_weight`, so calibrating from a `weighted` config file that sets a weight fails with a `ConfigError` before any run.

The result is a working measure from short runs, not a proof of long-run capacity. Near the boundary a few rates can pass just above one that fails, so calibration also confirms that the rate's heavy level passes and its overload level fails. It stops with an error if no rate passes, if no rate fails, or if that check fails (M23).

Store the results in `configs/load_rates.toml`, which is committed, so generation needs no recalibration. Calibrating on the target means the overload level is past capacity for it, and simpler algorithms will saturate sooner, which is a useful result.

Before the full suite, check that overload is actually past capacity and that heavy traffic produces left-behind passengers. If not, the guards won't be tested.

### 12.5 Fixed load

In Phase 1 every case also runs the arrivals of `3car-60floor-6cap`, which has the lowest limit on every pattern, so that a difference between cases comes from the building and not its traffic (M28).

- The 60-floor cases use that case's own input files.
- Other heights keep each request's tick and id, with floors drawn for the height from a separate stream, in `fixed-{floors}floor_{pattern}_{load}_s{seed}.csv`.
- `3car-60floor-6cap` needs no new runs, because its own runs are this load.
- These runs carry `load_basis` `fixed`, and the case's own load carries `own_limit`. Their run ids name the case, because cases share files.
- Level names mean the levels of `3car-60floor-6cap`, not a share of each case's limit.

Phase 2 uses the same idea (M30). Each express case runs on the passengers of the building it changes, and those runs also carry `load_basis` `fixed`. The 6-car express building runs at its own limit as well.

## 13. Experiment plan

### 13.1 Size

This section is the one home for run counts. Other documents link here.

The main experiment has 240 inputs: the 3 cases of the main experiment in section 12.1 × 4 patterns × 4 loads × 5 seeds. The overlap case runs on the files of `3car-60floor-6cap`.

| Stage | Purpose | Configurations | Inputs | Rows |
| --- | --- | --- | --- | --- |
| 1 | Each algorithm under each behaviour | 30 | 240 | 7,200 |
| 2 | Each anti-starvation method on the target | 18 | 180 | 3,240 |
| Total | | | | 10,440 rows from 10,080 runs |

The owner skipped the assignment rules (M34), so Stage 2 is rows 1 to 4 of section 13.3. The design had 42 configurations and 14,760 rows. 360 runs are in both stages, and each runs once with a row for each (M11). So a run is one execution, and a row is one line of the statistics, and the two counts differ.

Phase 6 also re-ran the two case studies on the default guard, so the final presentation uses final settings throughout (M38):

| Suite | Configurations | Runs | Output |
| --- | --- | --- | --- |
| Eight buildings | The 5 algorithms of Phase 1, on `min_time` | 6,000: 3,200 at each case's own limit and 2,800 at the fixed load (M28) | `results/cases/` |
| Express layouts | The 6 algorithms, on `min_time` | 4,800 | `results/express/` |

In all, Phase 6 ran 20,880 runs. The same inputs are used across configurations, so differences come from the configuration.

### 13.2 Stage 1

Every combination of:

- Algorithm: `round_robin`, `nearest_car`, `zone_based`, `eta`, `marginal_insertion`, `rush_express`
- Behaviour: `strict`, `min_time`, `weighted` at 0.5, 1 and 2

`min_time` and `weighted` use the default guard.

### 13.3 Stage 2

`marginal_insertion` only, at medium, heavy and overload load, because guards rarely act in light traffic. Each setting runs on two base behaviours, `min_time` and `weighted` at weight 1. Methods are tested alone, so settings use no guard unless shown. The design had 21 settings, and the 9 in rows 1 to 4 are built (M34).

| # | Setting | Values | Count |
| --- | --- | --- | --- |
| 1 | No guard (control, measurement only) | | 1 |
| 2 | `skip_limit`, seat hold on | S = 1, 2, 3 | 3 |
| 3 | `wait_expiry`, seat hold on | W = 1, 2, 3 RT | 3 |
| 4 | Seat hold off | `skip_limit` S = 2, `wait_expiry` W = 2 RT | 2 |
| 5 | `predicted_wait_limit` | W = 1, 2, 3 RT | 3 |
| 6 | `round_trip_cap` | R = 1, 2, 3 | 3 |
| 7 | `convex_cost` | p = 2, 3 | 2 |
| 8 | `lowest_worst_wait` | | 1 |
| 9 | `seat_headroom` | 100%, 80% | 2 |
| 10 | `convex_cost` p = 2 with the default guard | Combination | 1 |

Rows 5 to 10 aren't built, because the owner skipped the assignment rules (M34).

Label runs with no guard as `unguarded` in every output. On the 60-floor building, RT is 118 ticks, so check that wait limits actually trigger.

### 13.4 Running the suite

- Run in parallel with `concurrent.futures.ProcessPoolExecutor`. The development PC has 16 logical processors, and the default of 8 workers leaves some free.
- Save each run to `results/runs/<run_id>.json` as it finishes, with a fingerprint of its input file's contents, all its settings, its labels and the package's source files. A restarted suite reuses a saved run only if its fingerprint matches, and otherwise runs it again (M19).
- Build a `run_id` from the `config_id` and the input file's name, so that it is stable. A fixed-load run's id also names its case, because cases share files. It is a readable label, not proof that a saved run is still valid.
- Stop if an existing suite input no longer matches what the current rates generate, and never overwrite it (M19).
- Write aggregated files in sorted key order, so the output doesn't depend on completion order.
- An interrupted suite resumes when the same command runs again. The manifest is deleted first and written last, so `charts` refuses a comparison that didn't finish (M20).
- Wall-clock times go only to `suite_log.csv`, so every other file stays byte-identical (TST-14).

### 13.5 Run time

The target is a full suite within 2 hours (G17), and run time was measured at every gate (M9). The final runs, on 8 workers, from `results/final/phase_review.md`:

| Suite | Runs | Seconds |
| --- | --- | --- |
| Main experiment | 10,080 | 2,980 |
| Eight buildings | 6,000 | 531 |
| Express layouts | 4,800 | 766 |
| All | 20,880 | 4,277, about 71 minutes |

The runs waited for another program to finish, so the times are fair measures. Any future cut to meet the target needs the owner's agreement, and would be considered in this order:

1. Profile and speed up the forecast.
2. Use fewer seeds in Stage 2 overload runs.
3. Drop test values in Stage 2.

## 14. Statistics, report and charts

### 14.1 Statistics files

Results are kept separate per configuration so that each can be shown and compared alone (G9). `compare` writes these to its `--out` folder: `results/` for the main experiment, and `results/cases/` and `results/express/` for the case studies.

| File | Contents | Published (M40) |
| --- | --- | --- |
| `simulation_stats.csv` | One row per run and stage (G8) | Yes |
| `aggregate_stats.csv` | One row per configuration, building, pattern, load and load basis, with the mean, min and max of each statistic across seeds. Each row names its algorithm and behaviour as well as its `config_id` | Yes |
| `by_config/<config_id>.csv` | The `simulation_stats.csv` rows for one configuration | Yes |
| `samples/<input>/<config_id>/` | `positions.csv`, `passengers.csv` and `summary.json` for every configuration on two inputs per case: `up_peak` heavy and `lunch` overload, seed 1 | Yes |
| `report.md` | Summary tables | Yes |
| `suite_log.csv` | Each run's id, status and wall-clock seconds. The only file with wall-clock time | Yes |
| `run_manifest.json` | The `run_id` of every run these files cover, of any run asked for that didn't finish, and of the runs that kept full logs, all in task order. `charts` draws only the runs covered, and stops if the file is missing or any run didn't finish (M20, M22) | No |
| `runs/<run_id>.json` | Each saved run, for resuming (section 13.4) | No |

`results/sample/` holds the README's run on the PDF sample, and `results/final_presentation.pdf` the presentation. Both are published (M40).

Each row of `simulation_stats.csv` holds:

| Group | Columns |
| --- | --- |
| Identity | `run_id`, `config_id`, `stage`, `building`, `pattern`, `load`, `load_basis`, `seed` |
| Settings | `algorithm`, `behaviour`, `fairness_weight`, `guard`, `guard_value`, `seat_hold`, `assignment_rule`, `rule_value`, `unguarded` |
| Size | `passengers`, `ticks`, `passengers_per_tick` |
| Wait | `wait_min`, `wait_mean`, `wait_max`, `wait_p95`, `wait_stdev` |
| Total | `total_min`, `total_mean`, `total_max`, `total_p95`, `total_stdev` |
| Cars | `avg_car_load`, `empty_travel_share` |
| Fairness | `jain_wait`, `jain_total`, `times_left_behind`, `max_left_behind_one_passenger` |
| Guards | `flagged_passengers`, `fallback_count`, `held_seat_ticks`, `share_above_wait_limit` |

Definitions:

- `passengers_per_tick` is passengers divided by ticks.
- `avg_car_load` is the mean riders per car, over ticks in which the car moved.
- `empty_travel_share` is the share of car moves with no riders.
- Percentiles use the nearest-rank method.
- `stdev` is the population standard deviation.
- `jain_*` is `(sum of x)² ÷ (count × sum of x²)`, a 0–1 score of how evenly time is shared. If all values are 0, it is 1.

- `flagged_passengers` counts passengers flagged before they boarded. Flags only turn on, so these are the passengers flagged at the exchange where they boarded.
- `held_seat_ticks` sums, over every tick and car, the seats kept empty because seat hold left someone behind. A kept seat counts from that stop until someone boards the car, or until no flagged passenger is left ahead (M13, M35).
- `share_above_wait_limit` is the share of passengers whose wait is above the run's `wait_limit`, which is 2 RT unless set, whatever the guard (M13).
- `fallback_count` is always 0, because assignment rules aren't built (M34).

`config_id` is readable, for example `marginal_insertion__weighted-1__skip_limit-2-hold__none`. Each row of `aggregate_stats.csv` also names its `stage` and `fairness_weight`.

### 14.2 Report

`report.md` has one section per building, pattern and load, with a table per configuration in fixed order, and fixed-load sections after the own-limit ones. Charts show the own-limit load. It states the input counts, the seeds and which runs were unguarded.

It must not contain a rank, a winner, a "best" label, or any highlight of the lowest value.

### 14.3 Charts

`charts` writes static PNGs to `results/charts/` (O5).

| Chart | Shows |
| --- | --- |
| Algorithm comparison | Mean total time by configuration, for each building, pattern and load, with the spread across seeds |
| Distributions | Wait and total time distribution per configuration |
| Fairness vs efficiency | Mean total time against p95 or max wait, one point per configuration and weight |
| Load response | Mean total time against load level, one line per algorithm |
| Anti-starvation methods | Stage 2 mean total time, p95 and max wait, and times left behind, per method. One chart per building, with a panel per measure and load. Points are each seed's mean over the patterns, and each panel has its own axis. Every other chart draws Stage 1 |
| Car movement | Time against floor for each car, for the first 200 ticks of one sample run: `up_peak`, heavy, seed 1 (M17) |

Rules:

- Configurations always appear in the fixed order, never sorted by value (G4).
- Each algorithm keeps one colour across all charts.
- Show the spread across seeds. It describes the results and isn't a significance test. Configurations run the same inputs, so gaps are compared seed by seed (G11).
- Use the same axis range for charts that are meant to be compared.
- Label the wait and total charts so a reader knows they differ only by a fixed distance (section 7.3).

Each chart must show the runs it names. A chart that exists can still be wrong, so these rules are checked on the data a chart draws, not only on the PNG:

| Rule | Detail |
| --- | --- |
| Run selection | Draw only the runs in `run_manifest.json`, and only Stage 1, except the Anti-starvation methods chart, which draws Stage 2 |
| Load basis | Draw the own-limit runs only, never `fixed` ones (section 12.5). **Open (C33):** the car movement chart doesn't check the load basis. In the express suite a fixed-load sample of the same algorithm can replace the own-limit one, while the caption still names the own-limit input |
| Sample identity | A caption names the input of the run it draws, taken from that run's record |
| Incomplete comparison | `charts` refuses it with exit code 2 and leaves earlier charts in place, rather than drawing gaps (M22) |
| No passengers | A comparison with no passengers writes no charts and exits 0. In a comparison with some passengers, a panel with none is labelled "no passengers" (M22) |
| Observed zero | A panel whose passengers all have a value of 0 is drawn at 0, not labelled "no passengers". **Open (C34):** the Anti-starvation methods chart labels any panel whose highest value is 0 as "no passengers" |

## 15. Testing and definition of done

### 15.1 Tests

| ID | Test | Kind |
| --- | --- | --- |
| TST-01 | PDF sample gives the results in section 15.2 | Hand-calculated |
| TST-02 | Tick order, including wait 0 at the same floor, and idle ticks are logged | Hand-calculated |
| TST-03 | Each kind of invalid row is rejected, all bad rows are listed, sorting and ties are correct | Unit |
| TST-04 | `positions.csv` header, one row per tick from 0, and the run ends at the last drop-off | Unit |
| TST-05 | Statistics match hand-calculated values | Unit |
| TST-06 | No peeking: changing or removing requests after tick `t` leaves every assignment up to `t` unchanged | Property |
| TST-07 | LOOK scenarios: reversal at the furthest pickup, opposite-direction passenger not boarded on the way past, boarding after reversal | Hand-calculated |
| TST-08 | Seat shortage under each behaviour gives the results in section 15.2 | Hand-calculated |
| TST-09 | Rules hold on random inputs, listed below | Property |
| TST-10 | Forecast matches the actual outcome when a car gets no further passengers | Property |
| TST-11 | Each algorithm chooses the expected car in a hand-built case | Hand-calculated |
| TST-12 | Normal and express cars: skipped floors, eligibility, coverage failure, start floor, settings validation | Unit |
| TST-13 | Starvation scenarios, listed below | Fixed scenario |
| TST-14 | Same input and settings give byte-identical output files | Determinism |
| TST-15 | The generator is repeatable, and traffic mix and rates are within tolerance | Unit |
| TST-16 | Each configuration produces separate statistics, and aggregation is correct | Unit |
| TST-17 | Each command works end to end, including defaults, exit codes and `max_ticks`, and a small suite produces charts | Integration |
| TST-18 | No rank or winner in outputs, and fixed order in tables and charts | Unit |
| TST-19 | `ruff` and `mypy --strict` pass | Static |

**TST-09 rules**, checked with `hypothesis` on random buildings, including express cars, and random requests:

- Every passenger is served, with `request time <= board_tick < dropoff_tick`.
- Riders never exceed capacity.
- Each car moves at most one floor per tick and stays within 1..n.
- A car with riders moves only in their direction, and passengers board only in the car's direction.
- Each passenger rides only their assigned car, which never changes.
- Express cars pick up and drop off only at served floors.
- `travel_time == abs(dest − source)`.

**TST-13 scenarios:**

- **Seat starvation.** A lobby flood fills the car on every trip, with one mid-floor passenger going the same way past the flood's drop-offs. With one car, only seat hold or `strict` can help. The design also checked whether assignment rules steer the flood away with several cars, which isn't built (M34).
- **Same-floor starvation.** Steady short rides plus one long ride at a floor, under `min_time`. The long ride must board within the guard's limit.
- **Overload ramp.** Traffic rises past saturation, and every passenger is still served with no `max_ticks` error.
- **Bounds.** The limits in section 9.6 hold in these scenarios.

### 15.2 Worked examples

Use these as fixtures. All were calculated by hand, and the first was reproduced by a throwaway script.

**PDF sample:** 1 car, capacity 6, `floors = 60`, start floor 1.

| Passenger | Request | Boards | Drops off | Wait | Travel | Total |
| --- | --- | --- | --- | --- | --- | --- |
| passenger1 | t=0, 1→51 | 0 | 50 | 0 | 50 | 50 |
| passenger2 | t=0, 1→37 | 0 | 36 | 0 | 36 | 36 |
| passenger3 | t=10, 20→1 | 81 | 100 | 71 | 19 | 90 |

The car passes floor 20 going up at tick 19 without boarding passenger3, then reverses at floor 51. `positions.csv` has 101 rows, and mean total time is 58.67.

**Seat shortage:** 1 car, capacity 1, `floors = 5`. Requests at t=0: `a` 1→3, then `b` 1→2.

| Behaviour | `a`: wait, total | `b`: wait, total | Mean total |
| --- | --- | --- | --- |
| `strict` | 0, 2 | 4, 5 | 3.5 |
| `min_time` | 2, 4 | 0, 1 | 2.5 |

### 15.3 Definition of done

The work is done when all of these are true on the development PC (S6):

- All tests pass, including hypothesis and fixed scenarios.
- `ruff` and `mypy --strict` pass.
- `compare --suite` has finished and produced all files in section 14.
- `README.md` is complete, with the time spent and the conclusion in the owner's words.
- Every requirement in section 5 is met or listed in section 16.

All of these were met at Gate 6 (`results/final/phase_review.md`). Making the repo public is the owner's step after this (section 17).

## 16. Areas of concern

### 16.1 Contradictions that can't be fully met

| ID | Conflict | What was decided | What remains |
| --- | --- | --- | --- |
| C1 | The plan says to integrate into "our existing codebase", but none exists. This folder and the sibling `elevator_sim_codex` hold only the PDF and notes | New project, built here (P1) | Nothing to integrate with, so this spec defines a new structure |
| C2 | The first intent's outcome was to "discover or verify the best" algorithm, and "best" is defined (G1). The owner also decided that the software must not rank or name a winner (G3). The intent now says the same as G3 (M41) | Software presents statistics and charts. A person decides | **The software can't meet "discover the best" alone.** The conclusion is a human step. The report states none. The owner's conclusion is in the README and the presentation (M39) |
| C3 | "Serve all requests" and "no passenger should wait indefinitely" can't become a fixed maximum wait, because requests can't be refused | Defined as always served, with bounds in round trips (D19) | **No time limit is possible** under overload. Don't claim one |
| C4 | Strict fairness means request order, but LOOK stops a car turning back, and final assignment stops passengers changing cars | Strict applies per car and direction (D11) | **Absolute request order isn't achievable.** A later passenger on another car, or going the other way, can board first |
| C5 | The PDF requires immediate assignment to one car and also hard capacity. Nothing guarantees a seat when the car arrives | Capacity is hard at boarding and soft at assignment. Passengers can be left behind (D2) | **A seat can't be promised at assignment.** Holding a passenger back until a seat is free would break "immediately assigns" |
| C6 | The PDF requires a public GitHub repo, and the owner decided to work locally and push by hand, leaving out `project_docs/` and the PDF (R1, R2) | Local repo. At the owner's request the agent then pushed it to a private GitHub repo (M39) | **R-34 is met when the owner makes the repo public.** The README carries the assumptions, as the PDF asks (R6), and `assumptions_made.md` is published too (M42) |
| C7 | The intent says to follow the PDF strictly, but the PDF doesn't define direction logic, wait time, the start floor, or how a full car is handled | Each reading is recorded in `assumptions_made.md` | **The assessor may read these differently.** The README must state them |
| C8 | The target is "insertion", but LOOK leaves no insertion position, and free ordering would break the direction rule (D3) | Insertion reduces to choosing a car by forward simulation (D16) | The name is kept, but no position search exists. Published work found fixed order cost 7.13% in down-peak journey time and 1.41% in mixed traffic on small problems, and nothing in up-peak [7] |
| C9 | The PDF requires "how long you spent", which only the candidate knows | README had a placeholder (R4), and the owner then supplied the hours (M39) | Resolved: R-35 is met. No agent estimates the hours |
| C10 | The 10-floor default (B10) rejects the PDF's own sample, which reaches floor 51 (I2) | `examples/pdf_sample.csv` ships with `configs/pdf_sample.toml` | Running the sample with defaults gives a validation error. The README must show the right command |
| C11 | "No passenger waits forever" (D10) conflicts with no-guard control runs and with assignment-only settings in Stage 2, which weren't built (M34) | They are measurement only, labelled `unguarded`, and can't be defaults (D18) | Those runs don't meet D10's protection. They still finish, because inputs are finite |
| C28 | R-28 asks for every method in D17, and the owner skipped the assignment rules (M34) | Guards and seat hold are built. `assignment_rule` is refused, and Stage 2 is rows 1 to 4 | **R-28 is met for guards and seat hold only.** The README lists the five assignment rules as not built |

### 16.2 Consequences of the time model

| ID | Concern | Impact |
| --- | --- | --- |
| C12 | **Total time is just wait time plus a fixed distance.** Stops are free and LOOK never pauses a rider (section 7.3). So the objective reduces to mean wait, and no algorithm can change travel time | Wait and total charts show the same differences. There's no wait-against-ride trade-off to study |
| C13 | **The target algorithm's main published benefit is absent.** Gains in the literature come mostly from grouping passengers to reduce stops [1], [3], and stops cost nothing here. The owner accepted this (T4) | The gap between `marginal_insertion` and the baselines may be small. Published figures must not be quoted as expected results. The README must explain this |
| C14 | Delay to others exists only through waiting passengers on the car, such as a longer sweep or a used seat | `marginal_insertion` and `eta` may behave alike in light traffic |

### 16.3 Evidence and method risks

| ID | Concern | Impact |
| --- | --- | --- |
| C15 | Seat hold, cross-floor reservation, shortest-ride-first boarding and skip counts have no published elevator source (E1) | Describe them as our adaptations. Their bounds are unproven until tested |
| C16 | The `nearest_car` formula comes from a public README crediting Barney's handbook, which wasn't read (E2) | Acceptable for a baseline. Describe it that way |
| C17 | Ties may be common under free stops, and going to the lowest car number may push more work to low-numbered cars | Check per-car load. A tie-break can affect results, so disclose it |
| C18 | 5 seeds against typical published practice of 10 [5] | Small differences aren't reliable. Charts must show spread |
| C19 | The 60-floor building is taller than any building in the literature read, and has no published result to compare with | Thresholds may not trigger. Check them |
| C20 | Cars all start at floor 1, and nothing is trimmed from the start or end of runs (G12) | Early passengers are affected by the starting position. This is small over 1,000 ticks |
| C21 | Parts of the research came from abstracts or indirect citations. Section 7 of the research file lists them | Check any citation in full before quoting it in the presentation |

### 16.4 Delivery risks

| ID | Concern | Impact |
| --- | --- | --- |
| C22 | **Run time** could exceed the 2-hour target (section 13.5) | Resolved: measured at every gate (M9), and the final 20,880 runs took about 71 minutes on 8 workers. Any cut needs the owner's agreement |
| C23 | **Python 3.15 is new.** 3.15.0 came out on 2026-10-09 and 3.15.2 on 2026-10-25. Requiring it would mean an assessor on an older Python can't install the project | Eased: `requires-python = ">=3.14"`, at the owner's request (M44), and checked on 3.14.7. An assessor on 3.13 or older still can't install it. The README must state the minimum first, and that the final results were produced on 3.15.2. Windows builds were checked. Other systems were not |
| C24 | Python 3.15 wasn't installed on the development PC, and the `winget` catalogue listed only up to 3.14 | Resolved: WP 1.1 installed 3.15.2 (plan PC9). The Store Python 3.12 remains the default `python`, so use `.venv` |
| C25 | The PDF says nothing about AI tools | The README discloses AI assistance (R5). **The owner should check the company's rules before submitting** |
| C26 | Publishing the PDF, `project_docs/`, `AGENTS.md` or `CLAUDE.md` by accident would expose the exercise | `.gitignore` kept them local (M15), and Gate 6 found none of them in any commit. The owner then chose to publish `AGENTS.md`, `CLAUDE.md` and the five core documents in `project_docs/` (M42). The PDF and the other `project_docs/` files stay local. Check `git ls-files` before every push |
| C27 | Byte-identical output is only guaranteed on the same Python version and operating system | Acceptable for this project. State it in the README |

### 16.5 Rules the code doesn't meet yet

These rules are agreed, and the code doesn't meet them at `0393f52`. A code review on 2026-11-02 found them, and each was checked against the code. Each stays Open until a test checks the rule itself. Fixing them is a separate decision, because some fixes change code behind published files.

| ID | Rule | Gap | Section |
| --- | --- | --- | --- |
| C29 | Every setting is type-checked, in files and through the Python API (I7) | An `[[express]]` entry that isn't a table raises an uncaught `TypeError`. The API accepts an express car number or served floor that isn't a whole number, and a repeated served floor | 10.1 |
| C30 | An option that doesn't apply is refused with exit code 2 (M12) | `compare --requests` ignores `--guard`, `--stage`, `--phase`, `--quick` and `--inputs`, and other modes ignore options too | 10.2 |
| C31 | The saved settings are enough to repeat a run | `summary.json` and saved runs leave out `start_floor`, `max_ticks` and the floors each express car serves | 11.3 |
| C32 | A derived configuration passes the same validation as any other | Calibration switches to `min_time` and keeps a `weighted` file's weight, so it fails | 12.4 |
| C33 | Charts draw the own-limit runs only | The car movement chart keeps the last sample per algorithm. The published `results/express/charts/car_movement_6car-60floor-6cap-express.png` draws the fixed-load run, while its caption names the own-limit input | 14.3 |
| C34 | An observed zero isn't shown as missing | The Anti-starvation methods chart labels a panel whose highest value is 0 as "no passengers" | 14.3 |

## 17. Actions for the project owner

| Action | Why | When | Status |
| --- | --- | --- | --- |
| Check the company's rules on AI use | C25 | Before submitting | Open |
| Supply the real hours spent | C9 | Before pushing | Done (M39) |
| Read the charts and write the conclusion on which option is best | C2 | Before the presentation | Done (M39) |
| Create the GitHub repo, and make it public | C6 | At the end | The agent pushed to a private repo at the owner's request (M39). Making it public is open |
| Decide on any scope cut if the suite is too slow | C22 | If it happens | Not needed (section 13.5) |
| Decide whether to fix the rules in section 16.5 | C29 to C34 | Before making the repo public | Open |

## 18. Delivery plan

[plan.md](plan.md) holds the phases, work packages and gate approvals (M1). The package versions are in `pyproject.toml` and `CLAUDE.md`.

### README contents

R-35's checklist for the README:

- Python 3.14 requirement (M44), and how to install, activate the virtual environment and run, including the PDF sample command.
- Time spent, in the owner's words.
- Assumptions, simplifications and trade-offs, taken from `assumptions_made.md`, including sections 7.3 and 9.6.
- A short description of each algorithm, behaviour and method, marking our adaptations.
- How to reproduce the results, and where the charts are.
- What you'd improve with more time.
- One line disclosing AI assistance.
