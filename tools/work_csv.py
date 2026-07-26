#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据库连接数据(zp-data 月度工作安排)⇔ 按楼层拆分的 CSV(文件=楼层, 文件内按 EB/NB/MA 分组)。

导出:  python tools/work_csv.py export   → data-csv/work/<楼层>.csv
导入:  python tools/work_csv.py import   → 校验后重写 zp-data.global.js

CSV 列: 大区,小区,工作项,月份,序号,计划量,实际量,完成率%,单位,计划开始,计划结束,实际完成日期,标记
  - 每层一个文件, 行按 大区(EB/NB/MA)→小区→月份 排列;
  - 楼层按工作项名称归类(跨层段取上层, 如 "NB L1-L2 Steel Beam"→L2; 单层标注即该楼层);
  - 计划开始/计划结束: 默认=该月首末日, 可改成真实计划日期; 实际完成日期: 自行填写;
    三个日期都会存回数据文件并随导出往返保留;
  - 序号 = 该小区该月内的行顺序, 关系到网页上管理员手改值的对应, 请勿改动已有行的序号。
"""
import csv, json, re, sys, datetime, calendar
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT/'data-csv'/'work'
FLOORS = ['B2','B1','B1M','L1','L2','L3','L4','L5','其他']

def load_zp():
    t = (ROOT/'zp-data.global.js').read_text(encoding='utf-8')
    line = next(l for l in t.split('\n') if l.startswith('window.__RWS.ZP'))
    return json.loads(line[line.index('{'):line.rindex('}')+1].rstrip(';'))

def floor_of(w):
    w = str(w)
    m = re.search(r'L(\d)\s*-\s*L(\d)', w)
    if m: return f'L{max(int(m.group(1)), int(m.group(2)))}'
    if 'B1M' in w: return 'B1M'
    if re.search(r'\bB2\b', w): return 'B2'
    if re.search(r'\bB1\b', w): return 'B1'
    m = re.search(r'\bL(\d)\b', w)
    if m:
        return f'L{m.group(1)}'       # 错标L1的梁类已清除, 单层标注即真实楼层
    return '其他'

MONNUM={'January':1,'February':2,'March':3,'April':4,'May':5,'June':6,'July':7,'August':8,
        'September':9,'October':10,'November':11,'December':12}
def month_bounds(label):
    m=re.match(r'([A-Za-z]+)\s+(\d{4})',str(label))
    if not m or m.group(1) not in MONNUM: return ('','')
    y,mo=int(m.group(2)),MONNUM[m.group(1)]
    last=calendar.monthrange(y,mo)[1]
    return (f'{y:04d}-{mo:02d}-01', f'{y:04d}-{mo:02d}-{last:02d}')

def region_of(zp):
    r = {}
    for b in zp['buildings']:
        for z in b['zones']: r[z] = b['key'] if b['key'] != 'M' else 'MA'
    return r

def do_export():
    zp = load_zp(); reg = region_of(zp)
    rows_by_file = defaultdict(list)
    for zone in zp['plan']:
        area = reg.get(zone, '其他')
        for mon, items in zp['plan'][zone].items():
            for idx, it in enumerate(items):
                fl = floor_of(it.get('w',''))
                wname = str(it.get('w',''))
                marks = []
                if re.search(r'\bL1\b(?!\s*-)', wname) and ('Steel Beam' in wname or 'Main Beam' in wname):
                    marks.append('⚠原标注L1的梁类(规则: L1无梁; 确认误录请手动删除)')
                if it.get('tnote'): marks.append(it['tnote'])
                mark = ' ; '.join(marks)
                dft = month_bounds(mon)
                ps = it.get('ps') or dft[0]
                pf = it.get('pf') or dft[1]
                af = it.get('af') or ''
                rows_by_file[fl].append([
                    area, zone, wname, mon, idx,
                    '' if it.get('p') is None else it.get('p'),
                    '' if it.get('d') is None else it.get('d'),
                    '' if it.get('pct') is None else it.get('pct'),
                    it.get('u',''), ps, pf, af, mark])
    WORK.mkdir(parents=True, exist_ok=True)
    for old in WORK.glob('*.csv'): old.unlink()
    n = 0
    AREA_ORD = {'EB':0,'NB':1,'MA':2}
    for fl, rows in sorted(rows_by_file.items()):
        with open(WORK/f'{fl}.csv', 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(['大区','小区','工作项','月份','序号','计划量','实际量','完成率%','单位',
                        '计划开始','计划结束','实际完成日期','标记'])
            rows.sort(key=lambda r: (AREA_ORD.get(r[0], 9), r[1], r[3], r[4]))
            w.writerows(rows)
        n += 1
    print(f'导出完成: {n} 个楼层文件 → {WORK}(文件=楼层, 内按 EB/NB/MA 分组)')

def do_import():
    zp = load_zp(); reg = region_of(zp)
    months_ok = set(zp['months'])
    errors = []
    triples = {}          # (unused, kept)
    from collections import defaultdict as _dd
    seq_plan = _dd(lambda: _dd(list))   # zone -> mon -> [items]  (序号自动)
    for fp in sorted(WORK.glob('*.csv')):
        with open(fp, encoding='utf-8-sig') as f:
            for ln, row in enumerate(csv.DictReader(f), start=2):
                zone = (row.get('小区') or '').strip()
                if not zone: continue
                mon = (row.get('月份') or '').strip()
                wname = (row.get('工作项') or '').strip()
                if zone not in reg and zone not in zp['plan']:
                    errors.append(f'{fp.name} 第{ln}行: 小区 "{zone}" 不在楼栋分组里 — 跳过'); continue
                if mon not in months_ok:
                    errors.append(f'{fp.name} 第{ln}行: 月份 "{mon}" 不合法 — 跳过'); continue
                # 序号忽略CSV填的值, 按读取顺序自动分配(彻底避免序号冲突)
                idx = None
                def num(col):
                    v = (row.get(col) or '').strip().replace(',','')
                    if v in ('','—','-'): return None
                    try: return int(v) if float(v)==int(float(v)) else round(float(v),2)
                    except ValueError:
                        errors.append(f'{fp.name} 第{ln}行 {col}: "{v}" 不是数字 — 置空'); return None
                it = {'w': wname, 'p': num('计划量'), 'd': num('实际量'),
                      'u': (row.get('单位') or '').strip(), 'pct': num('完成率%')}
                for col, fld in [('计划开始','ps'), ('计划结束','pf'), ('实际完成日期','af')]:
                    v = (row.get(col) or '').strip()
                    if v:
                        try:
                            datetime.date.fromisoformat(v)
                            it[fld] = v
                        except ValueError:
                            errors.append(f'{fp.name} 第{ln}行 {col}: "{v}" 应为 YYYY-MM-DD — 跳过该格')
                seq_plan[zone][mon].append(it)
    plan = {}
    for zone in sorted(seq_plan):
        plan[zone] = {}
        for mon in seq_plan[zone]:
            plan[zone][mon] = seq_plan[zone][mon]  # 序号=列表顺序, 自动0..n连续
    if errors:
        print(f'✗ 发现 {len(errors)} 个问题, 未写入任何数据(修正后重跑):')
        for e in errors[:30]: print('   ', e)
        sys.exit(1)
    zp['plan'] = plan
    blob = json.dumps(zp, ensure_ascii=False, separators=(',',':'))
    g = (ROOT/'zp-data.global.js').read_text(encoding='utf-8').split('\n')
    gi = next(i for i,l in enumerate(g) if l.startswith('window.__RWS.ZP'))
    g[gi] = 'window.__RWS.ZP = ' + blob + ';'
    (ROOT/'zp-data.global.js').write_text('\n'.join(g), encoding='utf-8')
    # ---- 额外: 把柱/桩/梁/板类计划量灌进活动区(zone-activity.csv) ----
    try:
        _gen_zone_activity(plan)
    except Exception as _e:
        print('  (活动区灌入跳过:', _e, ')')
    n = sum(len(v) for z in plan.values() for v in z.values())
    print(f'✔ 导入完成: {len(plan)} 个小区, {n} 条工作安排 → zp-data.js / zp-data.global.js 已同步; 刷新网页生效')


_M2ABBR={'January':"Jan",'February':"Feb",'March':"Mar",'April':"Apr",'May':"May",'June':"Jun",'July':"Jul",'August':"Aug",'September':"Sep",'October':"Oct",'November':"Nov",'December':"Dec"}
def _month_to_act(mon):
    import re
    m=re.match(r'([A-Za-z]+)\s+(\d{4})',str(mon))
    if not m or m.group(1) not in _M2ABBR: return None
    return f"{_M2ABBR[m.group(1)]}'{m.group(2)[2:]}"

def _work_to_aid(w):
    wl=str(w).lower()
    if 'column' in wl: return 'col'
    if 'pile' in wl or 'cap' in wl: return 'pile'
    if 'steel' in wl and 'beam' in wl: return 'sbeam'
    if 'main beam' in wl or ('beam' in wl and 'steel' not in wl and 'core' not in wl): return 'mbeam'
    if 'core' in wl and 'wall' in wl: return 'act_corewall'
    if 'slab' in wl or 'demolition' in wl: return None  # slab/demo走台账, 不进活动区柱桩梁
    return None

def _load_zone_map():
    import json, re
    t=(ROOT/'zone-data.global.js').read_text(encoding='utf-8')
    line=next(l for l in t.split('\n') if l.startswith('window.__RWS.DATA'))
    D=json.loads(line[line.index('{'):line.rindex('}')+1].rstrip(';'))
    def norm(s): return re.sub(r'[^a-z0-9]','',str(s).lower())
    web={}
    for lv in D['levels']:
        for z in D['levels'][lv]['zones']:
            mk=z.get('mk')
            for nm in [z['label']]+[s.get('n') for s in z.get('sub',[]) if s.get('n')]:
                web[norm(nm)]=(lv,mk)
            web[norm(mk)]=(lv,mk)
    pod2slab={'POD2.1T':'SLAB 7-2','POD2.1':'SLAB 7-1','POD2.1CIST':'SLAB 7-4','POD2.1CIS':'SLAB 7-3','POD2.2T':'SLAB 8-2','POD2.2':'SLAB 8-1','POD2.3T':'SLAB 13 (F01-1)','POD2.3CIST':'SLAB 13 (F01-2)','POD2.4T':'SLAB 8A-2','POD2.4':'SLAB 8A-1','POD2.6CIST':'SLAB 10-2','POD2.6CIS':'SLAB 10-1','POD4.1 CIST':'SLAB B-2.1','POD4.1CIST':'SLAB B-2.1','POD4.1':'SLAB B-2.2','POD4.1CIS':'SLAB B-2.2','POD4.2':'SLAB B-2.3','POD4.2T':'SLAB B-2.4','POD4.3T':'SLAB B-3.2','POD4.3CIST':'SLAB B-3.1','POD4.4':'SLAB B-3.3'}
    return web, pod2slab, norm

def _gen_zone_activity(plan):
    import csv as _csv
    web, pod2slab, norm = _load_zone_map()
    rows=[]; hit=0; miss=set()
    for zone in plan:
        n=norm(zone); lvmk=web.get(n)
        if not lvmk and zone in pod2slab: lvmk=web.get(norm(pod2slab[zone]))
        for mon, items in plan[zone].items():
            am=_month_to_act(mon)
            for it in items:
                aid=_work_to_aid(it.get('w',''))
                if not aid or am is None: continue
                p=it.get('p')
                if p is None: continue
                if not lvmk: miss.add(zone); continue
                lv,mk=lvmk
                ps=it.get('ps') or ''; pf=it.get('pf') or ''
                rows.append([lv,mk,aid,am,p,ps,pf]); hit+=1
    out=ROOT/'data-csv'/'fixed'/'zone-activity.csv'
    with open(out,'w',newline='',encoding='utf-8-sig') as f:
        w=_csv.writer(f)
        w.writerow(['楼层','分区','活动','月份','计划量','活动开始','活动结束'])
        w.writerows(rows)
    print(f'  ✔ 活动区: 灌入{hit}条柱/桩/梁计划 → zone-activity.csv (映射不了的分区{len(miss)}个)')

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == 'export': do_export()
    elif mode == 'import': do_import()
    else: print(__doc__)
