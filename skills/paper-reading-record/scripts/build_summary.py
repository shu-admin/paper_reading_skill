#!/usr/bin/env python3
"""生成汇总文档 markdown（批量模式阶段 6a）。

用法:
  python3 build_summary.py --docs feishu_docs.json --meta meta.json \
      --out <records目录>/feishu-md/汇总-<批次名>.md \
      --title "YYYY-MM-DD 语音论文阅读记录汇总（N 篇）" \
      [--source-url <飞书 wiki 链接>] [--source-name <来源名>] [--note-file <补充说明md>]

  meta.json:  [{n, arxiv, title, cat, intro, ...}]，cat 用于分组，n 与 docs.json 的 pNN 对应
  docs.json:  pNN -> {url, ...}（阶段 5b 产物）

规则:
  1. 按 meta.cat 首次出现顺序分组，组内按 n 升序（对齐 wiki 原始顺序）
  2. 每行: 编号 | 标题 | arXiv 链接 | 评注（meta.intro 截断） | 打开阅读记录（docs url）
  3. 表格单元格内的 | 换成 \\|，换行换空格，防表格断裂
  4. 「打开阅读记录」字面文案是 batch_check.py --agg-url 的核验锚点，不能改

产物: 汇总 md 文件。创建飞书文档用阶段 5b 同款命令:
  lark-cli docs +create --doc-format markdown --title "<标题>" --content "@./feishu-md/汇总-xxx.md"
退出码: 0 = docs.json 覆盖 plan 全部篇目; 1 = 有 pNN 缺链接。
"""
import argparse, json, os, sys


def cell(s, limit=70):
    return str(s).replace('|', '\\|').replace('\n', ' ')[:limit]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--docs', required=True, help='docs.json（pNN -> url）')
    ap.add_argument('--meta', required=True, help='meta.json（论文元信息）')
    ap.add_argument('--out', required=True, help='输出 md 路径')
    ap.add_argument('--title', required=True, help='汇总文档标题')
    ap.add_argument('--source-url', default='', help='来源 wiki 链接')
    ap.add_argument('--source-name', default='飞书 wiki 论文清单')
    ap.add_argument('--note-file', default='',
                    help='可选 md 片段，追加到文末（如记录覆盖说明、本地路径）')
    ap.add_argument('--date', default='', help='生成日期，缺省不写')
    args = ap.parse_args()

    meta = json.load(open(args.meta))
    docs = json.load(open(args.docs))

    missing = [f"p{m['n']:02d}" for m in meta if f"p{m['n']:02d}" not in docs]
    if missing:
        print(f'docs.json 缺链接: {missing}', file=sys.stderr)
        sys.exit(1)

    lines = [f'# {args.title}', '']
    if args.source_url:
        lines.append(f'> - 来源：{args.source_name}（[原始 wiki]({args.source_url})）')
    else:
        lines.append(f'> - 来源：{args.source_name}')
    lines.append('> - 每篇论文按 `paper-reading-record` skill 全流程产出独立阅读记录'
                 '（四段式：结论摘要 / 论文解读 / 项目解读 / 附录 + 论文原图提取嵌入 + 手绘总体一览）')
    if args.date:
        lines.append(f'> - 生成日期：{args.date}')
    lines.append('')

    # 分组: cat 首次出现顺序，组内按 n 升序
    cat_order, cats = [], {}
    for m in sorted(meta, key=lambda x: x['n']):
        c = m.get('cat') or '未分类'
        if c not in cat_order:
            cat_order.append(c)
        cats.setdefault(c, []).append(m)

    for c in cat_order:
        lines += [f'## {c}', '',
                  '| # | 论文 | arXiv | 评注 | 阅读记录 |',
                  '|---|---|---|---|---|']
        for m in cats[c]:
            pk = f"p{m['n']:02d}"
            aid = m['arxiv']
            title = cell(m['title'])
            intro = cell(m.get('intro', ''), 60)
            lines.append(f"| {m['n']} | {title} "
                         f"| [{aid}](https://arxiv.org/abs/{aid}) "
                         f"| {intro} | [打开阅读记录]({docs[pk]['url']}) |")
        lines.append('')

    if args.note_file and os.path.exists(args.note_file):
        lines.append(open(args.note_file, encoding='utf-8').read().rstrip())
        lines.append('')

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    open(args.out, 'w', encoding='utf-8').write('\n'.join(lines))
    print(f'written {args.out} ({len(lines)} lines, {len(cat_order)} categories, '
          f'{len(meta)} records)')


if __name__ == '__main__':
    main()