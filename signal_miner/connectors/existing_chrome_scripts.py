"""Fixed DOM extraction scripts for ExistingChromeCollector.

No caller can supply arbitrary JavaScript; only these whitelisted scripts are allowed.
"""
from __future__ import annotations

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

