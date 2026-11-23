"""Tests for Bilibili and Weibo support in Existing Chrome DOM collector."""

from signal_miner.connectors.existing_chrome import (
    adapt_dom,
    detect_platform,
    validate_url,
)
from signal_miner.routes.existing_chrome import ChromeTaskRequest


def test_detect_and_validate_bilibili_and_weibo_urls():
    bili_video = "https://www.bilibili.com/video/BV1xx411c7mD"
    bili_search = "https://search.bilibili.com/all?keyword=AI"
    wb_post = "https://weibo.com/1234567890/Pabc123XYZ"
    wb_search = "https://s.weibo.com/weibo?q=AI"

    assert detect_platform(bili_video) == "bilibili"
    assert detect_platform(bili_search) == "bilibili"
    assert detect_platform(wb_post) == "weibo"
    assert detect_platform(wb_search) == "weibo"

    assert validate_url(bili_video, note=True) == bili_video
    assert validate_url(bili_search, note=False) == bili_search
    assert validate_url(wb_post, note=True) == wb_post
    assert validate_url(wb_search, note=False) == wb_search


def test_adapt_dom_for_bilibili_and_weibo():
    bili_task = {"id": "t_bili", "platform": "bilibili", "mode": "current", "max_posts": 1, "max_comments": 5}
    bili_record = {
        "url": "https://www.bilibili.com/video/BV1xx411c7mD",
        "title": "AI 工具评测",
        "body": "AI 工具评测\n详细对比几款插件",
        "comments": [{"text": "这个插件确实好用", "comment_id": "12345"}],
        "comment_container_present": True,
    }
    bili_out = adapt_dom(bili_record, bili_task)
    assert len(bili_out["items"]) == 2
    assert bili_out["items"][0]["source_type"] == "bilibili"
    assert bili_out["items"][0]["external_id"] == "BV1xx411c7mD"
    assert bili_out["items"][1]["entity_type"] == "comment"

    wb_task = {"id": "t_wb", "platform": "weibo", "mode": "current", "max_posts": 1, "max_comments": 5}
    wb_record = {
        "url": "https://weibo.com/1234567890/Pabc123XYZ",
        "title": None,
        "body": "今天试了这个工具，安装体验还需改进",
        "comments": [],
        "comment_container_present": False,
    }
    wb_out = adapt_dom(wb_record, wb_task)
    assert len(wb_out["items"]) == 1
    assert wb_out["items"][0]["source_type"] == "weibo"
    assert wb_out["items"][0]["external_id"] == "Pabc123XYZ"


def test_chrome_task_request_accepts_bilibili_and_weibo():
    req = ChromeTaskRequest(
        tab_id="tab1",
        platform="bilibili",
        pipeline_profile="aigc_video",
        mode="detail",
        url="https://www.bilibili.com/video/BV1xx411c7mD",
        max_posts=1,
        max_comments=10,
    )
    assert req.platform == "bilibili"
    assert req.pipeline_profile == "aigc_video"


def test_adapt_dom_subtitles_and_aigc_video_profile():
    task = {
        "id": "t_sub",
        "platform": "bilibili",
        "pipeline_profile": "aigc_video",
        "mode": "current",
        "max_posts": 1,
        "max_comments": 5,
    }
    record = {
        "url": "https://www.bilibili.com/video/BV1xx411c7mD",
        "title": "3秒抓人开场公式",
        "body": "3秒抓人开场公式\n\n【视频字幕逐字稿】\n前3秒先抛出反常识结果。",
        "has_subtitles": True,
        "subtitle_language": "中文（自动生成）",
        "comments": [],
        "comment_container_present": True,
    }
    out = adapt_dom(record, task)
    item = out["items"][0]
    assert item["pipeline_profile"] == "aigc_video"
    assert item["raw_payload"]["has_subtitles"] is True
    assert item["raw_payload"]["subtitle_language"] == "中文（自动生成）"
    assert "视频字幕逐字稿" in item["raw_payload"]["incomplete_reasons"][0]


def test_zhihu_urls_and_adapt_dom():
    zh_answer = "https://www.zhihu.com/question/123456/answer/987654"
    zh_question = "https://www.zhihu.com/question/123456"
    zh_article = "https://zhuanlan.zhihu.com/p/556677"
    zh_search = "https://www.zhihu.com/search?type=content&q=AI"

    for u in (zh_answer, zh_question, zh_article, zh_search):
        assert detect_platform(u) == "zhihu"

    assert validate_url(zh_answer, note=True) == zh_answer
    assert validate_url(zh_question, note=True) == zh_question
    assert validate_url(zh_article, note=True) == zh_article
    assert validate_url(zh_search, note=False) == zh_search

    task = {"id": "t_zh", "platform": "zhihu", "mode": "current", "max_posts": 1, "max_comments": 5}
    record = {
        "url": zh_answer,
        "title": "DeepSeek 插件有哪些痛点？",
        "body": "最大的痛点是安装配置步骤过多，新手很容易卡在第一步。",
        "comments": [{"text": "深有同感，希望能一键配置"}],
        "comment_container_present": True,
    }
    out = adapt_dom(record, task)
    assert len(out["items"]) == 2
    assert out["items"][0]["source_type"] == "zhihu"
    assert out["items"][0]["external_id"] == "987654"
    assert out["items"][1]["entity_type"] == "comment"


def test_douyin_urls_adapt_dom_and_source_policy():
    from signal_miner.utils.source_platforms import validate_required_source_url

    dy_video = "https://www.douyin.com/video/7412345678901234567"
    dy_note = "https://www.douyin.com/note/7412345678901234568"
    dy_search = "https://www.douyin.com/search/AI%E5%B7%A5%E5%85%B7?type=general"
    dy_discover = "https://www.douyin.com/discover"

    for u in (dy_video, dy_note, dy_search, dy_discover):
        assert detect_platform(u) == "douyin"

    assert validate_url(dy_video, note=True) == dy_video
    assert validate_url(dy_note, note=True) == dy_note
    assert validate_url(dy_search, note=False) == dy_search
    assert validate_url(dy_discover, note=False) == dy_discover

    task = {"id": "t_dy", "platform": "douyin", "pipeline_profile": "aigc_video", "mode": "current", "max_posts": 1, "max_comments": 5}
    record = {
        "url": dy_video,
        "title": "3秒抓人开场实测 #AI工具",
        "body": "3秒抓人开场实测 #AI工具\n实测这款插件效率翻倍",
        "comments": [{"text": "求安装包链接"}],
        "comment_container_present": True,
    }
    out = adapt_dom(record, task)
    assert len(out["items"]) == 2
    post = out["items"][0]
    assert post["source_type"] == "douyin"
    assert post["pipeline_profile"] == "aigc_video"
    assert post["capture_method"] == "manual_browser"
    assert post["external_id"] == "7412345678901234567"
    # Must pass P12-1 source platform ingest URL validation cleanly
    assert validate_required_source_url(post["source_type"], post["external_url"], capture_method=post["capture_method"]) == dy_video
