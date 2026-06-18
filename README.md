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

### 5. 获取管理员 OpenID

机器人需要知道谁是管理员，否则任何人都可能执行高权限命令。

你可以先写一个简单的 `/whoami` 测试插件，或者通过 NoneBot 日志查看事件中的用户 ID。

配置示例：

```env
ADMIN_USER_IDS=YOUR_QQ_OFFICIAL_USER_OPENID
```

如果有多个管理员，可以用英文逗号分隔：

```env
ADMIN_USER_IDS=OPENID_1,OPENID_2,OPENID_3
```

### 6. 获取群 OpenID

定时播报需要群聊 OpenID。

通常可以通过 QQ 官方机器人事件里的 `session_id` 获取。格式可能类似：

```text
group_群OPENID_用户OPENID
```

中间那段就是群 OpenID。

配置示例：

```env
REPORT_GROUP_OPENID=YOUR_GROUP_OPENID
```

### 7. 配置环境变量

复制示例配置：

```bash
cp .env.example .env.prod
```

然后编辑 `.env.prod`，填入你的真实配置。

不要把 `.env.prod` 上传到 GitHub。

### 8. 安装依赖

```bash
pip install -r requirements.txt
```

### 9. 启动机器人

```bash
nb run --reload
```

启动成功后，在 QQ 群里测试：

```text
@机器人 /reportnow
@机器人 /players
@机器人 /memory
```

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

请不要提交以下内容到 GitHub：

* `.env.prod`
* QQ 官方机器人 AppSecret
* MCSManager API Key
* 管理员 OpenID
* 群 OpenID
* NapCat 登录缓存
* QQ 密码
* 服务器真实管理入口

`/exec`、`/op`、`/ban`、`/kick` 等命令具有高权限，请务必正确配置 `ADMIN_USER_IDS`。
