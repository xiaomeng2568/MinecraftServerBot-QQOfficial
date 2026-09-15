"""Minecraft 运维插件入口；业务实现按职责拆分。"""
from nonebot.plugin import PluginMetadata
from .config import Config

__plugin_meta__ = PluginMetadata(
    name="Minecraft 服务器运维",
    description="通过 QQ 官方机器人管理 MCSManager 实例",
    usage="@机器人 /mchelp",
    config=Config,
)

from .commands import control, queries, players, help, diagnostics
from . import reporting
