# 逐日降水专题统一请求协议

状态：版本 1 已于 2026-08-30 完成实现和真实数据验收。

## 1. 阶段目标

将仓库中已有的逐日降水、降水效率和降水等级分析接入统一业务请求。一个请求集
统一声明日产品目录、必要区域、连续日期、标准结果和专题产物；专题层不得自行
重复发现产品或生成第二份 mask。

## 2. 请求协议

```json
{
  "schema_version": 1,
  "request_set": "daily_precipitation_analysis",
  "request_set_id": "nmg-zxb-daily-precipitation-2025",
  "shared_request": {
    "data_source": {
      "kind": "netcdf",
      "root": "H:\\NCEP_fixed\\2025\\p2_as_matlab",
      "engine": "h5netcdf"
    },
    "region": {
      "kind": "shp",
      "path": "../../data/inputs/内蒙古中西部/内蒙古中西部_7盟市融合研究区.shp"
    }
  },
  "requests": {
    "daily": {
      "request_id": "nmg-zxb-daily-precipitation-standard-2025",
      "period": {
        "scale": "day",
        "date_range": ["2025-01-01", "2025-12-31"]
      },
      "variables": ["Ps", "GMh", "CWR"],
      "operators": ["sum"],
      "results": [
        {"scope": "region", "format": "csv", "name": "daily_regional"},
        {"scope": "grid", "format": "netcdf", "name": "daily_grids"}
      ]
    }
  },
  "product": {
    "region_name": "内蒙古中西部七盟市研究区",
    "output_prefix": "nmg-zxb_2025"
  },
  "output_root": "../../artifacts/runs/nmg-zxb-daily-precipitation-2025"
}
```

## 3. 强制规则

- 请求集协议版本固定为 1，`request_set` 固定为
  `daily_precipitation_analysis`。
- `requests` 必须且只能包含 `daily`。
- 日请求必须位于同一自然年，日期连续且不得重复。
- 变量必须按 `Ps、GMh、CWR` 声明，算子固定为 `sum`。
- 标准结果固定为区域 CSV 和保留每日 period 的格点 NetCDF。
- 数据源必须为日 NetCDF 产品并显式声明 `h5netcdf` 引擎，所有请求日期必须各有且
  只有一个文件。
- 区域输入必须存在并编译为内部 mask；专题层复用标准准备结果和同一 mask。
- `dxy` 是计算降水量所需的辅助源字段，不作为用户物理量暴露。

## 4. 计算口径

对每日区域内格点求和：

- 区域降水量：`sum(SP) / sum(dxy)`，单位 mm；
- 水平降水效率：`sum(SP) / sum(GMh) × 100%`；
- 格点降水量：`SP / dxy`，单位 mm；
- 格点云水资源量：`CWR / dxy`，单位 mm。

降水等级使用右闭区间：小雨 `(0, 9.9]`、小到中雨 `(9.9, 24.9]`、
中到大雨 `(24.9, 49.9]`、暴雨 `(49.9, +∞]`。无降水日不进入等级。

## 5. 正式产物

```text
output_root/
  standard_request/...
  mask/mask_bundle.json
  daily_precipitation/<prefix>_daily_precipitation_pe.csv
  daily_precipitation/<prefix>_daily_precipitation_pe.png
  precipitation_classes/<prefix>_precipitation_class_distribution.nc
  precipitation_classes/<prefix>_precipitation_class_distribution.png
  precipitation_classes/<prefix>_precipitation_classes_dual_axis.png
  precipitation_classes/<prefix>_precipitation_class_summary.csv
  report_inputs/request_set_manifest.json
  report_inputs/report_inputs.json
```

## 6. 验收与截止

- 合成连续日请求验证公式、等级边界、标准产物和专题产物。
- 证明每个产品只加载一次、mask 只编译一次。
- 未知字段、跨年、非连续日期、缺日、重复日、网格不一致、空 mask 和发布失败
  均严格失败且不覆盖已有正式目录。
- 真实 2025 请求读取 365 个日产品，复现已有 CSV、等级 NetCDF 和三幅图的业务
  内容，并生成统一清单。
- 完整测试在 `cwr_py312` 中通过并形成独立提交后阶段截止。

本阶段不新增 DOCX、降水等级、物理公式、重采样、缓存、调度、GUI 或 Web UI。

## 7. 验收结果

- 合成三日请求的协议、公式、CLI、单次加载、单次 mask、缺日和发布失败测试共
  6 项通过。
- 完整测试共 141 项通过。
- 真实请求读取 2025 年 365 个日产品，生成 365 行日序列、8 个等级格点变量、
  2 个标准结果、3 幅专题图和完整统一清单。
- 新日序列与历史 52 格点结果的降水量、效率差异不超过浮点舍入误差。
- 历史等级 NC 使用旧 72 格点 mask；新结果使用当前 SHP 编译并已在单年报告中
  验收的正确 52 格点 mask。52 个共同格点的 8 个等级变量差异全部为 0，等级
  汇总按正确 mask 重算。
- 三幅图遵循当前图件规则：坐标和刻度 15–16 号、组图使用左上角子图标识、无总
  标题、colorbar 与子图等高且只标单位。
- 正式 JSON 中 staging 路径引用为 0。
- 真实环境显式使用 `h5netcdf`，避免依赖本机不可用的可选 `netCDF4` DLL。
