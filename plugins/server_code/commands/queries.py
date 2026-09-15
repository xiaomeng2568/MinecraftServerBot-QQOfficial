"""QQ 指令：queries"""
from nonebot import on_command
from nonebot.adapters import Event
from nonebot.params import CommandArg
from ..monitoring import build_size_info, find_server_java_process, get_system_memory_info
from ..parsing import (
    clamp_log_lines,
    extract_players_from_log,
    extract_tps_points,
    find_recent_lines_by_keywords,
    tail_log,
)
from ..permissions import get_event_user_id, require_admin_text
from ..rendering import build_report_status_text
from ..services import get_output_log, get_server_basic_data, send_command_and_read_log
from ..settings import DEFAULT_LOG_LINES, TOTAL_DISK_GB


log_cmd = on_command("log", priority=5)


@log_cmd.handle()
async def _(event: Event, args=CommandArg()):
    deny = require_admin_text(get_event_user_id(event))
    if deny:
        await log_cmd.finish(deny)

    raw = str(args).strip()
    line_count = DEFAULT_LOG_LINES

    if raw.isdigit():
        line_count = clamp_log_lines(int(raw))

    log_text = await get_output_log()

    await log_cmd.finish(
        f"服务器最近 {line_count} 行日志：\n\n"
        f"{tail_log(log_text, line_count)}"
    )


players_cmd = on_command("players", priority=5)


@players_cmd.handle()
async def _(event: Event):
    result, log_text = await send_command_and_read_log("list")

    if result.get("status") != 200:
        await players_cmd.finish(f"查询失败：{result.get('data')}")

    latest_line, online, max_players, players = extract_players_from_log(log_text)

    await players_cmd.finish(
        f"服务器玩家列表\n\n"
        f"在线人数：{online}/{max_players}\n\n"
        f"在线玩家：\n{players}"
    )


online_cmd = on_command("online", priority=5)


@online_cmd.handle()
async def _(event: Event):
    data = await get_server_basic_data()

    if not data:
        await online_cmd.finish("获取在线信息失败")

    await online_cmd.finish(
        f"在线人数：{data['online']}/{data['max_players']}"
    )


reportnow_cmd = on_command("reportnow", priority=5)


@reportnow_cmd.handle()
async def _(event: Event):
    await reportnow_cmd.finish(
        await build_report_status_text()
    )


worldsize_cmd = on_command("worldsize", priority=5)


@worldsize_cmd.handle()
async def _(event: Event):
    data = await get_server_basic_data()

    if not data:
        await worldsize_cmd.finish("获取世界目录失败")

    size_info = await build_size_info(data["cwd"])

    await worldsize_cmd.finish(
        f"服务器空间占用\n\n"
        f"{size_info['world_label']}：{size_info['world_size_gb']} GB\n"
        f"总文件夹占用：{size_info['server_size_gb']} GB\n\n"
        f"磁盘容量：{TOTAL_DISK_GB} GB\n"
        f"服务端目录占配置容量：{size_info['disk_percent']}%"
    )


memory_cmd = on_command("memory", priority=5)


@memory_cmd.handle()
async def _(event: Event):
    data = await get_server_basic_data()

    if not data:
        await memory_cmd.finish("获取服务器信息失败")

    cwd = data["cwd"]

    java_info = await find_server_java_process(cwd)
    sys_mem = await get_system_memory_info()
    size_info = await build_size_info(cwd)

    if not java_info:
        await memory_cmd.finish(
            f"服务器资源信息\n\n"
            f"Java进程：未找到\n"
            f"可能原因：服务器未启动，或 Java 进程工作目录无法匹配。\n\n"
            f"系统内存：{sys_mem['used_gb']} GB / {sys_mem['total_gb']} GB\n"
            f"系统可用：{sys_mem['available_gb']} GB\n"
            f"系统占用率：{sys_mem['percent']}%\n\n"
            f"{size_info['world_label']}：{size_info['world_size_gb']} GB\n"
            f"总文件夹占用：{size_info['server_size_gb']} GB\n"
            f"磁盘容量：{TOTAL_DISK_GB} GB\n"
            f"服务端目录占配置容量：{size_info['disk_percent']}%"
        )

    matched_text = "已匹配服务器目录"

    await memory_cmd.finish(
        f"服务器资源信息\n\n"
        f"Java进程：运行中\n"
        f"PID：{java_info.get('pid')}\n"
        f"匹配方式：{matched_text}\n\n"
        f"Java内存：{java_info.get('memory_gb')} GB\n"
        f"Java CPU（1 Core）：{java_info.get('cpu_percent')}%\n\n"
        f"系统内存：{sys_mem['used_gb']} GB / {sys_mem['total_gb']} GB\n"
        f"系统可用：{sys_mem['available_gb']} GB\n"
        f"系统占用率：{sys_mem['percent']}%\n\n"
        f"{size_info['world_label']}：{size_info['world_size_gb']} GB\n"
        f"总文件夹占用：{size_info['server_size_gb']} GB\n"
        f"磁盘容量：{TOTAL_DISK_GB} GB\n"
        f"服务端目录占配置容量：{size_info['disk_percent']}%"
    )


tps_cmd = on_command("tps", priority=5)


@tps_cmd.handle()
async def _(event: Event):
    result, log_text = await send_command_and_read_log("forge tps")

    if result.get("status") != 200:
        await tps_cmd.finish(f"⚠️ TPS查询失败：{result.get('data')}")

    points = extract_tps_points(log_text, max_points=3)

    if not points:
        matched = find_recent_lines_by_keywords(
            log_text,
            keywords=[
                "TPS",
                "Mean tick time",
                "Overall",
            ],
            max_lines=3,
            scan_lines=250,
        )

        if matched:
            await tps_cmd.finish(
                f"服务器 TPS 信息\n\n{matched}"
            )

        await tps_cmd.finish(
            f"服务器 TPS 信息\n\n未找到精简TPS数据，可查看 /log 20。"
        )

    await tps_cmd.finish(
        f"服务器 TPS 信息\n\n{points}"
    )
