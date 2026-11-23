#!/usr/bin/env python3
"""P13-2-1 fix-3: Generate pre-annotations using production signal type whitelist.

Fixture mode: deterministic templates using production profile.signal_types.
Default mode: calls real adapter via injectable function; BLOCKED if no key.

Signal types come from signal_miner.pipeline.pipeline_profile.get_profile().
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from signal_miner.pipeline.pipeline_profile import get_profile  # noqa: E402

# Deterministic keyword → signal type mapping for fixture mode
# All target signal types MUST be in the production profile whitelist
KEYWORD_SIGNAL_MAP = [
    # product_feedback types
    (["暗黑", "夜间", "深色", "markdown", "预览", "备份", "网盘",
      "菜单", "层级", "设置", "快捷键", "自定义", "通知", "静音",
      "版本", "回退", "升级", "更新", "批量", "效率", "阅读", "进度条"], "feature_request"),
    (["崩溃", "闪退", "报错", "bug", "500", "导出", "csv", "格式",
      "粘贴", "复制", "协作", "冲突", "锁"], "bug_report"),
    (["搜索", "历史记录", "标签页", "延迟", "慢", "性能"], "usability_issue"),
    (["移动端", "ios", "android", "输入框"], "usability_issue"),
    (["涨价", "换竞品", "流失"], "churn_risk"),
    (["好评", "好用", "效率提高", "批量操作功能很好"], "praise"),
    # aigc_video types
    (["视频", "拍摄", "剪辑", "特效", "新手", "路线", "攻略", "起号", "矩阵", "账号", "运营"], "viral_hook"),
    (["素材", "模板", "滤镜", "内容", "选题"], "content_pattern"),
    (["画面", "转场", "字幕", "封面"], "visual_technique"),
    (["音乐", "配音", "音效", "bgm"], "audio_strategy"),
    (["互动", "评论", "点赞", "收藏", "转发"], "engagement_trigger"),
    (["抖音", "快手", "b站", "小红书", "算法", "推荐", "流量"], "platform_algorithm"),
    (["热点", "趋势", "话题", "蹭"], "topic_trend"),
    (["变现", "带货", "商单", "收入"], "monetization_pattern"),
]


def _get_allowed_types(profile: str) -> list[str]:
    """Get production signal types from pipeline_profile."""
    try:
        p = get_profile(profile)
        return p.signal_types
    except KeyError:
        return []


def _detect_signal_type(text: str, profile: str) -> str:
    """Map text keywords to a signal type from the production whitelist."""
    allowed = _get_allowed_types(profile)
    if not allowed:
        return "feature_request"  # fallback for unknown profiles
    text_lower = text.lower()
    for keywords, sig_type in KEYWORD_SIGNAL_MAP:
        if any(kw in text_lower for kw in keywords) and sig_type in allowed:
            return sig_type
    return allowed[0]


async def generate_with_adapter(adapter, sample: dict) -> dict:
    """Generate a single suggestion using a real LLM adapter.

    This is the injectable function for testing. The adapter must implement
    the BaseLLMAdapter protocol (call_structured).

    Returns a suggestion dict with signal types validated against profile whitelist.
    Raises ValueError on invalid signal type or malformed JSON.
    Raises RuntimeError on adapter failure.
    """
    profile = sample.get("profile", "product_feedback")
    allowed_types = _get_allowed_types(profile)
    text = sample.get("redacted_text", "")

    prompt = (
        f"分析以下用户反馈，提取信号。Profile: {profile}。"
        f"允许的信号类型: {', '.join(allowed_types)}。\n"
        f"反馈内容: {text}\n"
        f"返回JSON格式: signal_type, summary, evidence_start, evidence_end"
    )

    raw = await adapter.call_structured(prompt, temperature=0.1, max_tokens=500)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"Adapter returned invalid JSON: {raw[:200]}") from None

    sig_type = data.get("signal_type", "")
    if sig_type not in allowed_types:
        raise ValueError(
            f"Signal type '{sig_type}' not in profile '{profile}' whitelist: {allowed_types}"
        )

    end = data.get("evidence_end", min(20, len(text)))
    start = data.get("evidence_start", 0)

    return {
        "suggestion_id": f"sg_{sample['sample_id']}",
        "suggestion_model": getattr(adapter, "provider_name", "unknown"),
        "suggestion_model_version": getattr(adapter, "model_name", "unknown"),
        "suggestion_prompt_version": "p13_2_v1",
        "fixture_only": False,
        "suggested_signals": [
            {
                "signal_type": sig_type,
                "summary": data.get("summary", ""),
                "evidence_spans": [{"start": start, "end": end, "text": text[start:end]}],
                "implicit_need": None,
                "implicit_need_has_basis": False,
                "hallucination": False,
            }
        ],
        "suggestion_created_at": datetime.now(timezone.utc).isoformat(),
        "label_status": "suggestion_only",
        "counts_as_human_verified": False,
    }


def _check_api_key(settings, provider: str) -> str:
    """Get the API key for the given provider from settings."""
    key_map = {
        "deepseek": "deepseek_api_key",
        "openai": "openai_api_key",
        "google": "google_api_key",
        "qwen": "qwen_api_key",
        "minimax": "minimax_api_key",
    }
    key_field = key_map.get(provider, "")
    return getattr(settings, key_field, "") or ""


def main() -> int:
    p = argparse.ArgumentParser(description="Generate pre-annotations for assisted_review splits")
    p.add_argument("--candidates", default="sample_data/p13_2/positive/candidates.json")
    p.add_argument("--out", default="sample_data/p13_2/positive/preannotations.json")
    p.add_argument("--fixture-mode", action="store_true",
                   help="Use deterministic templates instead of real LLM calls")
    args = p.parse_args()

    candidates_path = Path(args.candidates)
    if not candidates_path.exists():
        print(json.dumps({"status": "BLOCKED", "reason": "candidates file not found", "passed": False}))
        return 1

    samples = json.loads(candidates_path.read_text())
    if isinstance(samples, dict):
        samples = samples.get("samples", [])

    # --- Non-fixture mode: check real adapter availability ---
    if not args.fixture_mode:
        from signal_miner.settings import AppSettings

        settings = AppSettings()
        provider = settings.default_llm_provider or ""
        api_key = _check_api_key(settings, provider)

        if not provider or not api_key:
            result = {
                "status": "BLOCKED_PREANNOTATION_UNAVAILABLE",
                "passed": False,
                "reason": f"No API key configured for provider '{provider}'",
            }
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
            print(json.dumps({"status": "BLOCKED_PREANNOTATION_UNAVAILABLE", "passed": False}))
            return 2

        # Build real adapter using runtime
        import asyncio

        from signal_miner.runtime import _build_llm_adapter

        try:
            adapter = _build_llm_adapter(settings)
        except RuntimeError as e:
            result = {
                "status": "BLOCKED_PREANNOTATION_UNAVAILABLE",
                "passed": False,
                "reason": str(e),
            }
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
            print(json.dumps({"status": "BLOCKED_PREANNOTATION_UNAVAILABLE", "passed": False}))
            return 2

        # Generate suggestions using real adapter

        suggestions = []
        for s in samples:
            split = s.get("split", "development")
            if split == "test":
                continue
            try:
                sig = asyncio.run(generate_with_adapter(adapter, s))
                suggestions.append(sig)
            except (ValueError, RuntimeError) as e:
                # Skip invalid suggestion, don't generate partial results
                result = {
                    "status": "FAIL_SUGGESTION_GENERATION",
                    "passed": False,
                    "reason": str(e),
                    "failed_sample": s.get("sample_id", ""),
                }
                out_path = Path(args.out)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
                print(json.dumps({"status": "FAIL_SUGGESTION_GENERATION", "passed": False}))
                return 1

        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({
            "schema_version": "1.0.0",
            "fixture_only": False,
            "suggestions": suggestions,
            "suggestion_count": len(suggestions),
        }, indent=2, ensure_ascii=False))
        print(f"Generated {len(suggestions)} live pre-annotations → {args.out}")
        return 0

    # --- Fixture mode: deterministic templates ---
    suggestions = []
    for s in samples:
        split = s.get("split", "development")
        if split == "test":
            continue

        sid = s.get("sample_id", "unknown")
        profile = s.get("profile", "product_feedback")
        text = s.get("redacted_text", "")
        signal_type = _detect_signal_type(text, profile)

        end = min(20, len(text))

        sig = {
            "suggestion_id": f"sg_{sid}",
            "suggestion_model": "fixture",
            "suggestion_model_version": "fixture_v1",
            "suggestion_prompt_version": "fixture_p13_2_v1",
            "fixture_only": True,
            "suggested_signals": [
                {
                    "signal_type": signal_type,
                    "summary": "[预标注-fixture] 需要人工确认",
                    "evidence_spans": [{"start": 0, "end": end, "text": text[:end]}],
                    "implicit_need": None,
                    "implicit_need_has_basis": False,
                    "hallucination": False,
                }
            ],
            "suggestion_created_at": datetime.now(timezone.utc).isoformat(),
            "label_status": "suggestion_only",
            "counts_as_human_verified": False,
        }
        suggestions.append(sig)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "schema_version": "1.0.0",
        "fixture_only": True,
        "suggestions": suggestions,
        "suggestion_count": len(suggestions),
    }, indent=2, ensure_ascii=False))

    print(f"Generated {len(suggestions)} fixture pre-annotations → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
