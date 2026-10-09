#!/usr/bin/env python3
"""下载 arXiv HTML 引用的论文原图（批量模式步骤 3）。

用法:
  python3 download_figures.py --scan /tmp/r07/scan.json \
      --outdir /Users/.../records --key p01=p01-Itgan --key p02=p02-LIDAccent
  # 或直接用 scan.json 顺序编号（不传 --key 时自动 p01..pN）

产物:
  <outdir>/<pNN>-figures/<FID>.png|.jpg      每个锚点一个文件（子图带 _sfN 后缀）
  <outdir>/<pNN>-figures/bad.json            下载失败/占位/404 清单（含试过的 URL）

规则（全部来自 25 篇实战踩坑）:
  1. gfx 相对路径两种形态都要试: 带 <id>vN/ 前缀 -> https://arxiv.org/html/<gfx>;
     不带前缀 -> https://arxiv.org/html/<id>/<gfx>（拿 id 拼前缀会 404）
  2. 每张下载后验魔数（PNG \x89PNG / JPG \xff\xd8\xff; SVG 查 <svg 或 xmlns）。
     arXiv 404 页是 7882 字节 HTML——体积合格但魔数不过，必须删掉防占位混入。
  3. SVG 先落盘再由无头 Chrome 截图转 PNG（HTML 包装 + --screenshot）。
  4. 同一 figure 锚点挂多张图时文件名加 _sf1.._sfN，避免互相覆盖（DNS 语谱
     图组 9 张写同一路径的坑）。
  5. HTML 引用存在但服务端 404 的图（arXiv 渲染缺陷）记入 bad.json，
     记录里标注「从 PDF 提取」后手工补，脚本不自动猜。
"""
import argparse, json, os, re, subprocess, sys

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
CHROME_CANDIDATES = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
]


def find_chrome():
    for c in CHROME_CANDIDATES:
        if os.path.exists(c):
            return c
    return None


def real_image(path):
    """魔数校验: 返回 True 仅当文件是真实位图。"""
    if not os.path.exists(path):
        return False
    head = open(path, 'rb').read(8)
    return head[:4] == b'\x89PNG' or head[:3] == b'\xff\xd8\xff'


def real_svg(path):
    if not os.path.exists(path) or os.path.getsize(path) < 500:
        return False
    head = open(path, 'rb').read(400)
    return b'<svg' in head or b'xmlns' in head


def try_urls(urls, out):
    for u in urls:
        subprocess.run(['curl', '-sL', '--max-time', '60', '-A', UA, '-o', out, u],
                       capture_output=True)
        if real_image(out):
            return u
        if os.path.exists(out) and os.path.getsize(out) < 500:
            os.remove(out)
    return None


def svg_urls(g, arxiv_id):
    if g.startswith(arxiv_id):
        base = f'https://arxiv.org/html/{g}'
    else:
        base = f'https://arxiv.org/html/{arxiv_id}/{g}'
    v1 = f'https://arxiv.org/html/{arxiv_id}v1/{os.path.basename(g)}'
    return [base, v1]


def svg2png(chrome, svg_path, png_path, width=1200):
    d = os.path.dirname(svg_path)
    stem = os.path.splitext(os.path.basename(png_path))[0]
    html_path = f'{d}/{stem}_view.html'
    abs_svg = os.path.abspath(svg_path)
    with open(html_path, 'w') as fh:
        fh.write(f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
                 f'body{{margin:0;background:#fff}} img{{max-width:{width}px}}'
                 f'</style></head><body><img src="file://{abs_svg}"></body></html>')
    subprocess.run([chrome, '--headless', '--disable-gpu', '--no-sandbox',
                    f'--screenshot={os.path.abspath(png_path)}',
                    f'--window-size={width},1600', '--hide-scrollbars',
                    '--default-background-color=FFFFFFFF',
                    'file://' + os.path.abspath(html_path)],
                   capture_output=True, timeout=120)
    for p in (html_path,):
        if os.path.exists(p):
            os.remove(p)
    return real_image(png_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scan', required=True, help='scan.json 路径')
    ap.add_argument('--outdir', required=True, help='记录根目录（figures 目录的父目录）')
    ap.add_argument('--key', action='append', default=[],
                    help='pNN=短名 映射，如 --key p01=p01-Itgan；缺省用 p01..pN')
    ap.add_argument('--force', action='store_true', help='重下已存在的图')
    args = ap.parse_args()

    scan = json.load(open(args.scan))
    keys = {}
    if args.key:
        for kv in args.key:
            k, v = kv.split('=', 1)
            keys[k] = v
    chrome = find_chrome()

    total_ok = 0
    for i, p in enumerate(scan, 1):
        pk = keys.get(f'p{i:02d}', f'p{i:02d}')
        arxiv = p['arxiv']
        d = f'{args.outdir}/{pk}-figures'
        os.makedirs(d, exist_ok=True)
        bad_path = f'{d}/bad.json'
        bad = json.load(open(bad_path)) if os.path.exists(bad_path) else {}
        ok_count = 0

        for f in p.get('figs', []):
            gfx = f.get('gfx') or []
            if not gfx:
                continue
            fid_base = f['id'].replace('.', '_')
            # 单图: FID.ext；多图: FID_sfN.ext（防覆盖）
            for idx, g in enumerate(gfx, 1):
                fid = fid_base if len(gfx) == 1 else f'{fid_base}_sf{idx}'
                ext = os.path.splitext(g)[1].lower()
                if ext in ('.svg',):
                    png = f'{d}/{fid}.png'
                    if os.path.exists(png) and real_image(png) and not args.force:
                        ok_count += 1
                        continue
                    if not chrome:
                        bad[fid] = {'ref': g, 'reason': 'chrome not found for svg'}
                        continue
                    svg = f'{d}/{fid}.svg'
                    hit = None
                    for u in svg_urls(g, arxiv):
                        subprocess.run(['curl', '-sL', '--max-time', '60', '-A', UA,
                                        '-o', svg, u], capture_output=True)
                        if real_svg(svg):
                            hit = u
                            break
                        if os.path.exists(svg) and os.path.getsize(svg) < 500:
                            os.remove(svg)
                    if not hit:
                        bad[fid] = {'ref': g, 'reason': 'svg 404/empty',
                                    'tried': svg_urls(g, arxiv)}
                        if os.path.exists(svg):
                            os.remove(svg)
                        continue
                    if svg2png(chrome, svg, png):
                        ok_count += 1
                        os.remove(svg)
                    else:
                        bad[fid] = {'ref': g, 'reason': 'svg->png render failed'}
                        for x in (svg, png):
                            if os.path.exists(x):
                                os.remove(x)
                else:
                    out = f'{d}/{fid}{ext or ".png"}'
                    if os.path.exists(out) and real_image(out) and not args.force:
                        ok_count += 1
                        continue
                    urls = [f'https://arxiv.org/html/{g}'] if g.startswith(arxiv) \
                        else [f'https://arxiv.org/html/{arxiv}/{g}']
                    hit = try_urls(urls, out)
                    if hit:
                        ok_count += 1
                    else:
                        bad[fid] = {'ref': g, 'reason': '404/placeholder/timeout', 'tried': urls}
                        if os.path.exists(out):
                            os.remove(out)

        json.dump(bad, open(bad_path, 'w'), ensure_ascii=False, indent=1)
        total_ok += ok_count
        print(f'{pk} {arxiv}: {ok_count} ok, {len(bad)} bad'
              + (f' -> {list(bad)[:3]}' if bad else ''))

    print(f'--- total downloaded/verified: {total_ok} ---')
    # 汇总退出码: bad 非空不视为失败（占位/404 是预期降级路径），仅在 stderr 提示
    nbad = sum(len(json.load(open(f'{args.outdir}/{keys.get(f"p{i:02d}", f"p{i:02d}")}-figures/bad.json')))
               for i, p in enumerate(scan, 1)
               if os.path.exists(f'{args.outdir}/{keys.get(f"p{i:02d}", f"p{i:02d}")}-figures/bad.json'))
    if nbad:
        print(f'note: {nbad} refs failed (see bad.json; PDF 提取兜底见 SKILL.md)', file=sys.stderr)
    print('done')


if __name__ == '__main__':
    main()