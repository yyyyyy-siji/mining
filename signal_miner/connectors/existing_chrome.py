"""Bounded DOM collection through an explicitly authorized, borrowed Chrome.

No browser process, cookie/storage API, platform HTTP client or generic script API
is used. A tiny CDP transport attaches only to the selected domestic XHS target.
Closing this collector closes its WebSocket, never the browser or its targets.
"""
from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, quote, unquote, urljoin, urlsplit, urlunsplit
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Callable

CAPTURE_VERSION = "mining-existing-chrome-dom/v1"
SELECTOR_VERSION = "xhs-public-note-dom/v1"
HOSTS = {"xiaohongshu.com", "www.xiaohongshu.com"}
NOTE_PATH = re.compile(r"/(?:explore|discovery/item)/([a-fA-F0-9]{24})/?$")
SUPPORTED_PLATFORMS = ("xiaohongshu", "bilibili", "weibo", "zhihu", "douyin")
TERMINAL = {"completed", "failed", "cancelled"}
MAX_TEXT = 100_000
MAX_POSTS = 20
MAX_COMMENTS = 50
DEFAULT_TASK_TIMEOUT = 300

PLATFORM_CONFIGS = {
    "xiaohongshu": {
        "label": "小红书",
        "hosts": {"xiaohongshu.com", "www.xiaohongshu.com"},
        "detail_pattern": NOTE_PATH,
        "non_detail_paths": {"", "/explore", "/search_result", "/search_result_ai"},
        "selector_version": "xhs-public-note-dom/v1",
        "search_url": lambda q: "https://www.xiaohongshu.com/search_result?keyword=" + quote(q, safe="") + "&type=51",
        "search_query_keys": ("keyword", "type"),
        "comment_id_pattern": re.compile(r"[a-fA-F0-9]{24}"),
    },
    "bilibili": {
        "label": "B站",
        "hosts": {"bilibili.com", "www.bilibili.com", "search.bilibili.com"},
        "detail_pattern": re.compile(r"/video/(BV[A-Za-z0-9]+|av[0-9]+)/?"),
        "non_detail_paths": {"", "/all"},
        "selector_version": "bili-public-video-dom/v1",
        "search_url": lambda q: "https://search.bilibili.com/all?keyword=" + quote(q, safe=""),
        "search_query_keys": ("keyword",),
        "comment_id_pattern": re.compile(r"[0-9A-Za-z_-]{1,64}"),
    },
    "weibo": {
        "label": "微博",
        "hosts": {"weibo.com", "www.weibo.com", "s.weibo.com"},
        "detail_pattern": re.compile(r"/(?:[0-9]+/([A-Za-z0-9]+)|detail/([0-9]+))/?"),
        "non_detail_paths": {"", "/weibo", "/hot", "/hot/search", "/newlogin", "/mygroups", "/top/summary", "/realtime"},
        "non_detail_prefix": ("/hot/", "/u/"),
        "selector_version": "wb-public-post-dom/v1",
        "search_url": lambda q: "https://s.weibo.com/weibo?q=" + quote(q, safe=""),
        "search_query_keys": ("q",),
        "comment_id_pattern": re.compile(r"[0-9A-Za-z_-]{1,64}"),
    },
    "zhihu": {
        "label": "知乎",
        "hosts": {"zhihu.com", "www.zhihu.com", "zhuanlan.zhihu.com"},
        "detail_pattern": re.compile(r"/(?:question/[0-9]+/answer/([0-9]+)|question/([0-9]+)|p/([0-9]+))/?"),
        "non_detail_paths": {"", "/search", "/hot", "/follow", "/explore", "/waiting", "/knowledge-plan"},
        "non_detail_prefix": ("/topic/", "/column/", "/people/"),
        "selector_version": "zhihu-public-content-dom/v1",
        "search_url": lambda q: "https://www.zhihu.com/search?type=content&q=" + quote(q, safe=""),
        "search_query_keys": ("q",),
        "comment_id_pattern": re.compile(r"[0-9A-Za-z_-]{1,64}"),
    },
    "douyin": {
        "label": "抖音",
        "hosts": {"douyin.com", "www.douyin.com"},
        "detail_pattern": re.compile(r"/(?:video|note)/([0-9]{10,25})/?"),
        "non_detail_paths": {"", "/discover", "/jingxuan", "/follow", "/friend", "/hot", "/channel"},
        "non_detail_prefix": ("/search/", "/user/", "/channel/", "/jingxuan/"),
        "selector_version": "douyin-public-video-dom/v1",
        "search_url": lambda q: "https://www.douyin.com/search/" + quote(q, safe="") + "?type=video",
        "search_query_keys": (),
        "comment_id_pattern": re.compile(r"[0-9A-Za-z_-]{1,64}"),
    },
}


def detect_platform(value: str | None) -> str | None:
    """Return supported platform key for an HTTPS URL, or None."""
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    host = parsed.hostname.lower()
    for platform, cfg in PLATFORM_CONFIGS.items():
        if host in cfg["hosts"]:
            return platform
    return None


def _extract_detail_id(platform: str, path: str) -> str | None:
    match = PLATFORM_CONFIGS[platform]["detail_pattern"].fullmatch(path)
    if not match:
        return None
    for group in match.groups():
        if group:
            return group
    return None


class ChromeError(ValueError):
    """Safe, deterministic error suitable for the UI; never carries CDP data."""

    def __init__(self, code: str, message: str, status_code: int = 409):
        super().__init__(code)
        self.code, self.message, self.status_code = code, message, status_code


def validate_url(value: str, *, note: bool = False, platform: str | None = None) -> str:
    """Only exact domestic HTTPS supported platform public pages, without authority tricks."""
    try:
        if not isinstance(value, str) or len(value) > 4000 or any(
            ord(char) < 33 or char in "\\,#" for char in value
        ):
            raise ValueError
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.username or parsed.password or parsed.port is not None
            or parsed.fragment
        ):
            raise ValueError
        resolved_platform = platform or detect_platform(value)
        if resolved_platform not in PLATFORM_CONFIGS:
            raise ValueError
        cfg = PLATFORM_CONFIGS[resolved_platform]
        if (parsed.hostname or "").lower() not in cfg["hosts"]:
            raise ValueError
        is_note = bool(cfg["detail_pattern"].fullmatch(parsed.path))
        normalized_path = parsed.path.rstrip("/")
        is_entry = normalized_path in cfg["non_detail_paths"] or any(
            parsed.path.startswith(prefix) for prefix in cfg.get("non_detail_prefix", ())
        )
        if not is_note and (note or not is_entry):
            raise ValueError
        return value
    except (TypeError, ValueError) as exc:
        raise ChromeError("invalid_target_url", "仅支持国内小红书、B站、微博、知乎或抖音 HTTPS 首页、搜索页或详情链接。", 422) from exc


def default_discovery_file() -> Path:
    """Chrome stable's default user-data root; never accepts a client path."""
    if sys.platform == "darwin":
        root = Path.home() / "Library/Application Support/Google/Chrome"
    elif sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "Google/Chrome/User Data"
    else:
        root = Path(os.environ.get("CHROME_CONFIG_HOME") or os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "google-chrome"
    return root / "DevToolsActivePort"


def read_endpoint() -> str:
    """Read exactly bounded discovery metadata, never /json/version or cookies."""
    try:
        path = default_discovery_file()
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        with os.fdopen(os.open(path, flags), "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError
            data = stream.read(4097)
        lines = data.decode("ascii").splitlines()
        if len(data) > 4096 or len(lines) != 2:
            raise ValueError
        port, route = lines
        if not re.fullmatch(r"[0-9]{1,5}", port) or not 1 <= int(port) <= 65535:
            raise ValueError
        if not re.fullmatch(r"/devtools/browser(?:/[A-Za-z0-9_-]{1,200})?", route):
            raise ValueError
        return f"ws://127.0.0.1:{int(port)}{route}"
    except FileNotFoundError as exc:
        raise ChromeError("remote_debugging_not_enabled_or_chrome_not_running", "未发现 Chrome 当前会话端点。请在已运行 Chrome 的 chrome://inspect/#remote-debugging 启用本次调试授权；这不代表未登录。") from exc
    except PermissionError as exc:
        raise ChromeError("browser_profile_access_denied", "宿主应用无法读取 Chrome 的连接发现文件。请检查 macOS 对宿主应用访问 Google Chrome 文件夹的授权。") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise ChromeError("invalid_endpoint_metadata", "Chrome 连接发现信息无效或尚未写入完成；未探测其他端口。") from exc


# These fixed expressions are the entire DOM capability. No caller can supply JS.
# They inspect public content containers, never document-wide innerText or state.
_DOM_HELPERS = r"""
const visible = el => !!el && el.getClientRects().length > 0 &&
  getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
const first = (root, selectors) => Array.from(root.querySelectorAll(selectors)).find(visible);
const text = el => visible(el) ? el.innerText.trim() : '';
const allowed = url => url.protocol === 'https:' &&
  ['xiaohongshu.com','www.xiaohongshu.com'].includes(url.hostname) &&
  !url.port && !url.username && !url.password && !url.hash;
const here = new URL(location.href);
if (!allowed(here)) return {error:'invalid_target_url'};
if (first(document, '.login-container, .login-modal, .login-mask, .verify-container, .captcha-container, #captcha'))
  return {error:'access_gate'};
"""

NOTE_DOM_SCRIPT = r"""(() => {
""" + _DOM_HELPERS + r"""
if (!/^\/(?:explore|discovery\/item)\/[a-fA-F0-9]{24}\/?$/.test(here.pathname))
  return {error:'invalid_target_url'};
const root = first(document, '#noteContainer, .note-detail-mask .note-container, .note-detail-container');
if (!root) return {error:'content_missing'};
const body = first(root, '#detail-desc, .note-content .desc, .note-text.note-desc');
if (!body || !text(body)) return {error:'body_missing'};
const bodyArea = body.closest('.note-content, .desc') || body.parentElement;
const clippedNode = el => {
  const style = getComputedStyle(el);
  return el.scrollHeight > el.clientHeight + 2 &&
    (['hidden','clip'].includes(style.overflowY) || parseInt(style.webkitLineClamp || '0') > 0);
};
const clipped = clippedNode(body) || clippedNode(bodyArea);
const expanded = first(bodyArea, '.expand-btn, .show-more, .read-more');
const bodyText = text(body);
const title = first(root, '#detail-title, .note-content .title');
const postTime = Array.from(root.querySelectorAll('.bottom-container .date, .note-content > .date, .note-content time, .bottom-container time'))
  .find(el => visible(el) && !el.closest('.comments-container, .comment-list'));
const ident = value => /^[a-fA-F0-9]{24}$/.test(value || '') ? value : null;
const absolute = node => {
  const raw = visible(node) ? node.getAttribute('datetime') : null;
  return raw && /^\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d(?:\.\d+)?)?(?:Z|[+-]\d\d:\d\d)$/.test(raw) ? raw : null;
};
const comments = [];
const commentRoot = first(root, '.comments-container, .comment-list');
const emptyComments = commentRoot && first(commentRoot, '.no-comments, .no-comment, .empty-comment, .comments-empty');
if (commentRoot) for (const item of commentRoot.querySelectorAll('.comment-item')) {
  if (!visible(item) || item.parentElement.closest('.comment-item') || item.closest('.reply-container, .reply-list')) continue;
  const own = selectors => Array.from(item.querySelectorAll(selectors)).find(el =>
    visible(el) && el.closest('.comment-item') === item && !el.closest('.reply-container, .reply-list'));
  const content = own('.content .note-text, .content');
  const value = text(content);
  if (!value) continue;
  const stamp = own('time, .date');
  const cid = ident(item.getAttribute('data-comment-id')) ||
    ident((item.getAttribute('id') || '').replace(/^comment-/,''));
  comments.push({text:value.slice(0,100000),text_truncated:value.length>100000,
    comment_id:cid,parent_comment_id:ident(item.getAttribute('data-parent-comment-id')),
    source_time_display:text(stamp) || null,source_created_at:absolute(stamp)});
  if (comments.length >= 50) break;
}
return {url:here.href,title:text(title) || null,body:bodyText.slice(0,100000),
  body_clipped:clipped || !!expanded,body_limit:bodyText.length>100000,
  source_time_display:text(postTime) || null,source_created_at:absolute(postTime),
  comments,comment_container_present:!!commentRoot,comment_empty_explicit:!!emptyComments};
})()"""

SEARCH_DOM_SCRIPT = r"""(() => {
""" + _DOM_HELPERS + r"""
if (here.pathname.replace(/\/$/,'') !== '/search_result') return {error:'invalid_target_url'};
const notes = [], seen = new Set();
for (const anchor of document.querySelectorAll('.feeds-container section.note-item a.cover[href], section.note-item a.cover[href]')) {
  if (!visible(anchor)) continue;
  try {
    const url = new URL(anchor.getAttribute('href'),here);
    if (!allowed(url)) continue;
    const match = /^\/(?:explore|discovery\/item|search_result)\/([a-fA-F0-9]{24})\/?$/.exec(url.pathname);
    if (!match) continue;
    const id = match[1].toLowerCase();
    if (seen.has(id)) continue;
    seen.add(id);
    if (/^\/(?:explore|discovery\/item)\//.test(url.pathname)) notes.push({url:url.href});
    else notes.push({search_result_href:url.href});
    if (notes.length >= 20) break;
  } catch (_) {}
}
if (!notes.length) return {error:'search_result_missing'};
return {notes};
})()"""

# Navigation handoff reads metadata only, including while the old document still
# runs. It never queries public content, account information or browser state.
NAVIGATION_DOM_SCRIPT = r"""(() => {
const here = new URL(location.href);
if (here.protocol !== 'https:' ||
  !['xiaohongshu.com','www.xiaohongshu.com'].includes(here.hostname) ||
  here.port || here.username || here.password || here.hash)
  return {error:'invalid_target_url'};
return {url:here.href,ready_state:document.readyState};
})()"""

_BILI_HELPERS = r"""
const visible = el => !!el && el.getClientRects().length > 0 &&
  getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
const first = (root, selectors) => Array.from(root.querySelectorAll(selectors)).find(visible);
const text = el => visible(el) ? el.innerText.trim() : '';
const allowed = url => url.protocol === 'https:' &&
  ['bilibili.com','www.bilibili.com','search.bilibili.com'].includes(url.hostname) &&
  !url.port && !url.username && !url.password && !url.hash;
const here = new URL(location.href);
if (!allowed(here)) return {error:'invalid_target_url'};
if (first(document, '.bili-mini-mask, .login-panel-popover, .geetest_panel, #bili-captcha'))
  return {error:'access_gate'};
"""

BILI_NOTE_DOM_SCRIPT = r"""(async () => {
""" + _BILI_HELPERS + r"""
if (!/^\/video\/(?:BV[A-Za-z0-9]+|av[0-9]+)\/?$/.test(here.pathname))
  return {error:'invalid_target_url'};
const titleEl = first(document, 'h1.video-title, .video-info-title-inner h1, h1[title]');
const descEl = first(document, '#v_desc .basic-desc-info, .desc-info-text, .video-desc-container .basic-desc-info');
const titleText = text(titleEl);
const descText = text(descEl);
let bodyText = descText && titleText && descText !== titleText
  ? `${titleText}\n${descText}`
  : (descText || titleText);
if (!bodyText) return {error:'body_missing'};
let hasSubtitles = false;
let subtitleLanguage = null;
try {
  const init = window.__INITIAL_STATE__ || {};
  const vd = init.videoData || {};
  const bvid = vd.bvid || (here.pathname.match(/\/video\/(BV[A-Za-z0-9]+)/) || [])[1];
  const cid = vd.cid || (Array.isArray(vd.pages) && vd.pages[0] ? vd.pages[0].cid : null);
  if (bvid && cid && typeof fetch === 'function') {
    const ctrl = typeof AbortController === 'function' ? new AbortController() : null;
    const timer = ctrl ? setTimeout(() => ctrl.abort(), 5000) : null;
    try {
      const resp = await fetch(
        `https://api.bilibili.com/x/player/wbi/v2?bvid=${encodeURIComponent(bvid)}&cid=${encodeURIComponent(cid)}`,
        { credentials: 'include', signal: ctrl ? ctrl.signal : undefined }
      );
      if (resp.ok) {
        const json = await resp.json();
        const subs = json?.data?.subtitle?.subtitles;
        if (Array.isArray(subs) && subs.length) {
          const picked = subs.find(s => /zh/i.test(s.lan || '')) || subs[0];
          const subUrl = picked?.subtitle_url ? (picked.subtitle_url.startsWith('//') ? `https:${picked.subtitle_url}` : picked.subtitle_url) : '';
          if (subUrl.startsWith('https://')) {
            const subResp = await fetch(subUrl, { signal: ctrl ? ctrl.signal : undefined });
            if (subResp.ok) {
              const subJson = await subResp.json();
              const lines = Array.isArray(subJson?.body)
                ? subJson.body.map(seg => String(seg?.content || '').trim()).filter(Boolean)
                : [];
              if (lines.length) {
                hasSubtitles = true;
                subtitleLanguage = picked.lan_doc || picked.lan || 'CC/AI';
                bodyText = `${bodyText}\n\n【视频字幕逐字稿】\n${lines.join('\n')}`;
              }
            }
          }
        }
      }
    } finally {
      if (timer) clearTimeout(timer);
    }
  }
} catch (_) {}
const postTime = first(document, '.pubdate-ip-text, .pubdate-text');
const comments = [];
const pushComment = (val, cid) => {
  const clean = (val || '').trim();
  if (!clean || comments.length >= 50) return;
  comments.push({
    text: clean.slice(0, 100000),
    text_truncated: clean.length > 100000,
    comment_id: cid || null,
    parent_comment_id: null,
    source_time_display: null,
    source_created_at: null,
  });
};
const biliComments = document.querySelector('bili-comments');
let commentContainerPresent = !!biliComments;
if (biliComments && biliComments.shadowRoot) {
  const threads = biliComments.shadowRoot.querySelectorAll('bili-comment-thread-renderer');
  for (const th of threads) {
    const cr = th.shadowRoot ? th.shadowRoot.querySelector('bili-comment-renderer') : null;
    if (!cr || !cr.shadowRoot) continue;
    const rt = cr.shadowRoot.querySelector('bili-rich-text');
    const contentEl = rt && rt.shadowRoot ? rt.shadowRoot.querySelector('#contents, p') : (rt || cr.shadowRoot.querySelector('#content, .content'));
    const val = contentEl ? (contentEl.innerText || contentEl.textContent || '').trim() : '';
    pushComment(val, cr.getAttribute('data-id') || null);
    if (comments.length >= 50) break;
  }
}
if (!comments.length) {
  const legacyRoot = first(document, '.reply-list, .comment-list');
  if (legacyRoot) {
    commentContainerPresent = true;
    for (const item of legacyRoot.querySelectorAll('.reply-item, .list-item')) {
      const contentEl = first(item, '.reply-content, .text');
      pushComment(text(contentEl), item.getAttribute('data-id') || null);
      if (comments.length >= 50) break;
    }
  }
}
const cleanUrl = `${here.origin}${here.pathname}`;
return {
  url: cleanUrl,
  title: titleText || null,
  body: bodyText.slice(0, 100000),
  body_clipped: false,
  body_limit: bodyText.length > 100000,
  has_subtitles: hasSubtitles,
  subtitle_language: subtitleLanguage,
  source_time_display: text(postTime) || null,
  source_created_at: null,
  comments,
  comment_container_present: commentContainerPresent,
  comment_empty_explicit: false,
};
})()"""

BILI_SEARCH_DOM_SCRIPT = r"""(() => {
""" + _BILI_HELPERS + r"""
if (here.pathname.replace(/\/$/,'') !== '/all') return {error:'invalid_target_url'};
const notes = [], seen = new Set();
for (const anchor of document.querySelectorAll('.bili-video-card a[href*="/video/"], .video-list a[href*="/video/"], a[href*="/video/BV"]')) {
  if (!visible(anchor)) continue;
  try {
    const raw = anchor.getAttribute('href') || '';
    const url = new URL(raw.startsWith('//') ? `https:${raw}` : raw, here);
    if (!allowed(url)) continue;
    const match = /^\/video\/(BV[A-Za-z0-9]+|av[0-9]+)\/?$/.exec(url.pathname);
    if (!match) continue;
    const id = match[1];
    if (seen.has(id)) continue;
    seen.add(id);
    notes.push({url: `https://www.bilibili.com/video/${id}`});
    if (notes.length >= 20) break;
  } catch (_) {}
}
if (!notes.length) return {error:'search_result_missing'};
return {notes};
})()"""

BILI_NAVIGATION_DOM_SCRIPT = r"""(() => {
const here = new URL(location.href);
if (here.protocol !== 'https:' ||
  !['bilibili.com','www.bilibili.com','search.bilibili.com'].includes(here.hostname) ||
  here.port || here.username || here.password || here.hash)
  return {error:'invalid_target_url'};
return {url:here.href,ready_state:document.readyState};
})()"""

_WEIBO_HELPERS = r"""
const visible = el => !!el && el.getClientRects().length > 0 &&
  getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
const first = (root, selectors) => Array.from(root.querySelectorAll(selectors)).find(visible);
const text = el => visible(el) ? el.innerText.trim() : '';
const allowed = url => url.protocol === 'https:' &&
  ['weibo.com','www.weibo.com','s.weibo.com'].includes(url.hostname) &&
  !url.port && !url.username && !url.password && !url.hash;
const here = new URL(location.href);
if (!allowed(here)) return {error:'invalid_target_url'};
if (first(document, '.woo-modal-main .LoginPop_loginPop, .login-layer'))
  return {error:'access_gate'};
"""

WEIBO_NOTE_DOM_SCRIPT = r"""(() => {
""" + _WEIBO_HELPERS + r"""
if (!/^\/(?:[0-9]+\/[A-Za-z0-9]+|detail\/[0-9]+)\/?$/.test(here.pathname))
  return {error:'invalid_target_url'};
const body = first(document, '[class*="detail_wbtext"], .wbpro-feed-content [class*="wbtext"], .Feed_body_3R0rO [class*="wbtext"], .txt[node-type="feed_list_content"]');
const bodyText = text(body);
if (!bodyText) return {error:'body_missing'};
const postTime = first(document, '[class*="head-info_time"], a[class*="time"], .from a');
const comments = [];
const commentRoot = first(document, '[class*="RepostCommentList"], .wbpro-list, .card-comment');
if (commentRoot) {
  for (const item of commentRoot.querySelectorAll('[class*="CommentItem"], .item1, .txt')) {
    if (!visible(item)) continue;
    const contentEl = first(item, '[class*="text"], .txt') || item;
    const val = text(contentEl);
    if (!val) continue;
    comments.push({
      text: val.slice(0, 100000),
      text_truncated: val.length > 100000,
      comment_id: null,
      parent_comment_id: null,
      source_time_display: null,
      source_created_at: null,
    });
    if (comments.length >= 50) break;
  }
}
return {
  url: `${here.origin}${here.pathname}`,
  title: null,
  body: bodyText.slice(0, 100000),
  body_clipped: false,
  body_limit: bodyText.length > 100000,
  source_time_display: text(postTime) || null,
  source_created_at: null,
  comments,
  comment_container_present: !!commentRoot,
  comment_empty_explicit: false,
};
})()"""

WEIBO_SEARCH_DOM_SCRIPT = r"""(() => {
""" + _WEIBO_HELPERS + r"""
if (here.pathname.replace(/\/$/,'') !== '/weibo') return {error:'invalid_target_url'};
const notes = [], seen = new Set();
for (const anchor of document.querySelectorAll('.card-wrap .from a[href*="weibo.com/"], .card-wrap a[href*="weibo.com/"]')) {
  if (!visible(anchor)) continue;
  try {
    const raw = anchor.getAttribute('href') || '';
    const url = new URL(raw.startsWith('//') ? `https:${raw}` : raw, here);
    if (!allowed(url)) continue;
    const match = /^\/([0-9]+\/[A-Za-z0-9]+|detail\/[0-9]+)\/?$/.exec(url.pathname);
    if (!match) continue;
    const id = match[1];
    if (seen.has(id)) continue;
    seen.add(id);
    notes.push({url: `https://weibo.com/${id}`});
    if (notes.length >= 20) break;
  } catch (_) {}
}
if (!notes.length) return {error:'search_result_missing'};
return {notes};
})()"""

WEIBO_NAVIGATION_DOM_SCRIPT = r"""(() => {
const here = new URL(location.href);
if (here.protocol !== 'https:' ||
  !['weibo.com','www.weibo.com','s.weibo.com'].includes(here.hostname) ||
  here.port || here.username || here.password || here.hash)
  return {error:'invalid_target_url'};
return {url:here.href,ready_state:document.readyState};
})()"""

_ZHIHU_HELPERS = r"""
const visible = el => !!el && el.getClientRects().length > 0 &&
  getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
const first = (root, selectors) => Array.from(root.querySelectorAll(selectors)).find(visible);
const text = el => visible(el) ? el.innerText.trim() : '';
const allowed = url => url.protocol === 'https:' &&
  ['zhihu.com','www.zhihu.com','zhuanlan.zhihu.com'].includes(url.hostname) &&
  !url.port && !url.username && !url.password && !url.hash;
const here = new URL(location.href);
if (!allowed(here)) return {error:'invalid_target_url'};
if (first(document, '.Modal-wrapper .SignFlow, .Unhuman-verification, .Captcha-container'))
  return {error:'access_gate'};
"""

ZHIHU_NOTE_DOM_SCRIPT = r"""(() => {
""" + _ZHIHU_HELPERS + r"""
const isAnswer = /^\/question\/[0-9]+\/answer\/[0-9]+\/?$/.test(here.pathname);
const isQuestion = /^\/question\/[0-9]+\/?$/.test(here.pathname);
const isArticle = /^\/p\/[0-9]+\/?$/.test(here.pathname);
if (!isAnswer && !isQuestion && !isArticle) return {error:'invalid_target_url'};
const titleEl = first(document, 'h1.QuestionHeader-title, h1.Post-Title, .QuestionHeader-title');
const titleText = text(titleEl);
let bodyText = '';
if (isArticle) {
  const art = first(document, '.Post-RichTextContainer .RichText, .Post-RichText, article .RichText');
  bodyText = text(art);
} else if (isAnswer) {
  const ans = first(document, '.QuestionAnswer-content .RichContent-inner .RichText, .AnswerItem .RichContent-inner .RichText, .RichContent-inner .RichText');
  bodyText = text(ans);
} else {
  const parts = [];
  const qDesc = first(document, '.QuestionRichText .RichText');
  if (text(qDesc)) parts.push(text(qDesc));
  const answers = Array.from(document.querySelectorAll('.AnswerItem .RichContent-inner .RichText, .List-item .RichContent-inner .RichText')).filter(visible);
  for (const ans of answers.slice(0, 3)) {
    const val = text(ans);
    if (val) parts.push(val);
  }
  bodyText = parts.join('\n\n---\n\n');
}
if (!bodyText) return {error:'body_missing'};
const postTime = first(document, '.ContentItem-time a, .ContentItem-time');
const comments = [];
const commentRoot = first(document, '.Comments-container, .CommentsV2, .CommentListV2');
if (commentRoot) {
  for (const item of commentRoot.querySelectorAll('.CommentContent, .CommentItemV2-content, [class*="CommentContent"]')) {
    if (!visible(item)) continue;
    const val = text(item);
    if (!val) continue;
    comments.push({
      text: val.slice(0, 100000),
      text_truncated: val.length > 100000,
      comment_id: null,
      parent_comment_id: null,
      source_time_display: null,
      source_created_at: null,
    });
    if (comments.length >= 50) break;
  }
}
return {
  url: `${here.origin}${here.pathname}`,
  title: titleText || null,
  body: bodyText.slice(0, 100000),
  body_clipped: false,
  body_limit: bodyText.length > 100000,
  source_time_display: text(postTime) || null,
  source_created_at: null,
  comments,
  comment_container_present: !!commentRoot,
  comment_empty_explicit: false,
};
})()"""

ZHIHU_SEARCH_DOM_SCRIPT = r"""(() => {
""" + _ZHIHU_HELPERS + r"""
if (here.pathname.replace(/\/$/,'') !== '/search') return {error:'invalid_target_url'};
const notes = [], seen = new Set();
const selectors = '.SearchResult-Card h2.ContentItem-title a[href], .ContentItem h2.ContentItem-title a[href], .SearchResult-Card a[href*="/question/"], .SearchResult-Card a[href*="zhuanlan.zhihu.com/p/"]';
for (const anchor of document.querySelectorAll(selectors)) {
  if (!visible(anchor)) continue;
  try {
    const raw = anchor.getAttribute('href') || '';
    const url = new URL(raw.startsWith('//') ? `https:${raw}` : raw, here);
    if (!allowed(url)) continue;
    const match = /^\/(?:question\/[0-9]+\/answer\/([0-9]+)|question\/([0-9]+)|p\/([0-9]+))\/?$/.exec(url.pathname);
    if (!match) continue;
    const key = `${url.hostname}${url.pathname.replace(/\/$/,'')}`;
    if (seen.has(key)) continue;
    seen.add(key);
    notes.push({url: `${url.origin}${url.pathname.replace(/\/$/,'')}`});
    if (notes.length >= 20) break;
  } catch (_) {}
}
if (!notes.length) return {error:'search_result_missing'};
return {notes};
})()"""

ZHIHU_NAVIGATION_DOM_SCRIPT = r"""(() => {
const here = new URL(location.href);
if (here.protocol !== 'https:' ||
  !['zhihu.com','www.zhihu.com','zhuanlan.zhihu.com'].includes(here.hostname) ||
  here.port || here.username || here.password || here.hash)
  return {error:'invalid_target_url'};
return {url:here.href,ready_state:document.readyState};
})()"""

_DOUYIN_HELPERS = r"""
const visible = el => !!el && el.getClientRects().length > 0 &&
  getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
const first = (root, selectors) => Array.from(root.querySelectorAll(selectors)).find(visible);
const text = el => visible(el) ? el.innerText.trim() : '';
const allowed = url => url.protocol === 'https:' &&
  ['douyin.com','www.douyin.com'].includes(url.hostname) &&
  !url.port && !url.username && !url.password && !url.hash;
const here = new URL(location.href);
if (!allowed(here)) return {error:'invalid_target_url'};
if (first(document, '.captcha_verify_container, #captcha_container, .secsdk-captcha-drag-wrapper'))
  return {error:'access_gate'};
"""

DOUYIN_NOTE_DOM_SCRIPT = r"""(() => {
""" + _DOUYIN_HELPERS + r"""
if (!/^\/(?:video|note)\/[0-9]{10,25}\/?$/.test(here.pathname))
  return {error:'invalid_target_url'};
const descEl = first(document, '[data-e2e="detail-video-info"] h1, [data-e2e="video-desc"], [data-e2e="note-desc"], [data-e2e="detail-video-info"] [class*="desc"], [data-e2e="detail-video-info"] [class*="title"], .video-info-detail h1, main h1, h1');
let bodyText = text(descEl);
if (!bodyText) {
  const infoBox = first(document, '[data-e2e="detail-video-info"], .video-info-detail');
  bodyText = text(infoBox);
}
if (!bodyText) return {error:'body_missing'};
const postTime = first(document, '[data-e2e="detail-video-publish-time"], [class*="publish-time"], [class*="video-create-time"]');
const comments = [];
const seenComments = new Set();
const commentRoot = first(document, '[data-e2e="comment-list"], .comment-mainContent');
if (commentRoot) {
  const isMetaNoise = s => !s || /^\d+(?:\.\d+)?[万wWkK]?$/.test(s) || /^(?:回复|展开|收起|赞|分享|作者|置顶|刚刚|\d+(?:秒|分钟|小时|天|周|月|年)前|IP属地)/.test(s);
  for (const item of commentRoot.querySelectorAll('[data-e2e="comment-item"]')) {
    if (!visible(item) || (item.parentElement && item.parentElement.closest('[data-e2e="comment-item"]'))) continue;
    let val = text(first(item, '[data-e2e="comment-text"], [class*="comment-text"], [class*="CommentText"]'));
    if (isMetaNoise(val)) {
      const candidates = Array.from(item.querySelectorAll('span, p'))
        .filter(el => visible(el) && !el.closest('button, a, [class*="digg"], [class*="like"], [class*="action"], [class*="footer"], [class*="user"], [class*="author"], [class*="header"], [class*="time"]'))
        .map(el => (el.innerText || '').trim())
        .filter(s => !isMetaNoise(s));
      val = candidates.sort((a, b) => b.length - a.length)[0] || '';
    }
    if (isMetaNoise(val) || seenComments.has(val)) continue;
    seenComments.add(val);
    comments.push({
      text: val.slice(0, 100000),
      text_truncated: val.length > 100000,
      comment_id: null,
      parent_comment_id: null,
      source_time_display: null,
      source_created_at: null,
    });
    if (comments.length >= 50) break;
  }
}
return {
  url: `${here.origin}${here.pathname}`,
  title: bodyText.split('\n')[0].slice(0, 120) || null,
  body: bodyText.slice(0, 100000),
  body_clipped: false,
  body_limit: bodyText.length > 100000,
  source_time_display: text(postTime) || null,
  source_created_at: null,
  comments,
  comment_container_present: !!commentRoot,
  comment_empty_explicit: false,
};
})()"""

DOUYIN_SEARCH_DOM_SCRIPT = r"""(() => {
""" + _DOUYIN_HELPERS + r"""
if (!/^\/search\//.test(here.pathname)) return {error:'invalid_target_url'};
const notes = [], seen = new Set();
const addId = (kind, id) => {
  if (!id || seen.has(id) || notes.length >= 20) return;
  seen.add(id);
  notes.push({url: `https://www.douyin.com/${kind}/${id}`});
};
const isShown = el => !!el && (visible(el) || el.offsetParent !== null || !!el.querySelector('img, video, div'));
for (const anchor of document.querySelectorAll('a[href*="/video/"], a[href*="/note/"], a[href*="modal_id="]')) {
  if (!isShown(anchor)) continue;
  try {
    const raw = anchor.getAttribute('href') || '';
    const url = new URL(raw.startsWith('//') ? `https:${raw}` : raw, here);
    if (!allowed(url)) continue;
    const match = /^\/(video|note)\/([0-9]{10,25})\/?$/.exec(url.pathname);
    if (match) { addId(match[1], match[2]); continue; }
    const mid = url.searchParams.get('modal_id');
    if (mid && /^[0-9]{10,25}$/.test(mid)) addId('video', mid);
  } catch (_) {}
}
if (!notes.length) {
  for (const el of document.querySelectorAll('[id*="waterfall_item_"], [data-aweme-id], [data-e2e="scroll-list"] [id], #search-content-area [id]')) {
    if (!isShown(el)) continue;
    const raw = el.getAttribute('data-aweme-id') || el.getAttribute('id') || '';
    const m = /([0-9]{15,22})/.exec(raw);
    if (m) addId('video', m[1]);
  }
}
if (!notes.length) return {error:'search_result_missing'};
return {notes};
})()"""

DOUYIN_NAVIGATION_DOM_SCRIPT = r"""(() => {
const here = new URL(location.href);
if (here.protocol !== 'https:' ||
  !['douyin.com','www.douyin.com'].includes(here.hostname) ||
  here.port || here.username || here.password || here.hash)
  return {error:'invalid_target_url'};
return {url:here.href,ready_state:document.readyState};
})()"""

PLATFORM_SCRIPTS = {
    "xiaohongshu": {
        "note": NOTE_DOM_SCRIPT,
        "search": SEARCH_DOM_SCRIPT,
        "navigation": NAVIGATION_DOM_SCRIPT,
    },
    "bilibili": {
        "note": BILI_NOTE_DOM_SCRIPT,
        "search": BILI_SEARCH_DOM_SCRIPT,
        "navigation": BILI_NAVIGATION_DOM_SCRIPT,
    },
    "weibo": {
        "note": WEIBO_NOTE_DOM_SCRIPT,
        "search": WEIBO_SEARCH_DOM_SCRIPT,
        "navigation": WEIBO_NAVIGATION_DOM_SCRIPT,
    },
    "zhihu": {
        "note": ZHIHU_NOTE_DOM_SCRIPT,
        "search": ZHIHU_SEARCH_DOM_SCRIPT,
        "navigation": ZHIHU_NAVIGATION_DOM_SCRIPT,
    },
    "douyin": {
        "note": DOUYIN_NOTE_DOM_SCRIPT,
        "search": DOUYIN_SEARCH_DOM_SCRIPT,
        "navigation": DOUYIN_NAVIGATION_DOM_SCRIPT,
    },
}

ALLOWED_DOM_SCRIPTS = {
    script
    for scripts in PLATFORM_SCRIPTS.values()
    for script in scripts.values()
}


class DOMTransport:
    """Minimal CDP wire client: no auto-attach, Network or browser close command."""

    BROWSER_METHODS = {"Target.getTargets", "Target.getTargetInfo", "Target.attachToTarget", "Target.detachFromTarget"}
    SESSION_METHODS = {"Page.navigate", "Runtime.evaluate"}

    def __init__(self, socket):
        self.socket = socket
        self.pending = {}
        self.sessions = set()
        self.sequence = 0
        self.closed = False
        self.reader = asyncio.create_task(self._read())

    @classmethod
    async def connect(cls, endpoint: str):
        try:
            from websockets.asyncio.client import connect
        except ImportError as exc:
            raise ChromeError("dependency_unavailable", "请安装项目可选依赖 signal-miner[browser] 后重试。", 503) from exc
        try:
            socket = await connect(endpoint, open_timeout=45, proxy=None, max_size=4_000_000,
                                   additional_headers={"User-Agent": "MINING Existing Chrome DOM Collector"})
        except TimeoutError as exc:
            raise ChromeError("authorization_or_connection_timeout", "等待 Chrome 允许连接或建立传输超时；尚未连接。") from exc
        except Exception as exc:
            # Endpoint / handshake details may contain local or sensitive data.
            raise ChromeError("chrome_connection_unavailable", "Chrome 当前会话连接未建立，可能未允许连接或发现信息已失效。") from exc
        return cls(socket)

    async def _read(self):
        try:
            async for packet in self.socket:
                data = json.loads(packet)
                future = self.pending.get(data.get("id"))
                if future and not future.done():
                    if "error" in data:
                        message = str(data["error"].get("message", "")).lower()
                        context_changed = any(marker in message for marker in (
                            "execution context was destroyed", "cannot find default execution context",
                            "cannot find context with specified id",
                        ))
                        error = ChromeError("execution_context_changed", "所选页面正在切换执行上下文。") if context_changed else ChromeError("cdp_command_failed", "Chrome 未完成所选页面操作；标签可能已关闭或不可用。")
                        future.set_exception(error)
                    else:
                        future.set_result(data.get("result", {}))
        except (Exception, asyncio.CancelledError):
            pass
        finally:
            self.closed = True
            for future in tuple(self.pending.values()):
                if not future.done():
                    future.set_exception(ChromeError("transport_disconnected", "Chrome 连接已断开。"))

    async def command(self, method, params=None, *, session_id=None):
        params = params or {}
        allowed = self.SESSION_METHODS if session_id else self.BROWSER_METHODS
        if method not in allowed or (session_id and session_id not in self.sessions):
            raise ChromeError("forbidden_cdp_command", "采集器拒绝超出限定范围的浏览器操作。")
        if method == "Runtime.evaluate" and params.get("expression") not in ALLOWED_DOM_SCRIPTS:
            raise ChromeError("forbidden_script", "采集器仅允许固定正文选择器。")
        if method == "Page.navigate":
            validate_url(params.get("url"))
        if self.closed:
            raise ChromeError("transport_disconnected", "Chrome 连接已断开。")
        self.sequence += 1
        packet = {"id": self.sequence, "method": method, "params": params}
        if session_id:
            packet["sessionId"] = session_id
        future = asyncio.get_running_loop().create_future()
        self.pending[self.sequence] = future
        try:
            try:
                await self.socket.send(json.dumps(packet))
            except Exception as exc:
                self.closed = True
                raise ChromeError("transport_disconnected", "Chrome 连接在操作期间断开；本次操作未完成。") from exc
            result = await asyncio.wait_for(future, timeout=12)
            if method == "Target.attachToTarget":
                if not isinstance(result.get("sessionId"), str) or not result["sessionId"]:
                    raise ChromeError("invalid_cdp_response", "Chrome 未返回有效的所选标签会话。")
                self.sessions.add(result["sessionId"])
            if method == "Target.detachFromTarget":
                self.sessions.discard(params.get("sessionId"))
            return result
        except TimeoutError as exc:
            raise ChromeError("page_operation_timeout", "等待所选页面操作超时。") from exc
        finally:
            self.pending.pop(packet["id"], None)

    async def stop(self):
        """Disconnect only the owned wire. Borrowed browser targets stay open."""
        await self.socket.close()
        self.reader.cancel()
        with suppress(asyncio.CancelledError):
            await self.reader


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _absolute_time(value) -> str | None:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d(?:\.\d+)?)?(?:Z|[+-]\d\d:\d\d)", value
    ):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def adapt_dom(record: dict, task: dict) -> dict:
    """Whitelist public DOM values and retain unknown IDs/times as null."""
    platform = task.get("platform") or detect_platform(record.get("url")) or "xiaohongshu"
    pipeline_profile = task.get("pipeline_profile") or "product_feedback"
    cfg = PLATFORM_CONFIGS[platform]
    source_url = validate_url(record.get("url"), note=True, platform=platform)
    post_id = _extract_detail_id(platform, urlsplit(source_url).path)
    body = record.get("body")
    if not isinstance(body, str) or not body.strip():
        raise ChromeError("body_missing", "未找到已加载的正文内容；标题不能代替正文。")
    captured = _now()
    has_subtitles = bool(record.get("has_subtitles"))
    subtitle_lang = record.get("subtitle_language") or "CC/AI"
    incomplete = [
        f"已包含视频字幕逐字稿（{subtitle_lang}）；不包含无字幕画面文字。"
        if has_subtitles
        else "只覆盖本次已加载的 DOM；不包含图片文字、视频口播或未加载评论。"
    ]
    if record.get("body_clipped"):
        incomplete.append("正文容器存在折叠或裁剪，当前材料为片段。")
    if record.get("body_limit") or len(body) > MAX_TEXT:
        incomplete.append("正文超过 100000 字符安全上限，当前材料为片段。")
    if not record.get("comment_container_present") and task["max_comments"]:
        incomplete.append("未找到已加载评论容器，本次未覆盖评论。")
    elif task["max_comments"] and not record.get("comments") and not record.get("comment_empty_explicit"):
        incomplete.append("等待已加载评论达到上限，未见评论或明确空状态；本次评论覆盖未知，不能认定真实零评论。")
    coverage = f"1 篇已加载正文内容，最多 {task['max_comments']} 条已加载顶层评论；不遍历或加载更多。"
    cid_pattern = cfg["comment_id_pattern"]

    def make(text, *, comment=None):
        is_comment = comment is not None
        stamp = comment if is_comment else record
        cid = stamp.get("comment_id") if is_comment else post_id
        if is_comment and not (isinstance(cid, str) and cid_pattern.fullmatch(cid)):
            cid = None
        parent_cid = stamp.get("parent_comment_id") if is_comment else None
        if not isinstance(parent_cid, str) or not cid_pattern.fullmatch(parent_cid):
            parent_cid = None
        return {
            "source_type": platform, "platform": platform,
            "pipeline_profile": pipeline_profile, "capture_method": "manual_browser" if platform == "douyin" else "crawler",
            "capture_version": CAPTURE_VERSION, "text": text[:MAX_TEXT],
            "subject": None if is_comment or not isinstance(record.get("title"), str) else record["title"][:5000],
            "external_url": source_url, "external_id": cid,
            "entity_type": "comment" if is_comment else "post",
            "parent_id": post_id if is_comment else None,
            "parent_url": source_url if is_comment else None,
            "parent_comment_id": parent_cid, "parent_comment_url": None,
            "locator_level": "parent_page" if is_comment else "item",
            "content_nature": "original_text", "text_origin": "body",
            "source_created_at": _absolute_time(stamp.get("source_created_at")),
            "source_updated_at": None, "source_captured_at": captured,
            "coverage_scope": coverage,
            "source_note": "项目自有固定选择器读取当前 Chrome 已加载公开 DOM；非 MediaCrawler 导出。作者未知；来源真实性未认证。" + ("评论仅定位父页，未知评论ID和楼层保持空值。" if is_comment else "") + " ".join(incomplete),
            "raw_payload": {
                "acquisition_kind": "existing_chrome_loaded_dom",
                "capture_version": CAPTURE_VERSION, "selector_version": cfg["selector_version"],
                "source_url": source_url, "object_id": cid,
                "source_time_display": stamp.get("source_time_display"),
                "body_fragment": bool(record.get("body_clipped") or record.get("body_limit") or len(body) > MAX_TEXT),
                "has_subtitles": has_subtitles,
                "subtitle_language": record.get("subtitle_language"),
                "coverage_scope": coverage, "incomplete_reasons": list(incomplete),
                "task": {key: task[key] for key in ("id", "mode", "max_posts", "max_comments")},
            },
        }

    items = [make(body)]
    comments = record.get("comments") if isinstance(record.get("comments"), list) else []
    for comment in comments:
        if len(items) > task["max_comments"]:
            break
        if not isinstance(comment, dict) or not isinstance(comment.get("text"), str) or not comment["text"].strip():
            continue
        # A directly evidenced reply is outside the first version's top-level scope.
        if comment.get("parent_comment_id"):
            continue
        item = make(comment["text"], comment=comment)
        if comment.get("text_truncated") or len(comment["text"]) > MAX_TEXT:
            item["raw_payload"]["incomplete_reasons"].append("该评论超过 100000 字符安全上限，当前为片段。")
        items.append(item)
    return {"items": items, "summary": {
        "post_count": 1, "comment_count": len(items) - 1, "item_count": len(items),
        "comment_coverage": "not_requested" if not task["max_comments"] else "loaded_comments" if len(items) > 1 else "explicit_empty" if record.get("comment_empty_explicit") else "unknown",
        "coverage": coverage, "incomplete_reasons": incomplete,
        "capture_version": CAPTURE_VERSION, "source_captured_at": captured,
    }}


class ExistingChromeCollector:
    """One persistent connection and at most one bounded, cancellable task."""

    def __init__(self, *, transport_factory=None, endpoint_reader: Callable | None = None,
                 task_timeout: float = DEFAULT_TASK_TIMEOUT, page_wait: float = 20, comment_wait: float = 3):
        self._transport_factory = transport_factory or DOMTransport.connect
        self._endpoint_reader = endpoint_reader or read_endpoint
        self._task_timeout, self._page_wait = min(task_timeout, DEFAULT_TASK_TIMEOUT), page_wait
        self._detach_budget = min(0.5, self._task_timeout / 10)
        self._comment_wait = min(comment_wait, 5)
        self._transport = None
        self._connection_job = None
        self._task_job = None
        self._batch_job = None
        self._tabs = {}
        self._tab_meta = {}
        self._tasks = {}
        self._batches = {}
        self._status = "disconnected"
        self._message = "尚未连接当前 Chrome。"
        self._active_task = None
        self._active_batch = None
        self._lock = asyncio.Lock()

    def status(self) -> dict:
        # Pure local state: no discovery, port probing, browser access or prompt.
        state, message = self._status, self._message
        if self._transport is not None and self._transport.closed:
            state, message = "disconnected", "Chrome 传输已断开；可重新请求连接。"
        return {"status": state, "message": message, "active_task": self._active_task,
                "active_batch": self._active_batch,
                "capabilities": {"platform": "xiaohongshu", "platforms": list(SUPPORTED_PLATFORMS), "modes": ["current", "search", "detail"],
                                 "max_posts": MAX_POSTS, "max_comments": MAX_COMMENTS, "task_timeout_seconds": DEFAULT_TASK_TIMEOUT,
                                 "batch_concurrency": 3,
                                 "capture_version": CAPTURE_VERSION, "dom_scope": "loaded_public_dom_only",
                                 "browser_launch": False, "automatic_ingest": False}}

    async def connect(self) -> dict:
        async with self._lock:
            if self.status()["status"] in {"connected", "connecting"}:
                return self.status()
            if self._transport is not None:
                await self._transport.stop()
                self._transport = None
            self._status, self._message = "connecting", "正在请求连接已运行的 Chrome；请留意 Chrome 的本次授权提示。"
            self._connection_job = asyncio.create_task(self._connect())
            return self.status()

    async def _connect(self):
        try:
            if self._transport_factory == DOMTransport.connect and importlib.util.find_spec("websockets") is None:
                raise ChromeError("dependency_unavailable", "请安装项目可选依赖 signal-miner[browser]。", 503)
            endpoint = await asyncio.to_thread(self._endpoint_reader)
            self._transport = await self._transport_factory(endpoint)
            self._status, self._message = "connected", "已连接当前 Chrome；仅读取您选中的国内小红书、B站、微博、知乎或抖音页面。"
        except ChromeError as exc:
            auth = {"remote_debugging_not_enabled_or_chrome_not_running", "authorization_or_connection_timeout", "connection_not_authorized"}
            self._status = "authorization_required" if exc.code in auth else "unavailable"
            self._message = exc.message
        except asyncio.CancelledError:
            raise
        except Exception:
            self._status, self._message = "unavailable", "Chrome 连接发生未知错误；未启动浏览器或重试登录。"

    async def disconnect(self) -> dict:
        async with self._lock:
            if self._connection_job and not self._connection_job.done():
                self._connection_job.cancel()
                with suppress(asyncio.CancelledError):
                    await self._connection_job
            if self._active_task:
                await self.stop(self._active_task)
            if self._active_batch:
                await self.stop_batch(self._active_batch)
            if self._transport is not None:
                with suppress(Exception):
                    await self._transport.stop()
            self._transport, self._tabs, self._tab_meta = None, {}, {}
            self._status, self._message = "disconnected", "已断开采集连接，Chrome 和用户标签保持打开。"
            return self.status()

    async def close(self):
        await self.disconnect()

    def _connected(self):
        if self.status()["status"] != "connected":
            raise ChromeError("not_connected", "请先连接当前 Chrome。")
        return self._transport

    async def tabs(self) -> dict:
        transport = self._connected()
        response = await transport.command("Target.getTargets")
        result = []
        live = {}
        live_meta = {}
        prior = {target: temp_id for temp_id, target in self._tabs.items()}
        for info in response.get("targetInfos", []):
            if info.get("type") != "page" or not info.get("targetId"):
                continue
            try:
                url = validate_url(info.get("url"))
            except ChromeError:
                continue
            platform = detect_platform(url) or "xiaohongshu"
            temp_id = prior.get(info["targetId"]) or uuid4().hex
            title = str(info.get("title", ""))[:500]
            live[temp_id] = info["targetId"]
            live_meta[temp_id] = {"target_id": info["targetId"], "platform": platform, "url": url, "title": title}
            result.append({"id": temp_id, "title": title, "url": url, "platform": platform})
        self._tabs = live
        self._tab_meta = live_meta
        return {"tabs": result}

    async def start(self, payload: dict) -> dict:
        self._connected()
        if self._active_task or self._active_batch:
            raise ChromeError("task_already_running", "已有一个当前 Chrome 采集任务，请先等待或停止。")
        if payload["tab_id"] not in self._tabs:
            raise ChromeError("tab_not_found", "所选标签已失效，请刷新目标标签。", 404)
        identifier = uuid4().hex
        task = {**payload, "id": identifier, "status": "running", "message": "正在读取所选页面已加载的正文与评论。",
                "phase": "queued", "progress": {"current": 0, "total": payload["max_posts"], "percent": 0, "label": "已提交采集任务"},
                "error": None, "created_at": _now(), "finished_at": None, "summary": None}
        # Only the last 30 task batches are retained in this connection's memory.
        for old in list(self._tasks)[:-29]:
            self._tasks.pop(old)
        self._tasks[identifier] = task
        self._active_task = identifier
        self._task_job = asyncio.create_task(self._run(task, self._tabs[payload["tab_id"]]))
        return self.public(task)

    @staticmethod
    def public(task) -> dict:
        return {key: task.get(key) for key in ("id", "status", "phase", "progress", "mode", "tab_id", "message", "error", "created_at", "finished_at", "summary")} | {"terminal": task["status"] in TERMINAL}

    def get(self, identifier: str) -> dict:
        if identifier not in self._tasks:
            raise ChromeError("task_not_found", "当前会话中没有该采集任务。", 404)
        return self._tasks[identifier]

    async def stop(self, identifier: str) -> dict:
        task = self.get(identifier)
        if task["status"] == "running" and self._task_job:
            self._task_job.cancel()
            with suppress(asyncio.CancelledError):
                await self._task_job
            # Handles cancellation before the coroutine's first instruction.
            if task["status"] == "running":
                task.update(status="cancelled", message="采集已停止，未生成可导入批次。", finished_at=_now())
                self._active_task = None
        return self.public(task)

    def results(self, identifier: str) -> dict:
        task = self.get(identifier)
        if task["status"] != "completed":
            raise ChromeError("results_not_ready", "只有成功完成的任务才有可预览原文批次。")
        return task["result"]

    async def _run(self, task, target):
        try:
            result = await asyncio.wait_for(self._collect(task, target), self._task_timeout - self._detach_budget)
            task.update(status="completed", result=result, summary=result["summary"], message="原文材料已生成，可预览并选择导入。")
        except asyncio.CancelledError:
            task.update(status="cancelled", message="采集已停止，未生成可导入批次。")
        except TimeoutError:
            task.update(status="failed", message="采集超过总时限，未生成批次。", error={"code": "task_timeout", "message": "采集超过总时限，未生成批次。"})
        except ChromeError as exc:
            task.update(status="failed", message=exc.message, error={"code": exc.code, "message": exc.message, "phase": task["phase"]})
        except Exception:
            task.update(status="failed", message="采集发生未知错误，未生成批次。", error={"code": "unknown_collection_error", "message": "采集发生未知错误，未生成批次。"})
        finally:
            task["finished_at"] = _now()
            self._active_task = None

    async def _target_url(self, target, *, note=False, allow_pending_empty=False, platform: str | None = None):
        try:
            info = await self._connected().command("Target.getTargetInfo", {"targetId": target})
        except ChromeError as exc:
            if exc.code == "cdp_command_failed":
                raise ChromeError("tab_closed", "所选 Chrome 标签已关闭或不可访问。") from exc
            raise
        raw_url = info.get("targetInfo", {}).get("url")
        if allow_pending_empty and raw_url == "":
            return ""
        return validate_url(raw_url, note=note, platform=platform)

    async def _navigate(self, transport, target, session, url, *, platform: str | None = None):
        source_url = await self._target_url(target)
        destination = validate_url(url, platform=platform)
        resolved_platform = platform or detect_platform(destination) or "xiaohongshu"
        result = await transport.command("Page.navigate", {"url": destination}, session_id=session)
        if result.get("errorText"):
            raise ChromeError("navigation_failed", "Chrome 未能打开所选页面。")
        try:
            await asyncio.wait_for(
                self._navigation_handoff(transport, target, session, source_url, destination, platform=resolved_platform),
                self._page_wait,
            )
        except TimeoutError as exc:
            raise ChromeError("navigation_document_timeout", "等待目标文档切换超时；未读取旧页面内容。") from exc

    @staticmethod
    def _requested_document(current, destination, *, platform: str = "xiaohongshu"):
        parsed, wanted = urlsplit(current), urlsplit(destination)
        cfg = PLATFORM_CONFIGS[platform]
        note_id = _extract_detail_id(platform, wanted.path)
        if note_id:
            actual_id = _extract_detail_id(platform, parsed.path)
            return bool(actual_id and actual_id.lower() == note_id.lower())
        if unquote(parsed.path.rstrip("/")) != unquote(wanted.path.rstrip("/")):
            return False
        actual_query, expected_query = parse_qs(parsed.query), parse_qs(wanted.query)
        return all(actual_query.get(key) == expected_query.get(key) for key in cfg["search_query_keys"])

    @staticmethod
    def _same_source_document(current, source):
        parsed, prior = urlsplit(current), urlsplit(source)
        return (parsed.hostname, parsed.path.rstrip("/"), parsed.query) == (prior.hostname, prior.path.rstrip("/"), prior.query)

    async def _navigation_handoff(self, transport, target, session, source, destination, *, platform: str = "xiaohongshu"):
        nav_script = PLATFORM_SCRIPTS[platform]["navigation"]
        while True:
            # The old source is allowed only during this self-initiated navigation.
            # Chromium may also briefly report an empty targetInfo.url at commit.
            # A different domestic page, international site or error URL is fatal.
            target_url = await self._target_url(target, allow_pending_empty=True)
            target_matches = bool(target_url) and self._requested_document(target_url, destination, platform=platform)
            if target_url and not target_matches and not self._same_source_document(target_url, source):
                raise ChromeError("target_changed", "导航期间所选标签切换到了另一页面，采集停止。")
            try:
                output = await transport.command("Runtime.evaluate", {
                    "expression": nav_script, "returnByValue": True, "awaitPromise": False,
                }, session_id=session)
            except ChromeError as exc:
                if exc.code != "execution_context_changed":
                    raise
                await asyncio.sleep(0.05)
                continue
            if output.get("exceptionDetails"):
                raise ChromeError("navigation_metadata_failed", "无法核对目标文档切换状态。")
            meta = output.get("result", {}).get("value")
            if not isinstance(meta, dict) or meta.get("error"):
                raise ChromeError("invalid_target_url", "所选标签的当前文档已跳转到不支持的地址。")
            document_url = validate_url(meta.get("url"), platform=platform)
            document_matches = self._requested_document(document_url, destination, platform=platform)
            if not document_matches and not self._same_source_document(document_url, source):
                raise ChromeError("target_changed", "导航期间文档切换到了另一页面，采集停止。")
            if target_matches and document_matches and meta.get("ready_state") in {"interactive", "complete"}:
                return
            await asyncio.sleep(0.05)

    async def _dom(self, transport, target, session, *, search=False, want_comments=False, platform: str = "xiaohongshu"):
        deadline = asyncio.get_running_loop().time() + self._page_wait
        comment_deadline = None
        last_error = "content_missing"
        scripts = PLATFORM_SCRIPTS[platform]
        while True:
            await self._target_url(target, note=not search, platform=platform)
            output = await transport.command("Runtime.evaluate", {
                "expression": scripts["search"] if search else scripts["note"],
                "returnByValue": True, "awaitPromise": platform == "bilibili" and not search,
            }, session_id=session)
            if output.get("exceptionDetails"):
                raise ChromeError("dom_read_failed", "固定正文选择器未能读取所选页面。")
            record = output.get("result", {}).get("value")
            if not isinstance(record, dict):
                raise ChromeError("dom_read_failed", "固定正文选择器未返回可用材料。")
            last_error = record.get("error")
            if not last_error:
                if not search and want_comments and not record.get("comments") and not record.get("comment_empty_explicit"):
                    if comment_deadline is None:
                        comment_deadline = asyncio.get_running_loop().time() + self._comment_wait
                    if asyncio.get_running_loop().time() < comment_deadline:
                        await asyncio.sleep(0.25)
                        continue
                await self._target_url(target, note=not search, platform=platform)
                if not search:
                    validate_url(record.get("url"), note=True, platform=platform)
                return record
            if last_error in {"access_gate", "invalid_target_url"}:
                message = "所选页面出现登录或验证遮罩；本次未读取材料，未重试登录。" if last_error == "access_gate" else "所选页面已跳转到不支持的地址，采集停止。"
                raise ChromeError(last_error, message)
            if asyncio.get_running_loop().time() >= deadline:
                raise ChromeError(last_error, "未在限定时间内找到已加载的正文或实际搜索结果；未用标题补正文。")
            await asyncio.sleep(0.25)

    @staticmethod
    def _resolve_search_candidates(found: dict, search_url: str, max_posts: int, *, platform: str = "xiaohongshu") -> list[tuple[str, str | None]]:
        entries = found.get("notes")
        if not isinstance(entries, list):
            entries = [found] if (found.get("url") or found.get("search_result_href")) else []
        candidates = []
        for entry in entries[:max_posts]:
            if not isinstance(entry, dict):
                continue
            actual = entry.get("url")
            original_href = actual
            if not actual and entry.get("search_result_href"):
                href = entry["search_result_href"]
                original_href = href
                parsed = urlsplit(href)
                if parsed.fragment or parsed.hostname not in HOSTS or not re.fullmatch(r"/search_result/[a-fA-F0-9]{24}/?", parsed.path):
                    raise ChromeError("invalid_search_result", "实际搜索结果链接超出支持范围。")
                actual = urlunsplit((parsed.scheme, parsed.netloc, "/explore/" + parsed.path.rstrip("/").split("/")[-1], parsed.query, ""))
                validate_url(actual, note=True, platform=platform)
            resolved = validate_url(urljoin(search_url, actual or ""), note=True, platform=platform)
            candidates.append((resolved, original_href))
        if not candidates:
            raise ChromeError("search_result_missing", f"未在当前搜索结果中找到可用的{PLATFORM_CONFIGS[platform]['label']}内容链接。")
        return candidates

    @staticmethod
    def _merge_note_batches(batches: list[dict], task: dict, *, skipped_empty: int = 0) -> dict:
        if len(batches) == 1 and not skipped_empty:
            return batches[0]
        items = [item for batch in batches for item in batch["items"]]
        posts = sum(batch["summary"]["post_count"] for batch in batches)
        comments = sum(batch["summary"]["comment_count"] for batch in batches)
        incomplete = []
        for batch in batches:
            for reason in batch["summary"]["incomplete_reasons"]:
                if reason not in incomplete:
                    incomplete.append(reason)
        if skipped_empty:
            incomplete.append(f"跳过 {skipped_empty} 篇无正文描述的搜索结果（如纯图/视频笔记）。")
        coverage = f"共 {posts} 篇已加载笔记描述正文（请求上限 {task['max_posts']} 篇），每篇最多 {task['max_comments']} 条已加载顶层评论；不遍历或加载更多。"
        coverages = {batch["summary"]["comment_coverage"] for batch in batches}
        comment_coverage = "not_requested" if not task["max_comments"] else "loaded_comments" if comments > 0 else "explicit_empty" if coverages == {"explicit_empty"} else "unknown"
        return {
            "items": items,
            "summary": {
                "post_count": posts,
                "comment_count": comments,
                "item_count": len(items),
                "comment_coverage": comment_coverage,
                "coverage": coverage,
                "incomplete_reasons": incomplete,
                "capture_version": CAPTURE_VERSION,
                "source_captured_at": batches[-1]["summary"]["source_captured_at"],
            },
        }

    @staticmethod
    def _set_progress(task, *, phase: str, current: int, total: int, percent: int, label: str):
        task["phase"] = phase
        task["progress"] = {"current": current, "total": total, "percent": max(0, min(100, percent)), "label": label}

    async def _collect(self, task, target):
        transport = self._connected()
        platform = task.get("platform")
        self._set_progress(task, phase="validate_source", current=0, total=task["max_posts"], percent=5, label="正在校验当前标签")
        initial_url = await self._target_url(target, note=task["mode"] == "current", platform=platform)
        if not platform:
            platform = detect_platform(task.get("url") or initial_url) or "xiaohongshu"
            task["platform"] = platform
        cfg = PLATFORM_CONFIGS[platform]
        attached = await transport.command("Target.attachToTarget", {"targetId": target, "flatten": True})
        session = attached["sessionId"]
        try:
            if task["mode"] == "search":
                self._set_progress(task, phase="navigate_search", current=0, total=task["max_posts"], percent=10, label=f"正在打开{cfg['label']}搜索结果页")
                search_url = cfg["search_url"](task["query"])
                await self._navigate(transport, target, session, search_url, platform=platform)
                self._set_progress(task, phase="read_search_results", current=0, total=task["max_posts"], percent=18, label="正在提取搜索结果列表")
                found = await self._dom(transport, target, session, search=True, platform=platform)
                candidates = self._resolve_search_candidates(found, search_url, task["max_posts"], platform=platform)
                total = len(candidates)
                batches, skipped_empty = [], 0
                for index, (resolved, original_href) in enumerate(candidates, start=1):
                    self._set_progress(task, phase="navigate_note", current=index - 1, total=total, percent=20 + int((index - 1) / total * 75), label=f"正在打开第 {index}/{total} 条内容")
                    await self._navigate(transport, target, session, resolved, platform=platform)
                    expected_note_id = _extract_detail_id(platform, urlsplit(resolved).path)
                    self._set_progress(task, phase="read_note", current=index - 1, total=total, percent=20 + int((index - 0.5) / total * 75), label=f"正在读取第 {index}/{total} 条内容与评论")
                    try:
                        record = await self._dom(transport, target, session, want_comments=task["max_comments"] > 0, platform=platform)
                        if _extract_detail_id(platform, urlsplit(record["url"]).path) != expected_note_id:
                            raise ChromeError("target_changed", "所选标签已切换到另一条内容，本次材料未生成。")
                        note_result = adapt_dom(record, task)
                    except ChromeError as exc:
                        if exc.code in {"body_missing", "content_missing"} and len(candidates) > 1:
                            skipped_empty += 1
                            continue
                        raise
                    if original_href:
                        for item in note_result["items"]:
                            item["raw_payload"]["search_result_href"] = original_href
                            item["raw_payload"]["navigated_note_url"] = record["url"]
                    batches.append(note_result)
                    self._set_progress(task, phase="read_note", current=index, total=total, percent=20 + int(index / total * 75), label=f"已完成第 {index}/{total} 条内容读取")
                if not batches:
                    raise ChromeError("body_missing", "搜索结果中的条目均未找到已加载的正文；标题不能代替正文。")
                result = self._merge_note_batches(batches, task, skipped_empty=skipped_empty)
                self._set_progress(task, phase="complete", current=total, total=total, percent=100, label="采集完成")
                return result

            if task["mode"] == "detail":
                self._set_progress(task, phase="navigate_note", current=0, total=1, percent=35, label="正在打开指定链接")
                await self._navigate(transport, target, session, validate_url(task["url"], note=True, platform=platform), platform=platform)
                expected_note_id = _extract_detail_id(platform, urlsplit(task["url"]).path)
            else:
                expected_note_id = _extract_detail_id(platform, urlsplit(initial_url).path)
            self._set_progress(task, phase="read_note", current=0, total=1, percent=70, label="正在读取正文与评论")
            record = await self._dom(transport, target, session, want_comments=task["max_comments"] > 0, platform=platform)
            if _extract_detail_id(platform, urlsplit(record["url"]).path) != expected_note_id:
                raise ChromeError("target_changed", "所选标签已切换到另一条内容，本次材料未生成。")
            result = adapt_dom(record, task)
            self._set_progress(task, phase="complete", current=1, total=1, percent=100, label="采集完成")
            return result
        finally:
            # Detach our session only, even on timeout/cancel. Do not close target.
            with suppress(Exception):
                await asyncio.wait_for(
                    transport.command("Target.detachFromTarget", {"sessionId": session}),
                    self._detach_budget,
                )

    # ------------------------------------------------------------------
    # Multi-platform concurrent batch collection
    # ------------------------------------------------------------------

    async def start_batch(self, payload: dict) -> dict:
        self._connected()
        if self._active_task or self._active_batch:
            raise ChromeError("task_already_running", "已有一个当前 Chrome 采集任务，请先等待或停止。")
        tab_ids = list(dict.fromkeys(payload.get("tab_ids") or []))
        if not tab_ids:
            raise ChromeError("tab_not_found", "请至少选择一个平台标签。", 422)
        missing = [tid for tid in tab_ids if tid not in self._tabs]
        if missing:
            raise ChromeError("tab_not_found", "所选标签中有已失效的页面，请刷新目标标签后重试。", 404)

        batch_id = uuid4().hex
        mode = payload.get("mode", "search")
        max_posts = int(payload.get("max_posts", 5)) if mode == "search" else 1
        max_comments = int(payload.get("max_comments", 10))
        subtasks = []
        for tid in tab_ids:
            meta = self._tab_meta.get(tid, {})
            platform = meta.get("platform") or "xiaohongshu"
            label = PLATFORM_CONFIGS.get(platform, {}).get("label", platform)
            subtasks.append({
                "id": uuid4().hex,
                "tab_id": tid,
                "target_id": self._tabs[tid],
                "platform": platform,
                "platform_label": label,
                "title": meta.get("title", ""),
                "mode": mode,
                "query": payload.get("query", ""),
                "url": "",
                "max_posts": max_posts,
                "max_comments": max_comments,
                "pipeline_profile": payload.get("pipeline_profile") or "product_feedback",
                "status": "queued",
                "phase": "queued",
                "progress": {"current": 0, "total": max_posts, "percent": 0, "label": f"{label}：排队中"},
                "message": "等待开始采集",
                "error": None,
                "summary": None,
                "items": [],
                "created_at": _now(),
                "finished_at": None,
            })

        batch = {
            "id": batch_id,
            "status": "running",
            "mode": mode,
            "query": payload.get("query", ""),
            "max_posts": max_posts,
            "max_comments": max_comments,
            "pipeline_profile": payload.get("pipeline_profile") or "product_feedback",
            "concurrency": max(1, min(3, int(payload.get("concurrency", 3)))),
            "created_at": _now(),
            "finished_at": None,
            "message": f"正在并发采集 {len(subtasks)} 个平台标签…",
            "subtasks": subtasks,
            "summary": None,
            "result": None,
        }
        for old in list(self._batches)[:-19]:
            self._batches.pop(old)
        self._batches[batch_id] = batch
        self._active_batch = batch_id
        self._batch_job = asyncio.create_task(self._run_batch(batch))
        return self.public_batch(batch)

    def get_batch(self, batch_id: str) -> dict:
        if batch_id not in self._batches:
            raise ChromeError("task_not_found", "当前会话中没有该多平台采集批次。", 404)
        return self._batches[batch_id]

    @staticmethod
    def _rebuild_batch_result(batch: dict) -> None:
        all_items: list[dict] = []
        by_platform: dict[str, dict] = {}
        completed_tabs = 0
        failed_tabs = 0
        total_posts = 0
        total_comments = 0
        for st in batch["subtasks"]:
            p = st["platform"]
            st_items = st.get("items") or []
            if st["status"] == "completed":
                completed_tabs += 1
                all_items.extend(st_items)
                p_posts = sum(1 for it in st_items if it.get("entity_type") == "post")
                p_comments = len(st_items) - p_posts
                total_posts += p_posts
                total_comments += p_comments
            elif st["status"] == "failed":
                failed_tabs += 1
            entry = by_platform.setdefault(
                p,
                {
                    "platform": p,
                    "label": st["platform_label"],
                    "status": st["status"],
                    "post_count": 0,
                    "comment_count": 0,
                    "item_count": 0,
                    "error": st["error"],
                },
            )
            if st["status"] == "completed":
                p_posts = sum(1 for it in st_items if it.get("entity_type") == "post")
                entry["post_count"] += p_posts
                entry["comment_count"] += len(st_items) - p_posts
                entry["item_count"] += len(st_items)
                entry["status"] = "completed"
                entry["error"] = None
            elif entry["status"] != "completed":
                entry["status"] = st["status"]
                entry["error"] = st["error"]

        summary = {
            "post_count": total_posts,
            "comment_count": total_comments,
            "item_count": len(all_items),
            "completed_tabs": completed_tabs,
            "failed_tabs": failed_tabs,
            "total_tabs": len(batch["subtasks"]),
            "by_platform": by_platform,
            "coverage": f"多平台共完成 {completed_tabs}/{len(batch['subtasks'])} 个标签，合计正文 {total_posts} 篇、评论 {total_comments} 条。",
            "capture_version": CAPTURE_VERSION,
            "source_captured_at": _now(),
        }
        batch["summary"] = summary
        batch["result"] = {"items": all_items, "summary": summary}

    @staticmethod
    def public_batch(batch: dict) -> dict:
        subtasks = batch["subtasks"]
        total_pct = int(sum((st.get("progress") or {}).get("percent", 0) for st in subtasks) / max(len(subtasks), 1))
        completed_n = sum(1 for st in subtasks if st["status"] == "completed")
        failed_n = sum(1 for st in subtasks if st["status"] == "failed")
        return {
            "id": batch["id"],
            "status": batch["status"],
            "terminal": batch["status"] in TERMINAL,
            "mode": batch["mode"],
            "query": batch["query"],
            "max_posts": batch["max_posts"],
            "max_comments": batch["max_comments"],
            "pipeline_profile": batch["pipeline_profile"],
            "message": batch["message"],
            "created_at": batch["created_at"],
            "finished_at": batch["finished_at"],
            "progress": {
                "current": completed_n + failed_n,
                "total": len(subtasks),
                "percent": 100 if batch["status"] == "completed" else total_pct,
                "label": batch["message"],
            },
            "summary": batch["summary"],
            "subtasks": [
                {
                    "id": st["id"],
                    "tab_id": st["tab_id"],
                    "platform": st["platform"],
                    "platform_label": st["platform_label"],
                    "title": st["title"],
                    "status": st["status"],
                    "phase": st["phase"],
                    "progress": st["progress"],
                    "message": st["message"],
                    "error": st["error"],
                    "summary": st["summary"],
                    "item_count": len(st.get("items") or []),
                }
                for st in subtasks
            ],
        }

    async def _run_single_subtask(self, st: dict, sem: asyncio.Semaphore) -> None:
        async with sem:
            st["status"] = "running"
            st["message"] = f"正在采集 {st['platform_label']}…"
            try:
                res = await asyncio.wait_for(
                    self._collect(st, st["target_id"]),
                    self._task_timeout - self._detach_budget,
                )
                st["items"] = res["items"]
                st["summary"] = res["summary"]
                st["status"] = "completed"
                st["error"] = None
                st["message"] = f"采集完成：{res['summary']['post_count']} 篇正文、{res['summary']['comment_count']} 条评论"
                self._set_progress(st, phase="complete", current=st["max_posts"], total=st["max_posts"], percent=100, label=st["message"])
            except asyncio.CancelledError:
                st["status"] = "cancelled"
                st["message"] = "已取消"
                raise
            except TimeoutError:
                st["status"] = "failed"
                st["error"] = {"code": "task_timeout", "message": f"{st['platform_label']} 采集超过总时限。"}
                st["message"] = st["error"]["message"]
            except ChromeError as exc:
                st["status"] = "failed"
                st["error"] = {"code": exc.code, "message": exc.message, "phase": st["phase"]}
                st["message"] = exc.message
            except Exception:
                st["status"] = "failed"
                st["error"] = {"code": "unknown_collection_error", "message": f"{st['platform_label']} 采集发生未知错误。"}
                st["message"] = st["error"]["message"]
            finally:
                st["finished_at"] = _now()

    async def _run_batch(self, batch: dict, target_subtasks: list[dict] | None = None) -> None:
        sem = asyncio.Semaphore(batch["concurrency"])
        to_run = target_subtasks if target_subtasks is not None else batch["subtasks"]
        try:
            await asyncio.gather(*(self._run_single_subtask(st, sem) for st in to_run))
            self._rebuild_batch_result(batch)
            completed_n = sum(1 for st in batch["subtasks"] if st["status"] == "completed")
            failed_n = sum(1 for st in batch["subtasks"] if st["status"] == "failed")
            if completed_n > 0:
                batch["status"] = "completed"
                batch["message"] = (
                    f"多平台采集完成：{completed_n} 个平台成功"
                    + (f"，{failed_n} 个平台失败（可单独重试）" if failed_n else "")
                    + f"，共 {batch['summary']['item_count']} 条原文材料。"
                )
            else:
                batch["status"] = "failed"
                batch["message"] = f"所选 {failed_n} 个平台均未采集到材料，请检查对应标签状态后重试。"
        except asyncio.CancelledError:
            batch["status"] = "cancelled"
            batch["message"] = "多平台采集已停止。"
        finally:
            batch["finished_at"] = _now()
            self._active_batch = None

    async def retry_batch_tab(self, batch_id: str, tab_id: str) -> dict:
        self._connected()
        if self._active_task or self._active_batch:
            raise ChromeError("task_already_running", "当前有正在运行的采集任务，请先等待完成。")
        batch = self.get_batch(batch_id)
        subtask = next((st for st in batch["subtasks"] if st["tab_id"] == tab_id), None)
        if subtask is None:
            raise ChromeError("tab_not_found", "该批次中未找到指定平台标签。", 404)
        if tab_id not in self._tabs:
            raise ChromeError("tab_not_found", "该标签页已关闭或失效，请先刷新目标标签。", 404)
        subtask["target_id"] = self._tabs[tab_id]
        subtask["status"] = "queued"
        subtask["phase"] = "queued"
        subtask["error"] = None
        subtask["items"] = []
        subtask["summary"] = None
        subtask["finished_at"] = None
        subtask["progress"] = {"current": 0, "total": subtask["max_posts"], "percent": 0, "label": f"正在重试 {subtask['platform_label']}"}
        batch["status"] = "running"
        batch["finished_at"] = None
        batch["message"] = f"正在重试 {subtask['platform_label']}…"
        self._active_batch = batch_id
        self._batch_job = asyncio.create_task(self._run_batch(batch, target_subtasks=[subtask]))
        return self.public_batch(batch)

    async def stop_batch(self, batch_id: str) -> dict:
        batch = self.get_batch(batch_id)
        if batch["status"] == "running" and self._batch_job:
            self._batch_job.cancel()
            with suppress(asyncio.CancelledError):
                await self._batch_job
            if batch["status"] == "running":
                batch.update(status="cancelled", message="多平台采集已停止。", finished_at=_now())
                self._active_batch = None
        return self.public_batch(batch)

    def batch_results(self, batch_id: str) -> dict:
        batch = self.get_batch(batch_id)
        if batch["status"] != "completed" or not batch.get("result"):
            raise ChromeError("results_not_ready", "只有至少有一个平台成功完成的批次才有可预览结果。")
        return batch["result"]
