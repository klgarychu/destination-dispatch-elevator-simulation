"""The module rules in spec section 6.3, checked against the source."""

import ast
import sys
from pathlib import Path

import pytest

SOURCE = Path(__file__).parent.parent / "src" / "elevator_sim"
MODULES = sorted(SOURCE.rglob("*.py"))


def imported_packages(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


@pytest.mark.parametrize("path", MODULES, ids=lambda path: path.stem)
def test_the_simulator_imports_only_the_standard_library(path: Path) -> None:
    third_party = imported_packages(path) - sys.stdlib_module_names - {"elevator_sim"}

    if path.name == "charts.py":
        assert third_party == {"matplotlib"}
    else:
        assert third_party == set()


def test_schedulers_never_check_the_type_of_a_car() -> None:
    for path in (SOURCE / "schedulers").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "isinstance" not in text
        assert "NormalElevator" not in text
        assert "ExpressElevator" not in text


def test_forecast_has_no_second_model_of_movement() -> None:
    text = (SOURCE / "forecast.py").read_text(encoding="utf-8")

    assert "twin.exchange(" in text
    assert "position" not in text


def test_only_the_engine_receives_the_request_list() -> None:
    for path in (SOURCE / "schedulers").glob("*.py"):
        assert "requests:" not in path.read_text(encoding="utf-8")
