from __future__ import annotations

import json
from pathlib import Path
import re

from signal_miner.pipeline.pipeline_profile import PROFILE_REGISTRY

PROJECT = Path(__file__).resolve().parents[1]
WORKBENCH = PROJECT / "tools" / "annotation_workbench"
HTML_PATH = WORKBENCH / "index.html"
JS_PATH = WORKBENCH / "annotation-workbench.js"
AUTOLOAD_JS_PATH = WORKBENCH / "autoload-packaged-tasks.js"
CSS_PATH = WORKBENCH / "annotation-workbench.css"


def _html() -> str:
    return HTML_PATH.read_text()


def _javascript() -> str:
    return JS_PATH.read_text()


def test_workbench_assets_exist_and_are_offline() -> None:
    assert HTML_PATH.exists()
    assert JS_PATH.exists()
    assert AUTOLOAD_JS_PATH.exists()
    assert CSS_PATH.exists()

    html = _html()
    assert "https://" not in html
    assert "http://" not in html
    assert 'src="./annotation-workbench.js' in html
    assert 'href="./annotation-workbench.css"' in html

    javascript = _javascript()
    assert "fetch(" not in javascript
    assert "XMLHttpRequest" not in javascript
    assert "WebSocket(" not in javascript


def test_profile_types_match_production_registry() -> None:
    match = re.search(
        r'<script id="profileData" type="application/json">(.*?)</script>',
        _html(),
        re.DOTALL,
    )
    assert match is not None
    page_profiles = json.loads(match.group(1))
    expected = {
        name: list(profile.signal_types)
        for name, profile in PROFILE_REGISTRY.items()
    }
    assert page_profiles == expected


def test_required_annotation_controls_are_present() -> None:
    html = _html()
    required_ids = {
        "packInput",
        "annotationInput",
        "taskList",
        "sourceText",
        "addEvidenceButton",
        "pseudonymInput",
        "signalDecision",
        "reviewActionBlock",
        "signalEditor",
        "addSignalButton",
        "completeTaskButton",
        "exportJsonButton",
        "exportCsvButton",
    }
    actual_ids = set(re.findall(r'\bid="([^"]+)"', html))
    assert required_ids <= actual_ids


def test_fixture_assisted_autoload_is_explicit_and_local() -> None:
    html = _html()
    javascript = _javascript()
    autoload_javascript = AUTOLOAD_JS_PATH.read_text()
    assert 'type="module" src="./autoload-packaged-tasks.js' in html
    assert "../../sample_data/p13_2/human_tasks/human_tasks_development.json" in autoload_javascript
    assert "../../sample_data/p13_2/human_tasks/human_tasks_calibration.json" in autoload_javascript
    assert 'requestedSource === "fixture-assisted"' in autoload_javascript
    assert 'globalThis.addEventListener("annotation-workbench:autoload"' in javascript
    assert "fetch(" not in javascript
    assert "fetch(" not in autoload_javascript


def test_blind_leakage_and_identity_guards_are_in_main_path() -> None:
    javascript = _javascript()
    assert 'task.annotation_mode === "blind" && task.suggestion !== null' in javascript
    assert "FORBIDDEN_SUGGESTION_KEYS" in javascript
    assert 'pack.annotator_slot !== first.annotator_slot' in javascript
    assert 'Boolean(pack.fixture) !== Boolean(first.fixture)' in javascript
    assert 'draft.task_hash !== task.task_hash' in javascript
    assert 'draft.content_hash !== task.content_hash' in javascript


def test_unicode_evidence_uses_code_point_offsets() -> None:
    javascript = _javascript()
    assert "function codePointLength(text)" in javascript
    assert "return Array.from(text).length" in javascript
    assert "function codePointSlice(text, start, end)" in javascript
    assert "Array.from(text).slice(start, end).join" in javascript
    assert "codePointSlice(task.redacted_text, span.start, span.end) !== span.text" in javascript


def test_export_shape_uses_human_annotation_v2_fields() -> None:
    javascript = _javascript()
    for field in (
        "annotation_id",
        "dataset_id",
        "sample_id",
        "annotator_slot",
        "annotator_pseudonym",
        "annotation_mode",
        "has_signals",
        "signal_count",
        "signals",
        "review_action",
        "started_at",
        "completed_at",
        "task_hash",
        "content_hash",
        "fixture",
    ):
        assert f"{field}:" in javascript

    assert "downloadFile(fileName" in javascript
    assert "JSON.stringify({ annotations }" in javascript
