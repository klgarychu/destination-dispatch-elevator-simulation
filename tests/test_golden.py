"""M8: results must not drift. Update these files only when a phase is meant to change results."""

from pathlib import Path

import pytest

from elevator_sim.config import ALGORITHMS
from helpers import assert_rules_hold
from update_golden import CASES, GUARDS, golden_path, render_case


@pytest.mark.parametrize("guard", GUARDS)
@pytest.mark.parametrize("building", CASES)
@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_m8_short_runs_match_their_golden_output(
    tmp_path: Path, building: str, algorithm: str, guard: str
) -> None:
    result, text = render_case(building, algorithm, tmp_path, guard)

    assert text == golden_path(building, algorithm, guard).read_bytes()
    assert_rules_hold(result, result.config.capacity, result.config.floors)
