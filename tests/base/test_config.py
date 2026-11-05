"""Unit tests for bililive_danmaku.base.config.app."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import msgspec
import pytest

from bililive_danmaku.base.config import AppConfig, RoomConfig


def make_config_dict() -> dict[str, Any]:
    """Return a minimal valid config mapping for serialization tests."""

    return {
        "server_tokens": ["file-token"],
        "rooms": [{"room_id": 23058938, "id_code": "file-id-code"}],
        "upstream_app_id": "123456",
        "upstream_key": "file-key",
        "upstream_secret": "file-secret",
    }


class TestAppConfigDefaults:
    """``AppConfig`` optional fields carry the documented defaults."""

    def test_optional_fields_use_documented_defaults(
        self,
        make_app_config: Callable[..., AppConfig],
    ) -> None:
        config = make_app_config()

        assert config.server_host == "127.0.0.1"
        assert config.server_port == 8181
        assert config.upstream_host == "https://live-open.biliapi.com"
        assert config.reconnect_interval == 5.0


class TestAppConfigValidation:
    """Invalid configurations fail fast in ``__post_init__``."""

    @pytest.mark.parametrize(
        ("overrides", "match"),
        [
            pytest.param({"server_tokens": []}, "server_tokens", id="empty tokens"),
            pytest.param({"rooms": []}, "rooms", id="empty rooms"),
            pytest.param(
                {"rooms": [RoomConfig(room_id=0, id_code="c")]},
                "room_id",
                id="non-positive room_id",
            ),
            pytest.param(
                {"rooms": [RoomConfig(room_id=1, id_code="")]},
                "id_code",
                id="empty id_code",
            ),
            pytest.param(
                {
                    "rooms": [
                        RoomConfig(room_id=1, id_code="a"),
                        RoomConfig(room_id=1, id_code="b"),
                    ]
                },
                "duplicate",
                id="duplicate room_id",
            ),
            pytest.param({"server_port": 0}, "server_port", id="port too low"),
            pytest.param({"server_port": 65536}, "server_port", id="port too high"),
            pytest.param(
                {"reconnect_interval": 0.0},
                "reconnect_interval",
                id="non-positive reconnect interval",
            ),
        ],
    )
    def test_invalid_configuration_raises_value_error(
        self,
        make_app_config: Callable[..., AppConfig],
        overrides: dict[str, Any],
        match: str,
    ) -> None:
        with pytest.raises(ValueError, match=match):
            make_app_config(**overrides)


class TestAppConfigLoadFile:
    """``AppConfig.load_file`` reads yaml/json/toml and merges env overrides."""

    def test_loads_yaml_and_applies_env_override(
        self,
        tmp_path: Path,
        reset_app_config_singleton: None,
    ) -> None:
        confile = tmp_path / "config.yaml"
        confile.write_text(
            msgspec.yaml.encode(make_config_dict()).decode("utf-8"), encoding="utf-8"
        )

        envfile = tmp_path / ".env"
        envfile.write_text("upstream_secret=env-secret\n", encoding="utf-8")

        config = AppConfig.load_file(config=confile, env=envfile)

        assert config.upstream_secret == "env-secret"
        assert config.upstream_key == "file-key"
        assert config.rooms[0].room_id == 23058938

    def test_missing_env_file_is_tolerated(
        self,
        tmp_path: Path,
        reset_app_config_singleton: None,
    ) -> None:
        confile = tmp_path / "config.yaml"
        confile.write_text(
            msgspec.yaml.encode(make_config_dict()).decode("utf-8"), encoding="utf-8"
        )

        config = AppConfig.load_file(config=confile, env=tmp_path / "absent.env")

        assert config.upstream_secret == "file-secret"

    def test_singleton_caches_until_reset(
        self,
        tmp_path: Path,
        reset_app_config_singleton: None,
    ) -> None:
        confile = tmp_path / "config.yaml"
        confile.write_text(
            msgspec.yaml.encode(make_config_dict()).decode("utf-8"), encoding="utf-8"
        )

        first = AppConfig.load_file(config=confile, env=tmp_path / "absent.env")
        second = AppConfig.load_file(config=confile, env=tmp_path / "absent.env")

        assert first is second

    def test_missing_config_file_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            AppConfig.load_file(
                config=tmp_path / "absent.yaml",
                env=tmp_path / "absent.env",
            )

    def test_missing_required_field_fails_validation(
        self,
        tmp_path: Path,
        reset_app_config_singleton: None,
    ) -> None:
        raw = make_config_dict()
        del raw["upstream_key"]

        confile = tmp_path / "config.yaml"
        confile.write_text(msgspec.yaml.encode(raw).decode("utf-8"), encoding="utf-8")

        with pytest.raises(msgspec.ValidationError):
            AppConfig.load_file(config=confile, env=tmp_path / "absent.env")
