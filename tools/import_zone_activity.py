#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 data-csv/fixed/zone-activity/*.csv 规范化成系统可导入的格式。

做三件事:
  1) 分区列: 你的名称(如 B2-S1) -> xref mk键(如 B2|B2S1)
  2) 日期列: 27/8/2026 -> 2026-08-27 (ISO)
  3) 清掉多余的空列, 只保留 9 个标准列

默认 **试跑**(不改文件), 打印对不上的分区/活动。
加 --apply 才会真正写回(会先备份成 *.bak)。
"""
import csv, sys, re, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZA_DIR = ROOT/'data-csv'/'fixed'/'zone-activity'
XREF = ROOT/'data-csv'/'fixed'/'zone-xref.csv'
COMP = ROOT/'app'/'component.js'
COLS = ['楼层','分区','活动','活动名称(参考)','月份','计划量','完成量','活动开始','活动结束']

def _norm(s): return re.sub(r'\s+','',str(s or '')).upper().replace('-','')

def load_xref():
    name2mk, norm2mk, aliases = {}, {}, set()
    with open(XREF, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            typ=(row.get('类型type') or '').strip(); name=(row.get('名称name') or '').strip()
            mkcol=(row.get('mk键') or '').strip()
            if not name: continue
            if typ=='别名' or not mkcol:
                aliases.add(name); aliases.add(_norm(name)); continue
            name2mk[name]=mkcol; norm2mk[_norm(name)]=mkcol
    return name2mk, norm2mk, aliases

def valid_acts():
    s=COMP.read_text(encoding='utf-8')
    m=re.search(r'_actMeta\(\)\{return \[(.*?)\]\.concat', s, re.S)
    return set(re.findall(r"id:'([a-z_]+)'", m.group(1))) if m else set()

def to_iso(d):
    d=(d or '').strip()
    if not d: return ''
    if re.match(r'^\d{4}-\d{2}-\d{2}$', d): return d      # already ISO
    m=re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})$', d)     # D/M/YYYY
    if m:
        dd,mm,yy=m.groups(); yy=int(yy); yy=2000+yy if yy<100 else yy
        return f'{yy:04d}-{int(mm):02d}-{int(dd):02d}'
    return None   # 无法识别

def convert_zone(name, name2mk, norm2mk, aliases):
    name=(name or '').strip()
    if name in name2mk: return name2mk[name], 'ok'
    n=_norm(name)
    if n in norm2mk: return norm2mk[n], 'ok(归一化)'
    if name in aliases or n in aliases: return None, '别名/组合区'
    return None, '未找到'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--apply',action='store_true'); a=ap.parse_args()
    name2mk,norm2mk,aliases=load_xref(); acts=valid_acts()
    bad_zone={}; bad_act={}; bad_date={}
    files=sorted(ZA_DIR.glob('*.csv')); total=0; converted=0
    out_by_file={}
    for fp in files:
        with open(fp, encoding='utf-8-sig') as f:
            rd=csv.DictReader(f); rows=list(rd)
        outrows=[]; pending=[]
        for r in rows:
            zone=(r.get('分区') or '').strip()
            act=(r.get('活动') or '').strip()
            if not (r.get('楼层') or '').strip() and not zone and not act: continue
            total+=1
            mk,st=convert_zone(zone,name2mk,norm2mk,aliases)
            if mk is None: bad_zone.setdefault(f'{fp.name}: {zone}', st)
            else: converted+=1
            if act and act not in acts: bad_act.setdefault(f'{fp.name}: {act}', 1)
            for col in ('活动开始','活动结束'):
                iso=to_iso(r.get(col))
                if iso is None: bad_date.setdefault(f'{fp.name}: {r.get(col)}',1)
            rec={
                '楼层':(r.get('楼层') or '').strip(),
                '分区':mk if mk else zone,
                '活动':act,
                '活动名称(参考)':(r.get('活动名称(参考)') or '').strip(),
                '月份':(r.get('月份') or '').strip(),
                '计划量':(r.get('计划量') or '').strip(),
                '完成量':(r.get('完成量') or '').strip(),
                '活动开始':(to_iso(r.get('活动开始')) or (r.get('活动开始') or '').strip()),
                '活动结束':(to_iso(r.get('活动结束')) or (r.get('活动结束') or '').strip()),
            }
            (outrows if mk else pending).append(rec)
        out_by_file[fp]=(outrows,pending)

    print(f'总行数 {total}, 分区可转换 {converted}, 分区转不了 {total-converted}')
    def show(title,d):
        print(f'\n{title}: {len(d)} 个')
        for k in list(d)[:60]: print(f'   {k}  — {d[k] if not isinstance(d[k],int) else ""}')
    if bad_zone: show('⚠ 分区对不上(需你确认/补 xref)',bad_zone)
    if bad_act:  show('⚠ 活动 id 不在系统清单里',bad_act)
    if bad_date: show('⚠ 日期无法识别',bad_date)
    if not (bad_zone or bad_act or bad_date): print('\n✅ 全部能对上, 可以 --apply')

    if a.apply:
        pend_dir=ZA_DIR/'_unmatched'; pend_dir.mkdir(exist_ok=True)
        n_ok=n_pend=0
        for fp,(outrows,pending) in out_by_file.items():
            fp.with_suffix('.csv.bak').write_bytes(fp.read_bytes())  # 备份(复制, 不 rename)
            with open(fp,'w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=COLS); w.writeheader(); w.writerows(outrows)
            n_ok+=len(outrows)
            if pending:
                with open(pend_dir/fp.name,'w',encoding='utf-8-sig',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=COLS); w.writeheader(); w.writerows(pending)
                n_pend+=len(pending)
        print(f'\n已写回: 转换成功 {n_ok} 行(原文件备份 *.csv.bak)')
        print(f'对不上的 {n_pend} 行已单独放到 {pend_dir}/ (C/P 细分等, 之后再处理)')

if __name__=='__main__': main()
