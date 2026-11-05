"""Unit tests for bililive_danmaku.upstream.events."""

import msgspec
import pytest

from bililive_danmaku.base.schemas import BaseStruct
from bililive_danmaku.upstream.commands import Command
from bililive_danmaku.upstream.events import (
    DanmakuMessage,
    Event,
    GiftMessage,
    GuardBuyMessage,
    LikeMessage,
    LiveEndMessage,
    LiveStartMessage,
    RoomEnterMessage,
    SuperChatDeleteMessage,
    SuperChatMessage,
    parse_event,
)

DISPATCH_CASES = [
    pytest.param("LIVE_OPEN_PLATFORM_DM", DanmakuMessage(cmd=Command.DM), id="dm"),
    pytest.param(
        "LIVE_OPEN_PLATFORM_DM_MIRROR",
        DanmakuMessage(cmd=Command.DM_MIRROR),
        id="dm mirror",
    ),
    pytest.param(
        "LIVE_OPEN_PLATFORM_SEND_GIFT",
        GiftMessage(cmd=Command.SEND_GIFT),
        id="gift",
    ),
    pytest.param(
        "LIVE_OPEN_PLATFORM_GUARD", GuardBuyMessage(cmd=Command.GUARD), id="guard"
    ),
    pytest.param(
        "LIVE_OPEN_PLATFORM_SUPER_CHAT",
        SuperChatMessage(cmd=Command.SUPER_CHAT),
        id="super chat",
    ),
    pytest.param(
        "LIVE_OPEN_PLATFORM_SUPER_CHAT_DEL",
        SuperChatDeleteMessage(cmd=Command.SUPER_CHAT_DEL),
        id="super chat delete",
    ),
    pytest.param("LIVE_OPEN_PLATFORM_LIKE", LikeMessage(cmd=Command.LIKE), id="like"),
    pytest.param(
        "LIVE_OPEN_PLATFORM_LIVE_ROOM_ENTER",
        RoomEnterMessage(cmd=Command.LIVE_ROOM_ENTER),
        id="room enter",
    ),
    pytest.param(
        "LIVE_OPEN_PLATFORM_LIVE_START",
        LiveStartMessage(cmd=Command.LIVE_START),
        id="live start",
    ),
    pytest.param(
        "LIVE_OPEN_PLATFORM_LIVE_END",
        LiveEndMessage(cmd=Command.LIVE_END),
        id="live end",
    ),
]


class TestParseEventDispatch:
    """``parse_event`` routes each known command to its typed structure."""

    @pytest.mark.parametrize(("cmd", "expected"), DISPATCH_CASES)
    def test_known_command_converts_to_its_struct(
        self,
        cmd: str,
        expected: BaseStruct,
    ) -> None:
        assert parse_event({"cmd": cmd}) == expected

    def test_mirror_dm_keeps_mirror_command_on_danmaku_struct(self) -> None:
        event = parse_event({"cmd": "LIVE_OPEN_PLATFORM_DM_MIRROR"})

        assert event == DanmakuMessage(cmd=Command.DM_MIRROR)

    def test_interaction_end_has_no_payload_struct(self) -> None:
        assert parse_event({"cmd": "LIVE_OPEN_PLATFORM_INTERACTION_END"}) is None

    def test_unknown_command_returns_none(self) -> None:
        assert parse_event({"cmd": "LIVE_OPEN_PLATFORM_BRAND_NEW"}) is None

    def test_missing_command_returns_none(self) -> None:
        assert parse_event({"msg": "no cmd here"}) is None


class TestParseEventPayload:
    """Payload conversion maps fields and tolerates incremental changes."""

    def test_dm_fields_map_onto_the_struct(self) -> None:
        event = parse_event(
            {
                "cmd": "LIVE_OPEN_PLATFORM_DM",
                "uname": "tester",
                "msg": "hello",
                "guard_level": 3,
                "fans_medal_wearing_status": True,
            }
        )

        assert isinstance(event, DanmakuMessage)
        assert event.uname == "tester"
        assert event.msg == "hello"
        assert event.guard_level == 3
        assert event.fans_medal_wearing_status is True
        assert event.glory_level == 0

    def test_unknown_fields_are_ignored(self) -> None:
        event = parse_event({"cmd": "LIVE_OPEN_PLATFORM_DM", "brand_new": {"x": 1}})

        assert isinstance(event, DanmakuMessage)

    def test_gift_nested_structs_fall_back_to_factories(self) -> None:
        event = parse_event({"cmd": "LIVE_OPEN_PLATFORM_SEND_GIFT", "gift_name": "辣条"})

        assert isinstance(event, GiftMessage)
        assert event.anchor_info.uid == 0
        assert event.combo_info.combo_count == 0
        assert event.blind_gift.status is False

    def test_field_type_mismatch_raises_validation_error(self) -> None:
        with pytest.raises(msgspec.ValidationError):
            parse_event({"cmd": "LIVE_OPEN_PLATFORM_DM", "room_id": "not-a-number"})

    def test_event_union_covers_every_dispatched_struct(self) -> None:
        assert set(Event.__value__.__args__) == {
            DanmakuMessage,
            GiftMessage,
            GuardBuyMessage,
            SuperChatMessage,
            SuperChatDeleteMessage,
            LikeMessage,
            RoomEnterMessage,
            LiveStartMessage,
            LiveEndMessage,
        }
