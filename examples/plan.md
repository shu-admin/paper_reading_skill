# 批次清单示例

给 `fetch_arxiv.py --from-md` 用的清单格式：每篇一段 `## pNN 标题`，`source` 支持 arXiv 链接、裸 id、`pdf:` 本地路径、`md:` 本地路径；`note` 可选（进 meta.intro，汇总表用）。

```bash
python3 skills/paper-reading-record/scripts/fetch_arxiv.py \
  --from-md --ids examples/plan.md --outdir /tmp/batch
```

---

## p01 Itgan: NADI 2026 阿拉伯语 ASR 参赛系统
- source: https://arxiv.org/abs/2610.09934
- note: 共享配方 + 按任务诊断加增量

## p02 BFCB: 波束成形会议增强
- source: 2610.09467
- note: 子带滤波 + 卡尔曼后滤波

## p03 内部 PDF 材料（无 arXiv 版本）
- source: pdf:/Users/you/papers/internal-method.pdf
- note: 仅供内部对照

## p04 已整理的笔记 markdown
- source: md:/Users/you/notes/survey-notes.md
- note: 二手综述，需标注非一手材料
```

注意：

- `pNN` 编号两位零填充，贯穿 figures / overview / 记录文件名；不写编号时按出现顺序自动编。
- `pdf:` 路径必须是本机存在的文件；图片走 pypdf `page.images` 提取路径（无 arXiv HTML 可扫）。
- `md:` 输入的图片沿用 md 里写的本地路径（相对该 md 所在目录解析）。
- 来源是飞书 wiki 时，先用 lark-cli 读出节点清单再拼成上面的格式。