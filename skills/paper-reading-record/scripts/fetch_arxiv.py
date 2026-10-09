#!/usr/bin/env python3
"""arXiv 论文批量抓取与图片引用扫描（paper-reading-record 批量模式步骤 1-2）。

用法:
  python3 fetch_arxiv.py --ids 2610.09934,2610.09486 --outdir /tmp/r07
  python3 fetch_arxiv.py --ids @/tmp/r07/ids.txt --outdir /tmp/r07 --ids-file
  # 本地 PDF（无 arXiv HTML 的论文）:
  python3 fetch_arxiv.py --ids p01=/path/to/paper.pdf --outdir /tmp/r07 --local
  # 本地 markdown（已整理的阅读材料）:
  python3 fetch_arxiv.py --ids @/tmp/plan.md --outdir /tmp/r07 --from-md
  # 断点续跑: 重复执行同一命令，已存在且合格的产物自动跳过

输入形态（--ids 的取值）:
  - 裸 arXiv id（2610.09934）          -> 在线抓取 HTML/TXT
  - <key>=<本地.pdf 路径> + --local    -> pypdf 抽全文 TXT，无 HTML（图片走 PDF 提取路径）
  - --from-md 时 --ids 指向 markdown 清单文件，每篇一段:
      # pNN / 标题 / 来源（可空）
      ## p01 论文标题
      - source: https://arxiv.org/abs/xxxx  （或 pdf:/path/x.pdf 或 md:/path/x.md）
      - note: 评注（进 meta intro）
    输出 meta.json + 转成统一 ids 列表继续抓取

产物（全部写入 <outdir>）:
  <id>.html          arXiv HTML v1（5xx 重试 3 次）
  <id>.txt           剥离标签后的正文文本
  scan.json          [{arxiv, figs: [{id, cap, gfx}]}]   图片文件引用索引
  fetch_report.json  每篇状态: html_ok / txt_ok / figs_found / errors
  meta.json          --from-md 时生成: [{n, arxiv, title, intro}]

退出码: 0 = 全部合格; 1 = 有失败项（看 fetch_report.json 与 stderr 摘要）
"""
import argparse, json, os, re, subprocess, sys, time

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
MIN_TXT = 5000  # 低于此值视为抓取失败（HTML 不存在的老论文会触发降级路径）
MIN_HTML = 20000

TAG_RE = re.compile(r'<[^>]+>')
WS_RE = re.compile(r'[ \t]+')
H_TAG_RE = re.compile(r'\\\\[nt]')
IMG_SRC_RE = re.compile(r'<img[^>]+src="([^"]+)"')
GRAPHIC_RE = re.compile(r'<(?:graphic|inline-graphic)[^>]+(?:xlink:href|href)="([^"]+)"[^>]*>', re.S)
# arXiv LaTeXML 有时用 <object data="xxx.svg"> 挂 SVG（无 img/graphic 标签）
OBJECT_DATA_RE = re.compile(r'<object[^>]+data="([^"]+)"[^>]*>', re.S)


def curl(url, out, tries=3):
    for i in range(tries):
        r = subprocess.run(['curl', '-sL', '--max-time', '90', '-A', UA,
                            '-o', out, '-w', '%{http_code}', url],
                           capture_output=True, text=True)
        code = (r.stdout or '').strip()
        if code == '200' and os.path.exists(out) and os.path.getsize(out) > 1000:
            return True
        time.sleep(2 * (i + 1))
    return False


def strip_html(html_path, txt_path):
    html = open(html_path, encoding='utf-8', errors='ignore').read()
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.S)
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.S)
    # 保留标题/题注换行，其余标签剥除
    html = re.sub(r'<(h[1-6]|figcaption|p|li|tr)[^>]*>', '\n', html)
    txt = TAG_RE.sub(' ', html)
    txt = WS_RE.sub(' ', txt)
    lines = [l.strip() for l in txt.split('\n')]
    txt = '\n'.join(l for l in lines if l)
    open(txt_path, 'w', encoding='utf-8').write(txt)
    return len(txt)


def scan_figures(html_path, arxiv_id):
    """扫描 figure 块: 锚点 id + figcaption + 内部 img/graphic 引用。

    返回 [{id, cap, gfx:[相对路径]}]。相对路径保持 arXiv HTML 里的原样
    （可能带 <id>vN/ 前缀，也可能不带——下载侧两种 URL 都要试）。
    """
    html = open(html_path, encoding='utf-8', errors='ignore').read()
    figs = []
    for m in re.finditer(r'<figure[^>]*id="([^"]+)"[^>]*>(.*?)</figure>', html, re.S):
        fid, body = m.group(1), m.group(2)
        cap_m = re.search(r'<figcaption[^>]*>(.*?)</figcaption>', body, re.S)
        cap = TAG_RE.sub(' ', cap_m.group(1)) if cap_m else ''
        cap = WS_RE.sub(' ', cap).strip()[:200]
        gfx = []
        for im in IMG_SRC_RE.finditer(body):
            src = im.group(1)
            if src.startswith(('http', 'data:', '/static')):
                continue
            gfx.append(src)
        for gr in GRAPHIC_RE.finditer(body):
            href = gr.group(1)
            if href.startswith(('http', 'data:')):
                continue
            gfx.append(href)
        for ob in OBJECT_DATA_RE.finditer(body):
            data = ob.group(1)
            if data.startswith(('http', 'data:')):
                continue
            gfx.append(data)
        if fid and (cap or gfx):
            figs.append({'id': fid, 'cap': cap, 'gfx': gfx})
    return figs


def pdf_to_txt(pdf_path, txt_path):
    """pypdf 抽取 PDF 全文（本地 PDF 输入路径）。返回字符数，失败返回 -1。"""
    try:
        from pypdf import PdfReader
    except ImportError:
        return -1
    try:
        reader = PdfReader(pdf_path)
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or '')
        txt = '\n'.join(parts)
        open(txt_path, 'w', encoding='utf-8').write(txt)
        return len(txt)
    except Exception:
        return -1


def md_to_txt(md_path, txt_path):
    """剥离 markdown 标记后的正文（本地 md 输入路径）。返回字符数。"""
    txt = open(md_path, encoding='utf-8').read()
    txt = re.sub(r'```.*?```', ' ', txt, flags=re.S)
    txt = re.sub(r'!\[[^\]]*\]\([^)]*\)', ' ', txt)
    txt = re.sub(r'[#>*`|\-]+', ' ', txt)
    txt = re.sub(r'[ \t]+', ' ', txt)
    open(txt_path, 'w', encoding='utf-8').write(txt.strip())
    return len(txt)


def parse_md_plan(md_path):
    """解析 markdown 清单: 每篇一段 '## pNN 标题' + 'source:' + 可选 'note:'。
    返回 [{n, key, kind, src, title, intro}]，kind in {arxiv, pdf, md}。
    """
    txt = open(md_path, encoding='utf-8').read()
    entries = []
    cur = None
    for line in txt.split('\n'):
        h = re.match(r'^##\s+(?:(p\d+)\s+)?(.+?)\s*$', line)
        if h:
            if cur:
                entries.append(cur)
            n = int(h.group(1)[1:]) if h.group(1) else len(entries) + 1
            cur = {'n': n, 'key': f'p{n:02d}', 'title': h.group(2).strip(),
                   'intro': '', 'kind': None, 'src': None}
            continue
        if cur is None:
            continue
        s = re.match(r'^-\s*source:\s*(.+?)\s*$', line)
        if s:
            v = s.group(1)
            m = re.search(r'(?:abs/|html/)([0-9]{4}\.[0-9]{4,5})(?:v\d+)?', v)
            if v.startswith('pdf:'):
                cur['kind'], cur['src'] = 'pdf', v[4:]
            elif v.startswith('md:'):
                cur['kind'], cur['src'] = 'md', v[3:]
            elif m:
                cur['kind'], cur['src'] = 'arxiv', m.group(1)
            elif re.match(r'^\d{4}\.\d{4,5}$', v):
                cur['kind'], cur['src'] = 'arxiv', v
            else:
                cur['kind'], cur['src'] = 'unknown', v
            continue
        note = re.match(r'^-\s*(?:note|intro):\s*(.+?)\s*$', line)
        if note:
            cur['intro'] = note.group(1)
    if cur:
        entries.append(cur)
    return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ids', required=True,
                    help='逗号分隔 arXiv id；或配合 --ids-file / --from-md 传文件路径')
    ap.add_argument('--ids-file', action='store_true', help='把 --ids 当作 id 列表文件路径')
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--label', default='', help='可选批次标签，仅写入报告')
    ap.add_argument('--local', action='store_true',
                    help='允许 <key>=<本地路径> 形态的输入（按扩展名识别 pdf/md）')
    ap.add_argument('--from-md', action='store_true',
                    help='把 --ids 当作 markdown 清单文件解析（格式见模块 docstring）')
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    meta = None
    if args.from_md:
        meta = parse_md_plan(args.ids)
        bad = [m['key'] for m in meta if m['kind'] not in ('arxiv', 'pdf', 'md') or not m['src']]
        if bad:
            print(f'--from-md 清单里这些条目 source 无法解析: {bad}', file=sys.stderr)
            sys.exit(1)
        items = [(m['key'], m['kind'], m['src']) for m in meta]
    elif args.ids_file:
        raw = [l.strip() for l in open(args.ids) if l.strip() and not l.strip().startswith('#')]
        items = []
        for r in raw:
            if '=' in r and args.local:
                k, v = r.split('=', 1)
                kind = 'pdf' if v.lower().endswith('.pdf') else 'md'
                items.append((k.strip(), kind, v.strip()))
            else:
                items.append((r, 'arxiv', r))
    else:
        items = []
        for x in args.ids.split(','):
            x = x.strip()
            if not x:
                continue
            if '=' in x and args.local:
                k, v = x.split('=', 1)
                kind = 'pdf' if v.lower().endswith('.pdf') else 'md'
                items.append((k.strip(), kind, v.strip()))
            else:
                items.append((x, 'arxiv', x))

    # 断点续跑: 复用已有 scan.json 中合格条目
    scan_path = f'{args.outdir}/scan.json'
    scan = json.load(open(scan_path)) if os.path.exists(scan_path) else []
    done = {p['arxiv']: p for p in scan}

    report = {}
    fails = []
    for key, kind, src in items:
        aid = key  # 报告与产物文件名统一用 key（arXiv id 或 pNN）
        # 在线抓取用真实 arXiv id（--from-md 时 key 是 pNN，src 才是 id）
        fetch_id = src if kind == 'arxiv' else key
        st = {'input': kind, 'html_ok': False, 'txt_ok': False, 'figs_found': 0, 'errors': []}
        html_p, txt_p = f'{args.outdir}/{aid}.html', f'{args.outdir}/{aid}.txt'

        if kind == 'pdf':
            if not os.path.exists(src):
                st['errors'].append(f'pdf not found: {src}')
                report[aid] = st
                fails.append(aid)
                print(f'{aid}: ERR pdf not found: {src}', file=sys.stderr)
                continue
            if os.path.exists(txt_p) and os.path.getsize(txt_p) >= MIN_TXT:
                st['txt_ok'] = True
            else:
                n = pdf_to_txt(src, txt_p)
                if n < 0:
                    st['errors'].append('pypdf extract failed (install: pip3 install pypdf)')
                elif n < MIN_TXT:
                    st['errors'].append(f'pdf text too short ({n} < {MIN_TXT})')
                else:
                    st['txt_ok'] = True
            # 本地 PDF 无 HTML/图扫描；图片走 pypdf page.images 提取路径（见 SKILL.md）
            report[aid] = st
            if not st['txt_ok']:
                fails.append(aid)
            print(f'{aid}: pdf-local txt={st["txt_ok"]} '
                  f'{"ERR: " + "; ".join(st["errors"]) if st["errors"] else ""}')
            continue

        if kind == 'md':
            if not os.path.exists(src):
                st['errors'].append(f'md not found: {src}')
                report[aid] = st
                fails.append(aid)
                print(f'{aid}: ERR md not found: {src}', file=sys.stderr)
                continue
            if os.path.exists(txt_p) and os.path.getsize(txt_p) >= 500:
                st['txt_ok'] = True
            else:
                n = md_to_txt(src, txt_p)
                st['txt_ok'] = n >= 500
                if not st['txt_ok']:
                    st['errors'].append(f'md too short ({n})')
            report[aid] = st
            if not st['txt_ok']:
                fails.append(aid)
            print(f'{aid}: md-local txt={st["txt_ok"]}')
            continue

        # ---- arXiv 在线路径 ----
        # 1) HTML（已存在且合格则跳过）
        if os.path.exists(html_p) and os.path.getsize(html_p) >= MIN_HTML:
            st['html_ok'] = True
        else:
            if curl(f'https://arxiv.org/html/{fetch_id}', html_p):
                st['html_ok'] = True
            else:
                st['errors'].append('html fetch failed (404/5xx/timeout)')
        if not st['html_ok'] and os.path.exists(html_p):
            os.remove(html_p)

        # 2) TXT
        if st['html_ok']:
            if os.path.exists(txt_p) and os.path.getsize(txt_p) >= MIN_TXT:
                st['txt_ok'] = True
            else:
                n = strip_html(html_p, txt_p)
                st['txt_ok'] = n >= MIN_TXT
                if not st['txt_ok']:
                    st['errors'].append(f'txt too short ({n} < {MIN_TXT})')

        # 3) 图片扫描
        if st['html_ok']:
            figs = scan_figures(html_p, aid)
            st['figs_found'] = len([f for f in figs if f['gfx']])
            if fetch_id in done:
                done[fetch_id]['figs'] = figs  # 重扫覆盖，保持最新
            else:
                done[aid] = {'arxiv': fetch_id, 'figs': figs}
            # 无任何图时给显式标记，防误判「扫描器坏了」
            if st['figs_found'] == 0 and not [f for f in figs if f['cap']]:
                st['errors'].append('no figures found (maybe pure-table paper or HTML layout change)')

        report[aid] = st
        if st['errors'] and not st['txt_ok']:
            fails.append(aid)
        print(f"{aid}: html={st['html_ok']} txt={st['txt_ok']} figs={st['figs_found']} "
              f"{'ERR: ' + '; '.join(st['errors']) if st['errors'] else ''}")

    json.dump(list(done.values()), open(scan_path, 'w'), ensure_ascii=False, indent=1)
    json.dump({'label': args.label, 'items': [[k, kd, s] for k, kd, s in items],
               'status': report},
              open(f'{args.outdir}/fetch_report.json', 'w'), ensure_ascii=False, indent=1)

    if meta is not None:
        json.dump(meta, open(f'{args.outdir}/meta.json', 'w'), ensure_ascii=False, indent=1)
        print(f'--- meta.json: {len(meta)} papers ---')
    print(f'--- scan.json: {len(done)} papers ---')
    if fails:
        print(f'FAILED ({len(fails)}): {", ".join(fails)}', file=sys.stderr)
        sys.exit(1)
    print('all ok')


if __name__ == '__main__':
    main()