# Elevator dispatching algorithms: research findings

Prepared 2026-10-30 for the destination-dispatch simulation spec. Claims cite the numbered references in section 8, which state how much of each source was actually read. Statements marked **(our derivation)** are reasoning from the assessment's rules, not published results, and have not been checked by simulation.

**Later decisions.** After this report was written, these decisions replaced some of its findings. `assumptions_made.md` and `spec.md` take precedence over this report, whose findings are otherwise left as written.

| Topic | This report says | Decided instead | Entry |
| --- | --- | --- | --- |
| Stop time | Run a `stop_ticks` sensitivity pass, and test a wait to transit weight (sections 1 and 5) | Stops take no time, and there is no `stop_ticks` setting, because the PDF doesn't ask for one | T4 |
| Seed spread | Treat differences smaller than the spread between seeds as noise (section 6) | The spread describes the results and isn't a significance test. Configurations run the same inputs, so gaps are compared seed by seed | G11 |
| Trimming | Trim warm-up and end periods (section 6) | Nothing is trimmed, because the PDF's statistics cover all passengers | G12 |
| Lineup | Five algorithms (section 1) | Six. `rush_express` was added, and it is the project's own design: no source in this report describes it | M31 |
| Mechanisms | All ten in the test matrix (section 5) | Built: AS2, AS3, AS5, AS6 and AS10. The assignment-time rules AS1, AS4, AS7, AS8 and AS9 weren't built | M34 |
| Stage sizes | 4,500 and about 6,100 runs (section 5) | The final counts are in spec section 13 | M34 |
| D12 | Still pending research (section 7) | Accepted in Round 5 | D12 |

## 1. Summary

**The target algorithm is established practice, not a new idea.** Online pickup/drop-off insertion that minimises marginal total passenger time is the same idea as ThyssenKrupp's ETD (Estimated Time to Destination) [1], Schindler's Miconic-10 allocation [11] and Hiller and Tuchscherer's Best Insertion, which an industry partner deployed in real systems [8]. Its roots are the sequential insertion heuristics of the dial-a-ride literature [21], [22]. ETD's published cost is the new passenger's time to destination plus the delay caused to everyone else [1]. That is exactly a marginal cost.

**Our constraints collapse the algorithm to one decision: which car.** Immediate, final assignment leaves one unassigned passenger at each decision [7], [9]. Under collective control, which is our LOOK rule, the stops of any set of passengers have a unique route [7]. So there is no insertion position to choose: the algorithm simulates each eligible car with and without the new passenger and picks the cheapest. The strongest finding here is that exact reoptimisation gains almost nothing in this setting. Under immediate assignment, Hiller et al. found waiting times "almost identical" between exact reoptimisation and Best Insertion, and solved each decision by simple enumeration in at most 0.01 s [9]. MILP, branch-and-price and genetic search therefore add cost without benefit for us, and all three are excluded.

**One assumption of ours weakens the literature's main benefit.** Published gains come mostly from grouping passengers so that cars make fewer stops [1], [3]. With stops costing 0 ticks that mechanism disappears, so the gap between the target and simple baselines should be smaller than published figures suggest **(our derivation)**. Differences will come from how far each sweep extends and from seat shortages. A `stop_ticks` sensitivity run is essential, otherwise the comparison measures our simplification rather than the algorithm. G7 plans one pass at `stop_ticks = 1`, but a published stop costs about 5 floors of travel (7.19 s against 1.45 s per floor [14]), so a value near 5 should be added.

**A hard maximum wait cannot be guaranteed, and that shapes the fairness work.** Requests can't be refused, so under sustained overload no mechanism can bound waiting time **(our derivation)**, consistent with [7] and [9]. LOOK alone bounds waiting at about one round trip when seats are not scarce **(our derivation)**. The real risk is a passenger whose assigned car arrives full on every pass, because final assignment means they can't be moved. Seat reservation closes that gap. D11's strict behaviour already includes it, so a passenger's wait is bounded by their queue position on that car **(our derivation)**. The minimum-time behaviour (D12) and weighted behaviour (D14) do not include it, so they need a guard to satisfy D10. Cross-floor seat reservation has no published elevator source, so it needs extra testing. See section 5.

**Recommended lineup.**

| Role | Algorithm | Why |
| --- | --- | --- |
| Target | `marginal_insertion`: marginal total time with a capacity-aware forward simulation | The chosen target (D7). Delay weighting is a setting (D14), so the fairness variant is the same code |
| Comparator | `eta`: minimise the new passenger's predicted wait | Published step below ETD. Shows what counting delay to others adds. Almost no extra code |
| Baseline | `nearest_car`: Barney's figure of suitability | Named in the PDF, classic reference point |
| Baseline | `zone_based`: static zones by origin floor | Named in the PDF |
| Baseline | `round_robin` | Named in the PDF, the floor for "no intelligence" |

**Recommended mechanism set for the test matrix** (detail in section 5). Boarding behaviours, already decided: strict (D11), minimum-time (D12), weighted (D14). Guards at boarding: maximum skip count and wait-limit expiry, each with a seat hold. Assignment-time rules: predicted wait limit, round-trip cap, convex wait cost, min-max predicted wait, seat-space check with headroom. Control: minimum-time with no guard.

**Terms.** A *group* is a set of cars controlled together. A *hall call* or *landing call* is a request made at a floor; a *car call* is one made inside the car. *Collective control* is the rule that a car serves calls in floor order in its direction of travel, then reverses. *Up-peak*, *down-peak* and *interfloor* describe traffic into, out of and within a building. *Immediate assignment* tells the passenger their car at once; *delayed assignment* decides shortly before arrival.

## 2. Comparison table

"Adaptable" means the published version doesn't meet the constraint but a simple variant can. Effort is relative to a simulator that already has LOOK movement and a forward-simulation helper.

| Algorithm | What it optimises | Immediate | Final | Online | Capacity-aware | LOOK | Effort | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Marginal insertion (target) | Total time of the new passenger plus delay to others | Yes | Yes | Yes | Yes, through forward simulation | Yes | Medium | **Implement** |
| ETD [1], [2] | Same, with optional "pain" curves | Yes in full destination mode | Yes in full destination mode | Yes, but the product also learns traffic | Not described in the papers | Yes [7] | Same code | **Implement** as the target. Pain curve becomes the cost setting |
| Best Insertion, CBI [8], [9] | Cost increase over all calls | Yes | Yes | Yes | Penalty [9] or ignored [8] | Adaptable | Same code | **Implement** as the target. Position choice is not available under LOOK |
| Miconic-10 allocation [11] | Combined wait and delay | Yes | Yes | Yes | Yes, hard filter at allocation | Yes | Same code | Its seat filter is a mechanism in section 5 |
| ETA [1], [4] | New passenger's wait only | Yes | Yes | Yes | Not by itself | Yes | Low | **Implement** as comparator |
| Round robin | Nothing. Even share of calls | Yes | Yes | Yes | No | Yes | Low | **Baseline** |
| Nearest car, figure of suitability [4], [19] | Proximity and direction | Yes | Yes | Yes | No | Yes | Low | **Baseline** |
| Static zoning [4], [18] | Fewer stops, reduced conflict | Yes | Yes | Yes | No | Yes | Low | **Baseline** |
| Dynamic sectoring [16] | Same, with moving boundaries | Adaptable | Adaptable | Yes | No | Yes | Medium | **Exclude.** Designed for hall calls with no known destination. Forward simulation already uses more information. Primary text not read |
| Collective control [7], [17] | Single-car stop order | n/a | n/a | Yes | Yes, full cars bypass | It is LOOK | Done | **Exclude as a dispatcher.** It is the movement rule of every algorithm (D5) |
| Longest queue first [14] | Oldest waiting call first | No | No | Yes | Not stated | Partly | Medium | **Exclude.** Controls car stops, not assignment. The idea survives as aging at boarding |
| Highest unanswered floor first [14] | Highest waiting floor first | No | No | Yes | Not stated | Partly | Medium | **Exclude.** Same reason. Down-peak rule |
| SCAN, LOOK [38], [39] | Sweep order | n/a | n/a | Yes | No | It is LOOK | Done | **Exclude as a dispatcher.** Already the movement rule |
| SSTF [38], [39] | Nearest next stop | n/a | n/a | Yes | No | **No** | n/a | **Exclude.** Reverses with work ahead, and starves |
| Genetic algorithm [4], [7], [32] | Any cost, usually wait and journey | Possible | Possible | Yes | Can be | Yes | High | **Exclude.** With one unassigned passenger the search space is just the car list, so enumeration is exact |
| MILP or reoptimisation [7], [9], [10] | Exact snapshot cost | Possible | Possible | Yes | Yes | Optional | High | **Exclude.** Under our rules it reduces to enumeration [9]. Delayed-assignment gains are not allowed |
| Reinforcement learning [14], [15] | Learned reward, squared wait in [14] | No | No | Yes when running, trained on traffic | Partly | Partly | Very high | **Exclude.** Controls stops, needs 60,000 simulated hours [14], and hides results from review |
| Decision-theoretic ESA-DP [12], [13] | Expected wait with unknown destinations | Yes | Yes | Yes | Not stated | Yes | High | **Exclude.** Its machinery handles unknown destinations, which we know. Reduces to our forward simulation |
| Relative System Response [33] | Time penalties minus bonuses | No, reassigns | No | Yes | Yes, expected load | Yes | Medium | **Exclude.** Hall-call method with learned traffic. Its load check informs section 5 |

## 3. The target algorithm in detail

### Origin

| Year | Work | Contribution |
| --- | --- | --- |
| 1980 | Psaraftis [20] | Dynamic single-vehicle dial-a-ride with capacity. Each new request triggers an update over known inputs only. Priority rules prevent indefinite deferment |
| 1984, 1986 | Jaw; Jaw et al. [21], [22] | ADARTW: sequential insertion of customers into vehicle tours, with limits on time shift and ride time, and a nonlinear objective guiding insertions. Tested on 2,600 customers |
| 1995 | Savelsbergh and Sol [25] | General pickup and delivery problem. Survey of problem types |
| 2013 | Ma et al. [24] | T-share: insert a new trip into the taxi schedule with least added distance, keeping existing order, with capacity and slack-time checks |
| 2018 | Tong et al. [23] | Formal insertion operator, and a proof that no constant competitive ratio exists for the unified problem |
| 1996, 2002 | Schindler Miconic-10 [11] | Fit the new passenger into current routes. Pick the car with the shortest combined wait and delay |
| 2002 | Smith and Peters [1] | ETD: explicit cost of new passenger's time plus system degradation |
| 2007 | Hiller and Tuchscherer [8] | Best Insertion for immediate-assignment destination calls, deployed by Kollmorgen |

The elevator problem is a dial-a-ride problem: a passenger is a pickup and a delivery that the same vehicle must serve in order, within a capacity limit. Ruokokoski et al. model it this way, with paired pickup and delivery vertices [7]. Hiller et al. note their method is conceptually similar to a vehicle routing algorithm [9]. Cordeau and Laporte survey dial-a-ride models and algorithms [26].

### Definition

Tong et al. define insertion as finding a new feasible route with minimal added cost by inserting a request's origin and destination into the existing route, such that existing stops keep their order [23]. Basic insertion tries every pair of positions, which is O(n²) pairs and O(n³) overall. Their dynamic program reduces this to O(n) [23].

In a group, the operation runs per vehicle and the cheapest vehicle wins [23], [24]. Hiller and Tuchscherer state the elevator form: insert the new call at all feasible positions in the scheduled tours, and assign it where cost rises least [8].

### Cost formula

ETD's published cost for assigning a new passenger to elevator *e* is [1]:

```text
TC_e = sum over k = 1..n of SDF_e,k  +  ETD_e
```

`ETD_e` is the new passenger's estimated time to destination on car *e*, found by mapping the car's trip forward through all intermediate stops. `SDF_e,k` (System Degradation Factor) is the delay the new passenger causes to passenger *k*, found by mapping *k*'s journey before and after. The passenger with the lowest total cost gets that car [1].

In our terms, let `P_e` be the unfinished passengers of car *e* (waiting or riding), *r* the new request, `t_k` the request tick, and `D_k(S)` the predicted drop-off tick of *k* when the car serves set *S*:

```text
cost(e, r) = sum over k in P_e + {r} of g(D_k(P_e + {r}) - t_k)
           - sum over k in P_e       of g(D_k(P_e)       - t_k)
```

With `g(x) = x`, this equals `ETD_e + sum SDF_e,k`, because the `t_k` terms cancel. This matches our objective, mean total time [7, equation 13]. Three details matter:

- **Measure from the request tick, not from now.** Ruokokoski et al. add each request's elapsed time to the objective [7]. With a nonlinear `g`, this is what makes older passengers count for more.
- **Two-part cost.** The 2004 ETD "pain index" scores waiting and transit separately [2]: `g_w(wait) + g_t(transit)`. Waiting three times as painful as transit is one published example.
- **Simulate to the end.** Nikovski and Brand evaluate until all known passengers are delivered and ignore future arrivals, arguing the error is benign because random arrivals wash out the effect [12].

The published worked example makes a good test fixture. Fred, 7 to 2, has costs of 50, 55 and 190 on three cars, with 10 s per stop [1], [3]. Reproducing it needs `stop_ticks` set.

### Capacity

The literature has five approaches. None is both hard and always feasible.

| Source | Treatment | Limit |
| --- | --- | --- |
| Miconic-10 [11] | Allocate to a car only if enough space remains, based on calls already allocated | Hard filter. What happens when no car qualifies is not stated |
| Hiller, Tuchscherer [8] | Ignore capacity in planning. A passenger who finds a full cabin re-issues the call | Not allowed here (re-issue means reassignment) |
| Hiller et al. [9] | Per-call penalty for exceeding capacity at the pickup stop, set equal to 300 s of waiting. Fill to 80% of rated capacity | Soft. They state capacity violations cannot be strictly forbidden |
| Ruokokoski et al. [7] | Routes limited to one round trip, so no full-car bypass | They could not express bypass linearly, and heavy traffic becomes infeasible |
| Otis [33] | Predict load at the call floor. If above 80%, a 200 penalty effectively excludes the car | Hall-call method |

Forward simulation avoids this choice **(our derivation)**. Capacity stays hard at boarding and soft at assignment. A passenger who can't board in the simulated plan simply waits for the next pass, and that extra time appears in the cost with no separate penalty. Assignment can't be hard because a passenger must always be assigned. The simulation helper must use the same boarding rule as the real step (D9), or predictions will diverge from outcomes.

### Adapting insertion to fixed LOOK ordering

Ruokokoski et al. show that collective control plus four boarding assumptions defines a **unique route for any set of requests**, so the decision reduces to which car takes which request [7]. Their rule is the same as our D3, including going to the furthest opposite-direction pickup before reversing [7], [17]. The classic loop over positions therefore disappears. In place of it:

1. For each eligible car (`can_serve`), copy the car state.
2. Simulate to completion without *r*, then with *r*. Cache the first result per car between assignments.
3. Assign to the lowest cost, with a deterministic tie-break.

Work is about O(cars × pending stops) per request, which is cheap in Python **(our derivation)**.

Do not splice in a local delta. Hiller et al. show a small insertion can change a schedule's structure completely, because of the first-stop pickup rule: a passenger must board the first time their car stops at their floor going their way, which adds drop-off commitments that ripple [8], [9]. Re-simulating handles this for free.

An insertion can land in any of three phases of the car's round trip: the current sweep, the opposite sweep, or the sweep after two reversals [7]. Ruokokoski et al. model an idle car as two cars, one up and one down [7]. For us an idle car simply heads to the new passenger.

Fixed order has a known cost. On small snapshot problems in light and normal traffic, free routing improved average journey time by 7.13% in down-peak and 1.41% in mixed traffic, and not at all in up-peak, while average waiting time was unchanged [7]. For one entrance floor in up-peak with unlimited capacity, the two are provably equal [7, Theorem 1]. Since D3 fixes the order anyway, we accept this. It is still worth stating in the README.

### Known weaknesses

- **Myopia.** It assumes no future arrivals [12], [20].
- **Commitment.** A car chosen now can be the wrong one 5 seconds later, and in traffic with little grouping, destination systems offer no meaningful gain over conventional ones [1], [3].
- **Saturation.** Dispatch goals can become self-defeating above handling capacity [4]. Peters reports a destination system whose handling capacity fell from about 17% to about 10% when overloaded, also seen in real buildings [5].
- **Long waits.** A linear objective can defer individuals. Hiller and Tuchscherer restricted insertion positions for this reason [8]. In the ETD example, a choice 1 s better overall gives one passenger 60 s instead of 32 s [2].
- **No worst-case guarantee.** See section 5.
- **Bunching** of cars is a natural effect that needs care [4].
- **Ties at `stop_ticks = 0`.** A passenger whose trip lies inside a car's current sweep delays nobody, so many cars can cost the same **(our derivation)**. The tie-break must be deterministic for S6 and may noticeably affect results.

### Relationship to ETD

**ETD is the same idea as the target algorithm.** Both minimise the new passenger's time plus marginal delay to others by mapping trips forward, and both commit once the passenger is told their car [1]. Grouping is not programmed in ETD; it emerges from the cost [1].

| Aspect | ETD | Our target |
| --- | --- | --- |
| Cost | `ETD_e + sum SDF` [1] | Same, as a difference of two simulations |
| Time | Seconds, door and stop times | Ticks, stops 0 by default |
| Benefit source | Grouping, fewer stops [1], [3] | Sweep extent and seats **(our derivation)** |
| Capacity | Not described beyond learned capacity factor and full-car bypass [1] | Explicit in the forward simulation |
| Nonlinear cost | Pain curves, deliberately not exponential [2] | Exponent setting |
| Hall-call mode | Yes, with inferred destinations and reallocation [1] | Not needed |
| Learning | Traffic and capacity learning [1] | Not allowed (online only, no learned future) |
| Reallocation | None in full destination mode, except special cases such as a car out of service [1] | None |
| Status | Patented commercial product; internals unpublished [2] | Open description |

## 4. Other algorithms

### Round robin

Assign requests to cars in cyclic order, skipping cars that can't serve the trip. No primary elevator source describes this as a group control method; it is listed in the PDF. The description here is ours. It uses no state, so it is a clean lower reference.

### Physical nearest car and figure of suitability

Peters defines the basic rule as allocating the closest car that can stop in time for the call, and notes it works reasonably until demand exceeds handling capacity [4], [5]. Barney's version scores each car with a figure of suitability (FS), and the highest wins, where N is floors minus 1 and d is distance in floors [19]:

| Car state | FS |
| --- | --- |
| Moving toward the call, call in same direction | `(N + 2) - d` |
| Moving toward the call, call in opposite direction | `(N + 1) - d` |
| Moving away from the call | `1` |

This wording comes from a public project README crediting Barney [19]. The handbook's contents confirm a nearest-car section and tables of figures of suitability [16], but I could not read them. The handling of idle cars is unverified; treating an idle car as moving toward the call is our suggestion.

### Zone or sector based

**Static.** Floors are divided among cars. In the version Patiño-Forero et al. attribute to Barney, there is one zone per elevator, and each elevator serves its zone collectively [18]. Sectoring reduces stops per round trip and so raises handling capacity, which is why it is used in down-peak [4]. In Crites and Barto's down-peak tests, SECTOR had the worst average wait (21.4 s) [14]. For destination dispatch, zone by origin floor. B8 needs a fallback when the zone's car can't serve the trip.

**Dynamic.** Sector boundaries vary from trip to trip with demand [18]. Barney describes fixed-common, fixed priority-timed and dynamic systems [16], but I did not read those sections. Excluded in section 2.

### ETA-based group control

Allocate the car that can reach the call soonest, with allowance for intermediate stops [1], [4]. TKE used this from 1985 [1]. Peters adds a coincident-call bonus for a car already stopping at the floor, which reduces stops at the cost of some waits [4]. In our simulator this is the target's forward simulation scored on the new passenger's wait only. A similar wait-only adaptation was beaten by Best Insertion, especially in travel times and upper wait quantiles [8].

### Collective control

Six rules define it, per Hautamäki citing Barney and Al-Sharif [17]: serve calls in floor sequence; bypass opposite-direction landing calls; bypass when full; if only opposite-direction landing calls remain ahead, go to the furthest and reverse there; reverse when nothing remains ahead; stay still when no calls remain. This is D3. Direction reversal happens only when empty, because taking a passenger the wrong way is considered unacceptable [4], [7].

### Longest queue first and highest unanswered floor first

Both are verified from Crites and Barto [14], who cite Bao et al. HUFF gives priority to the highest floor with people waiting. LQF gives priority to the queue holding the person who has waited longest, so despite the name it is oldest-first rather than most-people-first. In down-peak they gave average wait 16.8 s and 19.1 s, and system time 48.6 s and 46.6 s [14]. These control which floor cars serve, so they conflict with D5.

### Disk scheduling analogues

SCAN moves the arm one way serving requests in order, then reverses, and is called the elevator algorithm [38]. LOOK is the common variant that reverses at the last request rather than the disk edge, which matches D3. I could not verify where the name originated. SSTF always serves the nearest request. It gives shorter mean times but high variance and starvation [38], [39]. SCAN was introduced to control that variance [39]. Teorey and Pinkerton added variance as a measure of discrimination against individual requests [41]. Disk results carry over only loosely, because a disk has no capacity limit.

### Metaheuristic, exact and learned methods

**Genetic algorithms.** Each gene maps a call to a car [4]. Tyni and Ylinen describe a GA group control system [31]. KONE uses one: a random start of 50 solutions [17], with chromosomes that also pick the round trip for each call [32]. The KONE patent's preferred embodiment delays allocation, though immediate allocation is claimed as an option [32]. With immediate assignment, one call is open, so the search is trivial [7], [9].

**MILP and reoptimisation.** Ruokokoski et al. solve the problem by branch and bound [7]. Hiller et al. use column generation and branch-and-price [9], [10]. Their key results are in section 1. Delayed assignment gave much better waits at high load but no higher handling capacity than immediate assignment [9]. Delayed assignment is excluded by the PDF.

**Reinforcement learning.** Crites and Barto used a team of Q-learning agents, one per car, in a 10-floor, 4-car building, minimising squared wait [14]. It beat the heuristics on average wait and system time in all three reported tables, for example 41.7 s system time against 46.6 to 53.2 s, after 60,000 simulated hours of training [14]. It did not always win on share of waits over 60 s [14]. Their agents choose stop or continue, which breaks D5, and they work with hall calls.

### Commercial systems

| Maker | Verified from a primary source | Not verified |
| --- | --- | --- |
| ThyssenKrupp | ETD cost, modes, reallocation policy, pain curves [1], [2] | Exact pain curves, internals |
| Schindler | Miconic-10 fits the passenger into current routes, picks shortest combined wait and delay, checks space, and never reallocates [11]. Earlier patents: passenger-seconds cost [36], operating-cost allocation [37] | Cost formula details |
| KONE | Genetic allocation with round-trip genes under collective control, up to 3 round trips [32]. Fixed and open calls [32] | Current product algorithm |
| Otis | Relative System Response for hall calls [33]. Channeling is cited in [1] but I did not read it | Any destination-dispatch method |
| Mitsubishi, Hitachi | Long-wait rules in patents [34], [35]. Decision-theoretic research [12], [13] | Current products |
| Kollmorgen | Controlled Best Insertion deployed [8] | |

Early patents are not evidence of present products.

## 5. Fairness and starvation: how "no passenger waits forever" is enforced

### What is known about fairness and efficiency

Average squared wait is a common objective because it keeps waits low and encourages fair service [14]. Brand and Nikovski note that dissatisfaction likely grows faster than wait, and that squared cost penalises long waits more [13]. Their risk-averse scheduler cut squared wait from 1737 to 1273 and waits over 60 s from 9.04% to 7.77%, with average wait no worse [13]. Hiller et al. used squared wait and travel times in 2009 explicitly to avoid long waits [10].

Weighting wait above transit has a price. ETD with waits 3 times as painful improved waiting significantly at the cost of slightly longer total time [2]. Peters warns that favouring the next car also loses the grouping gain [3].

Smith's rule (WSPT) minimises weighted completion time on a single machine by ordering jobs by processing time divided by weight, proven by an adjacent-swap argument [48]. It applies to us only by analogy, at boarding: when seats are short, shorter rides first favours mean time. It is not a theorem here, because a car's time is not a set of independent jobs **(our derivation)**. Like SSTF, it risks starving long rides. This analogy is the only support I found for D12. I found no elevator study of shortest-ride-first boarding. Hiller's idealised system chooses boarders by optimisation, not ride length, and found that boarding control pays off [8], [9].

### When a passenger can actually wait forever (our derivation)

1. **Without seat shortages, LOOK alone bounds service.** A car finishes its sweep, makes one opposite sweep and returns, so wait is under `2(n-1)` ticks and total time under `3(n-1)` ticks, times about `1 + stop_ticks`.
2. **Seat shortages break that bound across floors.** Suppose a car leaves the lobby full on every trip, with passengers going beyond floor 5. A passenger at floor 3 assigned to it is never reachable: the car is full every time it passes. Boarding in request order at floor 3 doesn't help, because the competing passengers boarded at a *different* floor. The fix must act before the car reaches floor 3, which is what D11's seat reservation does.
3. **Overload rules out a hard time limit.** Requests can't be refused, so if arrivals exceed throughput, queues grow without limit. Hiller et al. say capacity violations can't be strictly forbidden [9], and hard windows make heavy traffic infeasible [7].
4. **Finite inputs always finish.** After the last request, each car takes at least one waiting passenger per round trip. So for our finite runs, "forever" means waits that grow with input length. The O4 `max_ticks` guard remains a safety net.

Theory agrees that guarantees are limited. No competitive online algorithm exists for maximum flow time in dial-a-ride [27]. A competitive result needs a "reasonable load" assumption [28].

### Where a mechanism can act

Assignments are final, cars can't reverse with work ahead, and capacity is hard. So only two points remain:

- **A: choosing a car at assignment time.** Steers new passengers. Can't help anyone already assigned, except by steering others away from their car.
- **B: choosing who boards when seats are short.** Can reorder boarding or leave a seat empty.

This model is unusually predictable. Destinations are known, so a car's plan changes only when it gets a new passenger [11]. If a prediction filter at A never falls back, its predictions hold exactly **(our derivation)**.

**Guarantee classes used below.** *Hard*: an unconditional bound. *Conditional*: a hard bound while a stated condition holds. *Order*: limits overtaking, not time. *Soft*: discourages only.

### Mechanisms for the test matrix

Mechanism IDs start with AS, for anti-starvation. They were M1 to M10 until 2026-11-03, and were renamed so they don't collide with the M entries in `assumptions_made.md` (M41).

**AS1. Maximum wait, checked at assignment** (`wait_limit_assign`)

- Trigger: a car's plan, with the new passenger added, would give someone a predicted wait above W.
- Action: treat that car as ineligible. If no car qualifies, use the lowest-cost car anyway, as CGC does [9].
- Guarantee: conditional. Every wait stays at or below W as long as no fallback occurs. Report a fallback count.
- Sources and values: Hitachi treats a car as non-serviceable if it "provides an excessively long waiting time" [34]. CGC's "high threshold time" avoids pushing another request past a limit [9]. Ruokokoski et al. use W = 400 s and journey limit 800 s as hard windows [7]. Mitsubishi uses 60 s in a sample zone, and sets the limit as 3 times the presumed mean wait [35]. Brand and Nikovski describe a soft expected-wait limit [13]. Time windows in dial-a-ride [21] and deadlines in ride-sharing [23], [24] are the same idea.
- Drawbacks: W must be tuned. Filtering can raise mean time. Falls back under overload.

**AS2. Maximum wait, expiry at boarding** (`wait_expiry`)

- Trigger: elapsed wait reaches W.
- Action: the passenger gets top boarding priority, and a seat hold (AS10) if enabled. Cars can't jump to them.
- Guarantee: with AS10, conditional, as AS3. Without it, order only at the passenger's own floor.
- Sources and values: Linux `mq-deadline` gives each request an expiry and serves expired ones ahead of sweep order: reads 500 ms, writes 5 s, with limits marked "SOFT" and checks only between batches [42], [43]. Seltzer et al. enforce a 30 s maximum [39].
- Drawbacks: a disk can jump to an expired request, and our car can't, so this is weaker here. Many expiries at once degrade to chasing the oldest passenger, a risk Smith and Peters designed against [2].

**AS3. Maximum skip count** (`skip_limit`)

- Trigger: the passenger's own car reached their floor going their way and they could not board S times.
- Action: as AS2.
- Guarantee: with AS10, an upper limit on skips, and conditional on time: at most `(S + 1 + rank/C)` round trips, for rank among flagged passengers **(our derivation)**. Without AS10, order only.
- Sources and values: the closest elevator source is KONE's bound of 3 round trips, or two complete round trips waited [32]. `writes_starved` = 2 is a direct skip limit, "max times reads can starve a write" [43]. FR-FCFS+Cap limits younger accesses bypassing an older one, set to 4 [44]. Constrained position shifting allows k positions from FCFS order, typically 1 to 3 [46]. Bounded bypass is the formal concept [52]. Psaraftis prevents indefinite deferment through priority rules [20].
- Drawbacks: no elevator source gives this exact rule. Count-based, so slow in tall buildings where a skip costs many ticks.

**AS4. Round-trip cap at assignment** (`round_trip_cap`)

- Trigger: the plan with the new passenger needs more than R passes to board someone.
- Action: as AS1.
- Guarantee: conditional, as AS1. It is the assignment-time form of the skip count.
- Sources and values: R usually 1 or 2, at most 3 in very heavy traffic [32].
- Drawbacks: fallback under overload. Counts passes, not time.

**AS5. Strict request order with reservation** (D9 strict behaviour, D11)

- Trigger: seats short at a floor.
- Action: seats go in request order per car and direction. A later passenger boards only if a seat remains for every earlier passenger waiting ahead (D11).
- Guarantee: order across floors, for one car and direction. A passenger's rank among earlier passengers is fixed at assignment and can only fall, so wait is at most about `(rank/C + 1)` round trips, even in overload **(our derivation)**. This alone satisfies D10.
- Sources: first-come boarding at one floor is the usual assumption [7, Assumption 2], [8], [9]. The cross-floor reservation in D11 is a project decision. I found no published elevator precedent beyond Miconic-10's allocation-time space check [11].
- Drawbacks: seats can ride empty past later passengers, and it gives up reordering gains. Hiller and Tuchscherer found boarding control pays off [8].

**AS6. Aging at boarding** (D9 weighted behaviour, D14)

- Trigger: always, when seats are short.
- Action: rank by a score that improves with wait. D14's score is `(1 + weight × ticks waited ÷ floors) ÷ ride length`.
- Guarantee: soft. For weight above 0, age eventually beats any fresh passenger at the same floor, but not a car already filled at earlier floors **(our derivation)**. So D14 needs a guard to satisfy D10, or reservation by score (see below).
- Sources and values: Kleinrock priority `q(t) = b(t - T)^r`, running from fixed priority at r→0 to FCFS at r→∞ [47]. Seltzer et al.: `weighted = actual × (M - E) / M`, M = 30 s, within 1 to 2% of unaged throughput with a sharp drop in maximum response [39]. Otis lowers penalties for long-registered calls [33]. ETD gives an older hall call more weight, which it says inherently avoids long waits [1], but ETD can still reallocate hall calls, which we can't. D14 is Smith's rule [48] with a weight that grows linearly with wait, Kleinrock's first-order form [47] **(our derivation)**.
- Drawbacks: a same-floor rule, so it doesn't fix cross-floor seat starvation alone. Tuning.

**AS7. Convex wait cost at assignment** (`convex_cost`)

- Trigger: always.
- Action: use `g(wait) = wait^p` in the section 3 cost. D14's delay weighting is already a cost of this kind: weighting each tick of delay by `1 + w × wait / n` adds up to about `x + (w / 2n) x²` **(our derivation)**.
- Guarantee: soft.
- Sources and values: p = 2 in [10], [13], [14]. An example ETD curve is nearly flat for the first 10 s of wait and 30 s of transit, then rises, and is deliberately "not exponential" so an overloaded system doesn't end up always chasing the oldest call [2].
- Drawbacks: can only steer new passengers. Under final assignment it cannot rescue an assigned passenger, which is a real limit of ETD's aging [1]. Too steep a curve hurts in overload [2]. May raise the mean, the G1 measure.

**AS8. Min-max predicted wait at assignment** (`minmax_wait`)

- Trigger: always.
- Action: pick the car with the smallest maximum predicted wait over passengers affected.
- Guarantee: soft, but minimises the predicted worst case at each step.
- Sources: Hitachi's third embodiment, which allots a call to the car giving "a minimum value among these maximum forecast waiting times" [34].
- Drawbacks: ignores travel time, so the mean will probably suffer. Useful as the fairness extreme of the trade-off chart.

**AS9. Seat-space check with headroom at assignment** (`seat_headroom`)

- Trigger: predicted load on the passenger's sweep would exceed ρ × capacity.
- Action: treat the car as ineligible, or fall back to the lowest-cost car if none qualifies.
- Guarantee: conditional. It reserves seats on paper, so it prevents the left-behind case while no fallback occurs.
- Sources and values: Miconic-10 allocates only if enough space is available [11]. Hiller et al. fill to 80% [9]. Otis uses an 80% load threshold [33]. Hitachi counts a full car as non-serviceable [34].
- Drawbacks: in a real group, 80% allows for unregistered riders, a risk our simulation doesn't have. It may simply waste seats here.

**AS10. Seat hold for a flagged passenger at boarding** (`seat_hold`)

- Trigger: a passenger is flagged by AS2 or AS3. Not needed with D11, which already reserves for all earlier passengers.
- Action: on the sweep that reaches them, boarding at earlier floors leaves a seat free for each flagged passenger ahead, oldest first.
- Guarantee: if at most C passengers are flagged per direction, they board on the next pass, because LOOK reverses only when empty, so each sweep starts with free seats **(our derivation)**. With more, they board in order, at C per sweep. This is the only recommended rule giving a hard limit on skips.
- Sources: **no published elevator source found.** Nearest evidence is Miconic-10's space reservation at allocation [11], boarding control in Hiller's idealised system [8], [9], and PAR-BS priority for marked requests [45].
- Drawbacks: an empty seat rides past waiting passengers, who may then be skipped. Needs property tests.

**One rule for all three behaviours (our derivation).** D11's reservation generalises: a passenger boards only if a seat remains for every higher-priority passenger waiting ahead on that car and direction. With request order as the priority, this is D11. With D14's score and a weight above 0, age eventually puts any passenger on top, so it also satisfies D10. With D12's shortest ride, priority never changes, so a long ride can still starve, and D12 needs AS2 or AS3. D14 as written says only who gets seats, so the spec should state whether it looks ahead.

### Excluded mechanisms

| Mechanism | Trigger, action | Guarantee | Source, values | Drawback | Why excluded |
| --- | --- | --- | --- | --- | --- |
| Hard time windows that may reject | Deadline would fail, so reject | Hard, for accepted requests | Ride-sharing [23], [24]; windows [7], [21] | Infeasible in heavy traffic [7] | Must serve every passenger |
| Reassign after timeout | Long wait, so change car | Soft | Schindler returns unserved calls for reallocation [36]; ETD hall calls [1] | Confusing to passengers [11] | Breaks final assignment |
| Second car, or re-issue | Car full, so send another or re-register | Soft | Otis [33]; Hiller [8] | Same | Breaks final assignment |
| Deadline jump | Expiry, so head goes to the oldest | Soft, limits "SOFT" [43] | Linux [42]; forced "bad seeks" [39] | Seek cost | Breaks LOOK. The non-jump part is AS2 |
| Earliest deadline first | Serve the earliest deadline | Hard if feasible, in real-time theory | Liu and Layland [49]; SCAN-EDF [50] | Thrashing under overload (unverified) | With one wait limit for all, deadline order **is** request order, so it equals AS5 **(our derivation)** |
| FSCAN, N-step SCAN | Freeze the queue for a sweep | Soft to conditional | Coffman et al. [38], [39], [40]; N-step [51] | Delays late nearby requests [38] | Its job is to stop near requests holding the head. A LOOK sweep is already bounded by building height, and with 0-tick stops a floor can't hold a car. Freezing would also pass waiting passengers with free seats, against D3 |
| Batch priority | Serve a batch before the next | Conditional | PAR-BS, Marking-Cap 5 [45]; `fifo_batch` 16 [43] | Throughput at batch edges [45] | Seat-level form is AS10 applied to everyone, with more waste |
| Overtake cap counted by raw overtakes | Later passenger boards first | Order | FR-FCFS+Cap 4 [44]; CPS k 1 to 3 [46] | Ordinary sweeps overtake harmlessly | Counts harmless events under LOOK. AS3 counts only real harm |
| Restricted insertion positions | Avoid deferring calls | Soft | CBI [8] | Reduced search | LOOK leaves no positions to restrict |
| Variance or risk-averse scheduling | Penalise uncertain plans | Soft | [13], [35] | Heavy computation | Uncertainty here is zero, so variance vanishes and only AS7 remains **(our derivation)** |
| Load balancing across cars | Equalise car loads | Soft | DLB [14] | Worst on share over 60 s in one table [14] | Forward simulation already prices a loaded car |
| Load bypass | Full car doesn't stop | None | [4] | | It causes skips rather than curing them, and is cost-free at 0-tick stops |
| Parking cars | Reposition idle cars | None | [4] | | Not a fairness control. D8 fixes idle behaviour |

### Mechanism comparison

| ID | Mechanism | Acts at | Guarantee | Respects final assignment | Respects LOOK | Protects across floors | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AS1 | Max wait at assignment | A | Conditional | Yes | Yes | Yes, while no fallback | **Implement in test matrix** |
| AS2 | Max wait expiry | B | Conditional with AS10 | Yes | Yes | With AS10 | **Implement in test matrix** |
| AS3 | Max skip count | B | Skip limit with AS10 | Yes | Yes | With AS10 | **Implement in test matrix** |
| AS4 | Round-trip cap | A | Conditional | Yes | Yes | Yes, while no fallback | **Implement in test matrix** |
| AS5 | Strict order with reservation (D11) | B | Order, wait bounded by rank | Yes | Yes | Yes | **Implement in test matrix** |
| AS6 | Aging (D14) | B | Soft | Yes | Yes | No, unless it looks ahead | **Implement in test matrix** |
| AS7 | Convex cost | A | Soft | Yes | Yes | Partly | **Implement in test matrix** |
| AS8 | Min-max predicted wait | A | Soft | Yes | Yes | Partly | **Implement in test matrix** |
| AS9 | Seat check with headroom | A | Conditional | Yes | Yes | Yes, while no fallback | **Implement in test matrix** |
| AS10 | Seat hold | B | Skip limit | Yes | Yes | Yes | **Implement in test matrix**, flagged as unsourced |
| | Hard windows with rejection | A | Hard | Yes | Yes | Yes | Exclude: must serve all |
| | Reassignment or second car | | Soft | **No** | Yes | | Exclude |
| | Deadline jump | | Soft | Yes | **No** | | Exclude |
| | Earliest deadline first | B | As AS5 | Yes | Yes | No | Exclude: equals AS5 |
| | FSCAN, N-step SCAN | B | Conditional | Yes | Conflicts with D3 | | Exclude |
| | Batch priority | B | Conditional | Yes | Yes | Yes | Exclude: AS10 is the targeted form |
| | Raw overtake cap | B | Order | Yes | Yes | Partly | Exclude: AS3 is the faithful form |
| | Restricted insertion positions | A | Soft | Yes | n/a | | Exclude: no positions exist |
| | Risk-averse variance | A | Soft | Yes | Yes | | Exclude: reduces to AS7 |
| | Load balancing | A | Soft | Yes | Yes | | Exclude: already priced |
| | Load bypass, parking | | None | Yes | Yes | | Exclude: not fairness controls |

### Defaults and test values

Let `RT = 2(n-1)` ticks, the longest LOOK round trip at `stop_ticks = 0`. Thresholds scale with RT because any wait limit below one RT would trigger on passengers who aren't starved. **Every default is our suggestion.** The "Published" column shows what sources actually use, and many are in seconds or other domains. As a rough scale only: at Crites and Barto's 1.45 s per floor [14], 60 s is about 41 ticks, near `2 RT` at n = 10 (36 ticks).

| Parameter | Used by | Published | Default (our suggestion) | Test values |
| --- | --- | --- | --- | --- |
| W, wait limit in ticks | AS1, AS2 | 60 s [14], [35]; 400 s [7]; 3 × mean, G = 3 [35]; 30 s disk [39]; 500 ms, 5 s kernel [43] | `2 RT` | `1 RT`, `2 RT`, `3 RT`, off |
| S, max skips | AS3 | 2 [43]; two round trips waited [32]; 1 to 3 [46]; 4 [44] | 2 | 1, 2, 3, off |
| R, round-trip cap | AS4 | 1 to 2, up to 3 [32] | 2 | 1, 2, 3 |
| Weight, aging | AS6, AS7 | Not a literature value; project decision (D14) | 1 | 0.5, 1, 2 (D14) |
| p, pure wait exponent | AS7 | 2 [10], [13], [14] | 2 | 2, 3, as comparisons to D14 |
| Wait to transit weight | AS7 | 3:1 [2] | 1:1 | 1:1, 3:1 |
| ρ, planning fill | AS9 | 0.8 [9], [33] | 1.0 | 1.0, 0.8 |
| Seat hold | AS2, AS3 | none | on | on, off |
| `stop_ticks` | environment | 10 s per stop [1]; 7.19 s [14] | 0 (T4) | 0, 1 (G7), and add 5 |

With capacity 6, ρ = 0.8 gives 4 seats. An adaptive W of 3 × the rolling mean wait is a possible later addition, based on [35]. On the 60-floor building (G6), RT is 118 ticks, so `2 RT` spans almost a quarter of the 1,000-tick arrival window. Check that those limits trigger at all.

### Recommended test design

**Stage 1.** Run every algorithm with every boarding behaviour on the G6 inputs (G7). With five algorithms and behaviours D11, D12 and D14 at three weights, that is 25 pairings × 180 inputs, or 4,500 runs.

**Stage 2.** Run `marginal_insertion` only, varying one mechanism at a time from D12 and from D14 at weight 1, because D11 needs no guard. About 17 configurations (the test values above, without the off settings) across those two behaviours gives about 6,100 runs on all inputs. Restricting to medium and heavy load cuts that by a third. Then add a few combinations:

- AS3 with AS10, and AS2 with AS10, to test the only rules with a skip limit.
- AS7 with AS3 and AS10, as the likely practical choice: steer softly at assignment, enforce at boarding.
- D12 with and without AS3 and AS10, showing the full cost of unfairness and what protection recovers.

**Deterministic starvation fixtures (our suggestion).**

- *Seat starvation:* a lobby flood that fills the car each trip, plus one mid-floor passenger going the same way past the flood's drop-offs. With one car, only AS10 can help, because assignment has no other car to choose. With several cars, also test whether assignment-time rules steer the flood away.
- *Same-floor starvation:* steady short rides plus one long ride at a floor, under shortest-ride-first. Fails without aging or a limit.
- *Overload ramp:* traffic rising past saturation, to confirm that means degrade without the collapse Peters reports [5].

**Measures to report:** the G8 statistics, which already include times left behind and Jain's fairness index, plus maximum skips for one passenger, fallback count, held-seat ticks and share above W.

## 6. Evaluation practice

### Traffic patterns

Traffic is split into incoming, outgoing and interfloor components, and intensity is a percentage of population moved in 5 minutes [5], [6], [7].

| Pattern | Incoming | Outgoing | Interfloor | Source |
| --- | --- | --- | --- | --- |
| Up-peak | 100 | 0 | 0 | [1], [7] |
| Down-peak | 0 | 100 | 0 | [1], [7] |
| Mixed or lunch | 40 | 40 | 20 | [1], [6], [7] |
| CIBSE modern office up-peak | 85 | 10 | 5 | [5] |
| CIBSE modern office lunch | 45 | 45 | 10 | [5] |

Hiller et al. also use "real" up-peak and down-peak, mixed with 5% interfloor and 5% opposite traffic [9]. Interfloor is roughly even between floors, at lower intensity (10% against 16% in their tests) [9]. Arrivals are usually Poisson [7], [14]. Templates divide an hour into 5-minute periods [5]. A constant template tests a rate; a step profile raises intensity until saturation, and is agreed practice [5], [6]. Peters advises testing past saturation [4], [5]. ISO 8100-32 offers both up-peak equations and simulation for planning [53]. Lunch traffic matters because destination dispatch gains least there [3], [6].

### Metrics and targets

- Average wait, transit and time to destination [1], [5]; quantiles at 50, 75, 90 and 100% [8], [9]; squared wait and share above 60 s [13], [14]; handling capacity, car load and queue lengths [3], [5], [9].
- Avoid interval as a quality measure; it does not correlate with waiting under destination control [5], [6].
- Targets: excellent office service is 98% of waits under 60 s and 75% under 30 s (Barney via [7]). Fair performance is median at most 25 s and p90 at most 55 s (Barney via [9]). Prestige office, worst 5 minutes: up-peak wait 20 s and transit 80 s, lunch 30 s and 100 s (CIBSE via [5]). These use real seconds, so they don't transfer directly to ticks.

### Simulation sizes in the literature

| Source | Building | Traffic and duration | Repetition |
| --- | --- | --- | --- |
| Smith, Peters [1] | 18 floors, 50 per floor, 6 cars | 12 and 15% up and lunch, 7 and 15% down | Not stated |
| Crites, Barto [14] | 10 floors, 4 cars, capacity 20 | Down-peak profile | 30 simulated hours |
| Hiller, Tuchscherer [8] | 16 floors, 3 or 4 cars | 11 templates | 10 samples each |
| Hiller et al. [9] | 12 floors, 8 cars, capacity 19; 23 floors, 6 cars, capacity 13 | 5 minutes at 6 to 20% | 10 selected snapshots per pattern for solver tests; online repetition not stated |
| Hiller et al. [10] | 16 floors, 4 cars | 4 patterns | 10 realisations |
| Ruokokoski et al. [7] | 9 to 22 floors, 1 to 6 cars, capacity 21 | Light and normal traffic | 60 instances |
| Brand, Nikovski [13] | 10/3, 15/6, 20/8 floors/cars | 4 regimes, 3 rates, one hour | 10 streams, 360 hours per scheduler |
| Peters [5] | 15 floors, 5 cars | 30 minutes, ignore first and last 5; or 1% steps of 30 minutes | Typically 10 runs, 50 for very small effects |
| Siikonen in [6] | | 30 to 60 minutes per step | |

### Suggested approach for us

- G6 sets 5 seeds. Peters's typical practice is 10, with more for small effects [5], so treat differences smaller than the spread between seeds as noise. Use the same seeds across algorithms and trim warm-up and end periods [5].
- G6 fixes the buildings, including a 60-floor case that also fits the PDF sample (B11). That is taller than any building in the table above, so there is no published result to compare it with.
- Check that G6's heavy load really exceeds handling capacity. If it doesn't, the collapse Peters reports [5] and the overload behaviour in section 5 will go unobserved.
- Barney warns against conclusions from a single example [6]. This supports presenting results without naming a winner (G3).
- Peters warns that simulated gains don't always appear in reality [4]. State that limit in the presentation.

## 7. Gaps and uncertainties

**Not read.**

- Barney's handbook [16]. The figure-of-suitability rule comes from a project README that credits it [19]. Idle-car handling and the sectoring detail are unverified.
- Schröder 1990, Closs 1970, Port 1961, Tanaka et al. [30], Friese and Rambau [29], and the Crites and Barto journal paper [15] beyond its abstract.
- Psaraftis 1980 [20] beyond the abstract. His rule's mechanics are unknown. I recall it being "maximum position shift", but could not verify that. Balakrishnan and Chandran cite "Psaraftis 1980" for position shifting [46], which may be a different paper.
- Liu and Layland, Reddy and Wyllie, Smith 1956, Denning 1967 and Kleinrock's 1964 paper. Their claims come through citing sources. Bansal and Pruhs on Lp-norm flow time, and highest response ratio next, could not be verified and are left out.
- N-step SCAN rests on Wikipedia [51], which is a tertiary source.

**Refused or unavailable.** MDPI (a paper on figure of suitability) and two Elevator World articles refused automated access, so they are not used. The Lift and Escalator Library was unreachable, which blocked Barney's history paper and Al-Sharif on run counts. The Fernandez and Cortes 2015 survey was not obtained. AI Magazine's site was offline, so [11] came from a university-hosted copy with a damaged text layer, which I decoded. Only sections 1 and 2 were checked closely.

**Unknown about commercial systems.** ETD's exact curves and capacity logic are unpublished. I found no primary source for Otis's destination-dispatch method. No current product's algorithm is verified, and the patents cover what was claimed, not what ships.

**Not found.** No published elevator source for AS10 (seat hold), D11's cross-floor reservation, shortest-ride-first boarding (D12) or a skip count at boarding (AS3). KONE's round-trip bound [32] is the closest. These are adaptations justified by other fields or by reasoning.

**Project decisions.** D11 to D14, G3, G6 and G7 were added to `assumptions_made.md` while this research was under way, and this report is aligned to them. Two differ from what the research suggests, and I left both for a decision: G6's 5 seeds against Peters's typical 10 [5], and G7's single `stop_ticks = 1` pass against a published stop worth about 5 ticks [14]. D12 is still pending research. The finding is that it is a plausible heuristic by analogy only, and it needs a guard to meet D10.

**Our derivations.** These are reasoning, not results, and should be tested: the LOOK wait bound, overload impossibility, seat starvation, the AS10 guarantee, tie frequency at zero-cost stops, the reduced benefit of grouping, and "EDF equals strict order".

**Source conflicts.**

- Hiller's cost is squared in [10] and weighted linear in [9], which sets travel weight to 0 in its experiments.
- [4] says most systems reallocate, while [9] says all destination systems use immediate assignment. They mean hall-call and destination systems respectively. [12] adds that immediate assignment is typical in Japan.
- Web copy of [1] says Elevator Technology 15, while [2] and [3] cite volume 12.
- [11] dates Miconic-10 to market in 1996, whereas [9] says around 1990 and [1] cites a 1990 description.
- [9] was read as the revised preprint; the journal text may differ.

**Excluded as unreliable.** A 2016 conference review [54] misnames ETD as "Estimated Time to Dispatch" and scores systems subjectively. Not relied on.

**Unit mapping.** Published results are in seconds, with percentage-of-population intensity. Our ticks have no door time. Numbers can't be compared directly with ours; only relative order and trends transfer, and only with care.

## 8. References

Status labels: **read in full**; **abstract only** (or catalogue page or search listing); **cited via** another source. **Read in part** is added where specific sections of the full text were read, since neither of the other labels is accurate. For patents, "read in part" means passages extracted by a fetch tool.

1. Smith R, Peters R. ETD Algorithm with Destination Dispatch and Booster Options. Elevator Technology 12, Proc. ELEVCON 2002, Milan, IAEE. <https://download.peters-research.com/library/ETD_Algorithm_with_Destination_Dispatch_and_Booster_Options.pdf> — read in full.
2. Smith R, Peters R. Enhancements to the ETD Dispatcher Algorithm. Elevator Technology 14, Proc. ELEVCON 2004, Istanbul, IAEE. <https://download.peters-research.com/library/Enhancements_to_the_ETD_Dispatcher_Algorithm.pdf> — read in full.
3. Peters RD. Understanding the Benefits and Limitations of Destination Dispatch. Elevator Technology 16, Proc. ELEVCON 2006, Helsinki, IAEE. <https://download.peters-research.com/library/Understanding_the_Benefits_and_Limitations_of_Destination_Dispatch.pdf> — read in full.
4. Peters RD. Elevator Dispatching. Proc. ELEVCON 2014, Paris, IAEE. <https://download.peters-research.com/library/Elevator_Dispatching.pdf> — read in full.
5. Peters RD. The Application of Simulation to Traffic Design and Dispatcher Testing. 3rd Symposium on Lift and Escalator Technologies, 2013. <https://download.peters-research.com/library/The_Application_of_Simulation_to_Traffic_Design_and_Dispatcher_Testing.pdf> — read in full.
6. CIBSE Lifts Group. Traffic Analysis & Simulation Open Forum Report, May 2007, reported by R. Peters. <https://download.peters-research.com/library/CIBSE_Traffic_Analysis_and_Simulation_Open_Forum_Report.pdf> — read in full.
7. Ruokokoski M, Sorsa J, Siikonen M-L, Ehtamo H. Assignment formulation for the Elevator Dispatching Problem with destination control and its performance analysis. European Journal of Operational Research 252 (2016) 397–406. <https://doi.org/10.1016/j.ejor.2016.01.019>, <https://sal.aalto.fi/publications/pdf-files/ejor2016_public.pdf> — read in full.
8. Hiller B, Tuchscherer A. Real-Time Destination-Call Elevator Group Control on Embedded Microcontrollers. Operations Research Proceedings 2007, Springer 2008, 357–362. ZIB-Report 07-26. <https://opus4.kobv.de/opus4-zib/frontdoor/index/index/docId/1010> — read in full.
9. Hiller B, Klug T, Tuchscherer A. An exact reoptimization algorithm for the scheduling of elevator groups. Flexible Services and Manufacturing Journal 26 (2014) 586–608. <https://doi.org/10.1007/s10696-013-9175-6>. Preprint ZIB-Report 12-43: <https://opus4.kobv.de/opus4-zib/frontdoor/index/index/docId/1648> — read in full (revised preprint).
10. Hiller B, Klug T, Tuchscherer A. Improving the performance of elevator systems using exact reoptimization algorithms. Dagstuhl Seminar Proceedings 09261, 2009. <https://doi.org/10.4230/DagSemProc.09261.11> — read in full.
11. Koehler J, Ottiger D. An AI-Based Approach to Destination Control in Elevators. AI Magazine 23(3), 2002, 59–78. Authors at Schindler Lifts Ltd. <https://doi.org/10.1609/aimag.v23i3.1657>, <https://jmvidal.cse.sc.edu/library/koehler02a.pdf> — read in part (sections 1 to 2.3, results).
12. Nikovski D, Brand M. Decision-Theoretic Group Elevator Scheduling. Proc. ICAPS 2003, 133–142. MERL TR2003-61. <https://merl.com/publications/TR2003-61> — read in part (introduction, related work, assumptions).
13. Brand M, Nikovski D. Risk-Averse Group Elevator Scheduling. ELEVCON 2004. MERL TR2004-045. <https://www.merl.com/publications/docs/TR2004-045.pdf> — read in part (all except part of section 3).
14. Crites RH, Barto AG. Improving Elevator Performance Using Reinforcement Learning. Advances in Neural Information Processing Systems 8, 1996, 1017–1023. <https://proceedings.neurips.cc/paper_files/paper/1995/file/390e982518a50e280d8e2b535462ec1f-Paper.pdf> — read in full.
15. Crites RH, Barto AG. Elevator Group Control Using Multiple Reinforcement Learning Agents. Machine Learning 33 (1998) 235–262. <https://doi.org/10.1023/A:1007518724497> — abstract only.
16. Barney GC. Elevator Traffic Handbook: Theory and Practice. Spon Press, 2003. 2nd edition with Al-Sharif L, Routledge, 2016. <https://www.routledge.com/Elevator-Traffic-Handbook-Theory-and-Practice/Barney-Al-Sharif/p/book/9781032179650> — contents preview only; content cited via [5], [7], [9], [17], [18], [19].
17. Hautamäki T. Multiobjective Optimization Model for Elevator Call Allocation. Master's thesis, Aalto University, 2021. <https://sal.aalto.fi/publications/pdf-files/theses/mas/thau21_public.pdf> — read in part (background, normalisation).
18. Patiño-Forero AA, Muñoz DM, de Carvalho GC, et al. Modeling of an Elevator Group Control System Using Programmable Logic Control and Destination Control System. Proc. COBEM 2009. <https://abcm.org.br/symposium-series/SSM_Vol4/Section_IV_INDUSTRIAL_INFORMATICS_DISCRETE_AND_HYBRID_SYSTEMS/SSM4_IV_12.pdf> — read in part (zoning passages).
19. hhx97. elevator-algorithm-analysis, README. <https://github.com/hhx97/elevator-algorithm-analysis> — read in part. Not a primary source; credits [16].
20. Psaraftis HN. A Dynamic Programming Solution to the Single Vehicle Many-to-Many Immediate Request Dial-a-Ride Problem. Transportation Science 14(2), 1980, 130–154. <https://doi.org/10.1287/trsc.14.2.130> — abstract only.
21. Jaw J-J, Odoni AR, Psaraftis HN, Wilson NHM. A heuristic algorithm for the multi-vehicle advance request dial-a-ride problem with time windows. Transportation Research Part B 20(3), 1986, 243–257. <https://ideas.repec.org/a/eee/transb/v20y1986i3p243-257.html> — abstract only.
22. Jaw J-J. Solving large-scale dial-a-ride vehicle routing and scheduling problems. PhD thesis, MIT, 1984. <https://dspace.mit.edu/handle/1721.1/68045> — abstract only.
23. Tong Y, Zeng Y, Zhou Z, Chen L, Ye J, Xu K. A Unified Approach to Route Planning for Shared Mobility. PVLDB 11(11), 2018, 1633–1646. <https://doi.org/10.14778/3236187.3236211>, <https://www.vldb.org/pvldb/vol11/p1633-tong.pdf> — read in part (sections 1 to 4.2).
24. Ma S, Zheng Y, Wolfson O. T-Share: A Large-Scale Dynamic Taxi Ridesharing Service. Proc. ICDE 2013, 410–421. <https://www.cs.uic.edu/~wolfson/mobile_ps/ICDE2013.pdf> — read in part (insertion passages).
25. Savelsbergh MWP, Sol M. The General Pickup and Delivery Problem. Transportation Science 29(1), 1995, 17–29. <https://doi.org/10.1287/trsc.29.1.17> — abstract only.
26. Cordeau J-F, Laporte G. The dial-a-ride problem: models and algorithms. Annals of Operations Research 153(1), 2007, 29–46. <https://www.gerad.ca/en/papers/G-2006-78> — abstract only. Background; not relied on for specific claims.
27. Krumke SO, et al. On minimizing the maximum flow time in the online dial-a-ride problem. WAOA 2005, LNCS. <https://research.tue.nl/en/publications/on-minimizing-the-maximum-flow-time-in-the-online-dial-a-ride-pro/> — abstract only.
28. Hauptmeier D, Krumke SO, Rambau J. The online dial-a-ride problem under reasonable load. CIAC 2000. <https://doi.org/10.1007/3-540-45753-4_18> — abstract only.
29. Friese P, Rambau J. Online-optimization of a multi-elevator transport system with reoptimization algorithms based on set-partitioning models. Discrete Applied Mathematics 154(13), 2006, 1908–1931 — cited via [8], [9].
30. Tanaka S, Uraguchi Y, Araki M. Dynamic optimization of the operation of single-car elevator systems with destination hall call registration: Parts I and II. European Journal of Operational Research 167(2), 2005, 550–587 — cited via [7], [9], [10].
31. Tyni T, Ylinen J. Evolutionary bi-objective optimisation in the elevator car routing problem. European Journal of Operational Research 169(3), 2006, 960–977. <https://ideas.repec.org/a/eee/ejores/v169y2006i3p960-977.html> — abstract only.
32. Siikonen M-L, Ruokokoski M (Kone Corp). Allocating destination calls using genetic algorithm employing chromosomes. US 10,183,836 B2, 2019. <https://patents.google.com/patent/US10183836> — read in part.
33. Thangavelu K (Otis Elevator Co). Relative System Response Elevator Dispatcher System Using "Artificial Intelligence" to Vary Bonuses and Penalties. EP 0 385 810 A1, 1990. <https://data.epo.org/publication-server/rest/v1.0/publication-dates/19900905/patents/EP0385810NWA1/document.html> — read in part.
34. Kuzunuki S, Hirasawa K, Iwasaka T, Kaneko T (Hitachi Ltd). Elevator control system. US 4,081,059. <https://patents.google.com/patent/US4081059> — read in part.
35. Tsuji S (Mitsubishi Electric Corp). Group supervision apparatus for elevator. US 4,719,996. <https://patents.google.com/patent/US4719996> — read in part.
36. Schröder J, et al. (Inventio AG). Group control for elevators. US 4,355,705. <https://patents.google.com/patent/US4355705> — read in part.
37. Schröder J (Inventio AG). Group control for elevators with immediate allocation of target calls in dependence on the hall call entry location. US 5,092,431. <https://patents.google.com/patent/US5092431> — read in part.
38. Arpaci-Dusseau RH, Arpaci-Dusseau AC. Hard Disk Drives. In Operating Systems: Three Easy Pieces. <https://pages.cs.wisc.edu/~remzi/OSTEP/file-disks.pdf> — read in part (scheduling section).
39. Seltzer M, Chen P, Ousterhout J. Disk Scheduling Revisited. Proc. USENIX Winter 1990. <https://web.eecs.umich.edu/~pmchen/papers/seltzer90.pdf> — read in part (background, aging, conclusions).
40. Coffman EG, Klimko LA, Ryan B. Analysis of Scanning Policies for Reducing Disk Seek Times. SIAM Journal on Computing 1(3), 1972 — cited via [38], [39].
41. Teorey TJ, Pinkerton TB. A comparative analysis of disk scheduling policies. Communications of the ACM 15(3), 1972, 177–184 — abstract only.
42. Linux kernel documentation. Deadline IO scheduler tunables. <https://docs.kernel.org/block/deadline-iosched.html> — read in full.
43. Linux kernel source. block/mq-deadline.c. <https://raw.githubusercontent.com/torvalds/linux/master/block/mq-deadline.c> — read in part (constants, comments).
44. Mutlu O, Moscibroda T. Stall-Time Fair Memory Access Scheduling for Chip Multiprocessors. MICRO 2007. <https://people.inf.ethz.ch/omutlu/pub/stfm_micro07.pdf> — read in part.
45. Mutlu O, Moscibroda T. Parallelism-Aware Batch Scheduling: Enhancing both Performance and Fairness of Shared DRAM Systems. ISCA 2008. <https://people.inf.ethz.ch/omutlu/pub/parbs_isca08.pdf> — read in part.
46. Balakrishnan H, Chandran BG. Algorithms for Scheduling Runway Operations Under Constrained Position Shifting. Operations Research 58(6), 2010, 1650–1665. <https://www.mit.edu/~hamsa/pubs/BalakrishnanChandranOR.pdf> — read in part (introduction, problem statement).
47. Kleinrock L, Finkelstein RP. Time Dependent Priority Queues. Operations Research 15(1), 1967, 104–116. <https://doi.org/10.1287/opre.15.1.104> — read in part (introduction).
48. Smith WE. Various optimizers for single-stage production. Naval Research Logistics Quarterly 3(1–2), 1956, 59–66 — cited via scheduling course notes found in search; original not read.
49. Liu CL, Layland JW. Scheduling Algorithms for Multiprogramming in a Hard Real-Time Environment. Journal of the ACM 20(1), 1973, 46–61 — cited via patent citations found in search.
50. Reddy ALN, Wyllie J. Disk scheduling in a multimedia I/O system. Proc. ACM Multimedia 1993 — cited via secondary summaries found in search.
51. Wikipedia. N-Step-SCAN. <https://en.wikipedia.org/wiki/N-Step-SCAN> — read in full. Tertiary source.
52. Building a Theory of Distributed Systems: Work by Nancy Lynch and Collaborators. arXiv:2502.20468. <https://arxiv.org/pdf/2502.20468> — abstract only, via search excerpt.
53. ISO 8100-32:2020. Lifts for the transportation of persons and goods, Part 32: Planning and selection of passenger lifts to be installed in office, hotel and residential buildings. <https://www.iso.org/standard/73084.html> — abstract only.
54. Kheshaim M, Latif M, Kundu S. A Review of Elevator Dispatching Systems. Proc. World Congress on Engineering 2016, Vol II. <https://www.iaeng.org/publication/WCE2016/WCE2016_pp671-673.pdf> — read in full; rejected as unreliable (section 7).
