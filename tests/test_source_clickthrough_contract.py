"""Contract assertions for P9-1 clickthrough + P9-3/4/5 connector field contracts.

Frontend SPA tests use source-level string checks (no browser test framework).
Backend field tests are covered by Pydantic model / ASGI route tests in
``test_connector_response_models.py`` — this file only guards against
accidental SPA regression and keeps the Streamlit helper safety check.
"""

from __future__ import annotations

import pathlib

from signal_miner.utils.url_templates import (
    is_clickable_source_url,
    resolve_clickable_source_url,
    resolve_source_url,
)

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
APP_JS = PROJECT_ROOT / "frontend" / "static" / "app.js"
APP_PY = PROJECT_ROOT / "frontend" / "app.py"
ASSETS_PY = PROJECT_ROOT / "signal_miner" / "routes" / "assets.py"
SIGNALS_PY = PROJECT_ROOT / "signal_miner" / "routes" / "signals.py"


# =========================================================================
# Helpers
# =========================================================================

def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


# =========================================================================
# SPA: batch import contract (no frontend test framework — keep source checks)
# =========================================================================


def test_batch_import_sends_array_not_object():
    """SPA must POST a bare array to /feedback/batch, not { items: [...] }."""
    source = _read(APP_JS)
    assert "apiPost('/feedback/batch', items)" in source
    assert "apiPost('/feedback/batch', { items" not in source


def test_batch_import_uses_ingested_field():
    """SPA must read ``result.ingested`` (backend field name for /feedback/batch)."""
    source = _read(APP_JS)
    # Must use ingested (exists on BatchIngestResponse)
    assert "result.ingested}" in source or "result.ingested " in source
    # Must NOT use ingested_count in the batch feedback section
    assert "result.ingested_count" not in source.split("// Normalize URL fields")[0]


def test_batch_import_normalizes_url_fields():
    """SPA must map source_url / url / video_url / link → external_url."""
    source = _read(APP_JS)
    for field in ("item.source_url", "item.url", "item.video_url", "item.link"):
        assert field in source, f"Expected {field} in URL normalization mapping"


def test_spa_has_escape_html_helper():
    """SPA must have an escapeHtml helper for safe href attribute rendering."""
    source = _read(APP_JS)
    assert "function escapeHtml" in source


def test_spa_source_link_uses_target_blank():
    """All SPA source links must open in new tabs with rel=noopener."""
    source = _read(APP_JS)
    # Verify the pattern exists at least once
    assert 'target="_blank" rel="noopener noreferrer"' in source or \
           "target=\"_blank\" rel=\"noopener noreferrer\"" in source


def test_spa_source_status_keeps_unavailable_entry_visible():
    """Filtered placeholder URLs must still show a non-clickable source state."""
    source = _read(APP_JS)
    assert "function sourceStatusHtml" in source
    assert "function sourceButtonHtml" in source
    assert "source-action-disabled" in source
    assert "sourceButtonHtml(fb.source_url, fb.external_url" in source
    assert "card-header-actions" in source
    assert "sourceStatusHtml(sig.source_url, sig.external_url" in source
    assert "appendSourceStatus(bodyEl, link.source_url, link.external_url" in source


def test_spa_exposes_aigc_video_profile():
    """The static SPA must expose the AIGC video mining mode, not only Streamlit."""
    source = _read(APP_JS)
    assert "PROFILE_OPTIONS" in source
    assert "aigc_video" in source
    assert "AIGC视频爆款挖掘" in source
    assert 'id="profile-select"' in source


def test_spa_scopes_pages_and_pipeline_by_selected_profile():
    """Static SPA page queries and pipeline runs must use the active profile."""
    source = _read(APP_JS)
    expected_snippets = [
        "apiGet('/feedback', { limit: 100, profile: getSelectedProfile() })",
        "const params = { limit: 200, profile: getSelectedProfile() }",
        "apiGet('/themes', { limit: 50, profile: getSelectedProfile() })",
        "apiGet('/pain-points', { limit: 50, profile: getSelectedProfile() })",
        "apiGet('/opportunities', { limit: 50, profile: getSelectedProfile() })",
        "apiGet('/requirements', { limit: 50, profile: getSelectedProfile() })",
        "pipeline_profile: profile",
        "profile: getSelectedProfile()",
    ]
    for snippet in expected_snippets:
        assert snippet in source


def test_spa_requirement_trace_button_reveals_evidence_chain():
    """The trace button must expand the card before loading evidence."""
    source = _read(APP_JS)
    assert "loadEvidenceChain('${req.id}', this)" in source
    assert "function revealEvidenceChainContainer" in source
    assert "card.classList.add('expanded')" in source
    assert "toggle.classList.add('open')" in source
    assert "container.dataset.loaded === 'true'" in source
    assert "container.innerHTML = ''; return;" not in source


def test_spa_import_requires_real_source_url():
    """The import form must not allow source URL to be optional."""
    source = _read(APP_JS)
    assert "真实来源 URL（必填，可点击）" in source
    assert "视频链接（必填，真实可打开）" in source
    assert "必须提供真实可点击来源 URL" in source
    assert "数据来源 URL（可选）" not in source


def test_spa_import_exposes_per_platform_source_methods():
    """The import form must expose per-platform source acquisition guidance."""
    source = _read(APP_JS)
    assert "SOURCE_OPTION_GROUPS" in source
    assert "SOURCE_METHOD_GUIDES" in source
    assert "CAPTURE_METHOD_OPTIONS" in source
    assert "import-capture-method" in source
    assert "source-method-guide" in source
    assert "capture_method: captureMethod" in source

    for platform in (
        "video_douyin",
        "video_bilibili",
        "baidu_search",
        "google_search",
        "jd",
        "xianyu",
        "github",
    ):
        assert platform in source


# =========================================================================
# SPA: connector page field contract
# =========================================================================


def test_github_fetch_spa_reads_ingested_count():
    """SPA GitHub connector must read ``result.ingested_count`` (backend field)."""
    source = _read(APP_JS)
    assert "result.ingested_count" in source


def test_connectors_list_spa_destructures_connectors():
    """SPA must destructure ``{ connectors }`` from GET /connectors."""
    source = _read(APP_JS)
    assert "{ connectors } = await apiGet('/connectors')" in source or \
           "{connectors} = await apiGet('/connectors')" in source


# =========================================================================
# Streamlit: _render_source_link helper safety
# =========================================================================


def test_streamlit_has_safe_source_link_helper():
    """Streamlit must import html.escape and use it in _render_source_link.

    Verifies the helper exists, uses HTML-attribute-safe escaping, and is
    called for every source-link site (not raw f-string href injection).
    """
    source = _read(APP_PY)

    # 1. Import exists
    assert "from html import escape" in source, "Must import html.escape"

    # 2. Helper functions exist and the link helper escapes URL with quote=True
    assert "def _render_source_link" in source, "Must define _render_source_link"
    assert "def _render_source_status" in source, "Must define _render_source_status"
    assert '_html_escape(url, quote=True)' in source, (
        "Must escape URL with quote=True for HTML attribute safety"
    )

    # 3. All source-link sites call the status helper (not raw f-string href)
    assert source.count("_render_source_status(") >= 4
    assert "item.get('external_url')" in source
    assert "sig.get('external_url')" in source
    assert "ev.get('external_url')" in source


def test_streamlit_no_raw_href_fstring_injection():
    """Streamlit must not inject a user URL directly into href= via f-string.

    The _render_source_link helper is the only sanctioned pattern.  This
    test confirms that no remaining ``unsafe_allow_html=True`` line contains
    a raw ``href=...{variable}...`` outside the helper function.
    """
    source = _read(APP_PY)

    # Find lines with unsafe_allow_html=True outside _render_source_link
    in_helper = False
    violations: list[str] = []
    for lineno, line in enumerate(source.splitlines(), 1):
        if "def _render_source_link" in line:
            in_helper = True
        elif line.strip().startswith("def ") and in_helper:
            in_helper = False

        if "unsafe_allow_html=True" in line:
            if in_helper:
                continue  # the helper's own st.markdown is the safe one
            if "href=" in line and "{" in line:
                # A non-helper line using href= with an f-string variable
                violations.append(f"  line {lineno}: {line.strip()[:120]}")

    assert not violations, (
        f"Found {len(violations)} unsafe href= f-string(s) outside _render_source_link:\n"
        + "\n".join(violations)
    )


# =========================================================================
# Evidence trail: source_url field contract (assets.py)
# =========================================================================


def test_evidence_trail_includes_source_url_field():
    """The evidence-trail endpoint must include a 'source_url' key for every link.

    This is a lightweight source guard — the full route behavior is verified
    by the P9-2 runtime evidence in ``docs/P9-2-screenshots/``.
    """
    source = _read(ASSETS_PY)
    assert '"source_url"' in source
    assert "resolve_clickable_source_url" in source  # import is present


def test_signals_route_includes_external_url_for_unavailable_source_state():
    """Signals list must expose raw external_url so UI can show disabled source state."""
    source = _read(SIGNALS_PY)
    assert "external_url: str | None = None" in source
    assert "external_url=fb_external_url" in source


def test_template_resolver_still_supports_internal_url_resolution():
    """The legacy resolver can still build URLs for internal compatibility."""
    assert resolve_source_url("bilibili", external_id="BV123") == (
        "https://www.bilibili.com/video/BV123"
    )


def test_clickable_resolver_does_not_guess_from_external_id():
    """UI clickthroughs must not invent platform URLs from bare IDs."""
    assert (
        resolve_clickable_source_url("bilibili", external_id="BV123")
        is None
    )


def test_clickable_resolver_rejects_demo_import_urls():
    """Synthetic live_game_import URLs are provenance data, not click targets."""
    assert not is_clickable_source_url(
        "https://live.douyin.com/5836526759479846155",
        source_id="live_game_import",
    )
    assert (
        resolve_clickable_source_url(
            "douyin",
            external_url="https://live.douyin.com/5836526759479846155",
            source_id="live_game_import",
        )
        is None
    )


def test_clickable_resolver_keeps_real_explicit_urls():
    """Explicit non-placeholder URLs remain clickable."""
    assert resolve_clickable_source_url(
        "github",
        external_url="https://github.com/openai/codex/issues/1",
        source_id="github_openai_codex",
    ) == "https://github.com/openai/codex/issues/1"


def test_clickable_resolver_rejects_placeholder_urls():
    """Obvious placeholder URLs should not be rendered as source buttons."""
    assert not is_clickable_source_url("https://example.com/product-feedback-source")
