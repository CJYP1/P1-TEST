/* Core Wall 分组对照表(来自 RWS P1 Zone Quantities R3 主表)。
   键 = Core Wall / Lift-wall 编号;值 = 这个核心筒包含的 lift / stair 成员(含跨楼层的各种拼写变体)
   + f / t 楼层范围(整组并集)。
   画的 Core Wall 形状取这个名字后, 会在它所在分区里自动匹配到"确实存在的成员"(拼写对上的),
   楼层显示范围用 f→t, 颜色 = 匹配到的成员状态聚合。不同分区拼写不同 → 各自匹配, 不会串。
   —— 只是参照数据, 不影响 CSV 上传, 不进 bundle。 */
window.CW_GROUPS = {
  "CW3B": { lifts:["P1-VL-1","P1-VL1","P1-HSL/EL1","P1-FL-1","P1-FL1","P1-CML-1","P1-CML1"],
            stairs:["P1-ST-01B","P1-ST-01","P1-T-01B"], f:"B2", t:"L17" },
  "CW3A": { lifts:["P1-PL9A","P1-PL8","P1-PL7","P1-HSL/EL2","PL-HSL/EL2","P1-FL2"],
            stairs:["P1-ST-02B","P1-ST-02","P1-ST-02A"], f:"B2", t:"L17" },
  "CW4":  { lifts:["P1-FL11","P1-FL-11"],
            stairs:["P1-ST-44B","P1-ST-49","P1-ST-44/49"], f:"B2", t:"L4" },
  "CW5":  { lifts:["P1-FL5","P1-RSL1","P1-RSL-EL1"],
            stairs:["P1-ST-05B","P1-ST-05","P1-ST-05A"], f:"B2", t:"L4" },
  "CW8":  { lifts:["P1-CGL1","P1-CGL2","PL-CGL1","PL-CGL2"],
            stairs:["P1-ST-03B (LW8)","P1-ST-03/3B (LW8)","P1-ST-03 (LW8)"], f:"B2", t:"L4M" },
  "CW2A": { lifts:["P1-FL3","P1-HSL/EL3","PL-HSL/EL3","P1-HSL/EL4","PL-HSL/EL4","P1-HSL/E3","P1-CSL4","PL-CSL4","P1-PL11","P1-PL12","P1-FL-03"],
            stairs:[], f:"B2", t:"L17" },
  "CW2B": { lifts:["P1-CSL1","P1-CSL2","P1-CSL3","P1-PL5","P1-PL1","P1-PL3","P1-PL2","P1-PL4","P1-PL6"],
            stairs:[], f:"B2", t:"L4" },
  "CW01": { lifts:["PL-HSL/EL5","P1-FL4","P1-PL22","P1-PL21","P1-PL20","P1-PL19","P1-SK1","P1-SK2"],
            stairs:["P1-ST-20/21","P1-ST-04","P1-ST-18/19"], f:"L1", t:"L16" },
  "LW6":  { lifts:["P1-ML1","P1-ML2","P1-ML3","P1-ML4"], stairs:[], f:"L1", t:"L4" },
  "LW7":  { lifts:["P1-CL4","P1-CL3"], stairs:[], f:"L1", t:"L3" },
  "LW9":  { lifts:["P1-CL1","P1-CL2"], stairs:[], f:"L2", t:"L3" },
  "LW10": { lifts:["P1-FL7"], stairs:["P1-ST-07/50"], f:"L1", t:"L4" }
};
