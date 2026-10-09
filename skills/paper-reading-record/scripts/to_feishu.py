#!/usr/bin/env python3
"""把本地阅读记录转成飞书可导入的 markdown（批量模式阶段 5a）。

用法:
  python3 to_feishu.py --root <records目录> --plan final_map.json \
      [--meta meta.json] [--outdir <root>/feishu-md] [--out-plan <root>/feishu_plan.json]

  final_map.json: {"1": "p01-Itgan-论文阅读记录.md", ...}（编号 -> 记录文件名）
  meta.json:      [{n, title, cat, intro, ...}]（可选，用于拼标题与汇总；缺省标题只用短名）

转换规则:
  1. 本地图片路径 -> @./ 前缀（飞书 markdown 导入时自动上传该图片）
  2. 代码块外的字面 <token>（如 <p> <w>）转义成 \\<token\\>，防止被解析成 XML 标签吞掉
  3. 代码块（``` 围栏）与行内反引号内的内容原样保留

产物:
  <outdir>/pNN-xxx-论文阅读记录.md   转换后文件（与源文件同名）
  <out-plan>                          feishu_plan.json: pNN -> {file, title}

断点续跑: 重复执行会覆盖重写全部输出，天然幂等；只读不改源文件。
"""
import argparse, json, os, re, sys

TOKEN_RE = re.compile(r'<(/?[A-Za-z][A-Za-z0-9_]*(?:\s[^<>]*)?)>')


def convert(txt):
    out_lines = []
    in_code = False
    for line in txt.split('\n'):
        if line.strip().startswith('```'):
            in_code = not in_code
            out_lines.append(line)
            continue
        if in_code:
            out_lines.append(line)
            continue
        # 1) 本地图片路径 -> @./ 形态（http 外链与已带 @ 的跳过）
        def img_sub(m):
            alt, path = m.group(1), m.group(2)
            if path.startswith(('http', '@')):
                return m.group(0)
            if path.startswith('./'):
                return f'![{alt}](@{path[1:]})'
            return f'![{alt}](@{path})'
        line = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', img_sub, line)
        # 2) 行内反引号之外的尖括号 token 转义
        parts = line.split('`')
        for i in range(0, len(parts), 2):  # 偶数下标 = 反引号外
            parts[i] = TOKEN_RE.sub(lambda m: '\\<' + m.group(1) + '>', parts[i])
        line = '`'.join(parts)
        out_lines.append(line)
    return '\n'.join(out_lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True, help='记录根目录')
    ap.add_argument('--plan', required=True,
                    help='final_map.json（编号 -> 记录文件名）')
    ap.add_argument('--meta', default=None,
                    help='meta.json（可选，论文元信息，拼标题用）')
    ap.add_argument('--outdir', default=None,
                    help='输出目录，缺省 <root>/feishu-md')
    ap.add_argument('--out-plan', default=None,
                    help='feishu_plan.json 输出路径，缺省 <root>/feishu_plan.json')
    args = ap.parse_args()

    outdir = args.outdir or f'{args.root}/feishu-md'
    out_plan = args.out_plan or f'{args.root}/feishu_plan.json'
    os.makedirs(outdir, exist_ok=True)

    final = json.load(open(args.plan))
    meta = {}
    if args.meta and os.path.exists(args.meta):
        for m in json.load(open(args.meta)):
            meta[int(m['n'])] = m

    missing = []
    titles = {}
    for n_str, fname in sorted(final.items(), key=lambda kv: int(kv[0])):
        n = int(n_str)
        pk = f'p{n:02d}'
        src = f'{args.root}/{fname}'
        if not os.path.exists(src):
            missing.append(fname)
            continue
        conv = convert(open(src, encoding='utf-8').read())
        open(f'{outdir}/{fname}', 'w', encoding='utf-8').write(conv)
        short = fname.replace('-论文阅读记录.md', '')
        title = f'{short} · 论文阅读记录'
        if n in meta:
            title = f"{short} · {meta[n]['title'][:60]} · 论文阅读记录"
        titles[pk] = {'file': f'feishu-md/{fname}', 'title': title}

    json.dump(titles, open(out_plan, 'w'), ensure_ascii=False, indent=1)
    print(f'converted {len(titles)} files to {outdir}/')
    print(f'plan saved {out_plan}')
    if missing:
        print(f'MISSING ({len(missing)}): {", ".join(missing)}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()