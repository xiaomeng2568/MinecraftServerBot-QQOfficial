## 这是什么

MinecraftServerBot-QQOfficial 是一个基于 NoneBot2、QQ 官方机器人和 MCSManager API 的 Minecraft 服务器运维机器人。

它的作用是把 QQ 群、QQ 官方机器人、MCSManager 面板和 Minecraft Java 服务端连接起来，让服务器管理员可以直接在 QQ 群里查看和管理服务器。

你可以通过 QQ 群指令完成这些事情：

* 查看服务器是否在线
* 查看当前在线人数
* 查看在线玩家列表
* 查看服务器版本和延迟
* 查看 Java 内存与 CPU 占用
* 查看系统内存占用
* 查看世界存档和服务端目录大小
* 查询 TPS
* 启动、停止、重启服务器
* 向 Minecraft 控制台发送命令
* 定时向 QQ 群播报服务器状态

本项目目前主要面向个人服主、小型 Minecraft 服务器管理员，以及想学习 QQ 官方机器人、NoneBot2 和 MCSManager API 联动的新手开发者。

## 适合新手吗？

本项目适合想要通过 QQ 官方机器人管理 Minecraft 服务器的个人服主或小型服务器管理员。

如果你和作者一样是从零开始，也可以按本文档一步一步配置。但在使用本项目之前，你需要先理解或准备以下内容：

* 一台可以运行 Python 的 Windows / Linux 机器
* 一个已经可以正常运行的 Minecraft Java 服务端
* 一个已经部署好的 MCSManager 面板
* 一个 QQ 官方机器人应用
* QQ 官方机器人 AppID 和 AppSecret
* MCSManager 的 API Key
* MCSManager 节点 ID / 实例 UUID
* 管理员用户 OpenID
* 群聊 OpenID
* 可选：服务器公网地址或内网穿透地址，用于公网延迟检测

本项目不会自动帮你完成 QQ 官方机器人注册、MCSManager 安装、Minecraft 服务端搭建或内网穿透配置。它主要负责把这些已经准备好的系统连接起来，让你可以在 QQ 群里查询和管理服务器。

## 基本架构

```text
QQ群 / QQ官方机器人
        ↓
NoneBot2
        ↓
MCServerBot 插件
        ↓
MCSManager API
        ↓
Minecraft Java 服务端
```

机器人收到 QQ 群里的指令后，会通过 NoneBot2 调用本插件。本插件再通过 MCSManager API 查询或控制 Minecraft 服务端。

## 新手部署流程

### 1. 准备 Minecraft 服务端

你需要先确保 Minecraft Java 服务端可以正常启动，并且玩家可以正常进入服务器。

本项目不会负责安装 Minecraft 服务端本体，也不会负责配置模组包、Forge、Fabric 或服务端核心。

### 2. 准备 MCSManager

你需要安装并运行 MCSManager，并在 MCSManager 中创建好 Minecraft 服务端实例。

确认你可以在 MCSManager 面板里完成以下操作：

* 启动服务器
* 停止服务器
* 查看控制台日志
* 输入控制台命令，例如 `list`

### 3. 获取 MCSManager 配置信息

你需要准备：

```env
MCS_URL=http://127.0.0.1:23333
MCS_API_KEY=YOUR_MCS_API_KEY
MCS_DAEMON_ID=YOUR_DAEMON_ID
MCS_INSTANCE_UUID=YOUR_INSTANCE_UUID
```

其中：

* `MCS_URL` 是 MCSManager 面板地址
* `MCS_API_KEY` 是 MCSManager 的 API Key
* `MCS_DAEMON_ID` 是节点 ID
* `MCS_INSTANCE_UUID` 是 Minecraft 服务端实例 UUID

### 4. 准备 QQ 官方机器人

你需要在 QQ 开放平台 / QQ 机器人平台创建机器人，并获得：

```env
QQ_BOTS=[{"id":1234567890,"token":"","secret":"YOUR_APP_SECRET","intent":{"c2c_group_at_messages":true,"direct_message":true,"at_messages":true},"use_websocket":true}]
```

其中：

* `id` 填 QQ 官方机器人的 AppID
* `secret` 填 QQ 官方机器人的 AppSecret
* `use_websocket` 保持为 `true`

注意：AppSecret 是敏感信息，不要上传到 GitHub。

### 5. 获取管理员 OpenID 和群 OpenID

本项目从 `v0.2.0` 开始内置 `/whoami` 指令，不需要再单独编写 whoami 测试插件。

启动机器人后，在 QQ 群里发送：

```text
@机器人 /whoami
```

V0.2.0后可自动获取解析后的OpenID

### 6. 配置环境变量

复制示例配置：

```bash
cp .env.example .env.prod
```

然后编辑 `.env.prod`，填入你的真实配置。

不要把 `.env.prod` 上传到 GitHub。

### 7. 安装依赖

```bash
pip install -r requirements.txt
```

### 8. 启动机器人

```bash
python bot.py
```

请使用安装依赖时的同一个 Python 环境。此入口会从项目目录加载 `.env.prod`，无需额外安装 `nb-cli`。生产环境不启用热重载。

启动成功后，在 QQ 群里测试：

```text
@机器人 /reportnow
@机器人 /players
@机器人 /memory
```

## 本地开发与云端更新

### 主动播报无权限 / 重连报错

如果日志出现 `40034105: 主动消息失败, 无权限` 或 `RESUMED ... TypeError: 'str' object is not a mapping`，请先阅读 [云端故障处理与迁移](docs/troubleshooting.md)。前者需要平台允许主动消息，后者通过升级 QQ 适配器修复。

当前主动播报默认关闭。没有主动消息权限时，使用 `@机器人 /reportnow` 获取状态；管理员可通过 `/reportstatus` 查看播报诊断，平台权限恢复后通过 `/reportretry` 恢复下一轮尝试。

本地电脑用于编辑和测试；QQ 连接、MCSManager 操作和定时播报在云服务器上运行。

### 本地准备（Git Bash）

```bash
git clone https://github.com/xiaomeng2568/MinecraftServerBot-QQOfficial.git
cd MinecraftServerBot-QQOfficial
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Linux 激活环境使用 `source .venv/bin/activate`。测试使用虚拟配置和模拟请求，不会连接 QQ 或操作 Minecraft。不要把云服务器的 `.venv` 复制到开发电脑。

需要代理时，可只为当前 Git 命令指定代理：

```bash
git -c http.proxy=http://127.0.0.1:7890 pull --ff-only
```

### 云服务器更新

1. 记录当前版本：`git rev-parse HEAD`，在仓库外备份实际使用的 `.env.prod`。
2. 在进程管理器中停止机器人进程。
3. 在仓库目录执行 `git pull --ff-only`。如提示本地修改冲突，先保留并合并修改，不要强制覆盖。
4. 使用云端虚拟环境执行 `python -m pip install -r requirements.txt`。
5. 核对 `.env.prod` 后，通过原有进程管理器运行 `python bot.py`。
6. 检查插件加载日志，然后在 QQ 中验证 `/whoami`、`/online` 和 `/reportnow`。

旧的本地副本如果使用 `MCSM_API_BASE` / `MCSM_API_KEY`，迁移时请改为本仓库的 `MCS_URL` / `MCS_API_KEY`，并补齐节点和实例 ID。系统环境变量优先于 `.env.prod`。

`ADMIN_USER_IDS` 支持逗号分隔（`alice,bob`）或 JSON 数组（`["alice","bob"]`）。首次获取 OpenID 时可以先留空，此时运维命令无权限，但 `/whoami` 可用。定时播报需要有效的 `REPORT_GROUP_OPENID` 和 QQ 平台允许的主动消息权限；配置群 ID 不代表平台一定允许发送。

### v0.2.2 维护变更

- 使用 NoneBot 已加载的配置，修复只编辑 `.env.prod` 时插件仍使用默认值的问题。
- `/stop` 改用 MCSManager 正常停止接口；请在面板中确认 Minecraft 实例的停止命令为 `stop`。正常停止和强制终止是两个不同接口，详见 [MCSManager 实例 API](https://docs.mcsmanager.com/zh_cn/apis/api_instance.html)。
- 网络失败、超时和异常响应返回简明提示，不回显包含 API Key 的请求 URL；控制操作不会自动重试。MCSManager 请求直连配置的面板地址，不读取系统 HTTP 代理。
- 未匹配到实例的 Java 进程时不再使用内存最大的其他 Java 进程；进程信息、系统内存和目录大小仍来自机器人所在机器，完整监控要求与 Minecraft 实例同机并有读取权限。
- 退出机器人时取消定时播报任务；未配置群 ID 时跳过任务创建。

`TOTAL_DISK_GB` 仍为手动配置容量，报告中的百分比表示服务端目录大小占该容量的比例，并非整块磁盘实际已用百分比。TPS 当前仍使用 `forge tps`，其他服务端核心需要另行适配。

## 代码结构

```text
plugins/server_code/
├─ __init__.py          插件信息和模块加载入口
├─ config.py            配置模型和校验
├─ settings.py          加载后的共享配置
├─ permissions.py       管理员权限
├─ mcs_client.py        HTTP 请求与异常处理
├─ services.py          MCSManager 业务接口
├─ monitoring.py        本机 Java、内存、目录和 TCP 监控
├─ parsing.py           玩家列表、日志和 TPS 解析
├─ rendering.py         状态报告文本
├─ reporting.py         定时播报、权限暂停和任务生命周期
└─ commands/
   ├─ control.py       启动、停止、重启、执行命令、广播
   ├─ queries.py       日志、玩家、在线人数、资源、TPS、手动报告
   ├─ players.py       白名单、OP、封禁与踢出
   ├─ help.py          命令帮助和 OpenID 查询
   └─ diagnostics.py   播报诊断与恢复
```

各模块由入口统一加载，仍是一个 `server_code` 插件，不要把子模块单独写入插件列表。移除了无关的内置 `echo` 配置，新增诊断功能无需额外安装第三方插件。

## 常见问题

### 为什么机器人没反应？

可能原因：

* 没有 @ 机器人
* QQ 官方机器人没有加入当前群
* AppID 或 AppSecret 配置错误
* `.env.prod` 没有被正确读取
* NoneBot 没有成功加载 QQ 适配器
* 插件名和 `pyproject.toml` 中的配置不一致

### 为什么提示无权限？

说明你的 `ADMIN_USER_IDS` 没有填对。

请确认你填写的是 QQ 官方机器人体系下的 OpenID，而不是普通 QQ 号。

### 为什么无法启动或停止服务器？

可能原因：

* MCSManager API Key 错误
* Daemon ID 错误
* Instance UUID 错误
* MCSManager 面板没有运行
* Minecraft 实例状态不允许当前操作

### 为什么公网延迟显示为 MCS 本地？

如果没有配置：

```env
PUBLIC_MC_HOST=
PUBLIC_MC_PORT=25565
```

机器人会退回使用 MCSManager 返回的本地延迟。

真正准确的公网延迟需要从外部网络测试，例如使用 VPS 或其他网络环境部署探针。

## 安全提醒

请不要提交以下内容到 GitHub 也不要告诉你不信任的任何人：

* `.env.prod`
* QQ 官方机器人 AppSecret
* MCSManager API Key
* 管理员 OpenID
* 群 OpenID
* NapCat 登录缓存
* QQ 密码
* 服务器真实管理入口

`/exec`、`/op`、`/ban`、`/kick` 等命令具有高权限，请务必正确配置 `ADMIN_USER_IDS`。

### 若有其他问题 请发送电子邮件至xiaomeng2568@163.com
