import sys


def test_runs_on_the_project_interpreter() -> None:
    assert sys.version_info[:3] == (3, 15, 2)
