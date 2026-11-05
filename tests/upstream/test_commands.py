"""Unit tests for bililive_danmaku.upstream.commands."""

from bililive_danmaku.upstream.commands import Command


class TestCommandCatalog:
    """The catalog mirrors the official long-connection command set."""

    def test_catalog_covers_eleven_commands(self) -> None:
        assert len(list(Command)) == 11

    def test_values_carry_the_live_open_platform_prefix(self) -> None:
        for command in Command:
            assert str(command).startswith("LIVE_OPEN_PLATFORM_")

    def test_values_are_unique(self) -> None:
        assert len({str(command) for command in Command}) == len(list(Command))

    def test_str_enum_compares_equal_to_upstream_string(self) -> None:
        assert str(Command.DM) == "LIVE_OPEN_PLATFORM_DM"
        assert str(Command.INTERACTION_END) == "LIVE_OPEN_PLATFORM_INTERACTION_END"
