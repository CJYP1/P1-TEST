#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 generated/ 下的两个注入 bundle(改完源文件后运行本脚本, 刷新网页生效)。

  app/component.js                    → generated/app.bundle.js
  presentation/report-embed.html      ┐
  presentation/report-linked-template.html ├→ generated/embeds.bundle.js
  presentation/zone-lookup.html       │   (三个内嵌页面 + 分区对照表)
  data-csv/fixed/zone-xref.csv        ┘

用法: python tools/build.py   (或双击 build.bat)
"""
import json, base64, csv, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------- app bundle ----------
src = (ROOT/'app'/'component.js').read_text(encoding='utf-8')
if 'class Component' not in src[:200]:
    sys.exit('app/component.js 不是以 class Component 开头 — 请检查文件')
app_bundle = (
    "/* GENERATED — 请勿手改。源码: app/component.js ; 重新生成: python tools/build.py */\n"
    "var __DC_APP_SRC = " + json.dumps(src, ensure_ascii=False) + ";\n"
    "(function(){\n"
    "  if (document.querySelector('script[type=\"text/x-dc\"][data-dc-script]')) return;\n"
    "  var el = document.createElement('script');\n"
    "  el.type = 'text/x-dc'; el.setAttribute('data-dc-script','');\n"
    "  el.textContent = __DC_APP_SRC;\n"
    "  var cur = document.currentScript;\n"
    "  if (cur && cur.parentNode) cur.parentNode.insertBefore(el, cur.nextSibling);\n"
    "  else document.body.appendChild(el);\n"
    "})();\n")
(ROOT/'generated'/'app.bundle.js').write_text(app_bundle, encoding='utf-8')

# ---------- embeds bundle ----------
def b64(p): return base64.b64encode((ROOT/p).read_bytes()).decode()
rpl = b64('presentation/report-linked-template.html')
rpb = b64('presentation/report-embed.html')
zlk = b64('presentation/zone-lookup.html')

# zone-xref.csv → JSON(与原内嵌结构一致: 组列表, 每组 {B2..L2:{a:[{n,mk}],x:[]}, area})
groups = {}
order = []
with open(ROOT/'data-csv'/'fixed'/'zone-xref.csv', encoding='utf-8-sig') as f:
    rd = csv.DictReader(f)
    cols = rd.fieldnames
    g_c, a_c, l_c, t_c, n_c, m_c = cols[0], cols[1], cols[2], cols[3], cols[4], cols[5]
    for row in rd:
        gi = row[g_c].strip()
        if not gi: continue
        if gi not in groups:
            groups[gi] = {lv: {'a': [], 'x': []} for lv in ['B2','B1','B1M','L1','L2']}
            groups[gi]['area'] = row[a_c].strip()
            order.append(gi)
        lv = row[l_c].strip()
        if lv not in groups[gi]:
            sys.exit(f'zone-xref.csv: 未知楼层 "{lv}"(组 {gi})— 只允许 B2/B1/B1M/L1/L2')
        if row[t_c].strip() == '分区':
            groups[gi][lv]['a'].append({'n': row[n_c].strip(), 'mk': row[m_c].strip()})
        else:
            groups[gi][lv]['x'].append(row[n_c].strip())
zx = [groups[g] for g in order]
zx_json = json.dumps(zx, ensure_ascii=False, separators=(', ', ': '))

# zone-activity / zone-plan-dates / col-month → locked-data 种子(基准数据进区域面板)
seed = {}
za = ROOT/'data-csv'/'fixed'/'zone-activity.csv'
if za.exists():
    ap, ad, adm = {}, {}, {}
    with open(za, encoding='utf-8-sig') as f:
        rd = csv.DictReader(f)
        for row in rd:
            lv, zmk, aid = row['楼层'].strip(), row['分区'].strip(), row['活动'].strip()
            if not lv or not zmk or not aid: continue
            mon = (row.get('月份') or '').strip()
            qty = (row.get('计划量') or '').strip().replace(',','')
            if mon and qty not in ('','—','-'):
                try: v = float(qty); v = int(v) if v == int(v) else v
                except ValueError: sys.exit(f'zone-activity.csv: {lv}/{zmk}/{aid}/{mon} 计划量 "{qty}" 不是数字')
                ap[f'{lv}||{zmk}||{aid}||{mon}'] = v
            done = (row.get('完成量') or '').strip().replace(',','')
            if mon and done not in ('','—','-'):
                try: dv = float(done); dv = int(dv) if dv == int(dv) else dv
                except ValueError: sys.exit(f'zone-activity.csv: {lv}/{zmk}/{aid}/{mon} 完成量 "{done}" 不是数字')
                adm[f'{lv}||{zmk}||{aid}||{mon}'] = dv
            s, e = (row.get('活动开始') or '').strip(), (row.get('活动结束') or '').strip()
            if s or e:
                o = {}
                if s: o['start'] = s
                if e: o['end'] = e
                ad[f'{lv}||{zmk}||{aid}'] = o
    if ap: seed['actPlan'] = ap
    if ad: seed['actDate'] = ad
    if adm: seed['actDoneM'] = adm
zpd = ROOT/'data-csv'/'fixed'/'zone-plan-dates.csv'
if zpd.exists():
    zd = {}
    with open(zpd, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            lv, zmk = row['楼层'].strip(), row['分区'].strip()
            if not lv or not zmk: continue
            o = {}
            if (row.get('计划开始') or '').strip(): o['start'] = row['计划开始'].strip()
            if (row.get('计划结束') or '').strip(): o['end'] = row['计划结束'].strip()
            if o: zd[f'{lv}||{zmk}'] = o
    if zd: seed['zdate'] = zd
cmf = ROOT/'data-csv'/'fixed'/'col-month.csv'
if cmf.exists():
    cm = {}
    with open(cmf, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            lv, zmk = row['楼层'].strip(), row['分区'].strip()
            cat, elem, mon = row['类别'].strip(), row['构件'].strip(), row['月份'].strip()
            if lv and zmk and elem and mon: cm[f'{lv}||{zmk}||{cat}||{elem}'] = mon
    if cm: seed['colMonth'] = cm
if seed:
    seed['actDefs'] = [{'id':'act_wall','label':'Wall','unit':'nos'},
                       {'id':'act_corewall','label':'Core Wall','unit':'nos'}]

# level-summary.csv → window.__LEVELSUM(只取"覆盖值"列)
levelsum = {}
ls_csv = ROOT/'data-csv'/'fixed'/'level-summary.csv'
if ls_csv.exists():
    with open(ls_csv, encoding='utf-8-sig') as f:
        rd = csv.reader(f); next(rd)
        for row in rd:
            if len(row) < 5 or not row[0].strip(): continue
            lv, key, ov = row[0].strip(), row[1].strip(), row[4].strip().replace(',','')
            if ov in ('','—','-'): continue
            try:
                v = float(ov); v = int(v) if v == int(v) else v
            except ValueError:
                sys.exit(f'level-summary.csv: {lv}/{key} 覆盖值 "{ov}" 不是数字')
            levelsum.setdefault(lv, {})[key] = v

def js_str(x): return json.dumps(x, ensure_ascii=False)
embeds = (
    "/* GENERATED — 请勿手改。源: presentation/*.html + data-csv/fixed/zone-xref.csv */\n"
    "(function(){\n"
    "  function add(parent,id,type,content){ if(document.getElementById(id))return;\n"
    "    var el=document.createElement('script'); el.type=type; el.id=id; el.textContent=content; parent.appendChild(el); }\n"
    "  var app=document.querySelector('x-dc #app')||document.querySelector('x-dc')||document.body;\n"
    "  add(app,'rpLinkedTpl','application/octet-stream'," + js_str(rpl) + ");\n"
    "  add(app,'rpB64','application/octet-stream'," + js_str(rpb) + ");\n"
    "  var b=document.body||document.documentElement;\n"
    "  add(b,'zxrefData','application/json'," + js_str(zx_json) + ");\n"
    "  window.__LEVELSUM=" + json.dumps(levelsum, ensure_ascii=False) + ";  /* 楼层汇总覆盖(level-summary.csv) */\n"
    "  add(b,'zlookupB64','application/octet-stream'," + js_str(zlk) + ");\n"
    + ("  add(b,'locked-data','application/json'," + js_str(json.dumps(seed, ensure_ascii=False, separators=(',',':'))) + ");  /* 基准数据种子(zone-activity/zone-plan-dates/col-month.csv) */\n" if seed else "")
    + "})();\n")
(ROOT/'generated'/'embeds.bundle.js').write_text(embeds, encoding='utf-8')
print(f"OK: generated/app.bundle.js ({(ROOT/'generated'/'app.bundle.js').stat().st_size:,} B), "
      f"embeds.bundle.js ({(ROOT/'generated'/'embeds.bundle.js').stat().st_size:,} B), "
      f"zone-xref {len(zx)} 组, 楼层汇总覆盖 {sum(len(v) for v in levelsum.values())} 项")
