#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分区名称 <-> app 键 转换器。

对照表: data-csv/fixed/zone-xref.csv (名称name 列 <-> mk键 列)
  名称 "B2-S2-2"  <->  mk键 "B2|B2S22"  <->  app 键 "B2||B2S22"

用法:
  # 1) 单个/多个名称直接转 (命令行参数)
  python tools/zone_convert.py "B2-S2-2" "B2-S8a"

  # 2) 从文件读, 每行一个名称, 输出 名称 -> app键 的对照
  python tools/zone_convert.py --file mynames.txt

  # 3) 把某个 CSV 里指定列的分区名整列替换成 app 键, 另存新文件
  python tools/zone_convert.py --replace-csv in.csv --col 分区 --out out.csv

输出的 app 键默认是双竖线 "B2||B2S22" (系统内部格式)。
加 --single 则输出单竖线 "B2|B2S22" (跟 zone-xref 的 mk键 列一致)。
加 --mk-only 则只输出 mk "B2S22" (不含楼层)。
"""
import csv, sys, argparse, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
XREF = ROOT / 'data-csv' / 'fixed' / 'zone-xref.csv'

def _norm(s):
    """宽松归一化: 去空格、转大写、去掉连字符, 方便容错匹配。"""
    return re.sub(r'\s+', '', str(s or '')).upper().replace('-', '')

def load_xref():
    """返回: name2key(名称->(level,mk)), norm2key(归一化名->(level,mk)), aliases(别名集合)。"""
    name2key, norm2key, aliases = {}, {}, {}
    with open(XREF, encoding='utf-8-sig') as f:
        rd = csv.DictReader(f)
        for row in rd:
            typ = (row.get('类型type') or '').strip()
            name = (row.get('名称name') or '').strip()
            mkcol = (row.get('mk键') or '').strip()   # 形如 "B2|B2S22"
            level = (row.get('楼层level') or '').strip()
            if not name:
                continue
            if typ == '别名' or not mkcol:
                # 别名/组合区: 没有单独的 mk 键
                aliases[name] = row.get('组号group', '').strip()
                aliases[_norm(name)] = row.get('组号group', '').strip()
                continue
            if '|' in mkcol:
                lv, mk = mkcol.split('|', 1)
            else:
                lv, mk = level, mkcol
            name2key[name] = (lv, mk)
            norm2key[_norm(name)] = (lv, mk)
    return name2key, norm2key, aliases

def fmt(lv, mk, mode):
    if mode == 'mk':     return mk
    if mode == 'single': return f'{lv}|{mk}'
    return f'{lv}||{mk}'   # 默认 double

def convert(name, name2key, norm2key, aliases, mode='double'):
    name = str(name).strip()
    if name in name2key:
        return fmt(*name2key[name], mode), 'ok'
    n = _norm(name)
    if n in norm2key:
        return fmt(*norm2key[n], mode), 'ok(归一化匹配)'
    if name in aliases or n in aliases:
        return '', '别名/组合区(无单独mk键)'
    return '', '未找到'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('names', nargs='*')
    ap.add_argument('--file')
    ap.add_argument('--replace-csv')
    ap.add_argument('--col')
    ap.add_argument('--out')
    ap.add_argument('--single', action='store_true')
    ap.add_argument('--mk-only', action='store_true')
    a = ap.parse_args()
    mode = 'single' if a.single else ('mk' if a.mk_only else 'double')
    name2key, norm2key, aliases = load_xref()

    if a.replace_csv:
        if not a.col:
            sys.exit('--replace-csv 需要同时指定 --col 列名')
        out = a.out or (a.replace_csv.rsplit('.', 1)[0] + '_converted.csv')
        miss = []
        with open(a.replace_csv, encoding='utf-8-sig') as f:
            rd = csv.DictReader(f); rows = list(rd); cols = rd.fieldnames
        if a.col not in cols:
            sys.exit(f'列 "{a.col}" 不存在。可用列: {cols}')
        for r in rows:
            key, status = convert(r[a.col], name2key, norm2key, aliases, mode)
            if status.startswith('ok'):
                r[a.col] = key
            else:
                miss.append((r[a.col], status))
        with open(out, 'w', encoding='utf-8-sig', newline='') as f:
            wr = csv.DictWriter(f, fieldnames=cols); wr.writeheader(); wr.writerows(rows)
        print(f'已写出: {out} ({len(rows)} 行)')
        if miss:
            print(f'⚠ {len(miss)} 个未能转换:')
            for name, st in miss[:50]:
                print(f'   {name}  — {st}')
        return

    names = list(a.names)
    if a.file:
        names += [ln.strip() for ln in Path(a.file).read_text(encoding='utf-8').splitlines() if ln.strip()]
    if not names:
        sys.exit('请给出要转换的名称(命令行参数 / --file / --replace-csv)')
    ok = miss = 0
    for name in names:
        key, status = convert(name, name2key, norm2key, aliases, mode)
        print(f'{name:<20} -> {key or "—":<16} {status}')
        ok += status.startswith('ok'); miss += (not status.startswith('ok'))
    print(f'\n共 {len(names)} 个: 成功 {ok}, 未成功 {miss}')

if __name__ == '__main__':
    main()
