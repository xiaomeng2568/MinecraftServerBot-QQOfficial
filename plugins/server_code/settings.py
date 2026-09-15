"""共享的运行配置，只在插件加载时读取一次。"""
from nonebot import get_plugin_config
from .config import Config

_config = get_plugin_config(Config)
MCS_URL = _config.mcs_url
API_KEY = _config.mcs_api_key.get_secret_value()
DAEMON_ID = _config.mcs_daemon_id
INSTANCE_UUID = _config.mcs_instance_uuid
INSTANCE_NAME = _config.instance_name
ADMIN_USER_IDS = _config.admin_ids()
TOTAL_DISK_GB = _config.total_disk_gb
DEFAULT_LOG_LINES = 10
MAX_LOG_LINES = 60
COMMAND_LOG_WAIT = 1.5
PUBLIC_MC_HOST = _config.public_mc_host
PUBLIC_MC_PORT = _config.public_mc_port
