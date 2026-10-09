#!/usr/bin/env bash
# paper-reading-skill 一键安装: 复制三个技能到 Claude Code 或 Cursor 的 skills 目录
# 用法: bash install.sh [--dest <目录>] [--force]
#   --dest   直接指定安装目录（缺省交互选择 ~/.claude/skills 或 ~/.cursor/skills）
#   --force  目标已存在同名技能时覆盖（默认跳过）
set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")" && pwd)/skills"
DEST=""
FORCE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --dest)  DEST="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

SKILLS=(paper-reading-record hand-drawn-poster feishu-lark-docs)

# ---- 1. 确定目标目录 ----
if [ -z "$DEST" ]; then
  echo "安装到哪个技能目录？"
  echo "  1) ~/.claude/skills   (Claude Code)"
  echo "  2) ~/.cursor/skills   (Cursor)"
  printf "选择 [1/2]: "
  read -r choice
  case "$choice" in
    2) DEST="$HOME/.cursor/skills" ;;
    *) DEST="$HOME/.claude/skills" ;;
  esac
fi
mkdir -p "$DEST"
echo "目标: $DEST"

# ---- 2. 复制技能 ----
for s in "${SKILLS[@]}"; do
  if [ ! -d "$SRC_DIR/$s" ]; then
    echo "ERROR: 源缺失 $SRC_DIR/$s" >&2
    exit 1
  fi
  if [ -d "$DEST/$s" ] && [ "$FORCE" -ne 1 ]; then
    printf "SKIP  %s (exists, --force to overwrite)\n" "$s"
  else
    rm -rf "$DEST/$s"
    cp -R "$SRC_DIR/$s" "$DEST/$s"
    echo "OK    $s -> $DEST/$s"
  fi
done

# ---- 3. 依赖自检（缺什么提示，不阻塞） ----
echo
echo "== 依赖自检 =="
command -v python3 >/dev/null 2>&1 && echo "OK    python3 $(python3 --version 2>&1 | cut -d' ' -f2)" \
  || echo "MISS  python3 -> 系统包管理器安装"
command -v curl >/dev/null 2>&1 && echo "OK    curl" || echo "MISS  curl -> 系统包管理器安装"
if [ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ] \
   || command -v chromium >/dev/null 2>&1; then
  echo "OK    Chrome/Chromium（无头截图）"
else
  echo "MISS  Chrome -> 安装 Google Chrome 或 chromium"
fi
python3 -c "import pypdf" 2>/dev/null \
  && echo "OK    pypdf（本地 PDF 输入）" \
  || echo "MISS  pypdf -> pip3 install pypdf （仅本地 PDF 输入需要）"
command -v lark-cli >/dev/null 2>&1 \
  && echo "OK    lark-cli（飞书读写）" \
  || echo "MISS  lark-cli -> npm install -g @larksuiteoapi/lark-cli （仅发飞书需要）"

echo
echo "安装完成。验证："
echo "  python3 $DEST/paper-reading-record/scripts/fetch_arxiv.py --ids 2503.20314 --outdir /tmp/prs-verify"
echo "然后对 AI 助手说「用 paper-reading-record 技能读 arxiv.org/abs/2503.20314」"