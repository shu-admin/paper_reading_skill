# 安装指南

## 前置依赖

| 依赖 | 用途 | 检查命令 | 缺失时 |
|---|---|---|---|
| python3 (>=3.9) | 全部 6 个管线脚本 | `python3 --version` | 系统 包管理器安装 |
| curl | 抓取 arXiv HTML/图片 | `curl --version` | 同上 |
| Google Chrome | 无头截图（SVG 转 PNG、手绘总览） | `ls "/Applications/Google Chrome.app"` | Linux 装 chromium 即可（脚本自动回退查找） |
| pypdf | 本地 PDF 输入 / 缺图 PDF 兜底 | `python3 -c "import pypdf"` | `pip3 install pypdf` |
| lark-cli | 飞书读写（可选） | `lark-cli --version` | `npm install -g @larksuiteoapi/lark-cli` |

不发飞书时 lark-cli 完全不需要；本地 PDF 输入之外 pypdf 也不是必需。

## 一键安装

```bash
git clone https://github.com/shu-admin/paper_reading_skill.git
cd paper_reading_skill
bash install.sh
```

`install.sh` 做三件事：

1. 询问安装目标：Claude Code（`~/.claude/skills/`）或 Cursor（`~/.cursor/skills/`），或用 `--dest` 直接指定目录。
2. 复制 `skills/` 下三个技能目录（`paper-reading-record`、`hand-drawn-poster`、`feishu-lark-docs`）到目标。
3. 依赖自检（python3 / curl / Chrome / pypdf / lark-cli），缺什么打印安装命令，不阻塞。

已存在同名技能时默认跳过并列出差异，`--force` 覆盖。

## 手动安装

不想跑脚本就直接复制：

```bash
# Claude Code
cp -r skills/paper-reading-record skills/hand-drawn-poster skills/feishu-lark-docs ~/.claude/skills/

# Cursor
cp -r skills/paper-reading-record skills/hand-drawn-poster skills/feishu-lark-docs ~/.cursor/skills/
```

## 飞书配置（可选，仅发云文档需要）

```bash
npm install -g @larksuiteoapi/lark-cli
lark-cli config init     # 按提示填 app id / secret
lark-cli auth login      # 登录授权
lark-cli docs +fetch --doc <任意一篇你有权限的文档>   # 验证可读
```

细芈权限策略见 `skills/feishu-lark-docs/SKILL.md`。

## 验证安装

```bash
python3 ~/.claude/skills/paper-reading-record/scripts/fetch_arxiv.py \
  --ids 2503.20314 --outdir /tmp/prs-verify
# 输出 ...html=True txt=True figs=N ... all ok 即通
```

然后对 AI 助手说「用 paper-reading-record 技能读 arxiv.org/abs/2503.20314」即可走单篇全流程。

## 卸载

删除三个技能目录即可，无其他落点：

```bash
rm -rf ~/.claude/skills/paper-reading-record \
       ~/.claude/skills/hand-drawn-poster \
       ~/.claude/skills/feishu-lark-docs
```