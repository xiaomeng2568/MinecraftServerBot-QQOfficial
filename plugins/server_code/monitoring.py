"""本机进程、目录和网络监控"""
import asyncio
import os
import psutil
import time
from typing import Optional
from .settings import TOTAL_DISK_GB


def bytes_to_gb(size: int) -> float:
    return round(size / 1024 / 1024 / 1024, 2)


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


def find_server_java_process_sync(server_cwd: str) -> Optional[dict]:
    server_cwd_norm = normalize_path(server_cwd)

    exact_candidates = []

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

            if server_cwd_norm and (
                proc_cwd_norm == server_cwd_norm
                or server_cwd_norm.lower() in cmdline_norm
            ):
                item["matched"] = True
                exact_candidates.append(item)

        except Exception:
            continue

    candidates = exact_candidates

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
