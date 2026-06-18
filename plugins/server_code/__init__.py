from nonebot import on_command, get_driver, get_bots
from nonebot.adapters import Event
from nonebot.params import CommandArg

import asyncio
import httpx
import os
import re
import time
import psutil
from typing import Optional, Tuple, List

# 注意：/exec、/op、/ban、/kick 等命令具有高权限，请务必正确配置 ADMIN_USER_IDS。
# ============================================================
# Minecraft 运维机器人 - 官方 QQ 单适配版
# 适配：
# NoneBot2 + nonebot-adapter-qq + MCSManager 10.12.4
#
# 已包含：
# /start
# /stop
# /restart
# /exec
# /say
# /log
# /players
# /online
# /reportnow
# /worldsize
# /memory
# /whitelist
# /op
# /deop
# /kick
# /ban
# /pardon
# /tps
# /mchelp
#
#
# 不包含：
# /backup
# 玩家加入自动通知
# 玩家退出自动通知
# 死亡通知
# 自动备份
# ============================================================


# ====================
# 基础配置区
# ====================

MCS_URL = os.getenv("MCS_URL", "http://127.0.0.1:23333")

# 这里填你的 MCSManager API Key
API_KEY = os.getenv("MCS_API_KEY", "YOUR_MCS_API_KEY")

DAEMON_ID = os.getenv("MCS_DAEMON_ID", "YOUR_DAEMON_ID")
INSTANCE_UUID = os.getenv("MCS_INSTANCE_UUID", "YOUR_INSTANCE_UUID")

INSTANCE_NAME = os.getenv("INSTANCE_NAME", "Minecraft Server")

# 官方 QQ 机器人里，你自己的 user_id / openid
# 通过@机器人 /whoami的返回值
ADMIN_USER_IDS = {
    item.strip()
    for item in os.getenv("ADMIN_USER_IDS", "YOUR_ADMIN_USER_OPENID").split(",")
    if item.strip()
}

# 你当前沙箱群 session_id：
# 例如group_xxxxxxxxxxxxxxxxxxxxx_yyyyyyyyyyyyyyyyyyyy
# 群 openid 通常是 session_id 中 group_ 后、第一个用户 openid 前的部分
REPORT_GROUP_OPENID = os.getenv("REPORT_GROUP_OPENID", "YOUR_GROUP_OPENID")

# 磁盘容量 默认数值2000GB 可自行更改
TOTAL_DISK_GB = int(os.getenv("TOTAL_DISK_GB", "2000"))

DEFAULT_LOG_LINES = 10
MAX_LOG_LINES = 60

COMMAND_LOG_WAIT = 1.5


# ====================
# 定时播报配置
# ====================

ENABLE_HOURLY_REPORT = os.getenv("ENABLE_HOURLY_REPORT", "true").lower() == "true"

# 每隔多少秒自动播报一次
# 3600 = 1小时
REPORT_INTERVAL_SECONDS = int(os.getenv("REPORT_INTERVAL_SECONDS", "3600"))

# 启动后多久第一次播报
REPORT_FIRST_DELAY_SECONDS = int(os.getenv("REPORT_FIRST_DELAY_SECONDS", "180"))

# 玩家实际连接服务器用的公网IP或域名 可能需要部署一个或多个探针
PUBLIC_MC_HOST = os.getenv("PUBLIC_MC_HOST", "")
PUBLIC_MC_PORT = int(os.getenv("PUBLIC_MC_PORT", "25565"))


# ====================
# 权限与基础工具
# ====================

def is_admin(user_id) -> bool:
    return str(user_id) in ADMIN_USER_IDS


def require_admin_text(user_id) -> Optional[str]:
    if not is_admin(user_id):
        return "无权限"
    return None


def get_event_user_id(event: Event) -> str:
    return event.get_user_id()


def base_params() -> dict:
    return {
        "uuid": INSTANCE_UUID,
        "instanceUuid": INSTANCE_UUID,
        "daemonId": DAEMON_ID,
        "apikey": API_KEY,
    }


def status_text(code) -> str:
    mapping = {
        -1: "忙碌",
        0: "已停止",
        1: "停止中",
        2: "启动中",
        3: "运行中",
    }
    return mapping.get(code, f"未知({code})")


def clamp_log_lines(n: int) -> int:
    return max(5, min(n, MAX_LOG_LINES))


def bytes_to_gb(size: int) -> float:
    return round(size / 1024 / 1024 / 1024, 2)


def normalize_log_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def split_clean_lines(text: str) -> List[str]:
    lines = normalize_log_text(text).split("\n")
    return [line for line in lines if line.strip()]


def tail_log(log_text: str, line_count: int = DEFAULT_LOG_LINES) -> str:
    lines = split_clean_lines(log_text)

    if not lines:
        return "暂无日志"

    return "\n".join(lines[-line_count:])


def normalize_path(path: str) -> str:
    if not path:
        return ""

    try:
        return os.path.normcase(os.path.abspath(path)).replace("/", "\\").rstrip("\\")
    except Exception:
        return str(path).replace("/", "\\").lower().rstrip("\\")


def normalize_text_path(text: str) -> str:
    if not text:
        return ""

    return str(text).replace("/", "\\").lower()


def get_folder_size_sync(path: str) -> int:
    total = 0

    if not path or not os.path.exists(path):
        return 0

    for root, dirs, files in os.walk(path):
        for file in files:
            try:
                fp = os.path.join(root, file)

                if os.path.exists(fp):
                    total += os.path.getsize(fp)

            except Exception:
                pass

    return total


async def get_folder_size(path: str) -> int:
    return await asyncio.to_thread(get_folder_size_sync, path)


def format_player_names(raw_names: str) -> str:
    raw_names = raw_names.strip()

    if not raw_names:
        return "无"

    names = []

    for item in raw_names.split(","):
        name = item.strip()
        if name:
            names.append(name)

    if not names:
        return "无"

    return "\n".join(names)


def parse_player_list_line(line: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if not line:
        return None, None, None

    m = re.search(
        r"There are\s+(\d+)\s+of\s+a\s+max\s+of\s+(\d+)\s+players online:\s*(.*)",
        line,
    )

    if not m:
        return None, None, None

    online = m.group(1)
    max_players = m.group(2)
    raw_players = m.group(3)

    return online, max_players, format_player_names(raw_players)


def find_latest_player_list_line(log_text: str) -> str:
    lines = split_clean_lines(log_text)

    for line in reversed(lines):
        if "There are" in line and "players online" in line:
            return line

    return ""


def extract_players_from_log(log_text: str) -> Tuple[str, str, str, str]:
    latest_line = find_latest_player_list_line(log_text)

    online, max_players, players = parse_player_list_line(latest_line)

    if online is None:
        return latest_line, "未知", "未知", "未找到在线玩家信息"

    return latest_line, online, max_players, players


def find_recent_lines_by_keywords(
    log_text: str,
    keywords: List[str],
    max_lines: int = 8,
    scan_lines: int = 200,
) -> str:
    lines = split_clean_lines(log_text)
    recent = lines[-scan_lines:]

    matched = []

    for line in reversed(recent):
        if any(k.lower() in line.lower() for k in keywords):
            matched.append(line)

            if len(matched) >= max_lines:
                break

    if not matched:
        return ""

    return "\n".join(reversed(matched))


def extract_time_from_log_line(line: str) -> str:
    m = re.search(r"\[(\d{2}:\d{2}:\d{2})\]", line)

    if m:
        return m.group(1)

    return "??:??:??"


def extract_tps_value_from_line(line: str) -> Optional[str]:
    patterns = [
        r"Mean TPS[:：]?\s*([0-9]+(?:\.[0-9]+)?)",
        r"\bTPS[:：]\s*([0-9]+(?:\.[0-9]+)?)",
        r"\bTPS\s+([0-9]+(?:\.[0-9]+)?)",
    ]

    for pattern in patterns:
        m = re.search(pattern, line, flags=re.IGNORECASE)

        if m:
            try:
                return f"{float(m.group(1)):.3f}"
            except Exception:
                return m.group(1)

    return None


def extract_tps_points(log_text: str, max_points: int = 3) -> str:
    lines = split_clean_lines(log_text)

    order = []
    records = {}

    for line in lines:
        if "tps" not in line.lower():
            continue

        tps_value = extract_tps_value_from_line(line)

        if not tps_value:
            continue

        t = extract_time_from_log_line(line)
        lower = line.lower()
        is_overall = "overall" in lower or "mean" in lower

        if t not in records:
            order.append(t)
            records[t] = {
                "value": tps_value,
                "overall": is_overall,
            }
        else:
            if is_overall or not records[t]["overall"]:
                records[t] = {
                    "value": tps_value,
                    "overall": is_overall,
                }

    if not order:
        return ""

    last_times = order[-max_points:]

    result_lines = []

    for t in last_times:
        value = records[t]["value"]
        result_lines.append(f"[{t}] TPS:{value}")

    return "\n".join(result_lines)


# ====================
# MCSManager API
# ====================

async def call_api(action: str, extra: dict | None = None) -> dict:
    params = base_params()

    if extra:
        params.update(extra)

    url = f"{MCS_URL}/api/protected_instance/{action}"

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, params=params)

    try:
        return resp.json()
    except Exception:
        return {
            "status": resp.status_code,
            "data": resp.text,
        }


async def get_instance_info() -> dict:
    params = base_params()
    url = f"{MCS_URL}/api/instance"

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, params=params)

    try:
        return resp.json()
    except Exception:
        return {
            "status": resp.status_code,
            "data": resp.text,
        }


async def get_output_log() -> str:
    data = await call_api("outputlog")
    return str(data.get("data", ""))


async def send_console_command(command: str) -> dict:
    return await call_api("command", {"command": command})


async def send_command_and_read_log(
    command: str,
    wait: float = COMMAND_LOG_WAIT,
) -> Tuple[dict, str]:
    result = await send_console_command(command)

    if result.get("status") != 200:
        return result, ""

    await asyncio.sleep(wait)

    log_text = await get_output_log()
    return result, log_text


# ====================
# 服务器数据服务
# ====================

async def get_server_basic_data() -> Optional[dict]:
    info_json = await get_instance_info()

    if info_json.get("status") != 200:
        return None

    data = info_json.get("data", {})
    config = data.get("config", {})
    info = data.get("info", {})

    return {
        "raw": data,
        "config": config,
        "info": info,
        "name": config.get("nickname", INSTANCE_NAME),
        "state": status_text(data.get("status")),
        "state_code": data.get("status"),
        "started": data.get("started"),
        "auto_restarted": data.get("autoRestarted"),
        "version": info.get("version", "未知"),
        "online": info.get("currentPlayers", 0),
        "max_players": info.get("maxPlayers", "?"),
        "latency": info.get("latency", "?"),
        "ping_online": bool(info.get("mcPingOnline")),
        "cwd": config.get("cwd", ""),
        "process_info": data.get("processInfo"),
    }


def get_world_path(cwd: str) -> str:
    return os.path.join(cwd, "world")


async def build_size_info(cwd: str) -> dict:
    world_path = get_world_path(cwd)

    if os.path.exists(world_path):
        world_target = world_path
        world_label = "世界占用"
    else:
        world_target = cwd
        world_label = "世界占用"

    world_size_bytes = await get_folder_size(world_target)
    server_size_bytes = await get_folder_size(cwd)

    world_size_gb = bytes_to_gb(world_size_bytes)
    server_size_gb = bytes_to_gb(server_size_bytes)

    disk_percent = round(server_size_gb / TOTAL_DISK_GB * 100, 2)

    return {
        "world_label": world_label,
        "world_size_gb": world_size_gb,
        "server_size_gb": server_size_gb,
        "disk_percent": disk_percent,
    }


# ====================
# Windows Java 进程读取
# ====================

def find_server_java_process_sync(server_cwd: str) -> Optional[dict]:
    server_cwd_norm = normalize_path(server_cwd)

    exact_candidates = []
    fallback_candidates = []

    for proc in psutil.process_iter(
        attrs=[
            "pid",
            "name",
            "exe",
            "cmdline",
            "memory_info",
            "create_time",
            "status",
        ]
    ):
        try:
            name = (proc.info.get("name") or "").lower()

            if name not in {"java.exe", "javaw.exe", "java"}:
                continue

            try:
                proc_cwd = proc.cwd()
            except Exception:
                proc_cwd = ""

            proc_cwd_norm = normalize_path(proc_cwd)

            cmdline_list = proc.info.get("cmdline") or []
            cmdline = " ".join(cmdline_list)
            cmdline_norm = normalize_text_path(cmdline)

            mem_info = proc.info.get("memory_info")
            mem_bytes = mem_info.rss if mem_info else 0

            item = {
                "pid": proc.info.get("pid"),
                "name": proc.info.get("name"),
                "cwd": proc_cwd,
                "cmdline": cmdline,
                "memory_bytes": mem_bytes,
                "memory_gb": bytes_to_gb(mem_bytes),
                "create_time": proc.info.get("create_time"),
                "status": proc.info.get("status"),
                "matched": False,
                "proc": proc,
            }

            fallback_candidates.append(item)

            if server_cwd_norm and (
                proc_cwd_norm == server_cwd_norm
                or server_cwd_norm.lower() in cmdline_norm
            ):
                item["matched"] = True
                exact_candidates.append(item)

        except Exception:
            continue

    candidates = exact_candidates or fallback_candidates

    if not candidates:
        return None

    target = max(
        candidates,
        key=lambda x: x.get("memory_bytes", 0),
    )

    proc = target["proc"]

    try:
        proc.cpu_percent(None)
        time.sleep(0.6)
        cpu_percent = proc.cpu_percent(None)
    except Exception:
        cpu_percent = 0.0

    target["cpu_percent"] = round(cpu_percent, 2)
    target.pop("proc", None)

    return target


async def find_server_java_process(server_cwd: str) -> Optional[dict]:
    return await asyncio.to_thread(
        find_server_java_process_sync,
        server_cwd,
    )


async def get_system_memory_info() -> dict:
    def _read():
        vm = psutil.virtual_memory()

        return {
            "total_gb": bytes_to_gb(vm.total),
            "used_gb": bytes_to_gb(vm.used),
            "available_gb": bytes_to_gb(vm.available),
            "percent": vm.percent,
        }

    return await asyncio.to_thread(_read)


async def tcp_latency_ms(host: str, port: int, timeout: float = 3.0):
    if not host:
        return None

    loop = asyncio.get_running_loop()
    start = loop.time()

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )

        cost_ms = round((loop.time() - start) * 1000)

        writer.close()

        try:
            await writer.wait_closed()
        except Exception:
            pass

        return cost_ms

    except Exception:
        return None


# ====================
# 状态文本生成
# ====================

async def build_report_status_text() -> str:
    data = await get_server_basic_data()

    if not data:
        return (
            "服务器状态\n\n"
            "状态：获取失败\n"
            "可能原因：MCSManager 未响应或实例接口异常"
        )

    result, log_text = await send_command_and_read_log("list")

    if result.get("status") == 200:
        latest_line, log_online, log_max, players = extract_players_from_log(log_text)
    else:
        players = "未能读取玩家列表"

    size_info = await build_size_info(data["cwd"])

    java_info = await find_server_java_process(data["cwd"])

    sys_mem = await get_system_memory_info()

    external_latency = await tcp_latency_ms(
        PUBLIC_MC_HOST,
        PUBLIC_MC_PORT,
    )

    if external_latency is not None:
        latency_text = f"{external_latency}ms（公网TCP）"
    else:
        latency_text = f"{data['latency']}ms（MCS本地）"

    if java_info:
        java_mem_text = f"{java_info.get('memory_gb')} GB"
        java_cpu_text = f"{java_info.get('cpu_percent')}%"
    else:
        java_mem_text = "未找到Java进程"
        java_cpu_text = "未找到Java进程"

    return (
        f"🖥 {data['name']} 状态\n\n"
        f"状态：{data['state']}\n"
        f"版本：{data['version']}\n"
        f"延迟：{latency_text}\n\n"
        f"在线人数：{data['online']}/{data['max_players']}\n\n"
        f"在线玩家：\n"
        f"{players}\n\n"
        f"Java内存：{java_mem_text}\n"
        f"Java CPU（1 Core）：{java_cpu_text}\n\n"
        f"系统内存：{sys_mem['used_gb']} GB / {sys_mem['total_gb']} GB\n"
        f"系统占用率：{sys_mem['percent']}%\n\n"
        f"{size_info['world_label']}：{size_info['world_size_gb']} GB\n"
        f"总文件夹占用：{size_info['server_size_gb']} GB\n"
        f"磁盘容量：{TOTAL_DISK_GB} GB\n"
        f"磁盘占用率：{size_info['disk_percent']}%"
    )


# ====================
# /start
# ====================

start_cmd = on_command("start", aliases={"启动"}, priority=5)

@start_cmd.handle()
async def _(event: Event):
    deny = require_admin_text(get_event_user_id(event))
    if deny:
        await start_cmd.finish(deny)

    result = await call_api("open")

    if result.get("status") == 200:
        await start_cmd.finish("服务器启动请求已发送，请等待服务器加载完成。")

    await start_cmd.finish(f"启动失败：{result.get('data')}")


# ====================
# /stop
# ====================

stop_cmd = on_command("stop", aliases={"停止"}, priority=5)

@stop_cmd.handle()
async def _(event: Event):
    deny = require_admin_text(get_event_user_id(event))
    if deny:
        await stop_cmd.finish(deny)

    result = await call_api("kill")

    if result.get("status") == 200:
        await stop_cmd.finish("服务器停止请求已发送。")

    await stop_cmd.finish(f"停止失败：{result.get('data')}")


# ====================
# /restart
# ====================

restart_cmd = on_command("restart", aliases={"重启"}, priority=5)

@restart_cmd.handle()
async def _(event: Event):
    deny = require_admin_text(get_event_user_id(event))
    if deny:
        await restart_cmd.finish(deny)

    result = await call_api("restart")

    if result.get("status") == 200:
        await restart_cmd.finish("服务器重启请求已发送，请等待服务器重新加载。")

    await restart_cmd.finish(f"重启失败：{result.get('data')}")


# ====================
# /exec
# ====================

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


# ====================
# /say
# ====================

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


# ====================
# /log
# ====================

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


# ====================
# /players
# ====================

players_cmd = on_command("players", priority=5)

@players_cmd.handle()
async def _(event: Event):
    deny = require_admin_text(get_event_user_id(event))
    if deny:
        await players_cmd.finish(deny)

    result, log_text = await send_command_and_read_log("list")

    if result.get("status") != 200:
        await players_cmd.finish(f"查询失败：{result.get('data')}")

    latest_line, online, max_players, players = extract_players_from_log(log_text)

    await players_cmd.finish(
        f"服务器玩家列表\n\n"
        f"在线人数：{online}/{max_players}\n\n"
        f"在线玩家：\n{players}"
    )


# ====================
# /online
# ====================

online_cmd = on_command("online", priority=5)

@online_cmd.handle()
async def _(event: Event):
    deny = require_admin_text(get_event_user_id(event))
    if deny:
        await online_cmd.finish(deny)

    data = await get_server_basic_data()

    if not data:
        await online_cmd.finish("获取在线信息失败")

    await online_cmd.finish(
        f"在线人数：{data['online']}/{data['max_players']}"
    )


# ====================
# /reportnow
# ====================

reportnow_cmd = on_command("reportnow", priority=5)

@reportnow_cmd.handle()
async def _(event: Event):
    deny = require_admin_text(get_event_user_id(event))

    if deny:
        await reportnow_cmd.finish(deny)

    await reportnow_cmd.finish(
        await build_report_status_text()
    )


# ====================
# /worldsize
# ====================

worldsize_cmd = on_command("worldsize", priority=5)

@worldsize_cmd.handle()
async def _(event: Event):
    deny = require_admin_text(get_event_user_id(event))
    if deny:
        await worldsize_cmd.finish(deny)

    data = await get_server_basic_data()

    if not data:
        await worldsize_cmd.finish("获取世界目录失败")

    size_info = await build_size_info(data["cwd"])

    await worldsize_cmd.finish(
        f"服务器空间占用\n\n"
        f"{size_info['world_label']}：{size_info['world_size_gb']} GB\n"
        f"总文件夹占用：{size_info['server_size_gb']} GB\n\n"
        f"磁盘容量：{TOTAL_DISK_GB} GB\n"
        f"磁盘占用率：{size_info['disk_percent']}%"
    )


# ====================
# /memory
# ====================

memory_cmd = on_command("memory", priority=5)

@memory_cmd.handle()
async def _(event: Event):
    deny = require_admin_text(get_event_user_id(event))
    if deny:
        await memory_cmd.finish(deny)

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
            f"磁盘占用率：{size_info['disk_percent']}%"
        )

    matched_text = (
        "已匹配服务器目录"
        if java_info.get("matched")
        else "未精确匹配，使用内存最大的 Java 进程"
    )

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
        f"磁盘占用率：{size_info['disk_percent']}%"
    )


# ====================
# /whitelist
# ====================

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


# ====================
# /op
# ====================

op_cmd = on_command("op", priority=5)

@op_cmd.handle()
async def _(event: Event, args=CommandArg()):
    deny = require_admin_text(get_event_user_id(event))
    if deny:
        await op_cmd.finish(deny)

    player = str(args).strip()

    if not player:
        await op_cmd.finish("用法：/op 玩家名")

    command = f"op {player}"
    result, log_text = await send_command_and_read_log(command)

    if result.get("status") != 200:
        await op_cmd.finish(f"OP失败：{result.get('data')}")

    await op_cmd.finish(
        f"已给予 OP：{player}\n\n"
        f"最近日志：\n{tail_log(log_text, 6)}"
    )


# ====================
# /deop
# ====================

deop_cmd = on_command("deop", priority=5)

@deop_cmd.handle()
async def _(event: Event, args=CommandArg()):
    deny = require_admin_text(get_event_user_id(event))
    if deny:
        await deop_cmd.finish(deny)

    player = str(args).strip()

    if not player:
        await deop_cmd.finish("用法：/deop 玩家名")

    command = f"deop {player}"
    result, log_text = await send_command_and_read_log(command)

    if result.get("status") != 200:
        await deop_cmd.finish(f"DEOP失败：{result.get('data')}")

    await deop_cmd.finish(
        f"已取消 OP：{player}\n\n"
        f"最近日志：\n{tail_log(log_text, 6)}"
    )


# ====================
# /kick
# ====================

kick_cmd = on_command("kick", priority=5)

@kick_cmd.handle()
async def _(event: Event, args=CommandArg()):
    deny = require_admin_text(get_event_user_id(event))
    if deny:
        await kick_cmd.finish(deny)

    raw = str(args).strip()

    if not raw:
        await kick_cmd.finish("用法：/kick 玩家名 原因")

    parts = raw.split(maxsplit=1)
    player = parts[0]
    reason = parts[1] if len(parts) > 1 else "由管理员移出服务器"

    command = f"kick {player} {reason}"
    result, log_text = await send_command_and_read_log(command)

    if result.get("status") != 200:
        await kick_cmd.finish(f"踢出失败：{result.get('data')}")

    await kick_cmd.finish(
        f"已踢出：{player}\n"
        f"原因：{reason}\n\n"
        f"最近日志：\n{tail_log(log_text, 6)}"
    )


# ====================
# /ban
# ====================

ban_cmd = on_command("ban", priority=5)

@ban_cmd.handle()
async def _(event: Event, args=CommandArg()):
    deny = require_admin_text(get_event_user_id(event))
    if deny:
        await ban_cmd.finish(deny)

    raw = str(args).strip()

    if not raw:
        await ban_cmd.finish("用法：/ban 玩家名 原因")

    parts = raw.split(maxsplit=1)
    player = parts[0]
    reason = parts[1] if len(parts) > 1 else "由管理员封禁"

    command = f"ban {player} {reason}"
    result, log_text = await send_command_and_read_log(command)

    if result.get("status") != 200:
        await ban_cmd.finish(f"⚠️ 封禁失败：{result.get('data')}")

    await ban_cmd.finish(
        f"已封禁：{player}\n"
        f"原因：{reason}\n\n"
        f"最近日志：\n{tail_log(log_text, 6)}"
    )


# ====================
# /pardon
# ====================

pardon_cmd = on_command("pardon", priority=5)

@pardon_cmd.handle()
async def _(event: Event, args=CommandArg()):
    deny = require_admin_text(get_event_user_id(event))
    if deny:
        await pardon_cmd.finish(deny)

    player = str(args).strip()

    if not player:
        await pardon_cmd.finish("用法：/pardon 玩家名")

    command = f"pardon {player}"
    result, log_text = await send_command_and_read_log(command)

    if result.get("status") != 200:
        await pardon_cmd.finish(f"⚠️ 解封失败：{result.get('data')}")

    await pardon_cmd.finish(
        f"已解封：{player}\n\n"
        f"最近日志：\n{tail_log(log_text, 6)}"
    )


# ====================
# /tps
# ====================

tps_cmd = on_command("tps", priority=5)

@tps_cmd.handle()
async def _(event: Event):
    deny = require_admin_text(get_event_user_id(event))
    if deny:
        await tps_cmd.finish(deny)

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


# ====================
# /mchelp
# ====================

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
        "/reportnow - 手动查看服务器状态\n"
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


# ====================
# 官方 QQ 定时状态播报
# ====================

async def send_report_to_group():
    bots = get_bots()

    if not bots:
        return False

    message = await build_report_status_text()

    for bot in bots.values():
        try:
            await bot.call_api(
                "post_group_messages",
                group_openid=REPORT_GROUP_OPENID,
                msg_type=0,
                content=message,
            )
            return True

        except Exception as e:
            print(f"[服务器] 官方 QQ 定时状态播报失败：{repr(e)}")

    return False


async def hourly_report_loop():
    await asyncio.sleep(REPORT_FIRST_DELAY_SECONDS)

    while True:
        try:
            sent = await send_report_to_group()

            if not sent:
                print("[服务器] 暂无可用Bot，跳过本次定时状态播报")

        except Exception as e:
            print(f"[服务器] 定时状态播报失败：{repr(e)}")

        await asyncio.sleep(REPORT_INTERVAL_SECONDS)


_driver = get_driver()
_hourly_report_task = None


@_driver.on_startup
async def start_hourly_report_task():
    global _hourly_report_task

    if not ENABLE_HOURLY_REPORT:
        return

    if _hourly_report_task is None:
        _hourly_report_task = asyncio.create_task(
            hourly_report_loop()
        )

        print("[服务器] 官方 QQ 每小时服务器状态播报已启动")
