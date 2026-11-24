"""Authenticated explicit local collection; no feedback writes or model calls."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from signal_miner.auth import require_same_origin
from signal_miner.connectors.mediacrawler_adapter import validate_item_url
from signal_miner.connectors.mediacrawler_runner import RunnerError

router = APIRouter(prefix="/mediacrawler", dependencies=[Depends(require_same_origin)])


class CollectionTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    platform: Literal["xhs", "bili", "wb"]
    mode: Literal["search", "detail"] = "search"
    query: str = Field("", max_length=100)
    url: str = Field("", max_length=2000)
    max_posts: int = Field(3, ge=1, le=3)
    max_comments: int = Field(8, ge=0, le=8)

    @model_validator(mode="after")
    def validate_scope(self):
        self.query, self.url = self.query.strip(), self.url.strip()
        if self.mode == "search":
            if not self.query or self.url or any(char in self.query for char in (",", "，", "\n", "\r", "\x00")):
                raise ValueError("请填写一个关键词（不含逗号或换行），搜索模式不接受链接。")
        else:
            if self.query:
                raise ValueError("指定链接模式不接受关键词。")
            validate_item_url(self.platform, self.url)
            self.max_posts = 1
        return self


def _runner(request):
    return request.app.state.mediacrawler


def _error(error):
    return HTTPException(error.status_code, detail=f"本机采集请求未完成（{error.code}），请检查任务状态或运行环境。")


@router.get("/status")
async def environment_status(request: Request):
    return await _runner(request).status()


@router.post("/tasks", status_code=202)
async def start_task(body: CollectionTaskRequest, request: Request):
    try:
        return await _runner(request).start(body.model_dump())
    except RunnerError as error:
        raise _error(error) from error


@router.get("/tasks/{task_id}")
async def task_status(task_id: str, request: Request):
    try:
        return _runner(request).public(_runner(request).get(task_id))
    except RunnerError as error:
        raise _error(error) from error


@router.post("/tasks/{task_id}/stop")
async def stop_task(task_id: str, request: Request):
    try:
        return await _runner(request).stop(task_id)
    except RunnerError as error:
        raise _error(error) from error


@router.get("/tasks/{task_id}/results")
async def task_results(task_id: str, request: Request):
    try:
        return _runner(request).results(task_id)
    except RunnerError as error:
        raise _error(error) from error
