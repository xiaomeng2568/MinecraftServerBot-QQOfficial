"""QQ 指令：help"""
from nonebot import on_command
from nonebot.adapters import Event
from ..permissions import get_event_user_id, require_admin_text


mc_help_cmd = on_command("mchelp", aliases={"ctihelp"}, priority=5)


@mc_help_cmd.handle()
async def _(event: Event):
    deny = require_admin_text(get_event_user_id(event))
    if deny:
        await mc_help_cmd.finish(deny)

    await mc_help_cmd.finish(
        "服务器 运维命令\n\n"
        "基础控制：\n"
        "/start - 启动服务器\n"
        "/stop - 停止服务器\n"
        "/restart - 重启服务器\n\n"
        "状态查看：\n"
        "/reportnow - 手动查看服务器状态（被动回复）\n"
        "/reportstatus - 查看主动播报诊断\n"
        "/reportretry - 权限修复后恢复下一轮播报\n"
        "/players - 查看在线玩家\n"
        "/online - 只看在线人数\n"
        "/log - 查看最近10行日志\n"
        "/log 40 - 查看最近40行日志\n"
        "/worldsize - 查看世界/目录占用\n"
        "/memory - 查看 Java / 系统资源\n"
        "/tps - 查询TPS\n\n"
        "控制台：\n"
        "/exec 指令 - 执行任意控制台命令\n"
        "/say 内容 - 全服广播\n\n"
        "玩家管理：\n"
        "/whitelist on/off/list/add/remove/reload\n"
        "/op 玩家名\n"
        "/deop 玩家名\n"
        "/kick 玩家名 原因\n"
        "/ban 玩家名 原因\n"
        "/pardon 玩家名"
    )


whoami_cmd = on_command("whoami", priority=5)


@whoami_cmd.handle()
async def _(event: Event):
    user_id = event.get_user_id()
    session_id = event.get_session_id()
    event_type = event.get_type()

    group_openid = "未检测到群 OpenID"

    if session_id.startswith("group_"):
        parts = session_id.split("_")
        if len(parts) >= 3:
            group_openid = parts[1]

    await whoami_cmd.finish(
        "当前事件信息：\n\n"
        f"user_id: {user_id}\n"
        f"session_id: {session_id}\n"
        f"group_openid: {group_openid}\n"
        f"type: {event_type}\n\n"
        "说明：\n"
        "user_id 可填写到 ADMIN_USER_IDS\n"
        "group_openid 可填写到 REPORT_GROUP_OPENID"
    )
