"""QQ 指令：control"""
from nonebot import on_command
from nonebot.adapters import Event
from nonebot.params import CommandArg
from ..parsing import extract_players_from_log, tail_log
from ..permissions import get_event_user_id, require_admin_text
from ..services import call_api, send_command_and_read_log, send_console_command
from ..settings import DEFAULT_LOG_LINES


def register_control(name: str, action: str, alias: str, success: str):
    matcher = on_command(name, aliases={alias}, priority=5)

    @matcher.handle()
    async def handle(event: Event):
        if deny := require_admin_text(event.get_user_id()):
            await matcher.finish(deny)
        result = await call_api(action)
        if result.get("status") == 200:
            await matcher.finish(success)
        await matcher.finish(f"{alias}失败：{result.get('data')}")

    return matcher


start_cmd = register_control("start", "open", "启动", "服务器启动请求已发送，请等待服务器加载完成。")
stop_cmd = register_control("stop", "stop", "停止", "服务器正常停止请求已发送，请等待存档完成。")
restart_cmd = register_control("restart", "restart", "重启", "服务器重启请求已发送，请等待服务器重新加载。")


exec_cmd = on_command("exec", priority=5)


@exec_cmd.handle()
async def _(event: Event, args=CommandArg()):
    deny = require_admin_text(get_event_user_id(event))
    if deny:
        await exec_cmd.finish(deny)

    command = str(args).strip()

    if not command:
        await exec_cmd.finish("用法：/exec list")

    result, log_text = await send_command_and_read_log(command)

    if result.get("status") != 200:
        await exec_cmd.finish(f"命令发送失败：{result.get('data')}")

    if command.lower() == "list":
        latest_line, online, max_players, players = extract_players_from_log(log_text)

        await exec_cmd.finish(
            f"已执行：{command}\n\n"
            f"在线人数：{online}/{max_players}\n\n"
            f"在线玩家：\n{players}"
        )

    await exec_cmd.finish(
        f"已向服务器控制台发送命令：\n{command}\n\n"
        f"最近{DEFAULT_LOG_LINES}行日志：\n{tail_log(log_text, DEFAULT_LOG_LINES)}"
    )


say_cmd = on_command("say", priority=5)


@say_cmd.handle()
async def _(event: Event, args=CommandArg()):
    deny = require_admin_text(get_event_user_id(event))
    if deny:
        await say_cmd.finish(deny)

    msg = str(args).strip()

    if not msg:
        await say_cmd.finish("用法：/say 内容")

    result = await send_console_command(f"say {msg}")

    if result.get("status") == 200:
        await say_cmd.finish(f"已向服务器广播：\n{msg}")

    await say_cmd.finish(f"广播失败：{result.get('data')}")
