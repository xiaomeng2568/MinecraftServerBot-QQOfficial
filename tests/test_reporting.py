"""复现云端日志中的权限拒绝和 RESUMED 空字符串事件。"""
import asyncio
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import test_regressions  # 初始化同一测试用 NoneBot 实例
from nonebot.adapters.qq import Adapter
from nonebot.adapters.qq.exception import ActionFailed
from nonebot.adapters.qq.models import Dispatch
from nonebot.drivers import Response
from nonebot.exception import FinishedException

from plugins.server_code import reporting
from plugins.server_code.commands import control, diagnostics, help, queries, players


def qq_bot(error=None):
    return SimpleNamespace(
        self_id="test-bot", adapter=SimpleNamespace(get_name=lambda: "QQ"),
        call_api=AsyncMock(side_effect=error),
    )


class ReportingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.config_patch = patch.object(reporting, "config", SimpleNamespace(
            enable_hourly_report=True, report_group_openid="test-group",
            report_first_delay_seconds=3600, report_interval_seconds=3600,
        ))
        self.config_patch.start()
        reporting.blocked_bots.clear()
        reporting.state = reporting.ReportState()

    async def asyncTearDown(self):
        await reporting.stop_report_task()
        reporting.blocked_bots.clear()
        self.config_patch.stop()

    async def test_permission_denied_pauses_without_rebuilding(self):
        error = ActionFailed(Response(400, content=json.dumps({
            "code": 40034105, "message": "主动消息失败, 无权限",
        })))
        bot = qq_bot(error)
        with patch.object(reporting, "get_bots", return_value={bot.self_id: bot}), \
             patch.object(reporting, "build_report_status_text", new_callable=AsyncMock, return_value="report") as build:
            self.assertEqual(await reporting.send_report_to_group(), "blocked")
            self.assertEqual(await reporting.send_report_to_group(), "blocked")
            bot.call_api.assert_awaited_once()
            build.assert_awaited_once()
        self.assertIn("40034105", reporting.status_text())
        self.assertNotIn("暂无已连接", reporting.state.last_result)

    async def test_disabled_never_reads_server_or_sends(self):
        reporting.config.enable_hourly_report = False
        with patch.object(reporting, "get_bots") as bots:
            self.assertEqual(await reporting.send_report_to_group(), "disabled")
            bots.assert_not_called()

    async def test_offline_is_distinct_from_permission_denied(self):
        with patch.object(reporting, "get_bots", return_value={}):
            self.assertEqual(await reporting.send_report_to_group(), "offline")
        self.assertFalse(reporting.blocked_bots)

    async def test_success_sends_real_active_message(self):
        bot = qq_bot()
        with patch.object(reporting, "get_bots", return_value={bot.self_id: bot}), \
             patch.object(reporting, "build_report_status_text", new_callable=AsyncMock, return_value="report"):
            self.assertEqual(await reporting.send_report_to_group(), "sent")
        bot.call_api.assert_awaited_once_with(
            "post_group_messages", group_openid="test-group", msg_type=0, content="report",
        )

    async def test_other_errors_do_not_permanently_block(self):
        bot = qq_bot(ActionFailed(Response(429, content='{"code":123}')))
        with patch.object(reporting, "get_bots", return_value={bot.self_id: bot}), \
             patch.object(reporting, "build_report_status_text", new_callable=AsyncMock, return_value="report"):
            self.assertEqual(await reporting.send_report_to_group(), "failed")
        self.assertFalse(reporting.blocked_bots)
        self.assertEqual(reporting.state.last_code, 123)

    async def test_resume_clears_block_without_immediate_send(self):
        reporting.blocked_bots.add("test-bot")
        with patch.object(reporting, "send_report_to_group", new_callable=AsyncMock) as send:
            await reporting.resume_reports()
            self.assertFalse(reporting.blocked_bots)
            self.assertIsNotNone(reporting._task)
            send.assert_not_awaited()

    async def test_start_is_idempotent(self):
        await reporting.start_report_task()
        task = reporting._task
        await reporting.start_report_task()
        self.assertIs(reporting._task, task)

    async def test_unconfigured_does_not_start(self):
        reporting.config.report_group_openid = "YOUR_GROUP_OPENID"
        await reporting.start_report_task()
        self.assertIsNone(reporting._task)

    async def test_unauthorized_retry_does_not_clear_block(self):
        reporting.blocked_bots.add("test-bot")
        with patch.object(diagnostics.reportretry_cmd, "finish", new_callable=AsyncMock, side_effect=FinishedException):
            with self.assertRaises(FinishedException):
                await diagnostics.report_retry(SimpleNamespace(get_user_id=lambda: "stranger"))
        self.assertEqual(reporting.blocked_bots, {"test-bot"})

    async def test_manual_report_still_replies_while_blocked(self):
        reporting.blocked_bots.add("test-bot")
        with patch.object(queries, "build_report_status_text", new_callable=AsyncMock, return_value="report"), \
             patch.object(queries.reportnow_cmd, "finish", new_callable=AsyncMock, side_effect=FinishedException) as finish:
            with self.assertRaises(FinishedException):
                await queries.reportnow_cmd.handlers[0].call(SimpleNamespace(get_user_id=lambda: "alice"))
            finish.assert_awaited_once_with("report")

    async def test_player_factory_keeps_command_names(self):
        for matcher, command in ((players.op_cmd, "op Alex"), (players.deop_cmd, "deop Alex"),
                                 (players.pardon_cmd, "pardon Alex"),
                                 (players.kick_cmd, "kick Alex 由管理员移出服务器"),
                                 (players.ban_cmd, "ban Alex 由管理员封禁")):
            with self.subTest(command=command), \
                 patch.object(players, "send_command_and_read_log", new_callable=AsyncMock, return_value=({"status": 200}, "ok")) as send, \
                 patch.object(matcher, "finish", new_callable=AsyncMock, side_effect=FinishedException):
                with self.assertRaises(FinishedException):
                    await matcher.handlers[0].call(SimpleNamespace(get_user_id=lambda: "alice"), "Alex")
                send.assert_awaited_once_with(command)

    async def test_all_operational_commands_require_admin(self):
        matchers = []
        for module in (control, diagnostics, help, queries, players):
            matchers.extend((name, value) for name, value in vars(module).items()
                            if name.endswith("_cmd") and name not in {"whoami_cmd", "mc_help_cmd", "online_cmd", "players_cmd", "reportnow_cmd", "memory_cmd", "worldsize_cmd", "tps_cmd"})
        self.assertEqual(len(matchers), 14)
        for name, matcher in matchers:
            with self.subTest(command=name), \
                 patch.object(matcher, "finish", new_callable=AsyncMock, side_effect=FinishedException) as finish:
                with self.assertRaises(FinishedException):
                    await matcher.handlers[0].call(SimpleNamespace(get_user_id=lambda: "stranger"))
                finish.assert_awaited_once_with("无权限")


class AdapterTests(unittest.TestCase):
    def test_example_qq_configuration(self):
        from pathlib import Path
        from dotenv import dotenv_values
        from nonebot.adapters.qq.config import Config
        values = dotenv_values(Path(__file__).resolve().parents[1] / ".env.example")
        config = Config(qq_bots=json.loads(values["QQ_BOTS"]))
        self.assertIsInstance(config.qq_bots[0].id, str)

    def test_resumed_with_empty_string(self):
        payload = Dispatch.model_validate({"op": 0, "d": "", "s": 22, "t": "RESUMED"})
        event = Adapter.payload_to_event(payload)
        self.assertEqual(event.get_event_name(), "RESUMED")


class PublicCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_normal_player_can_use_all_public_commands(self):
        from contextlib import ExitStack
        event = SimpleNamespace(get_user_id=lambda: "normal-player",
                                get_session_id=lambda: "friend_normal-player",
                                get_type=lambda: "message")
        data = {"cwd": "test-server", "online": 1, "max_players": 20}
        size = {"world_label": "世界占用", "world_size_gb": 1,
                "server_size_gb": 2, "disk_percent": 0.1}
        memory = {"used_gb": 2, "total_gb": 8, "available_gb": 6, "percent": 25}
        with ExitStack() as stack:
            for name, result in {
                "get_server_basic_data": data, "build_size_info": size,
                "get_system_memory_info": memory, "find_server_java_process": None,
                "build_report_status_text": "测试状态报告",
                "send_command_and_read_log": ({"status": 200},
                    "There are 1 of a max of 20 players online: Alex\n[12:00:00] Mean TPS: 20.0"),
            }.items():
                stack.enter_context(patch.object(queries, name, new_callable=AsyncMock, return_value=result))
            for matcher in (help.mc_help_cmd, help.whoami_cmd, queries.online_cmd,
                            queries.players_cmd, queries.reportnow_cmd, queries.memory_cmd,
                            queries.worldsize_cmd, queries.tps_cmd):
                with self.subTest(matcher=matcher), patch.object(
                    matcher, "finish", new_callable=AsyncMock, side_effect=FinishedException
                ) as finish:
                    with self.assertRaises(FinishedException):
                        await matcher.handlers[0].call(event)
                    finish.assert_awaited_once()
                    self.assertNotEqual(finish.call_args.args[0], "无权限")
