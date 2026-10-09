#!/usr/bin/env python3
"""批量创建飞书云文档（批量模式阶段 5b）。

用法:
  python3 create_feishu_docs.py --plan feishu_plan.json --docs feishu_docs.json \
      --cwd <records目录> [--sleep 1]

  feishu_plan.json: {"p01": {"file": "feishu-md/p01-xxx.md", "title": "..."}, ...}
  feishu_docs.json:  追加式状态文件，pNN -> {url, id, title}
                    已存在的 pNN 直接跳过（断点续跑：中断后重跑即续）

命令形态（实战坑）:
  lark-cli 的子命令是 "docs +create" 两个 token，subprocess 列表参数传
  会报 unknown command。必须 shell=True + shlex.quote 拼命令字符串，
  --content 的 @./ 路径是 cwd 相对路径，subprocess.run 需传 cwd。

产物: 逐篇打印创建结果；docs.json 每篇成功后立即落盘（中断不丢已建链接）。
失败篇目不写入 docs.json，重跑脚本自动重试。
退出码: 0 = plan 内全部创建完成; 1 = 有失败篇目。
"""
import argparse, json, os, shlex, subprocess, sys, time


def create_one(cwd, title, mfile, timeout=300):
    cmd = (f'lark-cli docs +create --doc-format markdown '
           f'--title {shlex.quote(title)} --content @{shlex.quote(mfile)}')
    r = subprocess.run(cmd, shell=True, cwd=cwd,
                       capture_output=True, text=True, timeout=timeout)
    raw = r.stdout + r.stderr
    try:
        d = json.loads(raw)
    except Exception:
        return None, raw[:300]
    if d.get('ok'):
        doc = d['data']['document']
        return {'url': doc['url'], 'id': doc['document_id'], 'title': title}, ''
    return None, json.dumps(d)[:300]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', required=True, help='feishu_plan.json')
    ap.add_argument('--docs', required=True, help='docs.json 状态文件（追加式）')
    ap.add_argument('--cwd', required=True, help='记录根目录（@./ 相对路径基准）')
    ap.add_argument('--sleep', type=float, default=1.0, help='每篇间隔秒数')
    ap.add_argument('--force', action='store_true',
                    help='忽略已有 docs.json 条目重新创建（默认跳过）')
    args = ap.parse_args()

    plan = json.load(open(args.plan))
    docs = json.load(open(args.docs)) if os.path.exists(args.docs) else {}
    if args.force:
        docs = {}

    # 校验 plan 里的文件都存在，防止 @./ 引用空路径
    missing = [v['file'] for v in plan.values()
               if not os.path.exists(os.path.join(args.cwd, v['file']))]
    if missing:
        print(f'MISSING files ({len(missing)}): {missing}', file=sys.stderr)
        sys.exit(1)

    fails = []
    for pk in sorted(plan):
        if pk in docs and not args.force:
            print(f'{pk}: exists -> {docs[pk]["url"]}')
            continue
        info = plan[pk]
        print(f'creating {pk} ...', flush=True)
        entry, err = create_one(args.cwd, info['title'], info['file'])
        if entry:
            docs[pk] = entry
            json.dump(docs, open(args.docs, 'w'), ensure_ascii=False, indent=1)
            print(f'  {pk} -> {entry["url"]}')
        else:
            fails.append(pk)
            print(f'  {pk} FAILED: {err}')
        time.sleep(args.sleep)

    print(f'--- total docs: {len(docs)}/{len(plan)} ---')
    if fails:
        print(f'FAILED ({len(fails)}): {", ".join(fails)}', file=sys.stderr)
        print('重跑本脚本即自动重试失败篇目（已创建的会跳过）', file=sys.stderr)
        sys.exit(1)
    print('all done')


if __name__ == '__main__':
    main()