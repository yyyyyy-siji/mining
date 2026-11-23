"""Streamlit Web UI for SignalMiner.

Run with: streamlit run frontend/app.py
"""

from html import escape as _html_escape
import json
import os
import time

import httpx
import streamlit as st

st.set_page_config(page_title="SignalMiner ⛏️", page_icon="⛏️", layout="wide")

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")

# Phase 7: 8 video signal types (emoji + label in zh / en)
VIDEO_SIGNAL_LABELS = {
    "viral_hook":           {"emoji": "🪝", "zh": "开头钩子",   "en": "Viral Hook"},
    "content_pattern":      {"emoji": "📐", "zh": "内容模式",   "en": "Content Pattern"},
    "visual_technique":     {"emoji": "🎨", "zh": "视觉技巧",   "en": "Visual Technique"},
    "audio_strategy":       {"emoji": "🎵", "zh": "音频策略",   "en": "Audio Strategy"},
    "engagement_trigger":   {"emoji": "💬", "zh": "互动触发",   "en": "Engagement Trigger"},
    "platform_algorithm":   {"emoji": "📊", "zh": "平台算法",   "en": "Platform Algorithm"},
    "topic_trend":          {"emoji": "📈", "zh": "话题趋势",   "en": "Topic Trend"},
    "monetization_pattern": {"emoji": "💰", "zh": "变现模式",   "en": "Monetization"},
}

# Combined type → emoji map (product feedback + AIGC video)
def _signal_emoji(t: str) -> str:
    if t in VIDEO_SIGNAL_LABELS:
        return VIDEO_SIGNAL_LABELS[t]["emoji"]
    return {
        "feature_request": "✨",
        "bug_report": "🐛",
        "usability_issue": "🔧",
        "complaint": "😤",
        "churn_risk": "🚪",
        "question": "❓",
        "praise": "👍",
    }.get(t, "📌")


# ---------------------------------------------------------------------------
# Safe URL link renderer  (P9-1: HTML attribute escaping)
# ---------------------------------------------------------------------------

def _render_source_link(url: str | None, label: str = "") -> None:
    """Render a source URL as a clickable link with proper HTML escaping.

    Does nothing if *url* is falsy.
    """
    if not url:
        return
    safe_url = _html_escape(url, quote=True)
    safe_label = _html_escape(label) if label else safe_url
    st.markdown(
        f'🔗 <a href="{safe_url}" target="_blank" rel="noopener noreferrer">{safe_label}</a>',
        unsafe_allow_html=True,
    )


def _render_source_status(
    source_url: str | None,
    external_url: str | None,
    label: str = "",
) -> None:
    """Render either a clickable verified source link or an unavailable state."""
    if source_url:
        _render_source_link(source_url, label)
    elif external_url:
        st.caption("🔗 数据来源：演示/占位来源，无法打开真实页面。")


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Sidebar & Internationalization / i18n
# ---------------------------------------------------------------------------

lang = st.sidebar.selectbox("语言 / Language", ["中文 (简体)", "English"], index=0)
is_zh = (lang == "中文 (简体)")

if is_zh:
    st.sidebar.title("⛏️ SignalMiner 信号挖掘机")
    st.sidebar.markdown("用户反馈 → 提取信号 → 需求挖掘")
else:
    st.sidebar.title("⛏️ SignalMiner")
    st.sidebar.markdown("User Feedback → Extracted Signals → Requirements")

st.sidebar.divider()

# Phase 7: Profile switcher
PROFILE_OPTIONS_ZH = {
    "product_feedback": "🏭 用户反馈挖矿",
    "aigc_video": "🎬 AIGC视频爆款挖掘",
}
PROFILE_OPTIONS_EN = {
    "product_feedback": "🏭 Product Feedback Mining",
    "aigc_video": "🎬 AIGC Video Viral Mining",
}
profile_options = PROFILE_OPTIONS_ZH if is_zh else PROFILE_OPTIONS_EN

# Try to fetch the live profile list from the API; fall back to defaults
# so the UI keeps working even if the backend is offline.
try:
    _profiles_resp = httpx.get(f"{API_BASE}/profiles", timeout=5)
    if _profiles_resp.status_code == 200:
        _live = [p["name"] for p in _profiles_resp.json()]
        # Keep only profiles we know how to display.
        profile_options = {
            k: v for k, v in profile_options.items() if k in _live
        }
except Exception:
    pass

selected_profile = st.sidebar.selectbox(
    "挖矿模式" if is_zh else "Mining Profile",
    list(profile_options.keys()),
    format_func=lambda x: profile_options[x],
    key="selected_profile",
)
# Keep a session-state copy so sub-pages can read it.
# (Automatically handled by streamlit because of key="selected_profile")

# Show the active text model separately from the optional multimodal model.
try:
    _llm_resp = httpx.get(f"{API_BASE}/llm/capabilities", timeout=5)
    if _llm_resp.status_code == 200:
        _llm_data = _llm_resp.json()
        _primary = _llm_data["primary"]
        _media = _llm_data["multimodal"]
        st.sidebar.caption(
            f"🧠 主模型：{_primary['provider']} / {_primary['model']}"
            if is_zh else
            f"🧠 Primary: {_primary['provider']} / {_primary['model']}"
        )
        if _media.get("enabled"):
            _modalities = ", ".join(_media.get("input_modalities", []))
            st.sidebar.caption(
                f"👁️ 多模态：{_media['provider']} / {_media['model']} ({_modalities})"
                if is_zh else
                f"👁️ Multimodal: {_media['provider']} / {_media['model']} ({_modalities})"
            )
        else:
            st.sidebar.caption("👁️ 多模态：未启用" if is_zh else "👁️ Multimodal: disabled")
except Exception:
    pass

st.sidebar.divider()

PAGES_ZH = [
    "📥 导入反馈",
    "📋 原始反馈",
    "🔬 提取信号",
    "🏷️ 主题聚类",
    "😣 痛点",
    "💡 机会卡片",
    "📝 需求候选",
    "⚙️ 运行管线",
]

PAGES_EN = [
    "📥 Import Feedback",
    "📋 Raw Feedback",
    "🔬 Extracted Signals",
    "🏷️ Theme Clustering",
    "😣 Pain Points",
    "💡 Opportunity Cards",
    "📝 Requirements",
    "⚙️ Run Pipeline",
]

nav_options = PAGES_ZH if is_zh else PAGES_EN
selected_page = st.sidebar.radio("导航 / Navigation" if is_zh else "Navigation", nav_options)
page_idx = nav_options.index(selected_page)
page = PAGES_ZH[page_idx]  # Map back to Chinese internally for seamless routing compatibility



# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def api_get(path: str, params: dict = None) -> list | dict | None:
    try:
        resp = httpx.get(f"{API_BASE}{path}", params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        err_msg = f"API Error {resp.status_code}: {resp.text}"
        st.error(err_msg)
    except httpx.ConnectError:
        if is_zh:
            st.error("⚠️ 无法连接到后端。请确保已启动: `python -m signal_miner.main`")
        else:
            st.error("⚠️ Cannot connect to backend. Please ensure it is running: `python -m signal_miner.main`")
    except Exception as e:
        if is_zh:
            st.error(f"请求失败: {e}")
        else:
            st.error(f"Request failed: {e}")
    return None


def api_post(path: str, payload: dict | list) -> dict | None:
    try:
        resp = httpx.post(f"{API_BASE}{path}", json=payload, timeout=30)
        if resp.status_code in (200, 201, 202):
            return resp.json()
        err_msg = f"API Error {resp.status_code}: {resp.text}"
        st.error(err_msg)
    except httpx.ConnectError:
        if is_zh:
            st.error("⚠️ 无法连接到后端。请确保已启动: `python -m signal_miner.main`")
        else:
            st.error("⚠️ Cannot connect to backend. Please ensure it is running: `python -m signal_miner.main`")
    except Exception as e:
        if is_zh:
            st.error(f"请求失败: {e}")
        else:
            st.error(f"Request failed: {e}")
    return None


def render_empty_state_with_pipeline_trigger(asset_name: str):
    name_zh = asset_name
    name_en = {
        "信号": "Signal",
        "主题": "Theme",
        "痛点": "Pain Point",
        "机会卡片": "Opportunity Card",
        "需求候选": "Requirement",
    }.get(asset_name, asset_name)

    display_name = name_zh if is_zh else name_en

    header = f"🔍 暂无{display_name}数据" if is_zh else f"🔍 No {display_name} Data Available"
    desc = (
        f"由于这是新导入的反馈，AI 信号挖掘管线尚未运行。请点击下方按钮<b>立即启动管线</b>来处理反馈数据并生成{display_name}！"
        if is_zh else
        f"Since these are newly imported feedback, the AI signal mining pipeline has not run yet. Click the button below to <b>run the pipeline immediately</b> to process feedback and generate {display_name}!"
    )

    st.markdown(
        f"""
        <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; border: 1px solid #d3d3d3; margin-bottom: 20px;">
            <h4 style="margin-top: 0; color: #1f77b4;">{header}</h4>
            <p style="font-size: 14px; color: #555;">{desc}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    slider_label1 = "每条反馈最多提取信号数" if is_zh else "Max signals per feedback"
    # P13-1 fix-1: confidence_threshold deprecated — removed from UI
    # slider_label2 = "最低置信度阈值" if is_zh else "Min confidence threshold"

    max_signals = col1.slider(slider_label1, 1, 10, 5, key=f"empty_max_{asset_name}")
    # P13-1 fix-1: confidence slider removed — conf_threshold no longer used for decisions
    conf_threshold = 0.5  # Legacy default, not displayed

    btn_label = "🚀 一键运行管线并刷新页面" if is_zh else "🚀 Run Pipeline & Refresh Page"
    if st.button(btn_label, use_container_width=True, type="primary", key=f"empty_btn_{asset_name}"):
        payload = {
            "max_signals": max_signals,
            "profile": selected_profile,
        }
        result = api_post("/pipeline/run", payload)
        if result:
            success_msg = f"✅ 管线已成功启动！待处理反馈: {result['feedback_count']} 条。正在分析中..." if is_zh else f"✅ Pipeline successfully started! Pending feedback: {result['feedback_count']} items. Analyzing..."
            st.success(success_msg)

            # Show a progress bar while polling
            progress_bar = st.progress(0)
            status_text = st.empty()
            for i in range(40):
                time.sleep(1.5)
                # Check if data exists now
                signals = api_get("/signals", {"limit": 1, "profile": selected_profile})
                themes = api_get("/themes", {"limit": 1, "profile": selected_profile})
                reqs = api_get("/requirements", {"limit": 1, "profile": selected_profile})
                progress_bar.progress(min((i + 1) * 3, 100))

                if reqs or themes or signals:
                    status_success = "✅ 管线已完成，数据生成成功！正在刷新..." if is_zh else "✅ Pipeline completed, data generated successfully! Refreshing..."
                    status_text.success(status_success)
                    progress_bar.progress(100)
                    time.sleep(1.5)
                    st.rerun()
                    break
                status_text.info(f"⏳ 正在提取信号并聚类... (已用时 {i*1.5:.1f}s)")
            else:
                status_text.warning("⏱️ 管线仍在后台处理中，请稍后刷新页面查看。")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

if page == "📥 导入反馈":
    st.header("📥 导入反馈" if is_zh else "📥 Import Feedback")

    tab_manual, tab_batch = st.tabs(["手动输入", "批量导入 (JSON)"] if is_zh else ["Manual Input", "Batch Import (JSON)"])

    with tab_manual, st.form("manual_ingest"):
            if selected_profile == "aigc_video":
                source_type = st.selectbox(
                    "平台" if is_zh else "Platform",
                    ["video_douyin", "video_bilibili", "video_xiaohongshu", "video_kuaishou", "video_youtube", "video_manual"],
                )
                video_url = st.text_input("视频链接 (Video URL)" if is_zh else "Video URL")
                col_v1, col_v2 = st.columns(2)
                views = col_v1.number_input("播放量 (Views)" if is_zh else "Views", min_value=0, step=1, value=0)
                likes = col_v2.number_input("点赞数 (Likes)" if is_zh else "Likes", min_value=0, step=1, value=0)
                author_name = st.text_input("创作者名 (可选)" if is_zh else "Creator Name (Optional)")
                subject = st.text_input("视频标题 (可选)" if is_zh else "Video Title (Optional)")
                text = st.text_area(
                    "视频文案 / 简介" if is_zh else "Caption / Description",
                    height=200,
                    placeholder="粘贴视频标题、描述、字幕或评论…" if is_zh else "Paste video title, description, transcript, or comments…",
                )
                external_url = None
            else:
                source_type = st.selectbox("来源" if is_zh else "Source", ["manual", "bilibili", "xiaohongshu", "weibo", "tieba", "zhihu", "github"])
                author_name = st.text_input("用户名 (可选)" if is_zh else "Username (Optional)")
                company = st.text_input("公司/组织 (可选)" if is_zh else "Company/Organization (Optional)")
                subject = st.text_input("标题 (可选)" if is_zh else "Title (Optional)")
                external_url = st.text_input(
                    "数据来源 URL（可选）" if is_zh else "Source URL (Optional)",
                    placeholder="https://...",
                )
                text = st.text_area(
                    "反馈内容" if is_zh else "Feedback Content",
                    height=200,
                    placeholder="在这里粘贴用户反馈原文…" if is_zh else "Paste original user feedback here..."
                )
                video_url = None
                views = None
                likes = None

            submit_label = "提交" if is_zh else "Submit"
            if st.form_submit_button(submit_label, use_container_width=True):
                if text:
                    payload = {
                        "source_type": source_type,
                        "subject": subject,
                        "text": text,
                        "author_name": author_name,
                        "company": None,
                        "pipeline_profile": selected_profile,
                    }
                    if selected_profile == "aigc_video":
                        payload["video_url"] = video_url or None
                        payload["external_url"] = video_url or external_url or None
                        payload["views"] = int(views or 0)
                        payload["likes"] = int(likes or 0)
                        payload["platform"] = source_type.replace("video_", "") if source_type.startswith("video_") else source_type
                    else:
                        payload["external_url"] = external_url or None
                    result = api_post("/feedback/ingest", payload)
                    if result:
                        st.success(
                            f"✅ 已录入！ID: `{result['feedback_id']}` (profile: {result.get('pipeline_profile', selected_profile)})"
                            if is_zh else
                            f"✅ Ingested! ID: `{result['feedback_id']}` (profile: {result.get('pipeline_profile', selected_profile)})"
                        )
                else:
                    st.warning("请输入内容。" if is_zh else "Please enter content.")

    with tab_batch:
        uploader_label = "上传 JSON 文件（数组格式）" if is_zh else "Upload JSON file (Array format)"
        uploaded = st.file_uploader(uploader_label, type=["json"])
        if uploaded:
            try:
                data = json.load(uploaded)
                if not isinstance(data, list):
                    data = [data]
                st.info(f"检测到 {len(data)} 条反馈" if is_zh else f"Detected {len(data)} feedbacks")

                btn_start = "开始导入" if is_zh else "Start Import"
                if st.button(btn_start):
                    items = []
                    for row in data:
                        text_val = row.get("text", row.get("content", row.get("body", row.get("feedback", ""))))
                        item = {
                            "source_type": row.get("source", "csv"),
                            "subject": row.get("title", row.get("subject")),
                            "text": text_val,
                            "author_name": row.get("author", row.get("user")),
                            "company": row.get("company"),
                            "segment": row.get("segment"),
                            "pipeline_profile": selected_profile,
                        }
                        item["external_url"] = row.get("url", row.get("source_url", row.get("video_url", row.get("link"))))
                        if selected_profile == "aigc_video":
                            item["video_url"] = row.get("video_url")
                            item["views"] = row.get("views", 0)
                            item["likes"] = row.get("likes", 0)
                            item["platform"] = row.get("platform")
                        items.append(item)
                    result = api_post("/feedback/batch", items)
                    if result:
                        st.success(
                            f"✅ 导入完成！共 {result['total']} 条，{result['duplicates']} 条重复"
                            if is_zh else
                            f"✅ Import complete! Total: {result['total']}, {result['duplicates']} duplicates"
                        )
            except Exception as e:
                st.error(f"文件解析失败: {e}" if is_zh else f"File parsing failed: {e}")

elif page == "📋 原始反馈":
    st.header("📋 原始反馈" if is_zh else "📋 Raw Feedback")
    data = api_get("/feedback", {"limit": 100, "profile": selected_profile})
    if data:
        st.caption(f"共 {len(data)} 条" if is_zh else f"Total: {len(data)} items")
        for item in data:
            status_emoji = {"pending": "🕐", "completed": "✅", "failed": "❌", "extracting": "⚙️"}.get(item["processing_state"], "❓")
            no_title = "无标题" if is_zh else "No Title"
            signal_count_label = "信号" if is_zh else "signals"
            with st.expander(f"{status_emoji} [{item['source_type']}] {item.get('subject') or no_title} — {signal_count_label}: {item['signal_count']}"):
                st.markdown(item["text_preview"])
                # Source URL link
                source_url = item.get('source_url')
                _render_source_status(
                    source_url,
                    item.get('external_url'),
                    '数据来源' if is_zh else 'Source',
                )

                state_lbl = "状态" if is_zh else "State"
                created_lbl = "创建" if is_zh else "Created"
                st.caption(f"ID: `{item['id']}` | {state_lbl}: {item['processing_state']} | {created_lbl}: {item['created_at']}")
    else:
        if selected_profile == "aigc_video":
            st.info("暂无该 profile 下的视频数据。请先在「导入反馈」页录入视频元数据。" if is_zh else "No video data for this profile. Please import video metadata on the Import page.")
        else:
            st.info("暂无反馈数据。请先导入反馈。" if is_zh else "No feedback data available. Please import feedback first.")

elif page == "🔬 提取信号":
    st.header("🔬 提取信号" if is_zh else "🔬 Extracted Signals")
    col1, col2 = st.columns(2)

    if selected_profile == "aigc_video":
        # 8 video signal types
        type_options = [None] + list(VIDEO_SIGNAL_LABELS.keys())
        if is_zh:
            type_labels = {None: "全部 / All"}
            for k, v in VIDEO_SIGNAL_LABELS.items():
                type_labels[k] = f"{v['emoji']} {v['zh']} / {v['en']}"
        else:
            type_labels = {None: "All"}
            for k, v in VIDEO_SIGNAL_LABELS.items():
                type_labels[k] = f"{v['emoji']} {v['en']}"
    else:
        # 7 product-feedback types (preserved)
        type_options = [None, "feature_request", "bug_report", "usability_issue", "complaint", "churn_risk", "question", "praise"]
        type_labels = {
            None: "全部 / All",
            "feature_request": "功能需求 / Feature Request",
            "bug_report": "缺陷报告 / Bug Report",
            "usability_issue": "易用性问题 / Usability Issue",
            "complaint": "抱怨 / Complaint",
            "churn_risk": "流失风险 / Churn Risk",
            "question": "疑问 / Question",
            "praise": "好评 / Praise"
        } if is_zh else {
            None: "All",
            "feature_request": "Feature Request",
            "bug_report": "Bug Report",
            "usability_issue": "Usability Issue",
            "complaint": "Complaint",
            "churn_risk": "Churn Risk",
            "question": "Question",
            "praise": "Praise"
        }

    signal_type = col1.selectbox(
        "信号类型" if is_zh else "Signal Type",
        type_options,
        format_func=lambda x: type_labels.get(x, str(x))
    )
    # P13-1 fix-1: renamed to min_model_self_score, default 0 (show all)
    min_conf = col2.slider(
        "最低模型自评分（未校准，仅查看筛选）" if is_zh else "Min Model Self-Score (uncalibrated, view filter)",
        0.0, 1.0, 0.0, 0.05,
    )
    params = {"limit": 100, "profile": selected_profile}
    if signal_type:
        params["signal_type"] = signal_type
    # P13-1 fix-1: use min_model_self_score, not min_confidence
    if min_conf > 0:
        params["min_model_self_score"] = min_conf
    data = api_get("/signals", params)
    if data:
        st.caption(f"共 {len(data)} 条信号" if is_zh else f"Total: {len(data)} signals")
        for sig in data:
            type_emoji = _signal_emoji(sig["signal_type"])
            conf = sig['confidence']
            # P13-1: honest confidence — model self-report, not calibrated
            conf_label = (
                f"校准 {sig.get('calibrated_confidence'):.0%}"
                if sig.get('calibrated_confidence') is not None
                else f"模型自评 {conf:.2f}（未校准）"
            )
            evidence_status = sig.get('evidence_validation_status', 'not_checked')
            evidence_badge = {
                'verified': ' ✅证据已验证',
                'partial': ' ⚠️证据部分匹配',
                'invalid': ' ❌证据未匹配',
                'not_checked': '',
            }.get(evidence_status, '')
            with st.expander(f"{type_emoji} {sig['summary']} — {conf_label}{evidence_badge}"):
                st.markdown("**证据原文:**" if is_zh else "**Evidence Quotes:**")
                for ev in sig.get("evidence", []):
                    st.markdown(f"> _{ev}_")
                if sig.get("implicit_need"):
                    st.markdown(f"**隐性需求:** {sig['implicit_need']}" if is_zh else f"**Implicit Need:** {sig['implicit_need']}")

                type_lbl = "类型" if is_zh else "Type"
                model_lbl = "模型" if is_zh else "Model"
                st.caption(f"{type_lbl}: {sig['signal_type']} | {model_lbl}: {sig.get('extraction_model')} | ID: `{sig['id']}`")
                source_url = sig.get('source_url')
                _render_source_status(
                    source_url,
                    sig.get('external_url'),
                    '查看原始来源' if is_zh else 'View Original Source',
                )
                if not source_url and not sig.get('external_url') and sig.get('source_type'):
                    st.caption(f"📎 {'来源平台' if is_zh else 'Source'}: {sig['source_type']}")
    else:
        render_empty_state_with_pipeline_trigger("信号")

elif page == "🏷️ 主题聚类":
    st.header("🏷️ 主题聚类" if is_zh else "🏷️ Theme Clustering")
    data = api_get("/themes", {"profile": selected_profile})
    if data:
        st.caption(f"共 {len(data)} 个主题" if is_zh else f"Total: {len(data)} themes")
        for theme in data:
            sig_lbl = "个信号" if is_zh else "signals"
            with st.expander(f"🏷️ {theme['name']} ({theme['signal_count']} {sig_lbl})"):
                st.markdown(theme["description"])
                if theme.get("representative_quotes"):
                    st.markdown("**代表性引用:**" if is_zh else "**Representative Quotes:**")
                    for q in theme["representative_quotes"]:
                        st.markdown(f"> _{q}_")

                state_lbl = "状态" if is_zh else "State"
                st.caption(f"{state_lbl}: {theme['status']} | ID: `{theme['id']}`")
    else:
        render_empty_state_with_pipeline_trigger("主题")

elif page == "😣 痛点":
    st.header("😣 用户痛点" if is_zh else "😣 User Pain Points")
    data = api_get("/pain-points", {"profile": selected_profile})
    if data:
        st.caption(f"共 {len(data)} 个痛点" if is_zh else f"Total: {len(data)} pain points")
        for pp in data:
            sev_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}.get(pp["severity"], "⚪")
            with st.expander(f"{sev_emoji} [{pp['severity'].upper()}] {pp['description'][:80]}…"):
                st.markdown(f"**目标用户:** {pp['user_segment']}" if is_zh else f"**Target Segment:** {pp['user_segment']}")

                freq_lbl = "频率" if is_zh else "Frequency"
                sev_lbl = "严重度" if is_zh else "Severity"
                st.markdown(f"**{freq_lbl}:** {pp['frequency']} | **{sev_lbl}:** {pp['severity']}")

                st.markdown(f"**业务影响:** {pp['business_impact']}" if is_zh else f"**Business Impact:** {pp['business_impact']}")
                if pp.get("evidence_quotes"):
                    st.markdown("**支撑证据:**" if is_zh else "**Supporting Evidence:**")
                    for q in pp["evidence_quotes"]:
                        st.markdown(f"> _{q}_")
                st.caption(f"ID: `{pp['id']}`")
    else:
        render_empty_state_with_pipeline_trigger("痛点")

elif page == "💡 机会卡片":
    st.header("💡 机会卡片 (JTBD)" if is_zh else "💡 Opportunity Cards (JTBD)")
    if selected_profile == "product_feedback":
        st.info(
            "本批真实材料的候选发现、原话核对与清单导出，请使用主 SPA 的「机会卡片」页；本页仅展示历史机会资产。"
            if is_zh else
            "Use the main SPA Opportunity Cards page to select source materials, preview evidence-backed "
            "candidates, and export your decisions. This page displays historical assets only."
        )
    data = api_get("/opportunities", {"profile": selected_profile})
    if data:
        st.caption(f"共 {len(data)} 个机会" if is_zh else f"Total: {len(data)} opportunities")
        for opp in data:
            with st.expander(f"💡 {opp['description'][:80]}…"):
                st.markdown(f"**JTBD:** {opp['jtbd_statement']}")
                st.markdown(f"**描述:** {opp['description']}" if is_zh else f"**Description:** {opp['description']}")
                if opp.get("assumptions"):
                    st.markdown("**待验证假设:**" if is_zh else "**Assumptions to Validate:**")
                    for a in opp["assumptions"]:
                        st.markdown(f"- {a}")
                # Supporting evidence
                opp_detail = api_get(f"/opportunities/{opp['id']}")
                if opp_detail and opp_detail.get("supporting_evidence"):
                    st.divider()
                    st.markdown("**📎 支撑证据链:**" if is_zh else "**📎 Supporting Evidence Chain:**")
                    for ev in opp_detail["supporting_evidence"]:
                        src = f"[{ev.get('source_type', '?')}]" if ev.get('source_type') else ""
                        seg = f" ({ev.get('author_segment')})" if ev.get('author_segment') else ""
                        st.markdown(f"> 💬 _{ev.get('quote', ev.get('signal_summary', ''))}_")
                        st.caption(f"    Signal: `{ev.get('signal_id', '?')}` {src}{seg}")
                        _render_source_status(
                            ev.get('source_url'),
                            ev.get('external_url'),
                            '查看原始来源' if is_zh else 'View Source',
                        )

                state_lbl = "状态" if is_zh else "State"
                st.caption(f"{state_lbl}: {opp['status']} | ID: `{opp['id']}`")
    else:
        render_empty_state_with_pipeline_trigger("机会卡片")

elif page == "📝 需求候选":
    st.header("📝 需求候选" if is_zh else "📝 Requirement Specs")
    data = api_get("/requirements", {"profile": selected_profile})
    if data:
        st.caption(f"共 {len(data)} 个需求" if is_zh else f"Total: {len(data)} requirements")
        for req in data:
            trail_count = len(req.get('evidence_trail', []))

            trail_badge = (
                f" | 📎 {trail_count} 条证据" if is_zh else f" | 📎 {trail_count} Evidence Quotes"
            ) if trail_count > 0 else ""

            with st.expander(f"📝 {req['title']}{trail_badge}"):
                if req.get("user_stories"):
                    st.markdown("**用户故事:**" if is_zh else "**User Stories:**")
                    for us in req["user_stories"]:
                        if isinstance(us, dict):
                            if is_zh:
                                st.markdown(f"- 作为一个 **{us.get('role')}**，我想要 **{us.get('action')}**，以便于 **{us.get('benefit')}**。")
                            else:
                                st.markdown(f"- As a **{us.get('role')}**, I want to **{us.get('action')}**, so that **{us.get('benefit')}**.")
                        else:
                            st.markdown(f"- {us}")
                if req.get("acceptance_criteria"):
                    st.markdown("**验收标准:**" if is_zh else "**Acceptance Criteria:**")
                    for ac in req["acceptance_criteria"]:
                        st.markdown(f"- ✅ {ac}")
                if req.get("decision_reasoning"):
                    st.markdown(f"**决策推理:** {req['decision_reasoning']}" if is_zh else f"**Decision Reasoning:** {req['decision_reasoning']}")
                impact = req.get("impact", {})
                if impact:
                    st.markdown(f"**用户影响:** {impact.get('user_impact', '-')}" if is_zh else f"**User Impact:** {impact.get('user_impact', '-')}")
                    st.markdown(f"**业务影响:** {impact.get('business_impact', '-')}" if is_zh else f"**Business Impact:** {impact.get('business_impact', '-')}")

                # Evidence trail visualization
                evidence = req.get("evidence_trail", [])
                if evidence:
                    st.divider()
                    st.markdown("**📎 完整证据链** _(从原始用户反馈到本需求的追溯)_" if is_zh else "**📎 Full Traceability Evidence Trail** _(Tracing from Raw Feedback to Requirement)_")
                    for idx, ev in enumerate(evidence, 1):
                        src = f"[{ev.get('source_type', '?')}]" if ev.get('source_type') else ""
                        seg = f" · {ev.get('author_segment')}" if ev.get('author_segment') else ""
                        sig_type = ev.get('signal_type', '')
                        conf = ev.get('confidence', 0)
                        st.markdown(f"**{idx}.** 💬 _{ev.get('quote', '')}_")
                        st.caption(
                            f"    Signal: `{ev.get('signal_id', '?')}` ({sig_type}, {conf:.0%}) "
                            f"← Feedback: `{ev.get('raw_feedback_id', '?')}` {src}{seg}"
                        )
                        _render_source_status(
                            ev.get('source_url'),
                            ev.get('external_url'),
                            '查看原始来源' if is_zh else 'View Source',
                        )
                elif trail_count == 0:
                    st.caption("_暂无证据链数据_" if is_zh else "_No evidence trail data available_")

                state_lbl = "状态" if is_zh else "State"
                st.caption(f"{state_lbl}: {req['status']} | ID: `{req['id']}`")
    else:
        render_empty_state_with_pipeline_trigger("需求候选")

elif page == "⚙️ 运行管线":
    st.header("⚙️ 运行管线" if is_zh else "⚙️ Run Signal Mining Pipeline")
    if selected_profile == "aigc_video":
        if is_zh:
            st.markdown("""
            点击下方按钮将对所有"待处理"的 **AIGC 视频** 数据执行完整挖矿流程：

            **视频数据** → **爆款技巧提取** → **模式聚类** → **创作瓶颈** → **爆款公式** → **创作指南**
            """)
        else:
            st.markdown("""
            Click the button below to execute the complete viral-mining workflow on all pending AIGC video data:

            **Video Data** → **Viral Technique Extraction** → **Pattern Clustering** → **Creation Bottleneck** → **Viral Formula** → **Creator SOP**
            """)
    else:
        if is_zh:
            st.markdown("""
            点击下方按钮将对所有"待处理"的反馈执行完整挖矿流程：

            **反馈** → **信号提取** → **向量嵌入** → **主题聚类** → **痛点** → **机会** → **需求候选**
            """)
        else:
            st.markdown("""
            Click the button below to execute the complete signal mining workflow on all "pending" user feedback:

            **Raw Feedback** → **Signal Extraction** → **Vector Embedding** → **Theme Clustering** → **Pain Points** → **Opportunities** → **Requirements**
            """)

    col1, _col2 = st.columns(2)
    slider_lbl1 = "每条数据最多提取信号数" if is_zh else "Max signals per item"
    # P13-1 fix-1: confidence threshold removed — not used for trust decisions
    max_signals = col1.slider(slider_lbl1, 1, 10, 5)
    # conf_threshold slider removed, legacy default retained for API compat
    conf_threshold = 0.5

    btn_run = "🚀 启动管线" if is_zh else "🚀 Run Pipeline"
    if st.button(btn_run, use_container_width=True, type="primary"):
        payload = {
            "max_signals": max_signals,
            "profile": selected_profile,
        }
        result = api_post("/pipeline/run", payload)
        if result:
            success_msg = (
                f"✅ 管线已启动！Run ID: `{result['run_id']}` | profile: `{result.get('profile', selected_profile)}` | 待处理: {result['feedback_count']} 条"
                if is_zh else
                f"✅ Pipeline started! Run ID: `{result['run_id']}` | profile: `{result.get('profile', selected_profile)}` | pending: {result['feedback_count']}"
            )
            info_msg = (
                "管线正在后台运行。请稍后刷新各页面查看生成的资产。"
                if is_zh else
                "The pipeline is running in the background. Please refresh other pages later to view generated assets."
            )
            st.success(success_msg)
            st.info(info_msg)

            # Poll for completion
            progress_bar = st.progress(0)
            status_text = st.empty()
            run_id = result.get("run_id", "")
            for i in range(60):  # Poll for up to 60 seconds
                time.sleep(2)
                # P13-1 fix-2: Check run status for completed_with_skips
                if run_id:
                    run_status_data = api_get(f"/pipeline/runs/{run_id}")
                    if run_status_data and isinstance(run_status_data, dict):
                        rs = run_status_data.get("status", "")
                        if rs == "completed_with_skips":
                            status_text.warning(
                                "⚠️ 文本提取已完成；语义去重/聚类未执行（Embedding 不可用）。"
                                if is_zh else
                                "⚠️ Text extraction complete; semantic phases skipped (embedding unavailable).",
                            )
                            progress_bar.progress(100)
                            break
                        if rs == "completed":
                            status_text.success(
                                "✅ 管线完成！" if is_zh else "✅ Pipeline completed!"
                            )
                            progress_bar.progress(100)
                            break
                        if rs == "failed":
                            status_text.error(
                                "❌ 管线失败" if is_zh else "❌ Pipeline failed"
                            )
                            break
                # Fallback: check signals/themes/reqs
                signals = api_get("/signals", {"limit": 1, "profile": selected_profile})
                themes = api_get("/themes", {"limit": 1, "profile": selected_profile})
                reqs = api_get("/requirements", {"limit": 1, "profile": selected_profile})
                progress_bar.progress(min((i + 1) * 3, 100))

                if reqs:
                    status_text.success(
                        "✅ 管线完成！需求资产已生成。请到各页面查看。" if is_zh else "✅ Pipeline completed!"
                    )
                    break
                elif themes:
                    status_text.info("⏳ 主题已生成，正在生成需求资产..." if is_zh else "⏳ Themes generated...")
                elif signals:
                    status_text.info("⏳ 信号已提取，正在聚类..." if is_zh else "⏳ Signals extracted, clustering...")
                else:
                    status_text.info(
                        f"⏳ 正在提取信号... ({(i+1)*2}s)"
                        if is_zh else
                        f"⏳ Extracting signals... ({(i+1)*2}s elapsed)"
                    )
            else:
                warn_polling = "⏱️ 管线仍在运行中，请稍后刷新页面查看结果。" if is_zh else "⏱️ Pipeline is still processing. Please refresh the page later to view results."
                status_text.warning(warn_polling)
