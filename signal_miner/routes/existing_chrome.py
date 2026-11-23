"""Authenticated, explicit current-Chrome connection and DOM preview routes."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from signal_miner.connectors.existing_chrome import ChromeError, validate_url


async def same_origin(request: Request):
    """The browser capability cannot be invoked by an unrelated local web page."""
    origin = request.headers.get("origin")
    if origin is not None and (
        origin != str(request.base_url).rstrip("/")
        or request.base_url.hostname not in {"127.0.0.1", "localhost", "::1"}
    ):
        raise HTTPException(403, detail={"code": "cross_origin_forbidden", "message": "当前 Chrome 操作仅接受 MINING 页面同源请求。"})


router = APIRouter(prefix="/existing-chrome", dependencies=[Depends(same_origin)])


class ChromeTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tab_id: str = Field(min_length=1, max_length=100)
    platform: Literal["xiaohongshu", "bilibili", "weibo", "zhihu", "douyin"] | None = None
    pipeline_profile: Literal["product_feedback", "aigc_video"] | None = None
    mode: Literal["current", "search", "detail"] = "current"
    query: str = Field("", max_length=100)
    url: str = Field("", max_length=2000)
    max_posts: int = Field(1, ge=1, le=20)
    max_comments: int = Field(10, ge=0, le=50)

    @model_validator(mode="after")
    def scope(self):
        self.query, self.url = self.query.strip(), self.url.strip()
        if self.mode == "search":
            if not self.query or self.url or any(ord(char) < 32 or char in ",，" for char in self.query):
                raise ValueError("请填写一个不含逗号或换行的关键词；搜索模式不接受链接。")
        elif self.mode == "detail":
            if self.query:
                raise ValueError("指定链接模式不接受关键词。")
            if self.max_posts != 1:
                raise ValueError("指定链接模式每次只采集 1 篇。")
            try:
                validate_url(self.url, note=True, platform=self.platform)
            except ChromeError as exc:
                raise ValueError(exc.message) from exc
        elif self.query or self.url or self.max_posts != 1:
            raise ValueError("当前页面模式只采集当前 1 条内容，不接受关键词或另一个链接。")
        return self


def _collector(request):
    return request.app.state.existing_chrome


def _http_error(exc):
    return HTTPException(exc.status_code, detail={"code": exc.code, "message": exc.message})


@router.get("/status")
async def status(request: Request):
    return _collector(request).status()


@router.post("/connect", status_code=202)
async def connect(request: Request):
    try:
        return await _collector(request).connect()
    except ChromeError as exc:
        raise _http_error(exc) from exc


@router.post("/disconnect")
async def disconnect(request: Request):
    try:
        return await _collector(request).disconnect()
    except ChromeError as exc:
        raise _http_error(exc) from exc


@router.get("/tabs")
async def tabs(request: Request):
    try:
        return await _collector(request).tabs()
    except ChromeError as exc:
        raise _http_error(exc) from exc


@router.post("/tasks", status_code=202)
async def start_task(body: ChromeTaskRequest, request: Request):
    try:
        return await _collector(request).start(body.model_dump())
    except ChromeError as exc:
        raise _http_error(exc) from exc


@router.get("/tasks/{task_id}")
async def task_status(task_id: str, request: Request):
    try:
        collector = _collector(request)
        return collector.public(collector.get(task_id))
    except ChromeError as exc:
        raise _http_error(exc) from exc


@router.post("/tasks/{task_id}/stop")
async def stop_task(task_id: str, request: Request):
    try:
        return await _collector(request).stop(task_id)
    except ChromeError as exc:
        raise _http_error(exc) from exc


class ChromeBatchTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tab_ids: list[str] = Field(..., min_length=1, max_length=10)
    pipeline_profile: Literal["product_feedback", "aigc_video"] | None = None
    mode: Literal["current", "search"] = "search"
    query: str = Field("", max_length=100)
    max_posts: int = Field(5, ge=1, le=20)
    max_comments: int = Field(10, ge=0, le=50)
    concurrency: int = Field(3, ge=1, le=3)

    @model_validator(mode="after")
    def scope(self):
        self.query = self.query.strip()
        self.tab_ids = [t.strip() for t in self.tab_ids if isinstance(t, str) and t.strip()]
        if not self.tab_ids:
            raise ValueError("请至少选择一个目标平台标签。")
        if self.mode == "search":
            if not self.query or any(ord(char) < 32 or char in ",，" for char in self.query):
                raise ValueError("请填写一个不含逗号或换行的关键词。")
        elif self.query:
            raise ValueError("批量当前页面模式不接受关键词。")
        return self


@router.get("/tasks/{task_id}/results")
async def task_results(task_id: str, request: Request):
    try:
        return _collector(request).results(task_id)
    except ChromeError as exc:
        raise _http_error(exc) from exc


@router.post("/batch-tasks", status_code=202)
async def start_batch_task(body: ChromeBatchTaskRequest, request: Request):
    try:
        return await _collector(request).start_batch(body.model_dump())
    except ChromeError as exc:
        raise _http_error(exc) from exc


@router.get("/batch-tasks/{batch_id}")
async def batch_task_status(batch_id: str, request: Request):
    try:
        collector = _collector(request)
        return collector.public_batch(collector.get_batch(batch_id))
    except ChromeError as exc:
        raise _http_error(exc) from exc


@router.post("/batch-tasks/{batch_id}/stop")
async def stop_batch_task(batch_id: str, request: Request):
    try:
        return await _collector(request).stop_batch(batch_id)
    except ChromeError as exc:
        raise _http_error(exc) from exc


@router.post("/batch-tasks/{batch_id}/retry/{tab_id}", status_code=202)
async def retry_batch_tab(batch_id: str, tab_id: str, request: Request):
    try:
        return await _collector(request).retry_batch_tab(batch_id, tab_id)
    except ChromeError as exc:
        raise _http_error(exc) from exc


@router.get("/batch-tasks/{batch_id}/results")
async def batch_task_results(batch_id: str, request: Request):
    try:
        return _collector(request).batch_results(batch_id)
    except ChromeError as exc:
        raise _http_error(exc) from exc
