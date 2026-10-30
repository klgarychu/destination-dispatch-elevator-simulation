from pathlib import Path

import pytest

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


def test_tst03_validate_requests_sorts_a_list() -> None:
    requests = [Request(5, "late", 1, 2), Request(0, "early", 2, 1)]

    assert [r.id for r in validate_requests(requests, floors=5)] == ["early", "late"]
