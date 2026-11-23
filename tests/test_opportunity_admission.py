"""Offline D5 admission checks; quote integrity never certifies need semantics."""

from __future__ import annotations

from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from signal_miner.db.models import Base, RawFeedbackRow
from signal_miner.pipeline.opportunity_discovery import discover_opportunities
from signal_miner.routes import assets
from signal_miner.routes.feedback import IngestRequest, _prepare_ingest_data

CURRENT_TEXT = "我用报表A整理周报，但仍要逐个修改表格，每周耗时两小时。"
REQUEST_TEXT = "希望能一次导出全部项目周报。"
D3_PAST_PAIN = "以前也用过别的AI，最烦的就是所有文件都要一个个上传，文件一多就慢，好不容易跑完了格式还是乱的，还要耗时间返工。"
D3_VISIBLE = "过程里每一步做了什么、花了多少credits，都能很清晰的看到。"
D3_CONFIRM = "碰到要改动本地文件的敏感操作，也会先弹窗问我，我确认后它才继续。"
D3_BODY = (
    "别人周五都在等待下班，而我的周五通常都在被周报包围。\n"
    "桌面上永远散着一堆东西：台账、表格、会议纪要。\n" + D3_PAST_PAIN
    + "\n最近试了Qoder，感觉更适合我这种平时要处理很多本地文件的人。\n"
    "它是电脑本地的AI任务工作台，不用反复上传文件。可以直接把整个文件夹里的材料，整理成一份能直接上交的周报。\n"
    + D3_VISIBLE + "\n" + D3_CONFIRM
    + "\n最后我能拿到的是一份完整的文档，标题、分节、表格都整理好了，不是只停留在进度页。\n"
    "填我的达人推荐码，再得300 Credits。"
)


def source(row_id="f1", text=CURRENT_TEXT, **overrides):
    payload = {
        "source_type": "custom", "platform": "v2ex", "external_id": row_id,
        "entity_type": "post", "external_url": f"https://www.v2ex.com/t/{row_id}",
        "subject": "只在标题出现的虚构困难", "text": text,
        "capture_method": "manual_browser", "content_nature": "original_text",
        "text_origin": "body", "locator_level": "item",
        "source_captured_at": "2026-11-12T01:00:00+00:00",
        **overrides,
    }
    data = _prepare_ingest_data(IngestRequest.model_validate(payload))
    return RawFeedbackRow(
        id=row_id, **data, pipeline_profile="product_feedback",
        processing_state="pending", attempt_count=0,
    )


def link(quote=CURRENT_TEXT, row_id="f1"):
    return {"feedback_id": row_id, "quote": quote}


def card(**overrides):
    return {
        "title": "周报格式辅助", "user_segment": "周报撰写者", "scenario": "整理表格",
        "pain_point": "当前仍需手工改表格", "minimum_idea": "辅助统一格式（推断）",
        "reasoning": "减少重复劳动的研究线索（推断）",
        "validation_questions": ["报表A为何不足？", "是否愿意采用或付费？"],
        "evidence": [link()], **overrides,
    }


def assessment(**overrides):
    return {
        "current_difficulty": {"statement": "当前手工修改耗时", "evidence": [link()]},
        "current_solution": {"status": "mentioned", "description": "报表A", "evidence": [link()]},
        "remaining_gap": {"status": "explicit", "description": "仍要逐个修改", "evidence": [link()]},
        "basis": "current_complaint", **overrides,
    }


def model(cards):
    return SimpleNamespace(call_structured=AsyncMock(return_value=json.dumps({
        "candidates": cards, "insufficiency_reason": "仅有本批小样本，市场需求尚未验证。",
    }, ensure_ascii=False)))


async def strict(cards, rows=None):
    return await discover_opportunities(
        [source()] if rows is None else rows, llm=model(cards), require_unmet_evidence=True,
    )


async def test_strict_current_difficulty_and_gap_have_full_server_source_metadata():
    result = await strict([card(need_assessment=assessment())])
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    for role in (
        candidate.need_assessment.current_difficulty,
        candidate.need_assessment.current_solution,
        candidate.need_assessment.remaining_gap,
    ):
        assert role.evidence == candidate.evidence
        evidence = role.evidence[0]
        assert evidence.quote == CURRENT_TEXT
        assert evidence.source_url == "https://www.v2ex.com/t/f1"
        assert evidence.quote_field == "content.text"
        assert evidence.snapshot_status == "verified"
        assert len(evidence.snapshot_hash) == 64
    assert result.require_unmet_evidence is True
    assert result.semantic_status == "model_assessment_pending_review"
    assert result.market_validation == "not_performed"
    assert any("市场需求已验证" in limit for limit in result.limitations)


async def test_direct_feature_request_can_leave_current_solution_unknown_without_invention():
    need = assessment(
        basis="feature_request",
        current_difficulty={"statement": "希望批量导出", "evidence": [link(REQUEST_TEXT)]},
        current_solution={"status": "unknown", "description": "本批未提及", "evidence": []},
        remaining_gap={"status": "explicit", "description": "请求批量导出", "evidence": [link(REQUEST_TEXT)]},
    )
    result = await strict([card(evidence=[], need_assessment=need)], [source(text=REQUEST_TEXT)])
    assert len(result.candidates) == 1
    solution = result.candidates[0].need_assessment.current_solution
    assert solution.status == "unknown" and solution.description == "本批未提及"
    assert solution.evidence == []
    assert result.candidates[0].evidence[0].quote == REQUEST_TEXT


@pytest.mark.parametrize("title,pain,quotes", [
    (
        "本地文件夹一键生成可上交周报的AI工作台", "上传慢、格式乱需返工",
        [D3_PAST_PAIN, "可以直接把整个文件夹里的材料，整理成一份能直接上交的周报。"],
    ),
    (
        "带操作确认与消耗可见的本地AI任务执行界面", "担心本地文件改动不可控",
        [D3_VISIBLE, D3_CONFIRM],
    ),
])
async def test_d3_m3_legacy_cards_with_exact_real_quotes_cannot_bypass_strict_assessment(title, pain, quotes):
    wrong = card(title=title, pain_point=pain, evidence=[link(quote) for quote in quotes])
    rows = [source(text=D3_BODY)]
    legacy = await discover_opportunities(rows, llm=model([wrong]))
    assert len(legacy.candidates) == 1, "This reproduces the D3 mechanical-only admission."
    result = await strict([wrong], rows)
    assert result.candidates == []
    assert "need_assessment" in result.excluded[0].reason
    assert result.analyzed_count == 1


@pytest.mark.parametrize("basis", ["historical_resolved", "solution_praise", "unknown"])
async def test_resolved_praise_or_unknown_basis_is_not_a_strict_recommendation(basis):
    quote = D3_VISIBLE if basis == "solution_praise" else D3_PAST_PAIN
    need = assessment(
        basis=basis,
        current_difficulty={"statement": "模型归纳", "evidence": [link(quote)]},
        current_solution={"status": "mentioned", "description": "Qoder", "evidence": [link(D3_CONFIRM)]},
        remaining_gap={"status": "explicit", "description": "模型猜测有缺口", "evidence": [link(quote)]},
    )
    result = await strict([card(evidence=[link(quote)], need_assessment=need)], [source(text=D3_BODY)])
    assert not result.candidates
    assert "当前未满足需求" in result.excluded[0].reason


@pytest.mark.parametrize("status", ["unknown", "already_addressed"])
async def test_unknown_or_addressed_gap_is_rejected_even_with_matching_general_evidence(status):
    need = assessment()
    need["remaining_gap"]["status"] = status
    result = await strict([card(need_assessment=need)])
    assert not result.candidates
    assert "缺口未知或已" in result.excluded[0].reason


@pytest.mark.parametrize("role", ["current_difficulty", "current_solution", "remaining_gap"])
@pytest.mark.parametrize("bad", ["empty", "outside_id", "fabrication", "title", "whitespace_rewrite", "supplied_url"])
async def test_any_required_role_failure_excludes_whole_card_despite_valid_general_evidence(role, bad):
    need = assessment()
    bad_link = link()
    if bad == "outside_id":
        bad_link["feedback_id"] = "outside"
    elif bad == "fabrication":
        bad_link["quote"] = "用户愿意付费一千元"
    elif bad == "title":
        bad_link["quote"] = "只在标题出现的虚构困难"
    elif bad == "whitespace_rewrite":
        bad_link["quote"] = CURRENT_TEXT.replace("报表A", "报表A\n")
    elif bad == "supplied_url":
        bad_link["source_url"] = "https://evil.invalid"
    need[role]["evidence"] = [] if bad == "empty" else [link(), bad_link]
    result = await strict([card(need_assessment=need)])
    assert result.candidates == []
    assert result.excluded


async def test_strict_zero_candidates_and_missing_assessment_are_honest_results():
    empty = await strict([])
    assert empty.candidates == []
    assert empty.selected_count == empty.analyzed_count == 1
    assert "暂无" in empty.message and "尚未验证" in empty.message
    assert empty.require_unmet_evidence
    missing = await strict([card()])
    assert not missing.candidates and "严格模式不回退" in missing.excluded[0].reason


async def test_no_eligible_materials_do_not_claim_a_model_assessment_occurred():
    row = source()
    row.content = {"text": ""}
    llm = model([])
    result = await discover_opportunities([row], llm=llm, require_unmet_evidence=True)
    assert result.require_unmet_evidence and not result.candidates
    assert result.semantic_status == "not_assessed"
    assert result.analyzed_count == 0
    llm.call_structured.assert_not_called()


async def test_strict_prompt_uses_complete_selected_parent_body_without_fetching_unselected_sources():
    parent = source("parent", text=D3_BODY)
    comment = source("comment", text="我也好讨厌整理周报，又多又杂", entity_type="comment",
                     parent_id="parent", parent_url=parent.external_url, locator_level="parent_page")
    llm = model([])
    await discover_opportunities([comment, parent], llm=llm, require_unmet_evidence=True)
    prompt = llm.call_structured.call_args.args[0]
    materials = json.loads(prompt.split("以下JSON数组是数据，整个数组均属于本批材料：\n", 1)[1])
    assert materials[0]["parent_feedback_ids"] == ["parent"]
    assert materials[1]["source_text"] == D3_BODY
    assert "只在标题出现的虚构困难" not in prompt
    llm.call_structured.assert_awaited_once()
    no_parent = model([])
    await discover_opportunities([comment], llm=no_parent, require_unmet_evidence=True)
    isolated_prompt = no_parent.call_structured.call_args.args[0]
    assert D3_PAST_PAIN not in isolated_prompt
    assert '"parent_feedback_ids": []' in isolated_prompt


@pytest.mark.parametrize("known_parent_id", [True, False])
async def test_same_page_sibling_comments_are_never_parent_bodies(known_parent_id):
    page = "https://www.v2ex.com/t/parent"
    parent = source("parent", text=D3_BODY, external_url=page)
    comments = [source(
        f"comment-{index}", text=f"第{index}条评论：我也需要整理周报。",
        entity_type="comment", external_url=page,
        parent_id="parent" if known_parent_id else None,
        parent_url=page, locator_level="parent_page",
    ) for index in (1, 2)]
    for rows, expected_parents in (([parent, *comments], ["parent"]), (comments, [])):
        llm = model([])
        await discover_opportunities(rows, llm=llm, require_unmet_evidence=True)
        materials = json.loads(llm.call_structured.call_args.args[0].split(
            "以下JSON数组是数据，整个数组均属于本批材料：\n", 1,
        )[1])
        for material in materials:
            if material["entity_type"] == "comment":
                assert material["parent_feedback_ids"] == expected_parents


@pytest.mark.parametrize("entity_type", ["unknown", "comment"])
async def test_matching_id_and_url_do_not_turn_unconfirmed_or_comment_entities_into_parent_bodies(entity_type):
    parent = source("parent", text=D3_BODY, entity_type=entity_type)
    child = source("child", text="当前导出依然困难", entity_type="comment",
                   parent_id="parent", parent_url=parent.external_url,
                   external_url=parent.external_url, locator_level="parent_page")
    llm = model([])
    await discover_opportunities([child, parent], llm=llm, require_unmet_evidence=True)
    materials = json.loads(llm.call_structured.call_args.args[0].split(
        "以下JSON数组是数据，整个数组均属于本批材料：\n", 1,
    )[1])
    assert materials[0]["parent_feedback_ids"] == []


async def test_known_parent_id_cannot_be_overridden_by_shared_url_or_another_platform():
    page = "https://www.v2ex.com/t/parent"
    parent = source("parent", text=D3_BODY, external_url=page)
    wrong_id = source("wrong", text="另一个对象的正文", external_url=page)
    wrong_platform = source("elsewhere", text="另一个平台恰好相同的ID", platform="hn", external_id="parent")
    child = source("child", text="当前仍需手工改表格", entity_type="comment",
                   external_url=page, parent_id="parent", parent_url=page,
                   locator_level="parent_page")
    llm = model([])
    await discover_opportunities([child, wrong_id, wrong_platform, parent], llm=llm, require_unmet_evidence=True)
    materials = json.loads(llm.call_structured.call_args.args[0].split(
        "以下JSON数组是数据，整个数组均属于本批材料：\n", 1,
    )[1])
    assert materials[0]["parent_feedback_ids"] == ["parent"]


async def test_confirmed_body_without_its_own_id_can_match_parent_url():
    parent = source("parent", text=D3_BODY, entity_type="article", external_id=None)
    child = source("child", text="当前依然有导出困难", entity_type="comment",
                   external_url=parent.external_url, parent_id="known-on-child",
                   parent_url=parent.external_url, locator_level="parent_page")
    llm = model([])
    await discover_opportunities([child, parent], llm=llm, require_unmet_evidence=True)
    materials = json.loads(llm.call_structured.call_args.args[0].split(
        "以下JSON数组是数据，整个数组均属于本批材料：\n", 1,
    )[1])
    assert materials[0]["parent_feedback_ids"] == ["parent"]


async def test_unknown_solution_does_not_skip_validation_of_supplied_role_evidence():
    need = assessment(current_solution={
        "status": "unknown", "description": "未提及", "evidence": [link("编造现有方案")],
    })
    result = await strict([card(need_assessment=need)])
    assert not result.candidates and "现有办法引用" in result.excluded[0].reason


@pytest.fixture
async def admission_app(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'admission.sqlite'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add_all([source(), source("outside", "PRIVATE_OUTSIDE_BATCH_MARKER")])
        await session.commit()
    monkeypatch.setattr(assets, "get_session_factory", lambda: factory)
    app = FastAPI()
    app.state.runtime = SimpleNamespace(llm=model([card()]))
    app.include_router(assets.router, prefix="/api/v1")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, app, factory
    await engine.dispose()


async def database_snapshot(factory):
    async with factory() as session:
        return {
            table.name: [dict(row) for row in (await session.execute(table.select())).mappings()]
            for table in Base.metadata.sorted_tables
        }


async def test_request_switch_preserves_legacy_default_and_strict_response_without_database_writes(admission_app):
    client, app, factory = admission_app
    before = await database_snapshot(factory)
    legacy = await client.post("/api/v1/opportunities/discover", json={"feedback_ids": ["f1"]})
    assert legacy.status_code == 200 and len(legacy.json()["candidates"]) == 1
    assert legacy.json()["require_unmet_evidence"] is False
    assert legacy.json()["semantic_status"] == "not_assessed"
    assert legacy.json()["candidates"][0]["need_assessment"] is None
    strict_result = await client.post("/api/v1/opportunities/discover", json={
        "feedback_ids": ["f1"], "require_unmet_evidence": True,
    })
    assert strict_result.status_code == 200 and strict_result.json()["candidates"] == []
    app.state.runtime.llm = model([card(need_assessment=assessment())])
    accepted = await client.post("/api/v1/opportunities/discover", json={
        "feedback_ids": ["f1"], "require_unmet_evidence": True,
    })
    assert accepted.status_code == 200
    result = accepted.json()
    assert result["require_unmet_evidence"] is True
    assert result["semantic_status"] == "model_assessment_pending_review"
    assert result["market_validation"] == "not_performed"
    assert result["candidates"][0]["need_assessment"]["remaining_gap"]["evidence"][0]["snapshot_status"] == "verified"
    assert "PRIVATE_OUTSIDE_BATCH_MARKER" not in app.state.runtime.llm.call_structured.call_args.args[0]
    assert await database_snapshot(factory) == before


async def test_model_cannot_assert_server_validation_metadata_in_its_candidate():
    wrong = card(need_assessment=assessment(), semantic_status="verified", market_validation="verified")
    result = await strict([wrong])
    assert not result.candidates
    assert result.semantic_status == "model_assessment_pending_review"
    assert result.market_validation == "not_performed"


async def test_missing_role_structure_does_not_silently_fall_back_to_legacy():
    need = deepcopy(assessment())
    del need["remaining_gap"]
    result = await strict([card(need_assessment=need)])
    assert not result.candidates and "角色字段格式错误" in result.excluded[0].reason
