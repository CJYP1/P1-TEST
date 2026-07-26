#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 L1 违规元素标记清单(规则: 一楼没有主梁/钢梁)。

扫描当前生效数据(zone-data.global.js / zp-data.global.js),把出现在 L1 的
梁类元素逐条列出 → data-csv/fixed/L1-remove-list.csv,供人工核对后手动删除。
本工具只标记, 不改任何数据。   运行: python tools/mark_l1.py
"""
import json, re, csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def load(fn, var):
    t = (ROOT/fn).read_text(encoding='utf-8')
    line = next(l for l in t.split('\n') if l.startswith(var))
    return json.loads(line[line.index('{'):line.rindex('}')+1].rstrip(';'))

ZD = load('zone-data.global.js', 'window.__RWS.DATA')
ZP = load('zp-data.global.js', 'window.__RWS.ZP')
rows = []

# 1. 图上台账: L1 分区的主梁/钢梁计数与梁构件明细
for z in ZD['levels'].get('L1', {}).get('zones', []):
    c = z.get('counts') or {}
    for k, lab in [('mainbeam','主梁计数'), ('steelbeam','钢梁计数')]:
        if c.get(k):
            rows.append(['zone-data.global.js', f'DATA.levels.L1.zones[label="{z["label"]}"].counts.{k}',
                         'L1', z['label'], lab, c[k], 'L1 不应有梁 — 请人工核对后删除/清零'])
    for b in (z.get('beams') or []):
        rows.append(['zone-data.global.js', f'DATA.levels.L1.zones[label="{z["label"]}"].beams[id="{b.get("id","")}"]',
                     'L1', z['label'], '梁构件', f'{b.get("id","")} {b.get("sz","")}', 'L1 不应有梁 — 请人工核对后删除'])

# 2. 登记台账: 仅 L1 的分区却登记了梁
for k, q in ZP['qty'].items():
    lv = q.get('levels') or []
    beam = q.get('beam') or {}
    if lv == ['L1'] and (beam.get('nos') or beam.get('sbNos') or beam.get('beams')):
        rows.append(['zp-data.global.js', f'ZP.qty["{k}"].beam',
                     'L1', k, '登记表梁数量', f"主梁nos={beam.get('nos',0)}, 钢梁sbNos={beam.get('sbNos',0)}, 明细{len(beam.get('beams') or [])}条",
                     'levels仅L1却登记了梁 — 请人工核对后删除'])
        for b in (beam.get('beams') or []):
            bid = b.get('id','') if isinstance(b, dict) else str(b)
            rows.append(['zp-data.global.js', f'ZP.qty["{k}"].beam.beams[id="{bid}"]',
                         'L1', k, '登记表梁构件', bid, 'levels仅L1却登记了梁 — 请人工核对后删除'])

# 3. 月度工作安排: 工作项名标注 L1 的梁类(单层名, 非 L1-L2 段)
for zn, ms in ZP['plan'].items():
    for mon, items in ms.items():
        for idx, it in enumerate(items):
            w = str(it.get('w',''))
            if re.search(r'\bL1\b(?!\s*-)', w) and ('Steel Beam' in w or 'Main Beam' in w):
                rows.append(['zp-data.global.js', f'ZP.plan["{zn}"]["{mon}"][{idx}]',
                             'L1标注', zn, '工作项', f'{w} (计划{it.get("p","")}{it.get("u","")})',
                             '梁类标注为L1 — 工作CSV已按实际楼层归档并打⚠标; 确认误录后手动删除'])

# 排除用户确认为正确的条目 (L1-confirmed-ok.csv, 按 位置+数值 匹配)
ok_file = ROOT/'data-csv'/'fixed'/'L1-confirmed-ok.csv'
if ok_file.exists():
    import csv as _csv
    ok = set()
    with open(ok_file, encoding='utf-8-sig') as f:
        rd = _csv.reader(f); next(rd, None)
        for r in rd:
            if len(r) >= 6: ok.add((r[1], r[5]))
    before = len(rows)
    rows = [r for r in rows if (r[1], r[5]) not in ok]
    print(f'已排除确认正确的 {before-len(rows)} 条 (L1-confirmed-ok.csv)')

out = ROOT/'data-csv'/'fixed'/'L1-remove-list.csv'
with open(out, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['来源文件','位置(程序键)','楼层','分区','类型','数值/名称','说明'])
    w.writerows(rows)
print(f'L1 标记清单: {len(rows)} 条 → {out}')
