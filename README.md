# RWS P1 Tracking — v3(三框架结构)

基于你最新版本(index.html 1.1MB)做的**最小范围拆分**:所有基础文件内容原样保留,
只把写进 HTML 的数据抽出来。页面行为经浏览器逐项对比与原版**完全一致**
(渲染状态、内嵌报表、分区对照、楼层切换、选区面板全部相同)。
打开方式不变:双击 `index.html`;放到 **GitHub 上也可直接运行**(启用 GitHub Pages 即可,
纯静态、全部相对路径;仓库里附带 Actions 工作流,网页上改完 CSV 推送后自动校验并重新生成)。

## 三大框架

```
P1-Tracking-v3/
│
├── index.html                  页面骨架(10KB, 原 1.1MB)
│
├── presentation/               【展示框架】
│   ├── styles.css              全部样式(改完刷新生效)
│   ├── report-embed.html       内嵌报表页(原 rpB64, 489KB)
│   ├── report-linked-template.html  联动报表模板(原 rpLinkedTpl)
│   └── zone-lookup.html        分区速查页(原 zlookupB64)
│
├── app/                        【功能框架】
│   ├── component.js            应用逻辑(311KB 完整类, 改完跑 tools/build.py)
│   ├── cloud-sync.js           Supabase 云同步(改完刷新生效)
│   └── favicon.js
│
├── data-csv/                   【数据存储框架 — 用 CSV 调数】
│   ├── fixed/zone-xref.csv     87 组分区对照(大区↔楼层↔图上分区↔别名), 改完跑 build
│   ├── fixed/level-summary.csv ★网页右上楼层汇总卡的数值(柱/钢主梁/梯井/面积/挖土/拆除):
│   │                             "覆盖值"列填数字即生效, 清空恢复自动计算; 改完跑 build
│   ├── fixed/zone-activity.csv ★基准数据: 每分区每活动的 月份+计划量+活动起止日期(改完跑 build)
│   ├── fixed/zone-plan-dates.csv ★基准数据: 每分区的区域计划开始/结束(改完跑 build)
│   ├── fixed/col-month.csv     ★基准数据: 逐根柱构件的目标月份(改完跑 build)
│   ├── fixed/conflicts.csv     推不上去的基准条目(页面无 L3/L4/L5/Deck 楼层图等), 人工核对
│   ├── source/RWS_P1_CJ_full_import_aligned_final.json  最终基准数据原件
│   └── work/<楼层>.csv         ★数据库连接的数据: 每层一个文件(B2/B1/B1M/L1…L5),
│                                 文件内按 EB→NB→MA 分组到小区, 含工作项/月份/计划量/实际量/
│                                 完成率/计划开始/计划结束/实际完成日期, 改完跑 work_csv import
│
├── generated/                  自动生成的注入文件(勿手改)
│   ├── app.bundle.js           ← app/component.js
│   └── embeds.bundle.js        ← presentation 三个页面 + zone-xref.csv
│
├── tools/
│   ├── build.py         重新生成 generated/(改 component.js、内嵌页、fixed/*.csv 后跑)
│   ├── work_csv.py      export=导出工作CSV底稿 / import=校验并写回 zp-data.global.js
│   ├── push_final.py    把最终基准 JSON 重新推入(基准更新时重跑, 之后 build + export)
│   ├── push_excel.py    把《区域划分 EB_NB_MA》Excel 排程时间推入月度表
│   └── mark_l1.py       重新生成 L1 违规元素标记清单
│
├── .github/workflows/build.yml  GitHub Actions: 推送后自动 import→build→提交生成结果
└── 根目录仅保留页面实际加载的文件: support.js, zone-data.global.js,
   zp-data.global.js, floor-templates.global.js(内容未改)
   ★ 冲突旧文件已移除: zone-data.js(与生效数据不一致的旧版)、zp-data.js、
     floor-templates.js(未被页面引用的重复副本)、zp-data_global.js(旧备份)、全部 .bat
```

## 最终基准数据(RWS_P1_CJ_full_import_aligned_final.json)

基准 JSON 已全部推入(工作/区域/数量/时间):

- **区域面板**(点开每个分区看到的活动数据):活动计划量 394 条、活动起止日期 412 条、
  区域计划起止 110 条、柱构件目标月 102 条,已生成三个 CSV 并编入页面
  (`zone-activity.csv` / `zone-plan-dates.csv` / `col-month.csv`,改完跑 build 即生效;
  网页上管理员手改的数值仍然优先);
- **月度工作安排**:活动起止时间以基准为准对账,改写 159 处 `计划开始/计划结束`,
  247 处原本已一致;无逐项日期的条目按区域时间补 92 处;
  **计划量/实际量/完成率一律未动**,月度显示与后续实际量更新不受影响;
- **推不上去的 70 条**已标记在 `data-csv/fixed/conflicts.csv`(59 条活动计划量在 L3 等
  页面没有的楼层图、11 条区域起止在 L4/L5/Deck 且月度表无对应条目),需人工确认归属。

## 改什么 → 动哪里

| 想改 | 文件 | 之后 |
|---|---|---|
| 固定数值(分区对照/别名) | `data-csv/fixed/zone-xref.csv` | `python tools/build.py`(GitHub 上推送即自动跑) |
| 分区活动 计划量/起止时间 | `data-csv/fixed/zone-activity.csv` | `python tools/build.py` |
| 分区区域 计划开始/结束 | `data-csv/fixed/zone-plan-dates.csv` | `python tools/build.py` |
| 柱构件目标月份 | `data-csv/fixed/col-month.csv` | `python tools/build.py` |
| 工作安排/数量/时间(校准) | `data-csv/work/<楼层>.csv` | `python tools/work_csv.py import`(GitHub 推送自动跑) |
| 右上楼层汇总卡数值 | `data-csv/fixed/level-summary.csv` 的"覆盖值"列 | `python tools/build.py`(GitHub 推送自动跑) |
| 样式 | `presentation/styles.css` | 刷新 |
| 内嵌报表/速查页 | `presentation/*.html` | `python tools/build.py` |
| 应用逻辑 | `app/component.js` | `python tools/build.py` |
| 云同步 | `app/cloud-sync.js` | 刷新 |

## work CSV 说明(第二部分)

每个文件 = 一个楼层,文件内按 **EB → NB → MA** 分组到小区,行 = 一条工作安排:
`大区, 小区, 工作项, 月份, 序号, 计划量, 实际量, 完成率%, 单位, 计划开始, 计划结束, 实际完成日期, 标记`。
计划开始/结束默认为该月首末日,可改为真实计划日期;实际完成日期自行填写——三个日期
都会存入数据文件并往返保留,后续在 CSV 里直接调整和更新。
楼层按工作项名称归类("NB L1-L2 Steel Beam"→L2;梁类单层名按实际楼层上移一层)。
**序号**决定网页月度表里的行顺序,并与管理员在网页上手改的数值挂钩——改数可以,
不要改动已有行的序号;新增行用新序号。导入时自动校验:小区名必须在楼栋分组里、
月份必须合法、数字格式检查,问题行逐条列出并跳过。

## 右上楼层汇总卡(level-summary.csv)

网页右上每层的汇总数值(COLUMNS / STEEL MAIN BEAMS / LIFT-STAIR / AREA / EXCAVATION / DEMOLITION)
已分离为 `data-csv/fixed/level-summary.csv`:"当前自动值"列是按图上台账算出的参考(改它无效),
**"覆盖值"列填数字即以 CSV 为准显示,清空恢复自动**。已按你页面当前显示预填了
B1 钢主梁=14、B1 挖土=103,713 两项覆盖。此功能是对 app/component.js 的三处小改
(metricTotals/buildKPIs 读取 window.__LEVELSUM),已注释标明。

## L1 无梁规则(标记待人工删除)

按既定规则一楼没有主梁/钢梁。当前生效数据里图上台账 L1 已干净;仍存在的疑似违规项
已全部标记在 **`data-csv/fixed/L1-remove-list.csv`**(登记表中仅 L1 的分区却登记的梁、
工作项名标注 L1 的梁类 37 条),work CSV 里对应行的"标记"列也打了 ⚠。
**工具只标记不删改** —— 请核对后手动删除;删完跑 `python tools/mark_l1.py` 可刷新清单。

## GitHub 使用

1. 仓库根目录即本文件夹;Settings → Pages → 从 main 分支根目录发布,即可在线访问;
2. 在 GitHub 网页上直接编辑 `data-csv/` 下的 CSV → 提交 → Actions 自动校验并重新生成
   (校验不通过工作流会**红叉失败**并列出问题行,不会写入坏数据);
3. 本地使用只需 Python 3:`python tools/work_csv.py import` / `python tools/build.py`,
   不依赖任何 .bat。

## 注意

- 网页上管理员手改的数值(云同步)优先级仍高于文件,与原设计一致;
- `generated/` 里两个文件是生成品,请勿手改;
- 页面运行仍需联网加载 React / Supabase CDN(与原版相同)。
