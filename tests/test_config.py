from dataclasses import replace
from pathlib import Path

import pytest

from elevator_sim.config import ConfigError, ExpressCar, SimConfig, load_config, parse_serves


def write_toml(path: Path, text: str) -> Path:
    file = path / "config.toml"
    file.write_text(text, encoding="utf-8")
    return file


def test_tst12_defaults_are_the_agreed_building() -> None:
    config = SimConfig()

    assert (config.floors, config.elevators, config.capacity, config.start_floor) == (10, 3, 6, 1)
    assert (config.algorithm, config.behaviour) == ("marginal_insertion", "min_time")


def test_tst12_loads_building_and_dispatch_settings(tmp_path: Path) -> None:
    file = write_toml(
        tmp_path,
        """
        [building]
        floors = 60
        elevators = 6
        capacity = 10
        start_floor = 2

        [dispatch]
        algorithm = "eta"
        behaviour = "min_time"
        """,
    )

    assert load_config(file) == SimConfig(
        floors=60, elevators=6, capacity=10, start_floor=2, algorithm="eta"
    )


@pytest.mark.parametrize(
    "settings",
    [
        {"floors": 1},
        {"elevators": 0},
        {"capacity": 0},
        {"start_floor": 0},
        {"start_floor": 11},
        {"algorithm": "fastest"},
        {"behaviour": "fastest"},
        {"max_ticks": 0},
    ],
)
def test_tst12_rejects_invalid_settings(settings: dict[str, int | str]) -> None:
    with pytest.raises(ConfigError):
        SimConfig(**settings)  # type: ignore[arg-type]  # deliberately passes bad values


@pytest.mark.parametrize(
    "settings",
    [
        {"floors": 2.5},
        {"elevators": 1.5},
        {"capacity": True},
        {"start_floor": 1.0},
        {"max_ticks": 1.5},
        {"max_ticks": True},
        {"algorithm": ["eta"]},
        {"behaviour": ["min_time"]},
    ],
)
def test_tst12_rejects_settings_of_the_wrong_type(settings: dict[str, object]) -> None:
    with pytest.raises(ConfigError):
        SimConfig(**settings)  # type: ignore[arg-type]  # deliberately passes bad values


@pytest.mark.parametrize(
    ("toml", "named"),
    [
        ("building = 3\n", "building"),
        ("dispatch = 3\n", "dispatch"),
        ("[building]\ncapacity = true\n", "capacity"),
        ("[building]\nelevators = true\n", "elevators"),
        ('[dispatch]\nbehaviour = ["min_time"]\n', "behaviour"),
    ],
)
def test_tst12_rejects_a_badly_shaped_toml_value(tmp_path: Path, toml: str, named: str) -> None:
    with pytest.raises(ConfigError, match=named):
        load_config(write_toml(tmp_path, toml))


def test_tst12_rejects_a_settings_file_that_is_not_utf_8(tmp_path: Path) -> None:
    file = tmp_path / "config.toml"
    file.write_bytes(b'[dispatch]\nalgorithm = "caf\xe9"\n')

    with pytest.raises(ConfigError, match=r"config\.toml"):
        load_config(file)


def test_tst12_rejects_an_unknown_setting(tmp_path: Path) -> None:
    file = write_toml(tmp_path, "[building]\nstoreys = 10\n")

    with pytest.raises(ConfigError, match="storeys"):
        load_config(file)


def test_tst12_rejects_a_wrongly_typed_setting(tmp_path: Path) -> None:
    file = write_toml(tmp_path, '[building]\nfloors = "ten"\n')

    with pytest.raises(ConfigError, match="floors"):
        load_config(file)


def test_tst12_rejects_a_file_that_is_not_toml(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"config\.toml"):
        load_config(write_toml(tmp_path, "this is not toml"))


def test_tst12_rejects_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "absent.toml")


@pytest.mark.parametrize(
    ("toml", "phase"),
    [
        ('[dispatch]\nguard = "skip_limit"\n', "Phase 4"),
        ("[dispatch]\nskip_limit = 2\n", "Phase 4"),
        ('[dispatch]\nwait_limit = "2rt"\n', "Phase 4"),
        ("[dispatch]\nseat_hold = true\n", "Phase 4"),
        ("[dispatch]\nfairness_weight = 1.0\n", "Phase 3"),
        ('[dispatch]\nassignment_rule = "none"\n', "Phase 5"),
        ('[dispatch]\nbehaviour = "strict"\n', "Phase 3"),
        ('[dispatch]\nbehaviour = "weighted"\n', "Phase 3"),
    ],
)
def test_m12_settings_from_later_phases_are_rejected(tmp_path: Path, toml: str, phase: str) -> None:
    with pytest.raises(ConfigError, match=phase):
        load_config(write_toml(tmp_path, toml))


def test_tst12_reads_express_cars_from_the_file(tmp_path: Path) -> None:
    toml = '[building]\nfloors = 8\nelevators = 3\n\n[[express]]\ncar = 3\nserves = "1,5-8"\n'

    assert load_config(write_toml(tmp_path, toml)).express == (ExpressCar(3, (1, 5, 6, 7, 8)),)


def test_tst12_cars_not_listed_are_normal(tmp_path: Path) -> None:
    assert load_config(write_toml(tmp_path, "[building]\nfloors = 8\n")).express == ()


@pytest.mark.parametrize(
    ("text", "floors"),
    [
        ("1,5", (1, 5)),
        ("1, 5-7", (1, 5, 6, 7)),
        ("7-8,1", (1, 7, 8)),
        ("2,2,3", (2, 3)),
    ],
)
def test_tst12_serves_accepts_single_floors_and_ranges(text: str, floors: tuple[int, ...]) -> None:
    assert parse_serves(text) == floors


@pytest.mark.parametrize("text", ["", "a", "1,", "8-5", "1-2-3", "1.5,2"])
def test_tst12_rejects_a_badly_written_floor_list(text: str) -> None:
    with pytest.raises(ConfigError, match="serves"):
        parse_serves(text)


@pytest.mark.parametrize(
    ("toml", "named"),
    [
        ('[[express]]\ncar = 4\nserves = "1,5"\n', "car 4"),
        ('[[express]]\ncar = 0\nserves = "1,5"\n', "car 0"),
        ('[[express]]\ncar = 2\nserves = "1,5"\n[[express]]\ncar = 2\nserves = "1,6"\n', "twice"),
        ('[[express]]\ncar = 2\nserves = "5"\n', "at least 2"),
        ('[[express]]\ncar = 2\nserves = "1,11"\n', "floor 11"),
        ('[[express]]\ncar = "2"\nserves = "1,5"\n', "car"),
        ("[[express]]\ncar = 2\nserves = 5\n", "serves"),
        ("[[express]]\ncar = 2\n", "serves"),
        ('[[express]]\nserves = "1,5"\n', "car"),
        ('[[express]]\ncar = 2\nserves = "1,5"\nspeed = 2\n', "speed"),
        ('[express]\ncar = 2\nserves = "1,5"\n', r"\[\[express\]\]"),
    ],
)
def test_tst12_rejects_invalid_express_settings(tmp_path: Path, toml: str, named: str) -> None:
    with pytest.raises(ConfigError, match=named):
        load_config(write_toml(tmp_path, toml))


def test_tst12_rejects_a_building_where_a_pair_of_floors_has_no_shared_car() -> None:
    low, high = ExpressCar(1, (1, 2, 3)), ExpressCar(2, (1, 4, 5))

    with pytest.raises(ConfigError, match="floors 2 and 4"):
        SimConfig(floors=5, elevators=2, express=(low, high))


def test_tst12_one_normal_car_always_passes_the_coverage_check() -> None:
    config = SimConfig(
        floors=5, elevators=3, express=(ExpressCar(1, (1, 2)), ExpressCar(2, (4, 5)))
    )

    assert len(config.express) == 2


def test_tst12_express_cars_are_checked_again_when_a_setting_is_overridden() -> None:
    config = SimConfig(floors=8, elevators=3, express=(ExpressCar(3, (1, 8)),))

    with pytest.raises(ConfigError, match="car 3"):
        replace(config, elevators=2)
