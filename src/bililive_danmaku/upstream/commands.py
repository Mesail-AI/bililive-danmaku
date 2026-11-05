"""长连接推送的命令（ ``cmd`` ）目录。

命令全集与各命令的数据字段以官方「直播间数据」文档为权威来源：
https://open-live.bilibili.com/document/f9ce25be-312e-1f4a-85fd-fef21f1637f8
"""

import enum

__all__ = ("Command",)


class Command(enum.StrEnum):
    """长连接消息体 ``cmd`` 字段的已知取值。

    成员值即上游原样字符串。上游扩充新命令时不在目录内： ``events`` 照常
    透传原始 JSON，下游拿 ``event["cmd"]`` 按 ``str`` 比对即可。
    """

    # 弹幕
    DM = "LIVE_OPEN_PLATFORM_DM"
    # 跨房弹幕（连线、合唱等场景镜像到本房间的弹幕）
    DM_MIRROR = "LIVE_OPEN_PLATFORM_DM_MIRROR"
    # 礼物
    SEND_GIFT = "LIVE_OPEN_PLATFORM_SEND_GIFT"
    # 上舰（舰长 / 提督 / 总督）
    GUARD = "LIVE_OPEN_PLATFORM_GUARD"
    # 醒目留言（SC）
    SUPER_CHAT = "LIVE_OPEN_PLATFORM_SUPER_CHAT"
    # 醒目留言被删除
    SUPER_CHAT_DEL = "LIVE_OPEN_PLATFORM_SUPER_CHAT_DEL"
    # 点赞
    LIKE = "LIVE_OPEN_PLATFORM_LIKE"
    # 观众进入直播间
    LIVE_ROOM_ENTER = "LIVE_OPEN_PLATFORM_LIVE_ROOM_ENTER"
    # 开播
    LIVE_START = "LIVE_OPEN_PLATFORM_LIVE_START"
    # 下播
    LIVE_END = "LIVE_OPEN_PLATFORM_LIVE_END"
    # 服务端主动结束互动项目（收到后服务端会随即断开长连接）
    INTERACTION_END = "LIVE_OPEN_PLATFORM_INTERACTION_END"
