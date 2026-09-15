"""MCSManager 请求边界：错误信息不包含 URL、API Key 或原始响应。"""

import httpx


async def request_api(base_url: str, path: str, params: dict) -> dict:
    required = (params.get("apikey"), params.get("daemonId"), params.get("uuid"))
    if any(not value or str(value).startswith("YOUR_") for value in required):
        return {"status": 503, "data": "请先配置 MCS_API_KEY、MCS_DAEMON_ID 和 MCS_INSTANCE_UUID"}
    try:
        async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
            response = await client.get(f"{base_url.rstrip('/')}{path}", params=params)
        response.raise_for_status()
    except httpx.TimeoutException:
        return {"status": 504, "data": "MCSManager 请求超时；操作可能已执行，请先检查实例状态，勿重复发送"}
    except httpx.HTTPStatusError as exc:
        return {"status": exc.response.status_code, "data": f"MCSManager 返回 HTTP {exc.response.status_code}"}
    except httpx.RequestError:
        return {"status": 502, "data": "无法连接 MCSManager，请检查面板地址和网络"}

    try:
        payload = response.json()
    except ValueError:
        return {"status": 502, "data": "MCSManager 返回了非 JSON 响应"}
    if not isinstance(payload, dict) or type(payload.get("status")) is not int:
        return {"status": 502, "data": "MCSManager 响应格式异常"}
    if payload["status"] != 200:
        return {"status": payload["status"], "data": "MCSManager 拒绝请求，请检查权限、实例状态和面板日志"}
    if "data" not in payload:
        return {"status": 502, "data": "MCSManager 响应缺少 data"}
    return payload
