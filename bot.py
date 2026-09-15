"""在项目目录执行 python bot.py 启动生产服务。"""

from pathlib import Path
import os

import nonebot
from nonebot.adapters.qq import Adapter


def main() -> None:
    os.chdir(Path(__file__).resolve().parent)
    nonebot.init()
    nonebot.get_driver().register_adapter(Adapter)
    if nonebot.load_plugin("plugins.server_code") is None:
        raise RuntimeError("运维插件加载失败，请检查配置和上方日志")
    nonebot.run()


if __name__ == "__main__":
    main()
