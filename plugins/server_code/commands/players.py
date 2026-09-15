"""QQ 指令：players"""
from nonebot import on_command
from nonebot.adapters import Event
from nonebot.params import CommandArg
from ..parsing import tail_log
from ..permissions import get_event_user_id, require_admin_text
from ..services import send_command_and_read_log


whitelist_cmd = on_command("whitelist", priority=5)


@whitelist_cmd.handle()
async def _(event: Event, args=CommandArg()):
    deny = require_admin_text(get_event_user_id(event))
    if deny:
        await whitelist_cmd.finish(deny)

    raw = str(args).strip()

    if not raw:
        await whitelist_cmd.finish(
            "用法：\n"
            "/whitelist on\n"
            "/whitelist off\n"
            "/whitelist list\n"
            "/whitelist add 玩家名\n"
            "/whitelist remove 玩家名\n"
            "/whitelist reload"
        )

    parts = raw.split()
    action = parts[0].lower()

    if action in {"on", "off", "list", "reload"}:
        command = f"whitelist {action}"

    elif action in {"add", "remove"}:
        if len(parts) < 2:
            await whitelist_cmd.finish(f"用法：/whitelist {action} 玩家名")

        player = parts[1]
        command = f"whitelist {action} {player}"

    else:
        await whitelist_cmd.finish(
            "未知白名单操作，可用：on/off/list/add/remove/reload"
        )

    result, log_text = await send_command_and_read_log(command)

    if result.get("status") != 200:
        await whitelist_cmd.finish(f"白名单命令失败：{result.get('data')}")

    await whitelist_cmd.finish(
        f"已执行：{command}\n\n"
        f"最近日志：\n{tail_log(log_text, 6)}"
    )


def register_player_command(name: str, label: str, default_reason: str | None = None):
    matcher = on_command(name, priority=5)

    @matcher.handle()
    async def handle(event: Event, args=CommandArg()):
        if deny := require_admin_text(event.get_user_id()):
            await matcher.finish(deny)
        raw = str(args).strip()
        if not raw:
            suffix = " 原因" if default_reason is not None else ""
            await matcher.finish(f"用法：/{name} 玩家名{suffix}")
        parts = raw.split(maxsplit=1)
        if default_reason is None and len(parts) != 1:
            await matcher.finish("请只填写一个玩家名")
        player = parts[0]
        reason = (parts[1] if len(parts) > 1 else default_reason) if default_reason is not None else None
        command = f"{name} {player}" + (f" {reason}" if reason is not None else "")
        result, log_text = await send_command_and_read_log(command)
        if result.get("status") != 200:
            await matcher.finish(f"{label}失败：{result.get('data')}")
        await matcher.finish(f"已执行：{command}\n\n最近日志：\n{tail_log(log_text, 6)}")

    return matcher


op_cmd = register_player_command("op", "授予 OP")
deop_cmd = register_player_command("deop", "取消 OP")
pardon_cmd = register_player_command("pardon", "解封")
kick_cmd = register_player_command("kick", "踢出", "由管理员移出服务器")
ban_cmd = register_player_command("ban", "封禁", "由管理员封禁")
