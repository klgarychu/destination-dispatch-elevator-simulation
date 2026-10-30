from pathlib import Path

import pytest

from elevator_sim.config import ConfigError, SimConfig, load_config


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
        ('[[express]]\ncar = 1\nserves = "1,5"\n', "Phase 2"),
    ],
)
def test_m12_settings_from_later_phases_are_rejected(tmp_path: Path, toml: str, phase: str) -> None:
    with pytest.raises(ConfigError, match=phase):
        load_config(write_toml(tmp_path, toml))
