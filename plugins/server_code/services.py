"""MCSManager 服务操作"""
import asyncio
from typing import Optional, Tuple
from .mcs_client import request_api
from .parsing import status_text
from .settings import (
    API_KEY,
    COMMAND_LOG_WAIT,
    DAEMON_ID,
    INSTANCE_NAME,
    INSTANCE_UUID,
    MCS_URL,
)


def base_params() -> dict:
    return {
        "uuid": INSTANCE_UUID,
        "instanceUuid": INSTANCE_UUID,
        "daemonId": DAEMON_ID,
        "apikey": API_KEY,
    }


async def call_api(action: str, extra: dict | None = None) -> dict:
    params = base_params()
    if extra:
        params.update(extra)
    return await request_api(MCS_URL, f"/api/protected_instance/{action}", params)


async def get_instance_info() -> dict:
    return await request_api(MCS_URL, "/api/instance", base_params())


async def get_output_log() -> str:
    data = await call_api("outputlog")
    if data.get("status") != 200:
        return str(data.get("data", "读取日志失败"))
    return str(data.get("data", ""))


async def send_console_command(command: str) -> dict:
    if any(char in command for char in ("\r", "\n", "\x00")):
        return {"status": 400, "data": "控制台命令不能包含换行或空字符"}
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


async def get_server_basic_data() -> Optional[dict]:
    info_json = await get_instance_info()

    if info_json.get("status") != 200:
        return None

    data = info_json.get("data")
    if not isinstance(data, dict):
        return None
    config = data.get("config") or {}
    info = data.get("info") or {}
    if not isinstance(config, dict) or not isinstance(info, dict):
        return None

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
