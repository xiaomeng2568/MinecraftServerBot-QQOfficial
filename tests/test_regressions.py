import asyncio
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import httpx
import nonebot
from nonebot.exception import FinishedException
from pydantic import ValidationError


# 真正经过 NoneBot 的 dotenv 加载，不把测试值写入 os.environ。
with tempfile.TemporaryDirectory() as directory:
    env = Path(directory) / ".env.prod"
    env.write_text(
        "MCS_API_KEY=test-key\nMCS_DAEMON_ID=test-node\n"
        "MCS_INSTANCE_UUID=test-instance\nADMIN_USER_IDS=alice,bob\n"
        "ENABLE_HOURLY_REPORT=false\n", encoding="utf-8",
    )
    nonebot.init(_env_file=env)
    plugin = nonebot.load_plugin("plugins.server_code")
    if plugin is None:
        raise RuntimeError("测试插件加载失败")

from plugins.server_code import settings, monitoring, services, reporting
from plugins.server_code.commands import control
from plugins.server_code.config import Config
from plugins.server_code.mcs_client import request_api


class ConfigTests(unittest.TestCase):
    def test_dotenv_reaches_plugin(self):
        self.assertEqual(settings.API_KEY, "test-key")
        self.assertEqual(settings.ADMIN_USER_IDS, {"alice", "bob"})
        self.assertFalse(settings._config.enable_hourly_report)

    def test_admin_formats(self):
        self.assertEqual(Config(admin_user_ids="alice, bob, ").admin_ids(), {"alice", "bob"})
        self.assertEqual(Config(admin_user_ids=["alice", "bob"]).admin_ids(), {"alice", "bob"})
        self.assertEqual(Config().admin_ids(), set())
        self.assertEqual(Config(admin_user_ids="YOUR_ADMIN_USER_OPENID").admin_ids(), set())

    def test_invalid_settings(self):
        for config in ({"total_disk_gb": 0}, {"report_interval_seconds": 0},
                       {"public_mc_port": 65536}, {"mcs_url": "ftp://host"}):
            with self.subTest(config=config), self.assertRaises(ValidationError):
                Config(**config)

    def test_unrelated_java_is_not_reported(self):
        process = SimpleNamespace(
            info={"name": "java", "pid": 1, "cmdline": [], "memory_info": None},
            cwd=lambda: os.path.abspath("unrelated-server"),
        )
        with patch.object(monitoring.psutil, "process_iter", return_value=[process]):
            self.assertIsNone(monitoring.find_server_java_process_sync(os.path.abspath("target-server")))


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def request(self, response=None, error=None):
        client = AsyncMock()
        client.get.return_value = response
        client.get.side_effect = error
        context = AsyncMock()
        context.__aenter__.return_value = client
        with patch("plugins.server_code.mcs_client.httpx.AsyncClient", return_value=context):
            return await request_api("http://panel", "/api/instance", services.base_params())

    async def test_success(self):
        response = httpx.Response(200, json={"status": 200, "data": {"status": 3}},
                                  request=httpx.Request("GET", "http://panel"))
        self.assertEqual((await self.request(response))["data"], {"status": 3})

    async def test_timeout_does_not_leak_credentials(self):
        result = await self.request(error=httpx.ReadTimeout("http://panel?apikey=test-key"))
        self.assertEqual(result["status"], 504)
        self.assertNotIn("test-key", str(result))

    async def test_bad_responses(self):
        for status, body in ((200, "<html>secret</html>"), (200, "[]"),
                             (200, '{"status":200}'), (403, "secret"),
                             (200, '{"status":403,"data":"secret"}')):
            with self.subTest(status=status, body=body):
                response = httpx.Response(status, text=body,
                                         request=httpx.Request("GET", "http://panel"))
                result = await self.request(response)
                self.assertNotEqual(result["status"], 200)
                self.assertNotIn("secret", str(result))

    async def test_connection_failure(self):
        self.assertEqual((await self.request(error=httpx.ConnectError("secret")))["status"], 502)

    async def test_missing_credentials_do_not_send(self):
        with patch("plugins.server_code.mcs_client.httpx.AsyncClient") as client:
            result = await request_api("http://panel", "/api/instance", {})
            self.assertEqual(result["status"], 503)
            client.assert_not_called()

    async def test_multiline_command_is_rejected(self):
        with patch.object(services, "call_api", new_callable=AsyncMock) as api:
            result = await services.send_console_command("say hi\nstop")
            self.assertEqual(result["status"], 400)
            api.assert_not_awaited()

    async def test_stop_is_graceful(self):
        event = SimpleNamespace(get_user_id=lambda: "alice")
        with patch.object(control, "call_api", new_callable=AsyncMock, return_value={"status": 200}) as api:
            with patch.object(control.stop_cmd, "finish", new_callable=AsyncMock, side_effect=FinishedException):
                with self.assertRaises(FinishedException):
                    await control.stop_cmd.handlers[0].call(event)
            api.assert_awaited_once_with("stop")

    async def test_unauthorized_stop_never_calls_api(self):
        event = SimpleNamespace(get_user_id=lambda: "stranger")
        with patch.object(control, "call_api", new_callable=AsyncMock) as api:
            with patch.object(control.stop_cmd, "finish", new_callable=AsyncMock, side_effect=FinishedException):
                with self.assertRaises(FinishedException):
                    await control.stop_cmd.handlers[0].call(event)
            api.assert_not_awaited()

    async def test_shutdown_cancels_report(self):
        task = asyncio.create_task(asyncio.sleep(3600))
        reporting._task = task
        await reporting.stop_report_task()
        self.assertTrue(task.cancelled())
        self.assertIsNone(reporting._task)


if __name__ == "__main__":
    unittest.main()
