"""状态报告文本生成"""
from .monitoring import (
    build_size_info,
    find_server_java_process,
    get_system_memory_info,
    tcp_latency_ms,
)
from .parsing import extract_players_from_log
from .services import get_server_basic_data, send_command_and_read_log
from .settings import PUBLIC_MC_HOST, PUBLIC_MC_PORT, TOTAL_DISK_GB


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
        f"服务端目录占配置容量：{size_info['disk_percent']}%"
    )
