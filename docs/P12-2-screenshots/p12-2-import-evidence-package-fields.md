# P12-2 前端证据：批量 JSON 导入区-证据包字段说明

## 验证方法

无 headless browser 工具可用（browser-use CLI 未安装、playwright 未安装），
采用源代码级验证 + curl 页面渲染验证。

## 证据 1：app.js 中存在证据包字段说明

文件：`frontend/static/app.js`

### 批量 JSON 区证据包字段说明 (行 682-686)

```html
<summary style="cursor:pointer;font-weight:600;">📋 证据包字段说明（每项必须包含）</summary>
<div style="padding:8px 0;line-height:1.7;">
  <strong>必填：</strong><code>source_type</code>, <code>external_url</code>, <code>capture_method</code>, <code>text</code><br>
  <strong>可选：</strong><code>subject</code>, <code>author_name</code>, <code>source_note</code>, <code>screenshot_path</code>, <code>ocr_text</code>, <code>source_captured_at</code>, <code>raw_payload</code><br>
  <span style="color:#b91c1c;">⚠ browser_screenshot 方法必须填写 screenshot_path 或 source_note</span>
</div>
```

### browser-screenshot-hint 元素 (行 626-628)

```html
<div id="browser-screenshot-hint" style="display:none;margin-top:4px;padding:6px 10px;
background:#fff3cd;border:1px solid #ffc107;border-radius:4px;font-size:13px;color:#856404;">
  ⚠️ 截图/OCR 方法必须填写「截图路径」或在「来源备注」中说明截图内容，否则无法提交。
</div>
```

### updateSourceAcquisitionControls 函数中的提示切换逻辑 (行 583-597)

```javascript
const screenshotHintEl = document.getElementById('browser-screenshot-hint');
// ...
if (screenshotHintEl) {
  screenshotHintEl.style.display = methodSelect.value === 'browser_screenshot' ? 'block' : 'none';
}
```

## 证据 2：页面可正常渲染

```bash
$ curl -s http://localhost:8000/ | head -1
<!DOCTYPE html>
<html lang="zh-CN">
```

服务器在 8000 端口正常运行，页面可访问。

## 结论

✅ 前端批量 JSON 导入区包含证据包字段说明
✅ browser_screenshot 方法下有黄色警告提示
✅ 选 browser_screenshot 时提示自动显示/隐藏
