# AGENTS.md

Python simulation of a destination-dispatch elevator system, built for the take-home assessment in `docs/Take_home_Elevator.pdf`. It compares six dispatch algorithms under simulated traffic, and a person judges which is best.

**Claude Code:** follow [CLAUDE.md](CLAUDE.md) as well. **Other agents:** its Python, code and test sections apply to you too.

## Project documents

| Document | Holds | Read it when |
| --- | --- | --- |
| [sdlc/intent.md](sdlc/intent.md) | Why the project exists, and what success means | Judging whether a request fits the project |
| [sdlc/spec.md](sdlc/spec.md) | The behaviour contract | Building or changing behaviour. Section 5 gives each requirement's status, section 6.3 the module rules, and section 16 the conflicts already decided and the rules still Open |
| [sdlc/plan.md](sdlc/plan.md) | Sequencing and approvals | Starting any work. Section 13 holds the gate approvals, and section 14 the work since the last gate |
| [sdlc/assumptions_made.md](sdlc/assumptions_made.md) | Decisions, their reasons, and what superseded them | A detail is undefined, or a document cites an ID such as D18 or M6 |
| [sdlc/algorithm_research.md](sdlc/algorithm_research.md) | Published background. Its mechanisms are AS1 to AS10 | Citing published work or a reference such as [9] |

When sources disagree, spec section 2 sets the order, with the PDF first.

## Workflow

Every phase is done and every gate decided, so work comes only from the owner's requests.

1. Record a request that changes behaviour, scope or publishing as an entry in `sdlc/assumptions_made.md`, with any new assumption.
2. Update the spec and plan sections it affects (Decision consistency, below).
3. Do the work, until its tests pass and the checks in `CLAUDE.md` are clean.
4. Add it to plan section 14, and report what was done, what wasn't verified, and what remains.

If the owner opens a new phase, plan sections 2 and 3 apply again, gate included.

## Rules

- **Gates.** A phase starts only after a person records approval in plan section 13. Ask and wait at every gate, however small the next phase looks.
- **Scope.** The PDF is the boundary. Build what the PDF or `assumptions_made.md` calls for, and raise anything else as a concern.
- **Present, never judge.** Outputs are statistics and charts in fixed order, and a person decides. A rank, winner, "best" label or sorted-by-value result is always a defect (R-31).
- **Public boundary.** The GitHub repo, private until the owner makes it public, holds the code, tests, README, charts, the final logs and statistics, the presentation (M40), this file, `CLAUDE.md` and the five documents above (M42). `docs/` and the other files in `sdlc/` stay local, out of every commit. Push, or change the repo's visibility, only when the owner asks, each time (M39).
- **Owner's words.** The README's time spent and its conclusion on which option is best are the owner's. Keep them as written, and change them only at the owner's request (M39, C2).
- **Reviews.** A review request is read-only, and authorises no edits or commits. Report each finding with its severity, trigger, consequence, evidence and suggested fix.
- **Decision consistency.** When a decision changes behaviour or scope, update every spec section it affects in the same change, and mark each entry it replaces Superseded (M41).
- **Completion.** Passing tests are necessary, not sufficient. Check the request's acceptance criteria, and state what wasn't verified and what limits remain.
