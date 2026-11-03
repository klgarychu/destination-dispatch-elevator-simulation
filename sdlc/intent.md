# Intent: Elevator scheduling simulation

## Goal

Build a reproducible destination-dispatch elevator simulator for the take-home assessment in `docs/Take_home_Elevator.pdf`. It lets a reviewer see how dispatch algorithms, seat behaviours, express layouts and starvation protection affect passengers' total time and fairness, under traffic scenarios that are stated in full.

The simulator produces evidence for a person to compare. It doesn't claim that any algorithm is best everywhere, and it never picks a winner.

## Problem

Modern buildings use banks of elevators, express cars and scheduling to cut waiting and travel time. In destination dispatch, a passenger gives their origin and destination when they call, and the system assigns them to one car at once and for good. The assessment asks for a discrete-time model of that system, with a scheduler that serves everyone, keeps total time low, and respects capacity and direction.

## Users

- The assessment reviewer, who reads and runs the repository.
- The author, who presents the results and explains the design in the follow-up meeting.

## Main uses

- Run one request file, and get the position log, passenger log and summary statistics.
- Compare configurations on identical requests.
- Generate repeatable traffic.
- Read the statistics, logs and charts.

## Success

- The simulation is correct: it meets every requirement in the PDF, and the tests show it.
- Comparisons are reproducible: the same inputs and settings give the same files.
- Limits are stated plainly.
- The author can explain the design.

## Scope

| Kind | What |
| --- | --- |
| Required by the PDF | The simulator, the request function, the position log, summary statistics, a public repository, the README, and visualisations and statistics for the follow-up presentation |
| Bonus items | All three: several algorithms, express elevators, and fairness against efficiency |
| Added by the owner | The target algorithm `marginal_insertion` and its variant `rush_express`, three seat behaviours, guards with seat hold, simulated suites and case studies, the presentation deck and the published results |

## Non-goals

- Controlling real elevators, or proving real-world capacity.
- Showing that one algorithm is best in every building and traffic pattern.
- Anything an approved decision leaves out, such as sky lobbies, stop time and the assignment rules.

## Constraints

- Follow the PDF strictly. It is the scope boundary.
- Record every assumption and open question in `assumptions_made.md`.
