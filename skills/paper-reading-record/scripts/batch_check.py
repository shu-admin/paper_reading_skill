#!/usr/bin/env python3
"""批量产物终检（paper-reading-record 批量模式步骤 7 自检）。

用法:
  python3 batch_check.py --root /path/to/records --plan plan.json
  # plan.json: {"p01": {"file": "p01-Itgan-论文阅读记录.md"}, ...}
  # 飞书链接核验: --docs docs.json  {"p01": {"url": "...", "id": "..."}}

检查项（每条都可独立失败并给出修复动作）:
  A. 记录文件存在、行数 >= 200
  B. 四段式结构: # 结论摘要 / # 论文解读 / # 项目解读 / # 附录 / # 总体一览（手绘）
  C. mermaid >= 1
  D. 嵌图相对路径全部存在，且是真实位图（魔数校验，防 HTML 占位混入）
  E. 手绘总览 PNG 存在且为真实位图
  F. 无模板占位符残留（<xxx> 形态且非代码块内）
  G. 可选: 飞书 docs.json 的 URL 与汇总文档内「打开阅读记录」链接一一对应
  H. 可选: --fetch 模式回拉 2 篇飞书文档验证正文长度（防「创建成功但内容空」）
  I. WARN（不影响退出码）: <pNN>-figures/ 内已下载的真实位图未嵌入正文、
     且未在 figures-disposition 注释中注明排除理由（图片处置闭环）
  J. WARN（不影响退出码）: 「# 结论摘要 ~ # 论文解读」之间无论文原图
     （总体架构图应置于核心实现说明节，或显式交叉引用 §1/§2 的图）

输出: 逐篇 PASS/FAIL + 问题清单 + WARN 清单（含建议动作）；
退出码 0 仅当无 FAIL（WARN 需逐条人工确认，不阻断）。
"""
import argparse, glob, json, os, re, subprocess, sys

MIN_LINES = 200
STRUCT = ['# 结论摘要', '# 论文解读', '# 项目解读', '# 附录', '# 总体一览（手绘）']


def real_image(path):
    if not os.path.exists(path):
        return False
    head = open(path, 'rb').read(8)
    return head[:4] == b'\x89PNG' or head[:3] == b'\xff\xd8\xff'


def check_record(root, fname, pk):
    issues = []
    warns = []
    path = os.path.join(root, fname)
    if not os.path.exists(path):
        return [f'记录文件缺失: {fname}'], [], 0, 0
    txt = open(path, encoding='utf-8').read()
    lines = txt.count('\n') + 1
    if lines < MIN_LINES:
        issues.append(f'行数不足: {lines} < {MIN_LINES}（正文是否写完？）')

    for sec in STRUCT:
        if sec not in txt:
            issues.append(f'缺结构: {sec}')

    if 'mermaid' not in txt:
        issues.append('缺 mermaid 流程图')

    # 图片: 路径存在 + 魔数；同时收集已引用文件名供检查 I
    n_img = 0
    referenced = set()
    for m in re.finditer(r'!\[[^\]]*\]\(([^)]+)\)', txt):
        mp = m.group(1)
        if mp.startswith('http'):
            continue
        n_img += 1
        referenced.add(os.path.basename(mp))
        full = os.path.join(root, mp)
        if not os.path.exists(full):
            issues.append(f'图片路径缺失: {mp}')
        elif not real_image(full):
            issues.append(f'图片非真实位图（占位/损坏）: {mp}')
    if n_img == 0:
        issues.append('无嵌入图（纯表格论文应显式声明「论文无图」）')

    # figures-disposition 注释中已声明排除的图名（可带可不带扩展名）
    # 约定: <!-- figures-disposition: S2_F2=排除理由; S6_F6=... -->
    disposition = set()
    for dc in re.findall(r'<!--\s*figures-disposition:(.*?)-->', txt, flags=re.S):
        for tok in re.split(r'[;,，；]', dc):
            name = tok.split('=', 1)[0].strip()
            if name:
                disposition.add(os.path.splitext(name)[0])

    # I. 图片处置闭环: <pk>*-figures/ 内真实位图必须被嵌入或在 disposition 中说明
    if os.path.isdir(root):
        for dname in sorted(os.listdir(root)):
            if not re.match(rf'^{re.escape(pk)}.*-figures$', dname):
                continue
            fdir = os.path.join(root, dname)
            if not os.path.isdir(fdir):
                continue
            for name in sorted(os.listdir(fdir)):
                fpath = os.path.join(fdir, name)
                stem = os.path.splitext(name)[0]
                if (real_image(fpath) and name not in referenced
                        and stem not in disposition and name not in disposition):
                    warns.append(
                        f'已下载未嵌入且无处置说明: {dname}/{name}'
                        f'（嵌入正文，或在 figures-disposition 注释中注明排除理由）')

    # J. 核心实现说明节（# 结论摘要 ~ # 论文解读 之间）应有论文原图
    msec = re.search(r'# 结论摘要(.*?)# 论文解读', txt, flags=re.S)
    if msec and not re.search(r'!\[[^\]]*\]\([^)]+\)', msec.group(1)):
        warns.append('核心实现说明节无论文原图（总体架构图应置于该节 mermaid 之后，'
                     '或在此处显式交叉引用 §1/§2 已嵌入的图）')

    # 总览 PNG（os.listdir 避免 glob 对非 ASCII 文件名的坑）
    # 成品按 SKILL.md 流程 cp 到记录根目录，渲染中间产物在 pNN-overview/，两处任一存在即通过
    png_found = False
    for sdir in (os.path.join(root, f'{pk}-overview'), root):
        if not os.path.isdir(sdir):
            continue
        for name in os.listdir(sdir):
            if '总体一览' in name and name.endswith('.png'):
                if real_image(os.path.join(sdir, name)):
                    png_found = True
                break
        if png_found:
            break
    if not png_found:
        issues.append('手绘总览 PNG 缺失或损坏（记录根目录或 pNN-overview/ 下的 *总体一览.png）')

    # 占位符（代码块外）: <短标识> 形态且非 <br/> 等已知标签
    in_code = False
    for line in txt.split('\n'):
        if line.strip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        parts = line.split('`')
        for i in range(0, len(parts), 2):
            for ph in re.findall(r'<(/?[a-zA-Z][a-zA-Z0-9_]{1,20})>', parts[i]):
                if ph.strip('/').lower() not in ('br', 'b', 'i', 'p', 'w', 'x',
                                                  'p>', 's', 'e', 't', 'n', 'k'):
                    # 常见论文 token 如 <p>/<w> 在反引号外出现即提示
                    issues.append(f'代码块外裸尖括号 token: <{ph}>（应包进 ` ` 或转义）')
                    break
    return issues, warns, lines, n_img


def check_feishu(docs_path, agg_url=None, fetch_sample=None):
    issues = []
    docs = json.load(open(docs_path))
    if len(docs) < 1:
        issues.append('docs.json 为空')
    for pk, v in sorted(docs.items()):
        if not re.match(r'https://[\w.-]+/docx/\w+', v.get('url', '')):
            issues.append(f'{pk} URL 形态异常: {v.get("url")}')
    if agg_url:
        r = subprocess.run(f'lark-cli docs +fetch --doc {agg_url} --doc-format markdown',
                           shell=True, capture_output=True, text=True, timeout=120)
        try:
            content = json.loads(r.stdout)['data']['document']['content']
        except Exception:
            issues.append(f'汇总文档回拉失败: {agg_url[:60]}')
            return issues
        links = set(re.findall(r'\[打开阅读记录\]\(([^)]+)\)', content))
        expect = set(v['url'] for v in docs.values())
        if expect - links:
            issues.append(f'汇总缺链接: {sorted(expect - links)}')
        if links - expect:
            issues.append(f'汇总多链接: {sorted(links - expect)}')
        if len(links) != len(docs):
            issues.append(f'汇总链接数 {len(links)} != 记录数 {len(docs)}')
    if fetch_sample:
        for pk in fetch_sample:
            if pk not in docs:
                continue
            r = subprocess.run(
                f'lark-cli docs +fetch --doc {docs[pk]["url"]} --doc-format markdown',
                shell=True, capture_output=True, text=True, timeout=120)
            try:
                content = json.loads(r.stdout)['data']['document']['content']
                if len(content) < 3000:
                    issues.append(f'{pk} 飞书正文过短({len(content)})，疑似创建降级')
            except Exception:
                issues.append(f'{pk} 飞书回拉失败')
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True, help='记录根目录')
    ap.add_argument('--plan', help='plan.json（pNN -> file）；缺省扫 p*-论文阅读记录.md')
    ap.add_argument('--docs', help='docs.json（飞书链接映射）')
    ap.add_argument('--agg-url', help='汇总文档 URL，核验链接一致性')
    ap.add_argument('--fetch', help='逗号分隔的 pNN 列表，回拉飞书验证正文')
    args = ap.parse_args()

    if args.plan:
        plan = json.load(open(args.plan))
    else:
        plan = {}
        for name in os.listdir(args.root):
            m = re.match(r'(p\d+)-[^/]*论文阅读记录\.md$', name)
            if m:
                plan[m.group(1)] = {'file': name}

    all_fail = False
    total_warn = 0
    print(f'== 记录检查（{len(plan)} 篇）==')
    for raw_pk in sorted(plan):
        # 规范化 1 / p1 / p01 -> p01（figures/overview 目录都是两位编号）
        m = re.match(r'(?:p)?(\d+)$', raw_pk)
        pk = f'p{int(m.group(1)):02d}' if m else raw_pk
        fname = plan[raw_pk]['file'] if isinstance(plan[raw_pk], dict) else plan[raw_pk]
        issues, warns, lines, n_img = check_record(args.root, fname, pk)
        status = 'PASS' if not issues else 'FAIL'
        if issues:
            all_fail = True
        total_warn += len(warns)
        suffix = f'（{len(warns)} WARN）' if warns else ''
        print(f'{status} {pk}: {lines} 行 {n_img} 图{suffix}')
        for it in issues:
            print(f'   - {it}')
        for it in warns:
            print(f'   ! {it}')

    if args.docs:
        print('== 飞书链接检查 ==')
        sample = args.fetch.split(',') if args.fetch else None
        fi = check_feishu(args.docs, args.agg_url, sample)
        for it in fi:
            print(f'   - {it}')
        if fi:
            all_fail = True

    if all_fail:
        print('RESULT: FAIL（见上方问题清单）', file=sys.stderr)
        sys.exit(1)
    if total_warn:
        print(f'RESULT: ALL PASS（{total_warn} 条 WARN 不阻断交付，需逐条人工确认：'
              f'嵌入或在 figures-disposition 注释中注明排除理由）')
    else:
        print('RESULT: ALL PASS')


if __name__ == '__main__':
    main()
