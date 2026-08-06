# RWS P1 · Zone Resource & Progress Map — 交接说明 (Handoff)

> 用途:切换账号/新会话时,把当前项目状态、已做改动、待办一次交代清楚。日期约 2026-08。

---

## 1. 项目是什么 / 怎么构建部署

静态单页应用(SPA)。核心:

- **源码**:`app/component.js`(主逻辑,巨大单文件)、`app/cloud-sync.js`(Supabase 云同步)。
- **数据**:`zone-data.global.js`(分区几何/数量)、`zp-data.global.js`、`cw-groups.global.js`(核心筒对照表)、`floor-templates.global.js`。
- **构建**:`python3 tools/build.py` —— 把 `app/component.js` 打包成 `generated/app.bundle.js`,把 CSV 烤进 `generated/embeds.bundle.js`,并给 `index.html` 里的 `?v=` 做 cache-bust(按内容 hash)。
- **改完代码务必**:`node --check app/component.js` → `python3 tools/build.py`。
- **部署**:git push 后 GitHub Action(`build.yml`)自动重建并提交,几分钟后线上更新。**用户看新版要强刷 F5**。

### 构建/git 已知怪癖(重要)
- Action 会 push 重建后的 `index.html` + bundle,和本地 build 互相打架,`index.html` 的 `?v=` 老冲突。已放 `.gitattributes`(index.html / generated bundles = `merge=ours`)。用户需在本机跑一次:`git config merge.ours.driver true`(已跑过)。
- `zone-data`/`zp-data` 的 `?v=` 有时在两个值间反复跳(双构建器残留),一般无害。
- 本地工作区常残留未提交的构建产物(`generated/app.bundle.js`、`index.html`、`zp-data.global.js`)——Action 会在远程重建,可忽略。
- **助手无法 git push,也无法在本机跑 git config / Supabase SQL** —— 这些都得用户自己做。

---

## 2. 当前版本号(index.html 应引用)

- `app.bundle.js?v=c048f7d439`
- `cloud-sync.js?v=d9d109788f`
- `zone-data.global.js?v=e8594353e0`
- `cw-groups.global.js?v=6c366895d1`

> 截至交接:所有源码改动**已 push 到远程 origin/main**(用户确认过)。本地可能落后一两个提交 + 有构建产物残留,不影响线上。

---

## 3. ⚠️ 待办:用户需在 Supabase SQL Editor 跑的 SQL

`docs/` 下这些是"需要用户跑"的(助手不能跑)。不跑对应功能不生效:

- `补store_settings_edited_manpower_run_in_supabase.sql` — 补 `settings/edited/manpower` 三个 store(锁定同步、人数、Edit 设置)。**没跑会报 "bad store"**。
- `防改小_run_in_supabase.sql` — 非 admin 不能把已录 Done 改小。
- `快照_snapshots_run_in_supabase.sql` — 每周快照 + History 查看。
- `登录IP_run_in_supabase.sql` — 登录记录抓 IP(同账号多 IP 检测)。
- `账号删除改名_run_in_supabase.sql` — **本次新增**:`rws_admin_delete_user` / `rws_admin_rename_user`(删账号解外键、改名不新建)。没跑则前端删除/改名会报 function 不存在。

---

## 4. 本次会话做的改动(功能/修复)

### 地图 / marine 子区
- Marine 分三层可切换:**Top slab(=ZC 大父区)/ Bottom slab(=C 细分)/ Podium(=P)**(名字被用户调换过,当前就是这个映射)。
- **整体视图(不点任何子区开关)默认画出 C 细分**,按进度上色,反映真实进度。
- **marine 整体进度 = ZC 父区 + C + P 三层合并算**(`_marineComboPct`,按面积加权;用 SUBLINKS 的 c2zc/p2zone 链接;忽略 "ZC 3.2" 空格差异)。影响卡片 %、SITE PROGRESS、地图上色。
- **MONTHLY PLAN 列表**在 L1 把 C/P 细分里本月有计划或已开工(done>0)的也列进来,可点击进去。
- 点分类卡片(Marine 等)**自动把视野对准该分类**(`_fitVisible`),避免缩放后点了看不到。
- C 的 DXF 边界几何已换成正确版(偏移 -2393,-1285),面积按权威表更新。

### 进度/活动计算
- 活动条 = **累计完成 ÷ 总量**(含 "Before Apr'26" 桶),早做完的量一直保留、不因当月没做而回退。
- **做在计划前面**(done 已录、plan 在后面月)也照算(`_zonePhases` 分母优先用总量)。
- 非 admin:**有计划 或 任意月做过 或 有欠账**就显示该活动。
- **无总量+无计划但填了 done** → 不猜 100%,显示 "—",并给 admin 一个 **⚠ 缺总量/计划** 标签(活动面板 + 地图红色 "!" 角标,仅 admin)。
- 数量总量框(AREA/COLUMN NOS/SLAB 等)**都加了锁**:填了自动锁🔒,Import 不覆盖。计算规则:每个框=下面该活动各月计划量之和;AREA=图纸面积;Excavation=面积×深度(B2×6m/B1×8.5m,仅 NB)。

### 标记 / 颜色 / 图例
- **Behind schedule 红点**(原叫 delay):累计计划 > 累计完成就一直显示,直到做完才消失;delay 时不画 start 橙点(红优先)。
- "Finished earlier" 颜色由灰绿改**柔和浅绿 `#bcd7c3`**。
- 图例色块按地图透明度(area 0.5 / plan 0.62)叠白底显示,和板上一致(`_blendWhite`)。

### 画图工具 / Edit
- 新增 **Access 箭头折线**工具(多点可拐弯;整条线每隔一段一个箭头;**起点大圆点**;深蓝 `#1e3a8a`;图例有条目)。存 `_appCfg.access[lv]`(settings 同步)。
- **每层都能 Edit**(admin):非 L1 显示 "Edit · Lx" + 工具(放柱子/画核心筒/画楼梯/画 Access/底图)。

### 数据 / 其它
- 每个 zone 加 4 个 **MEP 活动:ACMV / FPS / ELEC / BMS**(和普通 activity 一样)。
- Marine 的 **Column / Column Cobel 只在 L1 归到 Podium**(L2/L3/L4 的 marine 柱子保留)。
- **L3/L4 柱子坐标**补全(复制 L2,之前 `this.COLUMNS` 没有 L3/L4 导致柱子不显示)。
- 删了柱子 `CX30-CY45-1`(COLUMNS 表 + zone cols;承台 piles 里还留了一个同名的,用户未确认是否删)。
- **Save 导出**改成自包含单文件(内联 CSS/JS)+ **打开即只读快照**(`__RWS_LOCKED_VIEW`:不登录/不连云/不能编辑;顶部只读横幅)。
- lift/staircase 与 CW_GROUPS 对照:补了 P1-ST-06→LW10(后又按 R3 撤销)、LW10=P1-FL7+P1-ST-07/50 到 L17、CW8/LW8 拆开(lift→L4M / stair→L17)、CW01 去掉 P1-ST-20/21、L1 的 ZC2.2/ZC2.1 补了 3.3CIST 的 4 个楼梯。还有一张 `lift_staircase_归属核对.xlsx`(32 个对不上的编号,用户在核对)。
- RP(报表)联动:`_rpRollup` 改成按录入的活动 Done 数量汇总;加了 **Critical/All zones 开关**(RP linked 右上角)。now 月份跟真实日期走(`actCurLabel`)。

---

## 5. 关键结构备忘

- 坐标系:app frame w=400987, h=298476.7;`proj(p,H)=[p[0], H-p[1]]`。
- `SUBZONES.L1`:C(27)、CZ(11)、P(22)、L2(11);**ZC 在渲染时由 L1 的 MA 父区自动生成**(排除 P 开头)。
- `SUBLINKS`:c2zc(C→ZC)、p2zone(P→ZC)、p2c、cz2c、l2c、l2p。
- marine 真实大区(DATA.levels.L1 里 cat=MA)只有 6 个 ZC;C/P 是叠加层,数据键 `L1|C1-3`、`L1|P1`。
- 进度:`zoneActPct`(marine 父区走 `_marineComboPct`,其它走 `_zonePhases`)→ `z._p` → 卡片/SITE PROGRESS/地图。`_subActPct(label)` 算某细分自己活动的 done/total 平均(P 标签会置 `_pod` 让柱子计入)。
- KV stores(前端→后端):act_total/act_plan/act_done_m/act_hidden/elem_date/act_def/crit/zdate/act_date/col_month/act_cmt/settings/edited/manpower/qty_ov。
- 账号 RPC:rws_login / rws_admin_list_users / rws_admin_upsert_user / **rws_admin_delete_user / rws_admin_rename_user(新,待跑SQL)**。

---

## 6. 用户下一步(马上要做的)
1. `git pull`(同步本地)后 **git push**(如还有未推的);线上强刷 F5。
2. 在 Supabase 跑 `docs/账号删除改名_run_in_supabase.sql`(删/改账号才生效),以及第 3 节其它还没跑的。
3. 继续核对 `lift_staircase_归属核对.xlsx`。
4. 待定:承台 piles 里同名 `CX30-CY45-1` 要不要删;RP 的 marine 是否也要三层合并口径。
