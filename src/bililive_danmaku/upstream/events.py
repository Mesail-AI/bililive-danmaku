"""哔哩哔哩直播开放平台「直播间数据」事件的 schema 层。

字段集以官方「直播间数据」文档为权威来源：
https://open-live.bilibili.com/document/f9ce25be-312e-1f4a-85fd-fef21f1637f8

所有结构都把 ``cmd`` 收进字段（:class:`Command` 枚举），其余字段全部带默认
值：上游新增字段被忽略、缺失字段落到默认，负载转换不因增量变化而失败。
字段语义一律经 ``Annotated[..., msgspec.Meta(description=...)]`` 声明；
数值字段附 ``ge=0`` 非负约束、 ``room_id`` 附 ``gt=0`` ，枚举类取值（如 dm_type、
guard_level）不设上限约束，保持对上游扩值的宽容。
``INTERACTION_END`` 没有独立的负载结构——服务端发出它之后会随即断开长连接。
"""

from typing import Annotated, Any

import msgspec
from msgspec import field

from bililive_danmaku.base.schemas import BaseStruct
from bililive_danmaku.upstream.commands import Command

__all__ = (
    "AnchorInfo",
    "BlindGift",
    "ComboInfo",
    "DanmakuMessage",
    "Event",
    "GiftMessage",
    "GuardBuyMessage",
    "LikeMessage",
    "LiveEndMessage",
    "LiveStartMessage",
    "RoomEnterMessage",
    "SuperChatDeleteMessage",
    "SuperChatMessage",
    "UserInfo",
    "parse_event",
)


class UserInfo(BaseStruct):
    """用户信息。"""

    open_id: Annotated[str, msgspec.Meta(description="用户唯一标识")] = ""
    union_id: Annotated[
        str,
        msgspec.Meta(
            description="用户在同一个开发者下的唯一标识（需单独申请开通，未开通时上游为空）"
        ),
    ] = ""
    uname: Annotated[str, msgspec.Meta(description="用户昵称")] = ""
    uface: Annotated[str, msgspec.Meta(description="用户头像")] = ""


class AnchorInfo(BaseStruct):
    """礼物消息附带的主播信息。"""

    uid: Annotated[int, msgspec.Meta(description="收礼主播 uid", ge=0)] = 0
    open_id: Annotated[str, msgspec.Meta(description="收礼主播唯一标识")] = ""
    union_id: Annotated[
        str,
        msgspec.Meta(
            description="用户在同一个开发者下的唯一标识（需单独申请开通，未开通时上游为空）"
        ),
    ] = ""
    uname: Annotated[str, msgspec.Meta(description="收礼主播昵称")] = ""
    uface: Annotated[str, msgspec.Meta(description="收礼主播头像")] = ""


class ComboInfo(BaseStruct):
    """礼物连击信息。"""

    combo_base_num: Annotated[
        int, msgspec.Meta(description="每次连击赠送的道具数量", ge=0)
    ] = 0
    combo_count: Annotated[int, msgspec.Meta(description="连击次数", ge=0)] = 0
    combo_id: Annotated[str, msgspec.Meta(description="连击 id")] = ""
    combo_timeout: Annotated[int, msgspec.Meta(description="连击有效期（秒）", ge=0)] = 0


class BlindGift(BaseStruct):
    """盲盒信息。"""

    blind_gift_id: Annotated[int, msgspec.Meta(description="盲盒 id", ge=0)] = 0
    status: Annotated[bool, msgspec.Meta(description="是否为盲盒")] = False


class DanmakuMessage(BaseStruct):
    """弹幕消息，对应 ``DM`` 与 ``DM_MIRROR`` 命令。"""

    cmd: Annotated[Command, msgspec.Meta(description="长连接命令")]

    uname: Annotated[str, msgspec.Meta(description="用户昵称")] = ""
    open_id: Annotated[str, msgspec.Meta(description="用户唯一标识")] = ""
    union_id: Annotated[
        str,
        msgspec.Meta(
            description="用户在同一个开发者下的唯一标识（需单独申请开通，未开通时上游为空）"
        ),
    ] = ""
    uface: Annotated[str, msgspec.Meta(description="用户头像")] = ""

    timestamp: Annotated[
        int, msgspec.Meta(description="弹幕发送时间的秒级时间戳", ge=0)
    ] = 0
    room_id: Annotated[int, msgspec.Meta(description="接收弹幕的直播间", gt=0)] = 0
    msg: Annotated[str, msgspec.Meta(description="弹幕内容")] = ""
    msg_id: Annotated[str, msgspec.Meta(description="消息唯一 id")] = ""
    guard_level: Annotated[
        int, msgspec.Meta(description="对应房间的大航海等级", ge=0)
    ] = 0

    fans_medal_wearing_status: Annotated[
        bool, msgspec.Meta(description="该房间粉丝勋章佩戴情况")
    ] = False
    fans_medal_name: Annotated[str, msgspec.Meta(description="粉丝勋章名")] = ""
    fans_medal_level: Annotated[
        int, msgspec.Meta(description="对应房间的勋章等级", ge=0)
    ] = 0

    emoji_img_url: Annotated[str, msgspec.Meta(description="表情包图片地址")] = ""
    dm_type: Annotated[
        int, msgspec.Meta(description="弹幕类型（0 普通弹幕、1 表情包弹幕）", ge=0)
    ] = 0
    glory_level: Annotated[int, msgspec.Meta(description="直播荣耀等级", ge=0)] = 0

    reply_open_id: Annotated[str, msgspec.Meta(description="被 @ 用户的唯一标识")] = ""
    reply_uname: Annotated[str, msgspec.Meta(description="被 @ 用户的昵称")] = ""
    is_admin: Annotated[
        int, msgspec.Meta(description="发送者是否为房管（取值 0 或 1，1 为房管）", ge=0)
    ] = 0
    is_mirror: Annotated[bool, msgspec.Meta(description="是否为跨房弹幕")] = False


class GiftMessage(BaseStruct):
    """礼物消息，对应 ``SEND_GIFT`` 命令。"""

    cmd: Annotated[Command, msgspec.Meta(description="长连接命令")]

    room_id: Annotated[int, msgspec.Meta(description="房间号", gt=0)] = 0
    msg_id: Annotated[str, msgspec.Meta(description="消息唯一 id")] = ""
    timestamp: Annotated[int, msgspec.Meta(description="收礼时间的秒级时间戳", ge=0)] = 0

    open_id: Annotated[str, msgspec.Meta(description="用户唯一标识")] = ""
    union_id: Annotated[
        str,
        msgspec.Meta(
            description="用户在同一个开发者下的唯一标识（需单独申请开通，未开通时上游为空）"
        ),
    ] = ""
    uname: Annotated[str, msgspec.Meta(description="送礼用户昵称")] = ""
    uface: Annotated[str, msgspec.Meta(description="送礼用户头像")] = ""

    gift_id: Annotated[
        int, msgspec.Meta(description="道具 id（盲盒为爆出的道具 id）", ge=0)
    ] = 0
    gift_name: Annotated[
        str, msgspec.Meta(description="道具名（盲盒为爆出的道具名）")
    ] = ""
    gift_num: Annotated[int, msgspec.Meta(description="赠送道具数量", ge=0)] = 0
    gift_icon: Annotated[str, msgspec.Meta(description="道具 icon")] = ""
    price: Annotated[
        int,
        msgspec.Meta(
            description=(
                "礼物爆出单价（1000 = 1 元 = 10 电池），盲盒为爆出道具的价值；"
                "免费礼物也可能非 0 而是银瓜子数；打折礼物非实际支付价值，实际价值用 r_price"
            ),
            ge=0,
        ),
    ] = 0
    r_price: Annotated[
        int,
        msgspec.Meta(
            description=(
                "实际支付价值（1000 = 1 元 = 10 电池），盲盒为爆出道具的价值；"
                "免费礼物也可能非 0"
            ),
            ge=0,
        ),
    ] = 0
    paid: Annotated[bool, msgspec.Meta(description="是否为付费道具")] = False

    guard_level: Annotated[int, msgspec.Meta(description="大航海等级", ge=0)] = 0
    fans_medal_wearing_status: Annotated[
        bool, msgspec.Meta(description="该房间粉丝勋章佩戴情况")
    ] = False
    fans_medal_name: Annotated[str, msgspec.Meta(description="粉丝勋章名")] = ""
    fans_medal_level: Annotated[
        int, msgspec.Meta(description="实际送礼人的勋章等级", ge=0)
    ] = 0

    anchor_info: Annotated[AnchorInfo, msgspec.Meta(description="收礼主播信息")] = field(
        default_factory=AnchorInfo
    )
    combo_gift: Annotated[
        bool, msgspec.Meta(description="是否为连击道具（官方调试工具不发此字段）")
    ] = False
    combo_info: Annotated[
        ComboInfo, msgspec.Meta(description="连击信息（官方调试工具不发此字段）")
    ] = field(default_factory=ComboInfo)
    blind_gift: Annotated[
        BlindGift, msgspec.Meta(description="盲盒信息（官方调试工具不发此字段）")
    ] = field(default_factory=BlindGift)


class GuardBuyMessage(BaseStruct):
    """上舰消息，对应 ``GUARD`` 命令。"""

    cmd: Annotated[Command, msgspec.Meta(description="长连接命令")]

    room_id: Annotated[int, msgspec.Meta(description="房间号", gt=0)] = 0
    msg_id: Annotated[str, msgspec.Meta(description="消息唯一 id")] = ""
    timestamp: Annotated[int, msgspec.Meta(description="上舰时间的秒级时间戳", ge=0)] = 0

    user_info: Annotated[UserInfo, msgspec.Meta(description="上舰用户信息")] = field(
        default_factory=UserInfo
    )
    guard_level: Annotated[
        int, msgspec.Meta(description="大航海等级（1 舰长、2 提督、3 总督）", ge=0)
    ] = 0
    guard_num: Annotated[int, msgspec.Meta(description="大航海数量", ge=0)] = 0
    guard_unit: Annotated[
        str,
        msgspec.Meta(
            description=(
                '大航海单位——正常为"月"，若为其他内容（如"*3天"）则以本字段为准，'
                "无视 guard_num"
            )
        ),
    ] = ""
    price: Annotated[int, msgspec.Meta(description="大航海金瓜子", ge=0)] = 0

    fans_medal_wearing_status: Annotated[
        bool, msgspec.Meta(description="该房间粉丝勋章佩戴情况")
    ] = False
    fans_medal_name: Annotated[str, msgspec.Meta(description="粉丝勋章名")] = ""
    fans_medal_level: Annotated[int, msgspec.Meta(description="粉丝勋章等级", ge=0)] = 0


class SuperChatMessage(BaseStruct):
    """醒目留言消息，对应 ``SUPER_CHAT`` 命令。"""

    cmd: Annotated[Command, msgspec.Meta(description="长连接命令")]

    room_id: Annotated[int, msgspec.Meta(description="直播间 id", gt=0)] = 0
    msg_id: Annotated[str, msgspec.Meta(description="消息唯一 id")] = ""

    open_id: Annotated[str, msgspec.Meta(description="用户唯一标识")] = ""
    union_id: Annotated[
        str,
        msgspec.Meta(
            description="用户在同一个开发者下的唯一标识（需单独申请开通，未开通时上游为空）"
        ),
    ] = ""
    uname: Annotated[str, msgspec.Meta(description="购买的用户昵称")] = ""
    uface: Annotated[str, msgspec.Meta(description="购买用户头像")] = ""

    message_id: Annotated[
        int, msgspec.Meta(description="留言 id（风控撤回时需要）", ge=0)
    ] = 0
    message: Annotated[str, msgspec.Meta(description="留言内容")] = ""
    rmb: Annotated[int, msgspec.Meta(description="支付金额（元）", ge=0)] = 0
    timestamp: Annotated[int, msgspec.Meta(description="赠送时间的秒级时间戳", ge=0)] = 0
    start_time: Annotated[int, msgspec.Meta(description="生效开始时间（秒级）", ge=0)] = 0
    end_time: Annotated[int, msgspec.Meta(description="生效结束时间（秒级）", ge=0)] = 0

    guard_level: Annotated[int, msgspec.Meta(description="对应房间大航海等级", ge=0)] = 0
    fans_medal_wearing_status: Annotated[
        bool, msgspec.Meta(description="该房间粉丝勋章佩戴情况")
    ] = False
    fans_medal_name: Annotated[str, msgspec.Meta(description="对应房间勋章名字")] = ""
    fans_medal_level: Annotated[
        int, msgspec.Meta(description="对应房间的勋章等级", ge=0)
    ] = 0


class SuperChatDeleteMessage(BaseStruct):
    """删除醒目留言消息，对应 ``SUPER_CHAT_DEL`` 命令。"""

    cmd: Annotated[Command, msgspec.Meta(description="长连接命令")]

    room_id: Annotated[int, msgspec.Meta(description="直播间 id", gt=0)] = 0
    message_ids: Annotated[
        list[int], msgspec.Meta(description="被删除留言的 id 列表")
    ] = field(default_factory=list)
    msg_id: Annotated[str, msgspec.Meta(description="消息唯一 id")] = ""


class LikeMessage(BaseStruct):
    """点赞消息，对应 ``LIKE`` 命令；仅开播中触发。"""

    cmd: Annotated[Command, msgspec.Meta(description="长连接命令")]

    uname: Annotated[str, msgspec.Meta(description="用户昵称")] = ""
    open_id: Annotated[str, msgspec.Meta(description="用户唯一标识")] = ""
    union_id: Annotated[
        str,
        msgspec.Meta(
            description="用户在同一个开发者下的唯一标识（需单独申请开通，未开通时上游为空）"
        ),
    ] = ""
    uface: Annotated[str, msgspec.Meta(description="用户头像")] = ""

    timestamp: Annotated[int, msgspec.Meta(description="时间的秒级时间戳", ge=0)] = 0
    room_id: Annotated[int, msgspec.Meta(description="发生的直播间", gt=0)] = 0
    like_text: Annotated[str, msgspec.Meta(description='点赞文案（"xxx 点赞了"）')] = ""
    like_count: Annotated[
        int, msgspec.Meta(description="对单一用户最近 2 秒的点赞次数聚合", ge=0)
    ] = 0
    msg_id: Annotated[str, msgspec.Meta(description="消息唯一 id")] = ""

    fans_medal_wearing_status: Annotated[
        bool, msgspec.Meta(description="该房间粉丝勋章佩戴情况")
    ] = False
    fans_medal_name: Annotated[str, msgspec.Meta(description="粉丝勋章名")] = ""
    fans_medal_level: Annotated[
        int, msgspec.Meta(description="对应房间的勋章等级", ge=0)
    ] = 0


class RoomEnterMessage(BaseStruct):
    """进入直播间消息，对应 ``LIVE_ROOM_ENTER`` 命令。"""

    cmd: Annotated[Command, msgspec.Meta(description="长连接命令")]

    room_id: Annotated[int, msgspec.Meta(description="直播间 id", gt=0)] = 0
    uname: Annotated[str, msgspec.Meta(description="用户昵称")] = ""
    uface: Annotated[str, msgspec.Meta(description="用户头像")] = ""
    open_id: Annotated[str, msgspec.Meta(description="用户唯一标识")] = ""
    union_id: Annotated[
        str,
        msgspec.Meta(
            description="用户在同一个开发者下的唯一标识（需单独申请开通，未开通时上游为空）"
        ),
    ] = ""
    timestamp: Annotated[int, msgspec.Meta(description="发生时间的秒级时间戳", ge=0)] = 0
    msg_id: Annotated[str, msgspec.Meta(description="消息唯一 id")] = ""


class LiveStartMessage(BaseStruct):
    """开播消息，对应 ``LIVE_START`` 命令。"""

    cmd: Annotated[Command, msgspec.Meta(description="长连接命令")]

    room_id: Annotated[int, msgspec.Meta(description="直播间 id", gt=0)] = 0
    open_id: Annotated[str, msgspec.Meta(description="主播唯一标识")] = ""
    union_id: Annotated[
        str,
        msgspec.Meta(
            description="用户在同一个开发者下的唯一标识（需单独申请开通，未开通时上游为空）"
        ),
    ] = ""
    timestamp: Annotated[int, msgspec.Meta(description="发生时间的秒级时间戳", ge=0)] = 0
    area_name: Annotated[str, msgspec.Meta(description="开播二级分区名")] = ""
    title: Annotated[str, msgspec.Meta(description="开播时刻，直播间的标题")] = ""
    msg_id: Annotated[str, msgspec.Meta(description="消息唯一 id")] = ""


class LiveEndMessage(BaseStruct):
    """下播消息，对应 ``LIVE_END`` 命令。"""

    cmd: Annotated[Command, msgspec.Meta(description="长连接命令")]

    room_id: Annotated[int, msgspec.Meta(description="直播间 id", gt=0)] = 0
    open_id: Annotated[str, msgspec.Meta(description="主播唯一标识")] = ""
    union_id: Annotated[
        str,
        msgspec.Meta(
            description="用户在同一个开发者下的唯一标识（需单独申请开通，未开通时上游为空）"
        ),
    ] = ""
    timestamp: Annotated[int, msgspec.Meta(description="发生时间的秒级时间戳", ge=0)] = 0
    area_name: Annotated[str, msgspec.Meta(description="开播二级分区名")] = ""
    title: Annotated[str, msgspec.Meta(description="开播时刻，直播间的标题")] = ""
    msg_id: Annotated[str, msgspec.Meta(description="消息唯一 id")] = ""


type Event = (
    DanmakuMessage
    | GiftMessage
    | GuardBuyMessage
    | SuperChatMessage
    | SuperChatDeleteMessage
    | LikeMessage
    | RoomEnterMessage
    | LiveStartMessage
    | LiveEndMessage
)


def parse_event(payload: dict[str, Any]) -> "Event | None":
    """按 ``cmd`` 把长连接原始负载转换为对应的事件结构。

    未知命令（不在 :class:`Command` 目录内）返回 ``None`` ，上游扩容时
    不抛错；``INTERACTION_END`` 同样返回 ``None``——它没有负载结构，收到
    它意味着服务端即将断开长连接。负载字段类型不符（如数字字段给了字符
    串）时抛 :class:`msgspec.ValidationError`。
    """

    try:
        cmd = Command(payload.get("cmd", ""))

    except ValueError:
        return None

    match cmd:
        case Command.DM | Command.DM_MIRROR:
            return msgspec.convert(payload, type=DanmakuMessage)

        case Command.SEND_GIFT:
            return msgspec.convert(payload, type=GiftMessage)

        case Command.GUARD:
            return msgspec.convert(payload, type=GuardBuyMessage)

        case Command.SUPER_CHAT:
            return msgspec.convert(payload, type=SuperChatMessage)

        case Command.SUPER_CHAT_DEL:
            return msgspec.convert(payload, type=SuperChatDeleteMessage)

        case Command.LIKE:
            return msgspec.convert(payload, type=LikeMessage)

        case Command.LIVE_ROOM_ENTER:
            return msgspec.convert(payload, type=RoomEnterMessage)

        case Command.LIVE_START:
            return msgspec.convert(payload, type=LiveStartMessage)

        case Command.LIVE_END:
            return msgspec.convert(payload, type=LiveEndMessage)

        case Command.INTERACTION_END:
            return None
