#!/usr/bin/env bash
# 手绘风海报渲染：HTML -> 2x PNG（无头 Chrome）
# 用法: render.sh <html文件> <输出png> <窗口高度|auto> [窗口宽度=1240]
# 高度给 auto 时自动测量内容高度（需要页面带 data-content-height 测量脚本，见 template.html）。
set -euo pipefail

html="$1"; out="$2"; h="$3"; w="${4:-1240}"

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [ ! -x "$CHROME" ]; then
  CHROME="$(command -v chromium || command -v google-chrome || command -v chrome || true)"
  [ -n "$CHROME" ] || { echo "ERROR: Chrome/Chromium not found" >&2; exit 1; }
fi

# 转成绝对路径，供 file:// 使用
dir="$(cd "$(dirname "$html")" && pwd)"
abs="$dir/$(basename "$html")"

# auto 模式：先在小窗口 dump-dom，读取页面自报的 data-content-height
if [ "$h" = "auto" ]; then
  measured="$("$CHROME" --headless=new --disable-gpu \
    --window-size="${w},800" --virtual-time-budget=5000 \
    --dump-dom "file://${abs}" 2>/dev/null \
    | grep -o 'data-content-height="[0-9]*"' | head -1 | grep -o '[0-9]*' || true)"
  if [ -n "${measured:-}" ] && [ "$measured" -gt 100 ]; then
    h=$((measured + 8))
  else
    h=2400  # 测量失败回退：给足高度再人工迭代
  fi
fi

"$CHROME" --headless=new --disable-gpu --hide-scrollbars \
  --force-device-scale-factor=2 \
  --window-size="${w},${h}" \
  --virtual-time-budget=5000 \
  --screenshot="$out" "file://${abs}" 2>/dev/null

[ -f "$out" ] || { echo "ERROR: screenshot not produced" >&2; exit 1; }
if command -v sips >/dev/null 2>&1; then
  sips -g pixelWidth -g pixelHeight "$out" | tail -2
else
  echo "OK: $out"
fi