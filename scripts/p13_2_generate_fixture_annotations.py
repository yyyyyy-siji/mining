#!/usr/bin/env python3
"""P13-2-2-1: Generate fixture human annotations from candidate samples.

Produces deterministic fixture annotations tagged fixture=true for:
  - all development + calibration samples (assisted_review, slot="assisted")
  - all test samples (blind, slot="A")
  - all double-annotation test samples (blind, slot="B")

These are ONLY for exercising the toolchain. They never count as real gold.
The validator will report FIXTURE_PASS, never READY.

Exit codes: 0 = written, 1 = error, 2 = BLOCKED waiting on authorized data.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from signal_miner.evaluation.human_annotation import (  # noqa: E402
    allowed_signal_types,
    compute_task_hash,
)

# Deterministic keyword → signal_type map, tagged with the profile it belongs to.
KEYWORD_MAP_PF = [
    (["暗黑", "夜间", "深色", "markdown", "预览", "备份", "网盘",
      "菜单", "层级", "设置", "快捷键", "自定义", "通知", "静音",
      "版本", "回退", "升级", "更新", "批量", "效率", "阅读", "进度条",
      "功能", "希望", "建议", "能否", "可以", "支持"], "feature_request", "product_feedback"),
    (["崩溃", "闪退", "报错", "bug", "500", "导出", "csv", "格式",
      "粘贴", "复制", "协作", "冲突", "锁", "错误", "失败", "无法"], "bug_report", "product_feedback"),
    (["搜索", "历史记录", "标签页", "延迟", "慢", "性能", "卡顿", "难用"], "usability_issue", "product_feedback"),
    (["移动端", "ios", "android", "输入框", "怎么", "如何", "？", "?"], "question", "product_feedback"),
    (["好评", "好用", "效率提高", "赞", "喜欢", "棒"], "praise", "product_feedback"),
    (["差评", "失望", "垃圾", "退款", "投诉"], "complaint", "product_feedback"),
    (["涨价", "换竞品", "流失", "不续费", "取消"], "churn_risk", "product_feedback"),
    # aigc_video
    (["视频", "拍摄", "剪辑", "特效", "新手", "路线", "攻略", "起号", "矩阵", "账号", "运营"], "viral_hook", "aigc_video"),
    (["素材", "模板", "滤镜", "内容", "选题"], "content_pattern", "aigc_video"),
    (["画面", "转场", "字幕", "封面"], "visual_technique", "aigc_video"),
    (["音乐", "配音", "音效", "bgm"], "audio_strategy", "aigc_video"),
    (["互动", "评论", "点赞", "收藏", "转发"], "engagement_trigger", "aigc_video"),
    (["抖音", "快手", "b站", "小红书", "算法", "推荐", "流量"], "platform_algorithm", "aigc_video"),
    (["热点", "趋势", "话题", "蹭"], "topic_trend", "aigc_video"),
    (["变现", "带货", "商单", "收入"], "monetization_pattern", "aigc_video"),
]

# Fallback per profile
FALLBACK = {
    "product_feedback": "feature_request",
    "aigc_video": "viral_hook",
}


def _detect(text: str, profile: str) -> str:
    """Map text keywords to a signal_type that belongs to the given profile."""
    text_lower = text.lower()
    allowed = set(allowed_signal_types(profile))
    for keywords, st, pf in KEYWORD_MAP_PF:
        if pf != profile:
            continue
        if any(k in text_lower for k in keywords) and st in allowed:
            return st
    # Fallback: first allowed type for the profile
    if allowed:
        return sorted(allowed)[0]
    return FALLBACK.get(profile, "feature_request")


def _build_annotation(dataset_id: str, sample: dict, annotator_slot: str,
                      mode: str, pseudonym_seed: str, profile: str) -> dict:
    """Build a single deterministic fixture annotation."""
    text = sample["redacted_text"]
    content_hash = sample["content_hash"]
    task_hash = compute_task_hash(dataset_id, sample["sample_id"], annotator_slot, content_hash)

    # 80% of samples "have signals", deterministically by content hash parity
    has_signals = (int(content_hash[-2:], 16) % 10) < 8
    signals = []
    sig_type = _detect(text, profile)

    if has_signals:
        # evidence = first 20 chars of redacted text (guaranteed valid)
        end = min(20, len(text))
        snippet = text[:end]
        signals.append({
            "signal_type": sig_type,
            "summary": f"[fixture] {sig_type} signal in sample {sample['sample_id'][:10]}",
            "evidence_spans": [{"start": 0, "end": end, "text": snippet}],
            "implicit_need": None,
            "implicit_need_has_basis": False,
            "hallucination": False,
            "notes": None,
        })

    now = datetime.now(timezone.utc).isoformat()
    aid = f"fixann_{sample['sample_id']}_{annotator_slot}"
    # Pseudonym must differ between A and B for the same sample to avoid
    # self-pairing. Encode slot deterministically.
    pseudonym = "anno_fixture_" + pseudonym_seed[-8:] + "_" + annotator_slot

    review_action = None
    if mode == "assisted_review":
        # Deterministic: mostly "accepted", some "modified"
        review_action = "modified" if (int(content_hash[-2:], 16) % 5 == 0) else "accepted"

    return {
        "annotation_id": aid,
        "dataset_id": dataset_id,
        "sample_id": sample["sample_id"],
        "annotator_slot": annotator_slot,
        "annotator_pseudonym": pseudonym,
        "annotation_mode": mode,
        "has_signals": has_signals,
        "signal_count": len(signals),
        "signals": signals,
        "review_action": review_action,
        "started_at": now,
        "completed_at": now,
        "task_hash": task_hash,
        "content_hash": content_hash,
        "fixture": True,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Generate fixture human annotations")
    p.add_argument("--candidates", default="sample_data/p13_2/positive/candidates.json")
    p.add_argument("--manifest", default="sample_data/p13_2/manifest.json")
    p.add_argument("--tasks", default="sample_data/p13_2/human_tasks",
                   help="Task pack directory (must have been generated first)")
    p.add_argument("--out", default="sample_data/p13_2/annotations/fixture_annotations.json")
    args = p.parse_args()

    cp = Path(args.candidates)
    mp = Path(args.manifest)

    if not cp.exists() or not mp.exists():
        print(json.dumps({"status": "FAIL_INPUT", "passed": False}))
        return 1

    cands_raw = json.loads(cp.read_text())
    if isinstance(cands_raw, dict) and cands_raw.get("status", "").startswith("BLOCKED"):
        print(json.dumps({"status": "BLOCKED_WAITING_AUTHORIZED_DATA", "passed": False}))
        return 2

    manifest = json.loads(mp.read_text())
    dataset_id = manifest["dataset_id"]
    cands = {c["sample_id"]: c for c in cands_raw}

    # Load task packs to get the authoritative task_hash and slot mapping
    task_dir = Path(args.tasks)
    pack_files = [
        task_dir / "human_tasks_development.json",
        task_dir / "human_tasks_calibration.json",
        task_dir / "human_tasks_test_A.json",
        task_dir / "human_tasks_test_B.json",
    ]

    annotations = []
    for pf in pack_files:
        if not pf.exists():
            continue
        pack = json.loads(pf.read_text())
        slot = pack.get("annotator_slot", "")
        mode = pack.get("annotation_mode", "")
        for task in pack.get("tasks", []):
            sid = task["sample_id"]
            sample = cands.get(sid)
            if not sample:
                continue
            # Different pseudonym per slot to avoid self-pairing on double samples
            pseudonym_seed = f"{sid}_{slot}"
            ann = _build_annotation(dataset_id, sample, slot, mode, pseudonym_seed,
                                    sample.get("profile", "product_feedback"))
            # Override task_hash from the authoritative pack
            ann["task_hash"] = task["task_hash"]
            annotations.append(ann)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"annotations": annotations}, indent=2, ensure_ascii=False))

    print(json.dumps({
        "status": "FIXTURE_GENERATED",
        "passed": True,
        "count": len(annotations),
        "out": str(out_path),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
