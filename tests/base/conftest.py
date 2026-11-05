"""Fixtures for the base-layer tests."""

from collections.abc import Iterator

import pytest

from bililive_danmaku.base.config import AppConfig


@pytest.fixture
def reset_app_config_singleton() -> Iterator[None]:
    """Reset the ``AppConfig`` singleton before and after the test."""

    AppConfig._instance = None
    yield
    AppConfig._instance = None
