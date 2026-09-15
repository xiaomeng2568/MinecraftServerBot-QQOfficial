# 云端故障处理与迁移

## 1. 主动消息失败：40034105

日志中的 `主动消息失败, 无权限` 是 QQ API 对主动发送的拒绝，不是机器人离线，也不是 `ADMIN_USER_IDS` 填错。没有用户消息作为上下文的定时推送属于主动消息；`@机器人 /reportnow` 使用当前消息上下文进行回复。

代码不能开通 QQ 平台权限，也不应使用伪造或过期的消息 ID 绕过限制。

### 当前推荐配置

在云端实际使用的 `.env.prod` 中设置：

```dotenv
ENABLE_HOURLY_REPORT=false
```

重启机器人后，在群里使用 `@机器人 /reportnow`。如需每小时自动推送，请先在 QQ 开放平台核实该应用和目标群是否允许主动消息；若没有对应能力，需要向平台咨询，不能靠修改本地权限解决。

### 新增诊断功能

- `/reportstatus`：显示开关、群配置是否存在、任务状态、最近结果和因权限被暂停的 Bot 数量。
- `/reportretry`：仅在配置开启且群已填写时清除暂停状态，在下一轮重新尝试。此命令不会授予平台权限，也不立即向目标群发送消息。
- `/reportnow`：保留手动状态查询，不受主动播报暂停影响。

以上指令均要求管理员权限。新代码遇到 `40034105` 后暂停对应 Bot 的主动播报，之后不会反复生成报告和调用被拒绝的发送接口。暂停状态保存在当前进程内，重启后会重新尝试；希望一直关闭时请使用上述环境配置。

## 2. RESUMED 事件解析异常

原日志已经显示 `Bot ... connected`，随后收到 `RESUMED` 且 `data=''`。旧版适配器在构造事件时直接展开字符串，触发 `TypeError`；这是事件解析告警，不等同于整台 Minecraft 服务器崩溃。

本项目将 `nonebot-adapter-qq` 最低版本提高到 **1.7.2**，该版本对非字典事件数据使用空字典。本地已用日志中的空字符串 `RESUMED` 事件验证。上游代码参见 [NoneBot QQ 适配器](https://github.com/nonebot/adapter-qq/blob/master/nonebot/adapters/qq/adapter.py)。无需手工修改 `.venv/Lib/site-packages`。

在**云服务器机器人实际使用的虚拟环境**中安装依赖并确认版本，例如 Windows：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -c "from importlib.metadata import version; print(version('nonebot-adapter-qq'))"
```

确认输出不低于 `1.7.2`，再重启机器人。只在开发电脑升级依赖不会改变云端环境。

## 3. 从 D:\Bot\BotTest1 旧项目迁移

本次拆分增加多个文件，**不能只替换 `__init__.py`**。

1. 在云端停止旧机器人进程，将旧目录和 `.env.prod` 备份到插件目录之外。
2. 推荐将仓库克隆到新的独立目录，例如 `D:\Bot\MinecraftServerBot-QQOfficial`，不要覆盖 Minecraft 存档目录。
3. 用云服务器上的 Python 新建 `.venv`，安装 `requirements.txt`。
4. 对照 `.env.example` 将旧的配置填入新的 `.env.prod`。旧代码里硬编码的 API Key、节点 ID、实例 ID、管理员和群 ID，需要显式迁移到配置文件。
5. 如果旧配置使用 `MCSM_API_BASE` / `MCSM_API_KEY`，改为 `MCS_URL` / `MCS_API_KEY`。无主动权限时设 `ENABLE_HOURLY_REPORT=false`。
6. 将进程管理器的工作目录改为新项目目录，启动命令使用该项目虚拟环境的 `python.exe bot.py`。
7. 确认只运行一个机器人进程，且只加载新的 `server_code` 插件。不要同时加载旧的 `QQ_OfficialBot_Test1`，否则旧定时器和同名指令仍会执行。
8. 测试 `/whoami`、`/online`、`/reportnow`、`/reportstatus`，检查日志是否仍出现旧版 `[服务器] 暂无可用Bot` 提示。

`qq_whoami` 和 `qq_official_test` 的旧独立插件已无迁移必要：OpenID 查询内置于 `help.py`，实际消息回复即可验证链路。`cti_status` 原本只是加载测试，不包含真实服务器状态功能。

本地测试不会发送真实 QQ 消息或控制云端服务器。部署后的平台权限和实际群回复仍需在云端验证。
