"""Connector management routes — GitHub fetch, Webhook ingest, registry listing."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import threading
import time
from typing import Literal

from fastapi import APIRouter, Body, HTTPException, Request, status
import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from signal_miner.connectors import list_connectors
from signal_miner.connectors.community_samples import (
    CollectionError,
    collect_samples,
    collect_v2ex_samples,
)
from signal_miner.connectors.zhihu_search import (
    ZHIHU_SETUP_URL,
    ZhihuSearchError,
    preview_zhihu_search,
)
from signal_miner.db import get_session_factory
from signal_miner.db.models import RawFeedbackRow
from signal_miner.routes.feedback import IngestRequest, _prepare_ingest_data

router = APIRouter()

# A single process accepts one network preview at a time. The worker owns the
# release, so a timed-out HTTP waiter cannot admit concurrent unfinished work.
_community_preview_lock = threading.Lock()
COMMUNITY_MAX_RESPONSE_BYTES = 2_000_000
COMMUNITY_MAX_TOTAL_BYTES = 6_000_000
COMMUNITY_HTTP_BUDGET_SECONDS = 20
COMMUNITY_WAIT_SECONDS = 24
COMMUNITY_REQUEST_TIMEOUT_SECONDS = 8


class _PreviewHTTPClient(httpx.Client):
    """Small streamed reader used only by the bounded web preview."""

    def __init__(self, *, transport: httpx.BaseTransport | None = None):
        super().__init__(
            timeout=COMMUNITY_REQUEST_TIMEOUT_SECONDS, follow_redirects=False,
            headers={
                "User-Agent": "SignalMiner-community-preview/1.0",
                "Accept-Encoding": "identity",
            },
            transport=transport,
        )
        self.deadline = time.monotonic() + COMMUNITY_HTTP_BUDGET_SECONDS
        self.total_bytes = 0

    def _remaining(self) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise httpx.TimeoutException("Community preview network budget expired")
        return min(COMMUNITY_REQUEST_TIMEOUT_SECONDS, remaining)

    def get(self, url, **kwargs) -> httpx.Response:
        # Core collectors only request fixed endpoints; there is no user URL.
        kwargs["timeout"] = self._remaining()
        kwargs["follow_redirects"] = False
        with self.stream("GET", url, **kwargs) as response:
            response.raise_for_status()
            if response.headers.get("Content-Encoding", "").strip().lower() not in {"", "identity"}:
                # Avoid expanding an arbitrarily large compressed chunk before
                # the size counter has a chance to reject it.
                raise ValueError("Compressed responses are not accepted by web preview")
            chunks = []
            received = 0
            # No chunk_size buffering: check each decoded transport chunk, not
            # after an unbounded response.content/response.read call.
            for chunk in response.iter_bytes():
                self._remaining()
                received += len(chunk)
                self.total_bytes += len(chunk)
                if received > COMMUNITY_MAX_RESPONSE_BYTES or self.total_bytes > COMMUNITY_MAX_TOTAL_BYTES:
                    raise ValueError("Community preview response exceeds byte budget")
                chunks.append(chunk)
            return httpx.Response(
                response.status_code, content=b"".join(chunks),
                headers={"Content-Type": response.headers.get("Content-Type", "")},
                request=response.request,
            )


class CommunityPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: Literal["hn", "v2ex"]
    query: str = Field(default="", max_length=200)
    days: int = Field(default=30, ge=1, le=365)
    limit: int = Field(default=10, ge=1, le=30)
    v2ex_node: Literal["qna", "ideas"] = "qna"
    kind: Literal["both", "ask", "comments"] = "both"


class CommunityPreviewResponse(BaseModel):
    items: list[dict]
    summary: dict


class ZhihuPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    query: str = Field(min_length=1, max_length=200)
    count: int = Field(default=5, ge=1, le=10)
    days: int = Field(default=30, ge=1, le=365)

    @field_validator("query")
    @classmethod
    def query_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Query must contain a non-whitespace character")
        return value.strip()


class ZhihuPreviewResponse(BaseModel):
    leads: list[dict]
    summary: dict


class ZhihuStatusResponse(BaseModel):
    configured: bool
    capabilities: list[str]
    limitations: list[str]
    setup_url: str
    configuration_hint: str


def _zhihu_secret(request: Request) -> str:
    runtime = request.app.state.runtime
    settings = getattr(runtime, "settings", None)
    secret = getattr(settings, "zhihu_access_secret", None)
    # Production settings use SecretStr; do not accept browser-supplied secrets.
    return secret.get_secret_value() if isinstance(secret, SecretStr) else ""


def _zhihu_preview_worker(body: ZhihuPreviewRequest, secret: str) -> tuple[dict | None, int | None, str | None]:
    try:
        with _PreviewHTTPClient() as client:
            result = preview_zhihu_search(
                client, access_secret=secret, query=body.query,
                count=body.count, days=body.days,
            )
        return result, None, None
    except ZhihuSearchError as exc:
        return None, exc.status_code, exc.detail
    except httpx.TimeoutException:
        return None, 504, "知乎搜索响应超时或采集预算已耗尽，未生成线索。"
    except Exception:
        return None, 502, "知乎搜索失败或响应未通过校验，未生成线索。"
    finally:
        _community_preview_lock.release()


def _preview_worker(body: CommunityPreviewRequest) -> tuple[dict | None, int | None]:
    """Network and parsing stay off the event loop; no files, ORM or LLM."""
    try:
        captured = datetime.now(timezone.utc)
        with _PreviewHTTPClient() as client:
            if body.source == "hn":
                items, summary = collect_samples(
                    client, query=body.query, days=body.days, limit=body.limit,
                    kind=body.kind, max_requests=3, now=captured,
                )
            else:
                items, summary = collect_v2ex_samples(
                    client, query=body.query, days=body.days, limit=body.limit,
                    node=body.v2ex_node, now=captured,
                )
        # Use the real ingest model and provenance gate without calling ingest.
        for item in items:
            _prepare_ingest_data(IngestRequest.model_validate(item))
        result = asdict(summary)
        result["published_from"] = (captured - timedelta(days=body.days)).isoformat()
        result["published_to"] = captured.isoformat()
        return {"items": items, "summary": result}, None
    except CollectionError as exc:
        # Do not expose network exception messages, request contents or config.
        cause = exc.__cause__
        return None, 504 if isinstance(cause, httpx.TimeoutException) else 502
    except httpx.TimeoutException:
        return None, 504
    except Exception:
        return None, 502
    finally:
        _community_preview_lock.release()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class GitHubFetchRequest(BaseModel):
    repo: str = Field(
        ...,
        description="GitHub repo in 'owner/repo' format",
        pattern=r"^[^/]+/[^/]+$",
    )
    labels: list[str] | None = None
    state: str = Field("all", pattern=r"^(open|closed|all)$")
    since: str | None = Field(None, description="ISO8601 datetime filter")
    include_comments: bool = True
    version_id: str = Field("default", max_length=40)


class ConnectorListResponse(BaseModel):
    """Response for ``GET /connectors``."""

    connectors: list[str] = Field(default_factory=list)


class GitHubFetchResponse(BaseModel):
    """Response for ``POST /connectors/github/fetch``."""

    repo: str
    ingested_count: int
    source_type: str = "github"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "/connectors/zhihu/status", response_model=ZhihuStatusResponse,
    summary="Report server-side Zhihu search readiness without contacting Zhihu",
)
async def zhihu_status(request: Request) -> dict:
    return {
        "configured": bool(_zhihu_secret(request).strip()),
        "capabilities": ["知乎官方搜索（检索线索）", "单次最多10条，按创建时间范围检索", "保留摘要、精选评论及原页面链接"],
        "limitations": [
            "本地配置存在不代表密钥已通过实网验证。",
            "接口返回摘要，精选评论缺少独立ID、作者和时间，不能直接作为原文依据。",
            "预览不导入、不调用模型；请补充所需原文材料后再分析机会。",
        ],
        "setup_url": ZHIHU_SETUP_URL,
        "configuration_hint": "在本机服务端环境变量设置 ZHIHU_ACCESS_SECRET 后重启服务；请勿在网页或URL填写密钥。",
    }


@router.post(
    "/connectors/zhihu/preview", response_model=ZhihuPreviewResponse,
    summary="Preview official Zhihu search excerpts as leads without importing",
)
async def zhihu_preview(body: ZhihuPreviewRequest, request: Request) -> dict:
    secret = _zhihu_secret(request)
    if not secret.strip():
        raise HTTPException(
            status_code=503,
            detail="知乎官方搜索未配置：请在本机服务端设置 ZHIHU_ACCESS_SECRET 后重启。",
        )
    if not _community_preview_lock.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="社区采集正在进行，请稍后重试；没有排队或重复采集。")
    worker = asyncio.create_task(asyncio.to_thread(_zhihu_preview_worker, body, secret))
    try:
        result, error_status, detail = await asyncio.wait_for(
            asyncio.shield(worker), timeout=COMMUNITY_WAIT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="等待知乎搜索超时；后台请求可能仍在收尾，未导入材料，请稍后重试。",
        ) from exc
    if error_status:
        raise HTTPException(status_code=error_status, detail=detail)
    return result


@router.post(
    "/connectors/community/preview",
    response_model=CommunityPreviewResponse,
    summary="Preview bounded community source materials without importing",
)
async def preview_community(body: CommunityPreviewRequest) -> dict:
    if not _community_preview_lock.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="社区采集正在进行，请稍后重试；没有排队或重复采集。")
    # Shield keeps the thread-backed task alive after an HTTP waiting timeout.
    # Its finally releases the busy lock when real work actually ends.
    worker = asyncio.create_task(asyncio.to_thread(_preview_worker, body))
    try:
        result, error_status = await asyncio.wait_for(
            asyncio.shield(worker), timeout=COMMUNITY_WAIT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="等待采集超时；后台请求可能仍在收尾，未导入材料，请稍后重试。",
        ) from exc
    if error_status:
        detail = (
            "社区来源响应超时或采集预算已耗尽，未导入材料，请稍后重试。"
            if error_status == 504 else
            "社区采集失败或来源材料未通过校验，未导入材料，请稍后重试。"
        )
        raise HTTPException(status_code=error_status, detail=detail)
    return result


@router.get("/connectors", response_model=ConnectorListResponse, summary="List available connector types")
async def list_available_connectors() -> dict:
    """Return the names of all registered connector types."""
    return {"connectors": list_connectors()}


@router.post(
    "/connectors/github/fetch",
    response_model=GitHubFetchResponse,
    summary="Fetch GitHub Issues into feedback database",
    status_code=status.HTTP_200_OK,
)
async def github_fetch(
    request: GitHubFetchRequest,
    http_request: Request,
) -> dict:
    """Pull issues (and optionally comments) from a GitHub repository.

    Each issue and comment is ingested as a RawFeedback item and stored
    in the raw_feedback_items table for downstream processing.
    """
    from signal_miner.connectors.github_connector import GitHubConnector

    runtime = http_request.app.state.runtime
    token = runtime.settings.github_token or None

    connector = GitHubConnector(
        repo=request.repo,
        token=token,
        labels=request.labels,
        state=request.state,
        since=request.since,
        include_comments=request.include_comments,
    )

    ingested_count = 0
    effective_version = "default" if not request.version_id or request.version_id == "all" else request.version_id.strip()
    session_factory = get_session_factory()

    async for feedback in connector.fetch():
        async with session_factory() as session:
            row = RawFeedbackRow(
                id=feedback.id,
                source_type=feedback.source_type,
                source_id=feedback.source_id,
                dedupe_key=feedback.dedupe_key,
                external_id=feedback.external_id,
                external_url=feedback.external_url,
                author=feedback.author.model_dump(),
                content=feedback.content.model_dump(),
                context=feedback.context,
                processing_state=feedback.processing_state.value,
                attempt_count=feedback.attempt_count,
                source_created_at=feedback.source_created_at,
                version_id=effective_version,
            )
            session.add(row)
            await session.commit()
            ingested_count += 1

    return {
        "repo": request.repo,
        "ingested_count": ingested_count,
        "source_type": connector.source_type,
    }


@router.post(
    "/connectors/webhook/ingest",
    summary="Ingest a webhook payload as feedback",
    status_code=status.HTTP_201_CREATED,
)
async def webhook_ingest(
    http_request: Request,
    payload: dict = Body(...),
) -> dict:
    """Receive a generic webhook payload and ingest it as a RawFeedback item.

    Signature verification is performed when a webhook_secret is configured
    in settings and the ``X-Signature`` or ``X-Hub-Signature-256`` header
    is present.
    """
    from signal_miner.connectors.webhook_connector import WebhookConnector

    runtime = http_request.app.state.runtime
    secret = runtime.settings.webhook_secret or None

    connector = WebhookConnector(
        source_id="webhook_ingest",
        secret=secret,
    )

    # Signature verification
    signature = http_request.headers.get("X-Hub-Signature-256") or http_request.headers.get("X-Signature") or ""

    if secret and signature:
        raw_body = await http_request.body()
        if not connector.verify_signature(raw_body, signature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid webhook signature.",
            )

    # Parse and persist
    feedback = connector.parse_payload(payload)

    session_factory = get_session_factory()
    async with session_factory() as session:
        row = RawFeedbackRow(
            id=feedback.id,
            source_type=feedback.source_type,
            source_id=feedback.source_id,
            dedupe_key=feedback.dedupe_key,
            external_id=feedback.external_id,
            external_url=feedback.external_url,
            author=feedback.author.model_dump(),
            content=feedback.content.model_dump(),
            context=feedback.context,
            processing_state=feedback.processing_state.value,
            attempt_count=feedback.attempt_count,
            source_created_at=feedback.source_created_at,
        )
        session.add(row)
        await session.commit()
        return {
            "feedback_id": feedback.id,
            "source_type": feedback.source_type,
        }
