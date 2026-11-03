import sys


def test_runs_on_a_supported_interpreter() -> None:
    assert sys.version_info >= (3, 14)
