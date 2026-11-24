"""Minimal CDP WebSocket wire transport for ExistingChromeCollector."""
from __future__ import annotations

import asyncio
from contextlib import suppress
import json

from signal_miner.connectors.existing_chrome_adapter import ChromeError, validate_url
from signal_miner.connectors.existing_chrome_scripts import ALLOWED_DOM_SCRIPTS


class DOMTransport:
    """Minimal CDP wire client: no auto-attach, Network or browser close command."""

    BROWSER_METHODS = {"Target.getTargets", "Target.getTargetInfo", "Target.attachToTarget", "Target.detachFromTarget"}
    SESSION_METHODS = {"Page.navigate", "Runtime.evaluate"}

    def __init__(self, socket):
        self.socket = socket
        self.pending = {}
        self.sessions = set()
        self.sequence = 0
        self.closed = False
        self.reader = asyncio.create_task(self._read())

    @classmethod
    async def connect(cls, endpoint: str):
        try:
            from websockets.asyncio.client import connect
        except ImportError as exc:
            raise ChromeError("dependency_unavailable", "请安装项目可选依赖 signal-miner[browser] 后重试。", 503) from exc
        try:
            socket = await connect(endpoint, open_timeout=45, proxy=None, max_size=4_000_000,
                                   additional_headers={"User-Agent": "MINING Existing Chrome DOM Collector"})
        except TimeoutError as exc:
            raise ChromeError("authorization_or_connection_timeout", "等待 Chrome 允许连接或建立传输超时；尚未连接。") from exc
        except Exception as exc:
            # Endpoint / handshake details may contain local or sensitive data.
            raise ChromeError("chrome_connection_unavailable", "Chrome 当前会话连接未建立，可能未允许连接或发现信息已失效。") from exc
        return cls(socket)

    async def _read(self):
        try:
            async for packet in self.socket:
                data = json.loads(packet)
                future = self.pending.get(data.get("id"))
                if future and not future.done():
                    if "error" in data:
                        message = str(data["error"].get("message", "")).lower()
                        context_changed = any(marker in message for marker in (
                            "execution context was destroyed", "cannot find default execution context",
                            "cannot find context with specified id",
                        ))
                        error = ChromeError("execution_context_changed", "所选页面正在切换执行上下文。") if context_changed else ChromeError("cdp_command_failed", "Chrome 未完成所选页面操作；标签可能已关闭或不可用。")
                        future.set_exception(error)
                    else:
                        future.set_result(data.get("result", {}))
        except (Exception, asyncio.CancelledError):
            pass
        finally:
            self.closed = True
            for future in tuple(self.pending.values()):
                if not future.done():
                    future.set_exception(ChromeError("transport_disconnected", "Chrome 连接已断开。"))

    async def command(self, method, params=None, *, session_id=None):
        params = params or {}
        allowed = self.SESSION_METHODS if session_id else self.BROWSER_METHODS
        if method not in allowed or (session_id and session_id not in self.sessions):
            raise ChromeError("forbidden_cdp_command", "采集器拒绝超出限定范围的浏览器操作。")
        if method == "Runtime.evaluate" and params.get("expression") not in ALLOWED_DOM_SCRIPTS:
            raise ChromeError("forbidden_script", "采集器仅允许固定正文选择器。")
        if method == "Page.navigate":
            validate_url(params.get("url"))
        if self.closed:
            raise ChromeError("transport_disconnected", "Chrome 连接已断开。")
        self.sequence += 1
        packet = {"id": self.sequence, "method": method, "params": params}
        if session_id:
            packet["sessionId"] = session_id
        future = asyncio.get_running_loop().create_future()
        self.pending[self.sequence] = future
        try:
            try:
                await self.socket.send(json.dumps(packet))
            except Exception as exc:
                self.closed = True
                raise ChromeError("transport_disconnected", "Chrome 连接在操作期间断开；本次操作未完成。") from exc
            result = await asyncio.wait_for(future, timeout=12)
            if method == "Target.attachToTarget":
                if not isinstance(result.get("sessionId"), str) or not result["sessionId"]:
                    raise ChromeError("invalid_cdp_response", "Chrome 未返回有效的所选标签会话。")
                self.sessions.add(result["sessionId"])
            if method == "Target.detachFromTarget":
                self.sessions.discard(params.get("sessionId"))
            return result
        except TimeoutError as exc:
            raise ChromeError("page_operation_timeout", "等待所选页面操作超时。") from exc
        finally:
            self.pending.pop(packet["id"], None)

    async def stop(self):
        """Disconnect only the owned wire. Borrowed browser targets stay open."""
        await self.socket.close()
        self.reader.cancel()
        with suppress(asyncio.CancelledError):
            await self.reader


