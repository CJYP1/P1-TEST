#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""以最终基准 JSON(RWS_P1_CJ_full_import_aligned_final.json)更新整个系统。

推送内容(工作 / 区域 / 数量 / 时间 全部推入):
  1. 区域面板原生数据 → 三个 CSV(build 后直接进页面, 无需手工导入):
       data-csv/fixed/zone-activity.csv    每分区每活动: 月份+计划量+活动起止日期
       data-csv/fixed/zone-plan-dates.csv  每分区: 区域计划开始/结束
       data-csv/fixed/col-month.csv        逐根柱构件的目标月份
  2. 月度工作安排(zp-data)对账: 活动起止时间以 JSON 为准, 不一致处直接改 ps/pf;
     计划量p/实际量d/完成率pct 一律不动(月度显示与后续实际量更新不受影响)。
  3. 推不上去的条目 → data-csv/fixed/conflicts.csv 标记(页面没有的楼层图 L3/L4/L5/Deck、
     分区不存在等), 供人工验证。

运行: python tools/push_final.py   (JSON 在 data-csv/source/ 下; 之后跑 build.py + work_csv.py export)
"""
import json, re, csv, datetime
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT/'data-csv'/'source'/'RWS_P1_CJ_full_import_aligned_final.json'
FIX = ROOT/'data-csv'/'fixed'

J = json.loads(SRC.read_text(encoding='utf-8'))
CS = J['current_state']

def load(fn, var):
    t = (ROOT/fn).read_text(encoding='utf-8')
    line = next(l for l in t.split('\n') if l.startswith(var))
    return json.loads(line[line.index('{'):line.rindex('}')+1].rstrip(';'))

ZD = load('zone-data.global.js', 'window.__RWS.DATA')
APP = {lv: {str(z.get('mk') or z.get('lid')) for z in o.get('zones', [])}
       for lv, o in ZD['levels'].items()}

ACT_MONTHS = {"Before Apr'26","Apr'26","May'26","Jun'26","Jul'26","Aug'26","Sep'26","Oct'26",
              "Nov'26","Dec'26","Jan'27","Feb'27","Mar'27","Apr'27","May'27"}
ACT_LABEL = {'col':'Columns','pile':'Pile Caps','mbeam':'Steel Main Beams','cbeam':'Cast S Main Beams',
             'ls':'Lift/Stairs','exc':'Excavation','demo':'Demolition','slab':'Cast Slab','sbeam':'Steel Beams',
             'act_wall':'Wall','act_corewall':'Core Wall'}

conflicts = []   # [来源, 楼层, 分区, 活动/构件, 月份, 数值, 开始, 结束, 原因]

def ok_zone(lv, zmk): return zmk in APP.get(lv, set())

# ---------- 1) 区域面板 CSV ----------
acts = defaultdict(dict)   # (lv, zmk, act) -> {'months': {mon: qty}, 'start':, 'end':}
for k, v in CS.get('act_plan', {}).items():
    lv, zmk, aid, mon = k.split('||')
    if not ok_zone(lv, zmk):
        conflicts.append(['act_plan(活动计划量)', lv, zmk.split('|',1)[-1], ACT_LABEL.get(aid, aid), mon, v, '', '',
                          '页面无该楼层图/分区, 推不上去 — 需人工确认归属'])
        continue
    if mon not in ACT_MONTHS:
        conflicts.append(['act_plan(活动计划量)', lv, zmk.split('|',1)[-1], ACT_LABEL.get(aid, aid), mon, v, '', '',
                          '月份不在系统月份表中, 推不上去'])
        continue
    acts[(lv, zmk, aid)].setdefault('months', {})[mon] = v
for k, v in CS.get('act_date', {}).items():
    lv, zmk, aid = k.split('||')
    if not ok_zone(lv, zmk):
        conflicts.append(['act_date(活动起止)', lv, zmk.split('|',1)[-1], ACT_LABEL.get(aid, aid), '', '',
                          v.get('start',''), v.get('end',''), '页面无该楼层图/分区, 推不上去 — 需人工确认归属'])
        continue
    acts[(lv, zmk, aid)]['start'] = v.get('start','')
    acts[(lv, zmk, aid)]['end'] = v.get('end','')

with open(FIX/'zone-activity.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['楼层','分区','活动','月份','计划量','活动开始','活动结束'])
    n_act = 0
    for (lv, zmk, aid) in sorted(acts, key=lambda t: (t[0], t[1], t[2])):
        a = acts[(lv, zmk, aid)]
        mons = a.get('months') or {'': ''}
        for mon, qty in sorted(mons.items()):
            w.writerow([lv, zmk, aid, mon, qty, a.get('start',''), a.get('end','')])
            n_act += 1

zd_rows = []
for k, v in CS.get('zone_dates', {}).items():
    lv, zmk = k.split('||')
    if ok_zone(lv, zmk):
        zd_rows.append([lv, zmk, v.get('start',''), v.get('end','')])
with open(FIX/'zone-plan-dates.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['楼层','分区','计划开始','计划结束'])
    w.writerows(sorted(zd_rows))

cm_rows = []
for k, mon in CS.get('col_month', {}).items():
    lv, zmk, cat, elem = k.split('||')
    if not ok_zone(lv, zmk):
        conflicts.append(['col_month(柱目标月)', lv, zmk.split('|',1)[-1], elem, mon, '', '', '',
                          '页面无该楼层图/分区, 推不上去'])
        continue
    if mon not in ACT_MONTHS:
        conflicts.append(['col_month(柱目标月)', lv, zmk.split('|',1)[-1], elem, mon, '', '', '',
                          '月份不在系统月份表中, 推不上去'])
        continue
    cm_rows.append([lv, zmk, cat, elem, mon])
with open(FIX/'col-month.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['楼层','分区','类别','构件','月份'])
    w.writerows(sorted(cm_rows))

# ---------- 2) 月度工作安排(zp-data)时间对账: JSON 为准 ----------
t = (ROOT/'zp-data.global.js').read_text(encoding='utf-8')
lines = t.split('\n')
gi = next(i for i, l in enumerate(lines) if l.startswith('window.__RWS.ZP'))
ZP = json.loads(lines[gi][lines[gi].index('{'):lines[gi].rindex('}')+1].rstrip(';'))
zp_zones = {z for b in ZP['buildings'] for z in b['zones']} | set(ZP['plan'])

def norm(z): return re.sub(r'[\s\-()]', '', str(z).strip()).upper()
xref_group = {}
with open(FIX/'zone-xref.csv', encoding='utf-8-sig') as f:
    rd = csv.reader(f); next(rd)
    for row in rd:
        if len(row) >= 5 and row[0].strip():
            xref_group[norm(row[4])] = row[0].strip()
def group_of(name):
    n = norm(name)
    for c in (n, 'POD'+n, n[3:] if n.startswith('POD') else None, 'P'+n, n[1:] if n.startswith('P') else None):
        if c and c in xref_group: return xref_group[c]
    return None

def type_of_label(wname):
    wname = str(wname)
    if 'Steel Beam' in wname: return 'sbeam'
    if 'Main Beam' in wname: return 'mbeam'
    if 'Column' in wname: return 'col'
    if 'Core Wall' in wname: return 'act_corewall'
    if 'Wall' in wname: return 'act_wall'
    if 'Lift/Stair' in wname or 'Lift / Stair' in wname: return 'ls'
    if 'Top Slab' in wname or 'Slab' in wname: return 'slab'
    if 'Demoli' in wname: return 'demo'
    if 'Pilecap' in wname or 'Pile Cap' in wname: return 'pile'
    if 'Excavat' in wname: return 'exc'
    return None
def floor_of_label(wname):
    wname = str(wname)
    m = re.search(r'L(\d)\s*-\s*L(\d)', wname)
    if m: return f'L{max(int(m.group(1)),int(m.group(2)))}'
    if 'B1M' in wname: return 'B1M'
    if re.search(r'\bB2\b', wname): return 'B2'
    if re.search(r'\bB1\b', wname): return 'B1'
    m = re.search(r'\bL(\d)\b', wname)
    return f'L{m.group(1)}' if m else '其他'

# 系统条目索引: (组, 楼层, 类型) -> [item]
items_by = defaultdict(list)
for zn, ms in ZP['plan'].items():
    g = group_of(zn)
    for mon, its in ms.items():
        for it in its:
            items_by[(g, floor_of_label(it.get('w','')), type_of_label(it.get('w','')))].append(it)

TOWER = re.compile(r'^\d|^P\d')
SHIFT = {'L1':'L2','L2':'L3','L3':'L4','L4':'L5'}
STRUCT = {'col','mbeam','sbeam','act_wall','act_corewall','ls'}
def target_floor(lv, zpart, aid):
    if aid in STRUCT and lv in SHIFT and TOWER.match(norm(zpart)): return SHIFT[lv]
    return lv

n_upd = n_same = 0
seen_updates = []
for k, v in CS.get('act_date', {}).items():
    lv, zmk, aid = k.split('||')
    zpart = zmk.split('|', 1)[-1]
    g = group_of(zpart)
    if g is None: continue                      # 面板已收录; 月度表无从对应, 不算冲突
    fl = target_floor(lv, zpart, aid)
    cand = items_by.get((g, fl, aid), [])
    if not cand: continue
    s, e = v.get('start',''), v.get('end','')
    if not s and not e: continue
    for it in cand:
        if it.get('ps') != s or it.get('pf') != e:
            it['ps'], it['pf'] = s, e
            if it.get('tnote') in ('无Excel排程',): it['tnote'] = ''
            n_upd += 1
            seen_updates.append(f"{g}/{fl}/{aid}: {it.get('w','')}")
        else:
            n_same += 1

# zone_dates 兜底: 楼层图上没有的 L3/L4/L5/Deck 区域时间 → 该组该楼层仍无真实日期的条目
def month_bounds(mon_label):
    MON = {'January':1,'February':2,'March':3,'April':4,'May':5,'June':6,'July':7,'August':8,
           'September':9,'October':10,'November':11,'December':12}
    m = re.match(r'([A-Za-z]+)\s+(\d{4})', str(mon_label))
    if not m or m.group(1) not in MON: return None
    import calendar as _c
    y, mo = int(m.group(2)), MON[m.group(1)]
    return (f'{y:04d}-{mo:02d}-01', f'{y:04d}-{mo:02d}-{_c.monthrange(y,mo)[1]:02d}')

items_with_mon = defaultdict(list)   # (组, 楼层) -> [(mon, item)]
for zn, ms in ZP['plan'].items():
    g = group_of(zn)
    for mon, its in ms.items():
        for it in its:
            items_with_mon[(g, floor_of_label(it.get('w','')))].append((mon, it))

n_zd = 0
zd_unpushed = []
for k, v in CS.get('zone_dates', {}).items():
    lv, zmk = k.split('||')
    if ok_zone(lv, zmk): continue               # 已进面板
    zpart = zmk.split('|', 1)[-1]
    g = group_of(zpart)
    pushed = False
    if g is not None:
        for mon, it in items_with_mon.get((g, lv), []):
            mb = month_bounds(mon)
            if mb and (it.get('ps'), it.get('pf')) == mb:   # 仍是默认月首末日 = 无真实日期
                it['ps'], it['pf'] = v.get('start',''), v.get('end','')
                if it.get('tnote') == '无Excel排程': it['tnote'] = '依区域时间(基准JSON)'
                n_zd += 1; pushed = True
        if items_with_mon.get((g, lv)): pushed = True       # 有对应条目(已带真实日期)也算已覆盖
    if not pushed:
        zd_unpushed.append(k)
        conflicts.append(['zone_dates(区域起止)', lv, zpart, '', '', '',
                          v.get('start',''), v.get('end',''),
                          '页面无该楼层图且月度表无对应条目, 推不上去 — 需人工确认'])

# 写回 zp-data
lines[gi] = 'window.__RWS.ZP = ' + json.dumps(ZP, ensure_ascii=False, separators=(',',':')) + ';'
(ROOT/'zp-data.global.js').write_text('\n'.join(lines), encoding='utf-8')

# ---------- 3) conflicts.csv ----------
with open(FIX/'conflicts.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['来源','楼层','分区','活动/构件','月份','数值','开始','结束','原因'])
    w.writerows(conflicts)

print(f'区域面板: 活动行 {n_act} 条 → zone-activity.csv; 区域起止 {len(zd_rows)} 条 → zone-plan-dates.csv; '
      f'柱目标月 {len(cm_rows)} 条 → col-month.csv')
print(f'月度表对账(JSON为准): 改写 ps/pf {n_upd} 处, 原已一致 {n_same} 处, 区域时间兜底 {n_zd} 处 (p/d/pct 未动)')
print(f'推不上去标记: {len(conflicts)} 条 → conflicts.csv')
