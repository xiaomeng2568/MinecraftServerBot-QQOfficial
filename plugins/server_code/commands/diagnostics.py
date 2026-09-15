"""播报故障诊断和恢复指令，仅供管理员使用。"""
from nonebot import on_command
from nonebot.adapters import Event
from .. import reporting
from ..permissions import require_admin_text


reportstatus_cmd = on_command("reportstatus", priority=5, block=True)
reportretry_cmd = on_command("reportretry", priority=5, block=True)


@reportstatus_cmd.handle()
async def report_status(event: Event):
    if deny := require_admin_text(event.get_user_id()):
        await reportstatus_cmd.finish(deny)
    await reportstatus_cmd.finish(reporting.status_text())


@reportretry_cmd.handle()
async def report_retry(event: Event):
    if deny := require_admin_text(event.get_user_id()):
        await reportretry_cmd.finish(deny)
    await reportretry_cmd.finish(await reporting.resume_reports())
