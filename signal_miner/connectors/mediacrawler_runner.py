"""A local, single-task subprocess bridge. Never forwards upstream logs."""
from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import uuid

from signal_miner.connectors.mediacrawler_adapter import (
    PIN,
    ExportError,
    adapt_exports,
    read_task_exports,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME = PROJECT_ROOT / "tools" / "mediacrawler-runtime"
BRIDGE = PROJECT_ROOT / "scripts" / "run_mediacrawler_task.py"
TASK_TIMEOUT = 600
TERMINAL = {"completed", "empty", "failed", "cancelled", "timed_out"}
DIAGNOSTIC_PHASES = frozenset({
    "initializing", "importing_upstream", "configuring", "starting_crawler",
    "launching_browser", "navigating_platform", "waiting_for_domestic_page", "waiting_for_login", "collecting", "cleaning_up",
})
DIAGNOSTIC_V1_CATEGORIES = frozenset({
    "browser_socket_path_limit", "certificate_error", "connection_error", "timeout", "runtime_error",
})
DIAGNOSTIC_CATEGORIES = DIAGNOSTIC_V1_CATEGORIES | frozenset({
    "platform_verification_required", "platform_access_restricted", "platform_ip_blocked",
    "data_fetch_error", "response_json_error", "content_unavailable",
})
FAILURE_HINTS = {
    "platform_verification_required": "平台要求人工验证；本次任务已结束、未开放部分输出。仅在下一次受控任务确有需要时由用户手动处理，不自动重试或绕过。",
    "platform_access_restricted": "平台拒绝访问，可能涉及认证、限流或账号安全限制；本次已停止，不能仅据此判断登录失效。",
    "platform_ip_blocked": "上游报告IP访问限制；本次已停止，不自动重试或切换代理。",
    "data_fetch_error": "平台数据请求失败，具体原因尚未确定；本次已停止，不把它等同登录失效。",
    "response_json_error": "响应未能解析为JSON；本次已停止，尚不能据此判断网络、验证或登录状态。",
    "content_unavailable": "上游报告内容不存在或异常；本次已停止，未开放部分输出。",
    "certificate_error": "证书校验失败；本次已停止，请核对本机证书或网络，保持TLS校验。",
    "connection_error": "连接失败；本次已停止，请核对本机网络，不自动重试。",
    "timeout": "请求或页面等待超时；本次已停止，未开放部分输出。",
    "browser_socket_path_limit": "浏览器临时套接字路径受限；本次已停止，需核对本机运行环境。",
}
MESSAGES = {
    "running": "专用浏览器正在运行；如出现登录或验证码，请在该窗口手动操作。",
    "waiting_for_domestic_page": "当前专用标签页跳到了Rednote国际站。请先使同一个专用标签页停留在国内小红书（www.xiaohongshu.com）；此时尚未读取登录态或采集，请勿在国际页登录。可手动停止本任务。",
    "waiting_for_login": "请在专用浏览器手动登录或完成验证；普通Chrome登录不会自动共享。",
    "collecting": "正在处理本次有界样本；如遇登录或验证，请手动操作。",
    "completed": "已取得本次采集材料，请核对来源与正文后选择导入。",
    "empty": "进程已结束，但没有可导入材料；未宣称采集成功。",
    "failed": "任务失败，具体原因尚未确定，未开放部分输出。",
    "cancelled": "本任务已停止，未开放部分输出。",
    "timed_out": "本任务达到10分钟总时限，已停止；未开放部分输出。",
}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def read_failure_diagnostic(directory: Path) -> dict | None:
    """Strictly whitelist bounded metadata; malformed diagnostics stay generic."""
    path = directory / "diagnostic.json"
    try:
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 4096:
            return None
        with path.open("rb") as stream:
            encoded = stream.read(4097)
        if len(encoded) > 4096:
            return None
        data = json.loads(encoded)
        if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] not in {1, 2}:
            return None
        expected = {"version", "exception_type", "phase", "category", "frames"}
        if data["version"] == 2:
            expected |= {"root_exception_type", "root_frames"}
        if set(data) != expected:
            return None
        categories = DIAGNOSTIC_CATEGORIES if data["version"] == 2 else DIAGNOSTIC_V1_CATEGORIES
        if data["phase"] not in DIAGNOSTIC_PHASES or data["category"] not in categories:
            return None
        names = [data["exception_type"]]
        groups = [data["frames"]]
        if data["version"] == 2:
            names.append(data["root_exception_type"])
            groups.append(data["root_frames"])
            if data["root_exception_type"] == "unknown" and data["root_frames"] != []:
                return None
        if any(not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", name) for name in names):
            return None
        for frames in groups:
            if not isinstance(frames, list) or len(frames) > 5:
                return None
            for frame in frames:
                if not isinstance(frame, dict) or set(frame) != {"file", "function", "line"}:
                    return None
                filename = frame["file"]
                if not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9_./-]{1,180}", filename) or any(part in {"", ".", ".."} for part in filename.split("/")):
                    return None
                if filename != "mining/scripts/run_mediacrawler_task.py" and not (filename.startswith("upstream/") and filename.endswith(".py")):
                    return None
                if not isinstance(frame["function"], str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", frame["function"]):
                    return None
                if type(frame["line"]) is not int or not 1 <= frame["line"] <= 1_000_000:
                    return None
        return data
    except (OSError, ValueError, TypeError, KeyError):
        return None


def clean_child_environment(runtime: Path) -> dict[str, str]:
    # Explicit allowlist: no inherited model, API, DB, proxy or browser cookies.
    env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "LC_ALL", "TZ", "SYSTEMROOT") if key in os.environ}
    temp = runtime / "tmp"
    temp.mkdir(mode=0o700, parents=True, exist_ok=True)
    env.update({"TMPDIR": str(temp), "PLAYWRIGHT_BROWSERS_PATH": str(runtime / "browsers"),
        "PYTHON_DOTENV_DISABLED": "1", "PYTHONUNBUFFERED": "1", "NO_COLOR": "1"})
    return env


def preflight(runtime: Path) -> dict:
    """No browser launch or platform network; marker created by actual install probe."""
    result = {"ready": False, "reason": "not_installed", "upstream_pin": PIN,
        "browser_mode": "dedicated_visible_profile", "live_verified": False,
        "limits": {"max_posts": 3, "max_comments_per_post": 8, "max_preview": 30, "timeout_seconds": TASK_TIMEOUT},
        "message": "本机运行环境未就绪，请运行安装校验脚本。"}
    if runtime.resolve().is_relative_to(PROJECT_ROOT / "frontend" / "static"):
        result["reason"] = "runtime_inside_public_static_path"
        return result
    try:
        marker = runtime / "installed.json"
        python = runtime / ".venv" / "bin" / "python"
        if not marker.is_file() or marker.stat().st_size > 8192 or not python.is_file():
            return result
        installed = json.loads(marker.read_text(encoding="utf-8"))
        browser = Path(installed["browser_executable"])
        if installed.get("pin") != PIN or not installed.get("help_verified") or not installed.get("dependencies_verified") or not installed.get("node_version") or not shutil.which("node") or not browser.is_relative_to(runtime / "browsers") or not browser.is_file() or not os.access(browser, os.X_OK):
            result["reason"] = "invalid_install_marker"
            return result
        checkout = runtime / "upstream"
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=checkout, capture_output=True, text=True, timeout=3, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=checkout, capture_output=True, text=True, timeout=3, check=True).stdout
        if head != PIN or dirty.strip() or not (checkout / "LICENSE").is_file():
            result["reason"] = "upstream_pin_or_checkout_changed"
            return result
        # Validate actual interpreter and dependency import on every start/status.
        probe = subprocess.run([str(python), "-c", "import sys,playwright,typer,httpx; print(sys.prefix)"],
            cwd=runtime, env=clean_child_environment(runtime), capture_output=True, text=True, timeout=10, check=True)
        if Path(probe.stdout.strip()).resolve() != (runtime / ".venv").resolve():
            result["reason"] = "interpreter_mismatch"
            return result
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        result["reason"] = "runtime_check_failed"
        return result
    result.update(ready=True, reason="ready", message="本机运行环境已就绪。点击开始才会打开专用浏览器；平台账号实采尚待验证。")
    return result


class RunnerError(ValueError):
    def __init__(self, code, status_code=409):
        self.code, self.status_code = code, status_code
        super().__init__(code)


class MediaCrawlerRunner:
    def __init__(self, runtime_dir="", *, timeout=TASK_TIMEOUT):
        self.runtime = Path(runtime_dir).expanduser().resolve() if runtime_dir else DEFAULT_RUNTIME.resolve()
        self.timeout = timeout
        self.tasks = {}
        self.active_id = None
        self.lock = asyncio.Lock()

    async def status(self):
        result = await asyncio.to_thread(preflight, self.runtime)
        result["active_task"] = self.public(self.tasks[self.active_id]) if self.active_id else None
        return result

    def public(self, task):
        state = task["status"]
        if state == "running":
            try:
                path = task["dir"] / "phase.json"
                if path.is_file() and path.stat().st_size < 1000:
                    phase = json.loads(path.read_text())["phase"]
                    if phase in {"waiting_for_domestic_page", "waiting_for_login", "collecting"}:
                        state = phase
            except (OSError, ValueError, KeyError):
                pass
        message = MESSAGES[state]
        if state == "waiting_for_login" and task["platform"] == "xhs":
            message = "请在专用页面手动点击登录，程序正在等待登录确认；二维码是否出现以窗口实际内容为准。普通Chrome登录不会自动共享。"
        if state == "failed" and isinstance(task.get("diagnostic"), dict):
            diagnostic = task["diagnostic"]
            fallback = "搜索或请求失败，原因尚未确定；本次任务已结束，未开放部分输出。" if diagnostic.get("phase") == "collecting" else message
            message = FAILURE_HINTS.get(diagnostic.get("category"), fallback)
        return {key: task.get(key) for key in ("id", "platform", "mode", "query", "url", "max_posts", "max_comments", "started_at", "ended_at", "exit_code", "error_code")} | {
            "status": state, "terminal": task["status"] in TERMINAL, "message": message,
            "upstream_pin": PIN, "diagnostic": task.get("diagnostic") if task["status"] == "failed" else None,
        }

    def get(self, task_id):
        task = self.tasks.get(task_id)
        if task is None:
            raise RunnerError("task_not_found", 404)
        return task

    async def start(self, request: dict):
        async with self.lock:
            if self.active_id:
                raise RunnerError("task_already_running")
            check = await asyncio.to_thread(preflight, self.runtime)
            if not check["ready"]:
                raise RunnerError(check["reason"], 503)
            task_id = uuid.uuid4().hex
            directory = self.runtime / "tasks" / task_id
            directory.mkdir(mode=0o700, parents=True, exist_ok=False)
            task = dict(request, id=task_id, started_at=utcnow(), ended_at=None,
                status="running", dir=directory, exit_code=None, error_code=None)
            manifest = {key: value for key, value in task.items() if key not in {"dir", "status"}}
            manifest["task_dir"] = str(directory)
            path = directory / "manifest.json"
            path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            path.chmod(0o600)
            self.tasks[task_id] = task
            self.active_id = task_id
            try:
                task["process"] = await asyncio.create_subprocess_exec(
                    str(self.runtime / ".venv" / "bin" / "python"), str(BRIDGE),
                    "--runtime", str(self.runtime), "--manifest", str(path),
                    cwd=str(self.runtime / "upstream"), env=clean_child_environment(self.runtime),
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                    start_new_session=True,
                )
            except OSError:
                task.update(status="failed", ended_at=utcnow(), error_code="process_start_failed")
                self.active_id = None
                return self.public(task)
            task["watcher"] = asyncio.create_task(self._watch(task))
            # Bound process-local receipts; files remain local for explicit user cleanup.
            for old in list(self.tasks)[:-50]:
                if self.tasks[old]["status"] in TERMINAL:
                    self.tasks.pop(old)
            return self.public(task)

    async def _kill(self, process):
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.shield(process.wait()), timeout=7)
        # Also close child browsers left in the task's own process group.
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        await process.wait()

    async def _watch(self, task):
        process = task["process"]
        try:
            code = await asyncio.wait_for(asyncio.shield(process.wait()), timeout=self.timeout)
            task["exit_code"] = code
            if task["status"] == "running":
                task["ended_at"] = utcnow()
                if code != 0:
                    task.update(status="failed", error_code="upstream_nonzero_exit")
                else:
                    try:
                        rows = await asyncio.to_thread(read_task_exports, task["dir"], platform=task["platform"], mode=task["mode"], started_at=task["started_at"])
                        task["result"] = adapt_exports(rows, task)
                        task["status"] = "completed" if task["result"]["items"] else "empty"
                        bounds = task["dir"] / "bounds.json"
                        if bounds.is_file() and bounds.stat().st_size < 1000:
                            metrics = json.loads(bounds.read_text())
                            if not isinstance(metrics, dict):
                                raise ValueError("invalid bounds metadata")
                            for field in ("search_page_objects", "selected_objects"):
                                value = metrics.get(field)
                                if value is not None and (type(value) is not int or not 0 <= value <= 1000):
                                    raise ValueError("invalid bounds count")
                                task["result"]["summary"][field] = value
                    except (ExportError, OSError, ValueError, KeyError):
                        task.update(status="failed", error_code="invalid_task_output")
        except asyncio.TimeoutError:
            if task["status"] == "running":
                task.update(status="timed_out", error_code="task_timeout")
        finally:
            await self._kill(process)
            if task["status"] == "failed":
                task["diagnostic"] = read_failure_diagnostic(task["dir"])
            task["exit_code"] = process.returncode
            task["ended_at"] = task["ended_at"] or utcnow()
            if self.active_id == task["id"]:
                self.active_id = None

    async def stop(self, task_id):
        task = self.get(task_id)
        if task["status"] == "running":
            task.update(status="cancelled", error_code="user_cancelled")
            await self._kill(task["process"])
            await task["watcher"]
        return self.public(task)

    def results(self, task_id):
        task = self.get(task_id)
        if task["status"] not in {"completed", "empty"}:
            raise RunnerError("results_not_available")
        return {"task": self.public(task), **task["result"]}

    async def close(self):
        if self.active_id:
            await self.stop(self.active_id)
