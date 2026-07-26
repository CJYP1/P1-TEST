#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一 data-csv/fixed/zone-activity/*.csv 里的"活动开始/活动结束"日期格式为 YYYY-MM-DD。

用途: 从 Excel 填完数据导出 CSV 后, 日期经常被 Excel 转成 1/3/2027、2027/1/3 之类的
本地格式 —— build.py 只认 YYYY-MM-DD, 格式不对不会报错但会导致该行日期读取出错。
上传/推送前先跑一遍这个脚本, 自动把常见日期格式统一转好, 有无法识别的格式会打印警告
（不会漏改也不会瞎改, 无法识别的原样保留, 需要你手工看一眼）。

用法:
  python tools/normalize_dates.py            # 直接修改 data-csv/fixed/zone-activity/*.csv
  python tools/normalize_dates.py --check     # 只检查不写入, 报告有多少处会被改
"""
import csv, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZA_DIR = ROOT / 'data-csv' / 'fixed' / 'zone-activity'


def normalize(s: str) -> str:
    s = s.strip()
    if not s or s in ('-', '—'):
        return ''
    # 已经是 YYYY-MM-DD (只是可能缺前导 0)
    m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', s)
    if m:
        y, mo, d = m.groups()
        return f'{int(y):04d}-{int(mo):02d}-{int(d):02d}'
    # D/M/YYYY 或 M/D/YYYY (Excel 常见, 有歧义时按 日/月/年 处理 —— 与新加坡地区设置一致)
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', s)
    if m:
        a, b, y = m.groups()
        a, b = int(a), int(b)
        if a > 12:
            d, mo = a, b
        elif b > 12:
            mo, d = a, b
        else:
            d, mo = a, b  # 歧义情况按 日/月/年
        return f'{y}-{mo:02d}-{d:02d}'
    # YYYY/M/D
    m = re.match(r'^(\d{4})/(\d{1,2})/(\d{1,2})$', s)
    if m:
        y, mo, d = m.groups()
        return f'{y}-{int(mo):02d}-{int(d):02d}'
    # D-M-YYYY 或 D.M.YYYY
    m = re.match(r'^(\d{1,2})[.\-](\d{1,2})[.\-](\d{4})$', s)
    if m:
        d, mo, y = m.groups()
        return f'{y}-{int(mo):02d}-{int(d):02d}'
    print(f'  ⚠ 无法识别的日期格式 "{s}" — 已原样保留, 请手工检查', file=sys.stderr)
    return s


def main():
    check_only = '--check' in sys.argv
    if not ZA_DIR.exists():
        sys.exit(f'找不到 {ZA_DIR}')

    total_changed = 0
    for path in sorted(ZA_DIR.glob('*.csv')):
        with open(path, encoding='utf-8-sig') as f:
            r = csv.reader(f)
            header = next(r)
            rows = list(r)

        changed = 0
        for row in rows:
            if len(row) < 9:
                continue
            for idx in (7, 8):  # 活动开始, 活动结束
                old = row[idx]
                new = normalize(old)
                if new != old:
                    row[idx] = new
                    changed += 1

        if changed and not check_only:
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.writer(f)
                w.writerow(header)
                for row in rows:
                    w.writerow(row)

        tag = '(会修改)' if check_only and changed else ('(已写入)' if changed else '(无需改动)')
        print(f'{path.name}: {changed} 处 {tag}')
        total_changed += changed

    print(f'\n共 {total_changed} 处日期已' + ('待修改(--check 模式, 未写入)' if check_only else '统一为 YYYY-MM-DD'))


if __name__ == '__main__':
    main()
