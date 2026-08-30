# 季节云水资源距平请求集契约

状态：协议与真实基线已于 2026-08-31 冻结，尚未实现引擎适配器。

## 1. 产品选择

第三专题确定为 `seasonal_cloud_water_anomaly`，来源为
`H:\邢台观测站\compare\2025_report\2025年云水资源报告-距平图绘制.ipynb`。
该产品计算目标年四季云水含量相对多年气候态的格点距平。它不同于现有单年/多年
云水报告，也不同于逐日降水等级分析，主要验证“基准期 + 目标期”双时间角色和
格点气候距平能力。

降水频次脚本不作为第三专题，因为其降水等级日数和分级 CWR 累计已经由
`daily_precipitation_analysis` 覆盖。

## 2. 冻结请求协议

建议协议版本为 1：

```json
{
  "schema_version": 1,
  "request_set": "seasonal_cloud_water_anomaly",
  "request_set_id": "north-seasonal-cvh-anomaly-2025",
  "shared_request": {
    "data_source": {
      "kind": "netcdf",
      "root": "H:\\YeWu\\cm\\CRA40_trans1P00",
      "engine": "h5netcdf"
    },
    "region": {
      "kind": "shp",
      "path": "H:\\我的业务\\CM\\2026-04\\shp\\merged_beifang\\merged_beifang.shp"
    }
  },
  "requests": {
    "monthly": {
      "request_id": "north-seasonal-cvh-anomaly-monthly-2000-2025",
      "period": {
        "scale": "month",
        "year_range": [2000, 2025],
        "months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
      },
      "variables": ["Cvh"],
      "operators": ["mean"],
      "results": [
        {"scope": "region", "format": "csv", "name": "monthly_regional"},
        {"scope": "grid", "format": "netcdf", "name": "monthly_grids"}
      ]
    }
  },
  "product": {
    "baseline_year_range": [2000, 2024],
    "target_year": 2025,
    "seasons": ["spring", "summer", "autumn", "winter"],
    "output_prefix": "north_2025_seasonal_cvh_anomaly",
    "map_extent": [90, 130, 33, 55],
    "color_limit_mm": 100
  },
  "output_root": "artifacts/runs/north-seasonal-cvh-anomaly-2025"
}
```

`region` 仍为必要输入，必须编译或读取为内部 mask；专题计算和图件只使用这一份
mask。版本 1 只接受 `Cvh`，其源变量兼容名为 `MC`，`dxy` 是换算深度所需的辅助
字段，不作为用户物理量暴露。

## 3. 时间与计算口径

- 基准年份必须为首尾均包含的连续区间，至少 5 年。
- 目标年份必须是一个完整自然年，并且不得包含在基准区间内。
- 月产品必须覆盖基准年份和目标年份所需的全部月份，每月各有且只有一个产品。
- 春季为 3–5 月、夏季为 6–8 月、秋季为 9–11 月、冬季为 12、1、2 月。
- 为复现原业务，冬季在同一标记自然年内使用该年的 1 月、2 月和 12 月，不跨年。
- 单月格点深度为 `Cvh_mm = MC / dxy`。
- 每年季节值先对该季三个月的 `Cvh_mm` 求和。
- 气候态先得到基准期内每一年的季节值，再对各年等权算术平均。
- 季节距平为 `目标年季节值 - 基准期季节平均值`。
- 正式格点产物在 mask 外写为缺测值；区域摘要只统计 mask 内格点。

版本 1 不计算距平百分率、趋势或显著性，不重采样不同网格，也不改变冬季定义。

## 4. 正式产物

计划实现阶段应一次事务发布：

```text
output_root/
  standard_requests/monthly/...
  mask/mask_bundle.json
  seasonal_anomaly/<prefix>.nc
  seasonal_anomaly/<prefix>_summary.csv
  seasonal_anomaly/<prefix>.png
  report_inputs/request_set_manifest.json
  report_inputs/report_inputs.json
```

专题 NetCDF 固定包含：

- `target_cvh_mm(season, lat, lon)`；
- `baseline_mean_cvh_mm(season, lat, lon)`；
- `anomaly_cvh_mm(season, lat, lon)`；
- `mask(lat, lon)`。

摘要 CSV 每季记录目标期区域格点平均、气候态区域格点平均，以及距平的平均、最小和
最大值。版本 1 不生成 DOCX。

## 5. 图件规则

- 四季按春、夏、秋、冬组成 2×2 图，使用 `(a)`–`(d)`，不设子图 title 和总标题。
- 文字和刻度执行 `figure-visual-acceptance-rules.md`，使用英文和规范变量名。
- 四个面板使用同一个以 0 为中心的对称色标；基线请求固定为 `-100–100 mm`，
  超出范围使用 extend 表示。
- 只显示单位 `mm`，不在 colorbar 上写物理量名称。
- 共享 colorbar 与完整 2×2 子图区域等高，刻度采用整齐等距值。
- 绘图时使用区域几何路径裁剪，不得先把 mask 外改为 `NaN` 再进行几何 clip。
- 地图范围必须比目标区域边界更宽；基线范围为 `[90, 130, 33, 55]`。
- 历史 notebook PNG 只用于核对区域、季节顺序和大致色彩分布，不作为像素验收
  标准；新图必须服从以上最新规则。

## 6. 严格失败规则

下列任一情况必须在正式发布前失败，并保留已有输出：

- 请求字段、请求成员、变量、算子或季节名称不符合版本 1；
- 基准期少于 5 年、不连续，或目标年与基准期重叠；
- 缺少或重复任一所需月产品；
- 缺少 `MC/Cvh` 或 `dxy`，`dxy` 非正，或 mask 内存在不可计算的源值；
- 月产品的网格、坐标或 `dxy` 不兼容；
- SHP/mask 不存在、与产品网格不兼容或没有有效格点；
- NetCDF、CSV、PNG、清单写出或事务发布失败。

## 7. 共享能力映射

可以直接复用：

- 月产品目录发现、`h5netcdf` 读取、变量别名和网格一致性校验；
- SHP/已有 mask 的统一编译、mask bundle 和单次复用；
- 标准区域 CSV、格点 NetCDF、请求清单、事务发布和产品注册表；
- NumPy、xarray、Matplotlib、Shapely 和 pyshp，无需引入重型流程框架。

实现阶段真正缺少的能力只有：

- 基准区间与目标年份的协议校验；
- 按年先聚合、再跨年平均的季节气候态和距平派生；
- 三种专题产物写出和按几何路径裁剪的四季距平图。

该缺口应由薄专题适配器实现，不增加通用引擎的“anomaly”算子，也不引入动态插件
平台。

## 8. 真实基线

基线目录：`artifacts/examples/seasonal_cloud_water_anomaly_2025/`。

- 数据源：CRA40 1° 月产品，2000–2025 年共 312 个，逐月完整且无重复；
- 区域：北方合并区域 SHP，1° 网格 mask 为 41×71，其中 349 个有效格点；
- 基准期：2000–2024；目标年：2025；
- 距平数组 SHA-256：
  `49ddbd105004fdaab61d23131f189b29cf995565959ce7fe83a67f63043e86b4`。

| 季节 | 目标均值/mm | 气候态均值/mm | 距平均值/mm | 距平最小/mm | 距平最大/mm |
| --- | ---: | ---: | ---: | ---: | ---: |
| 春季 | 87.201487 | 86.439510 | 0.761976 | -63.887278 | 102.517168 |
| 夏季 | 233.612703 | 194.116820 | 39.495883 | -124.029215 | 411.916741 |
| 秋季 | 123.118595 | 90.791637 | 32.326958 | -46.534580 | 601.463941 |
| 冬季 | 39.270537 | 37.878617 | 1.391920 | -14.545070 | 19.745250 |

`seasonal_cvh_anomaly_baseline.nc` 和 `baseline_manifest.json` 是数值验收基线；
`historical_notebook_figure.png` 是从原 notebook 提取的非像素验收参考。

## 9. 本阶段截止

本文件、真实数值基线、候选选择理由、共享能力映射和缺口清单完成后，本设计阶段
立即截止。适配器、注册表接入、合成测试和正式新图属于下一实现阶段，不在本阶段
继续推进。
