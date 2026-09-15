"""主动播报生命周期与权限拒绝状态；被动查询不依赖本模块。"""
import asyncio
from contextlib import suppress
from dataclasses import dataclass
from nonebot import get_bots, get_driver, logger
from nonebot.adapters.qq.exception import ActionFailed
from .rendering import build_report_status_text
from .settings import _config as config


@dataclass
class ReportState:
    last_result: str = "尚未发送"
    last_code: int | None = None


state = ReportState()
blocked_bots: set[str] = set()
_task: asyncio.Task | None = None


def configured() -> bool:
    group = config.report_group_openid.strip()
    return bool(group and not group.startswith("YOUR_"))


async def send_report_to_group() -> str:
    if not config.enable_hourly_report:
        state.last_result = "已关闭主动播报；可使用 /reportnow 查询"
        return "disabled"
    if not configured():
        state.last_result = "未配置有效 REPORT_GROUP_OPENID"
        return "unconfigured"
    bots = [bot for bot in get_bots().values() if bot.adapter.get_name() == "QQ"]
    if not bots:
        state.last_result = "暂无已连接的 QQ Bot"
        return "offline"
    candidates = [bot for bot in bots if bot.self_id not in blocked_bots]
    if not candidates:
        state.last_result = "主动消息无权限，已暂停重试；请使用 /reportnow"
        return "blocked"

    message = await build_report_status_text()
    for bot in candidates:
        try:
            await bot.call_api(
                "post_group_messages", group_openid=config.report_group_openid.strip(),
                msg_type=0, content=message,
            )
        except ActionFailed as exc:
            state.last_code = exc.code
            if exc.code == 40034105:
                blocked_bots.add(bot.self_id)
                state.last_result = "QQ 拒绝主动消息权限（40034105），已暂停该 Bot 重试"
                logger.warning(
                    "{}。请在 QQ 开放平台核实主动消息权限，或使用 /reportnow；"
                    "权限修复后可用 /reportretry 恢复下一轮尝试。trace_id={}",
                    state.last_result, exc.trace_id or "无",
                )
            else:
                state.last_result = f"QQ 发送失败：HTTP {exc.status_code}，code={exc.code}"
                logger.warning("{}，trace_id={}", state.last_result, exc.trace_id or "无")
        except Exception as exc:
            state.last_code = None
            state.last_result = f"播报发送异常：{type(exc).__name__}"
            logger.warning(state.last_result)
        else:
            state.last_code = None
            state.last_result = "主动播报发送成功"
            return "sent"
    return "blocked" if all(bot.self_id in blocked_bots for bot in bots) else "failed"


def status_text() -> str:
    running = _task is not None and not _task.done()
    return (
        "定时播报诊断\n\n"
        f"主动播报配置：{'开启' if config.enable_hourly_report else '关闭'}\n"
        f"目标群配置：{'已填写' if configured() else '未填写'}\n"
        f"后台任务：{'运行中' if running else '未运行'}\n"
        f"间隔：{config.report_interval_seconds} 秒\n"
        f"被权限拒绝的 Bot 数：{len(blocked_bots)}\n"
        f"最近结果：{state.last_result}\n\n"
        "40034105 表示 QQ 平台未允许主动消息，修改本地管理员权限不能解决。\n"
        "无主动权限时请 @机器人 /reportnow 获取被动回复。\n"
        "在平台确认权限并核对目标群后，使用 /reportretry 恢复下一轮尝试。"
    )


async def report_loop():
    await asyncio.sleep(config.report_first_delay_seconds)
    while True:
        try:
            await send_report_to_group()
        except Exception as exc:
            state.last_result = f"报告生成异常：{type(exc).__name__}"
            logger.warning(state.last_result)
        await asyncio.sleep(config.report_interval_seconds)


@get_driver().on_startup
async def start_report_task():
    global _task
    if not config.enable_hourly_report or not configured():
        logger.info("主动播报未启用或目标群未配置；/reportnow 可用于手动查询")
        return
    if _task is None or _task.done():
        _task = asyncio.create_task(report_loop(), name="qq-server-report")
        logger.info("定时播报任务已启动，间隔 {} 秒", config.report_interval_seconds)


@get_driver().on_shutdown
async def stop_report_task():
    global _task
    if _task is not None:
        _task.cancel()
        with suppress(asyncio.CancelledError):
            await _task
        _task = None


async def resume_reports() -> str:
    if not config.enable_hourly_report:
        return "主动播报已关闭。确认平台权限后设置 ENABLE_HOURLY_REPORT=true 并重启机器人。"
    if not configured():
        return "请先填写 REPORT_GROUP_OPENID 并重启机器人。"
    blocked_bots.clear()
    state.last_result = "已清除权限拒绝记录，等待下一轮播报"
    state.last_code = None
    await start_report_task()
    return "已恢复下一轮播报尝试；若 QQ 仍返回 40034105，将再次暂停。此操作不会开通平台权限。"
