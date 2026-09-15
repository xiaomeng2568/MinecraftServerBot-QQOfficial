"""Minecraft 日志和状态解析"""
import re
from typing import List, Optional, Tuple
from .settings import DEFAULT_LOG_LINES, MAX_LOG_LINES


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
