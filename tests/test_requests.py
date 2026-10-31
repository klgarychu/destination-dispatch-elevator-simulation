import pickle
from pathlib import Path

import pytest

from elevator_sim.config import SimConfig
from elevator_sim.engine import simulate
from elevator_sim.requests import InputValidationError, Request, load_requests, validate_requests

HEADER = "time,id,source,dest\n"


def write_csv(path: Path, body: str, header: str = HEADER, encoding: str = "utf-8") -> Path:
    file = path / "requests.csv"
    file.write_text(header + body, encoding=encoding, newline="")
    return file


def test_tst03_loads_the_pdf_sample(tmp_path: Path) -> None:
    file = write_csv(tmp_path, "0,passenger1,1,51\n0,passenger2,1,37\n10,passenger3,20,1\n")

    assert load_requests(file, floors=60) == [
        Request(0, "passenger1", 1, 51),
        Request(0, "passenger2", 1, 37),
        Request(10, "passenger3", 20, 1),
    ]


def test_tst03_sorts_by_time_and_keeps_file_order_for_ties(tmp_path: Path) -> None:
    file = write_csv(tmp_path, "5,late,1,2\n0,first,2,1\n0,second,3,1\n")

    assert [r.id for r in load_requests(file, floors=5)] == ["first", "second", "late"]


def test_tst03_accepts_a_byte_order_mark(tmp_path: Path) -> None:
    file = write_csv(tmp_path, "0,a,1,2\n", encoding="utf-8-sig")

    assert load_requests(file, floors=5) == [Request(0, "a", 1, 2)]


def test_tst03_empty_input_is_valid(tmp_path: Path) -> None:
    assert load_requests(write_csv(tmp_path, ""), floors=5) == []


def test_tst03_rejects_a_wrong_header(tmp_path: Path) -> None:
    file = write_csv(tmp_path, "0,a,1,2\n", header="when,who,from,to\n")

    with pytest.raises(InputValidationError, match="header"):
        load_requests(file, floors=5)


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ("x,a,1,2", "time"),
        ("-1,a,1,2", "time"),
        ("0,,1,2", "id"),
        ("0,a,one,2", "source"),
        ("0,a,1,two", "dest"),
        ("0,a,0,2", "source"),
        ("0,a,1,6", "dest"),
        ("0,a,2,2", "source and dest"),
        ("0,a,1", "fields"),
    ],
)
def test_tst03_rejects_each_kind_of_invalid_row(tmp_path: Path, row: str, expected: str) -> None:
    with pytest.raises(InputValidationError, match=expected):
        load_requests(write_csv(tmp_path, row + "\n"), floors=5)


def test_tst03_rejects_a_duplicate_id(tmp_path: Path) -> None:
    with pytest.raises(InputValidationError, match="duplicate id 'a'"):
        load_requests(write_csv(tmp_path, "0,a,1,2\n1,a,2,1\n"), floors=5)


def test_tst03_lists_every_bad_row(tmp_path: Path) -> None:
    file = write_csv(tmp_path, "x,a,1,2\n0,b,1,2\n0,c,9,2\n0,d,3,3\n")

    with pytest.raises(InputValidationError) as caught:
        load_requests(file, floors=5)

    assert [problem.split(":")[0] for problem in caught.value.problems] == [
        "row 2",
        "row 4",
        "row 5",
    ]


def test_tst03_validate_requests_applies_the_same_rules_to_a_list() -> None:
    with pytest.raises(InputValidationError, match="dest"):
        validate_requests([Request(0, "a", 1, 6)], floors=5)


@pytest.mark.parametrize(
    ("bad", "expected"),
    [
        (Request(0.5, "a", 1, 2), "time"),
        (Request(float("nan"), "a", 1, 2), "time"),
        (Request(True, "a", 1, 2), "time"),
        (Request(0, 5, 1, 2), "id"),
        (Request(0, ["a"], 1, 2), "id"),
        (Request(0, "a", 1.5, 2), "source"),
        (Request(0, "a", True, 2), "source"),
        (Request(0, "a", 1, 2.5), "dest"),
    ],
)
def test_tst03_validate_requests_rejects_fields_of_the_wrong_type(
    bad: Request, expected: str
) -> None:
    with pytest.raises(InputValidationError, match=expected):
        validate_requests([bad], floors=5)


def test_tst03_simulate_refuses_a_fractional_time_instead_of_stalling() -> None:
    with pytest.raises(InputValidationError, match="time"):
        simulate([Request(0.5, "a", 1, 2)], SimConfig(floors=3))


def test_tst03_rejects_a_file_that_is_not_utf_8(tmp_path: Path) -> None:
    file = tmp_path / "requests.csv"
    file.write_bytes(b"time,id,source,dest\n0,caf\xe9,1,2\n")

    with pytest.raises(InputValidationError, match=r"requests\.csv"):
        load_requests(file, floors=5)


def test_tst03_rejects_a_file_the_csv_reader_cannot_parse(tmp_path: Path) -> None:
    file = write_csv(tmp_path, f"0,{'x' * 200_000},1,2\n")

    with pytest.raises(InputValidationError, match=r"requests\.csv"):
        load_requests(file, floors=5)


def test_tst03_an_input_error_keeps_its_problems_between_processes() -> None:
    error = InputValidationError(["row 2: dest 99 is outside floors 1..5"])

    copy = pickle.loads(pickle.dumps(error))

    assert copy.problems == error.problems
    assert str(copy) == str(error)


def test_tst03_validate_requests_sorts_a_list() -> None:
    requests = [Request(5, "late", 1, 2), Request(0, "early", 2, 1)]

    assert [r.id for r in validate_requests(requests, floors=5)] == ["early", "late"]
