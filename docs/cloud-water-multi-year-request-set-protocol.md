# 云水资源多年报告请求集协议

状态：版本 1 已于 2026-08-30 完成实现和真实数据验收。

## 1. 阶段目标

使用一个 `cloud_water_multi_year` 请求集统一声明数据源、必要区域、连续年份、
年度/月度标准结果和多年报告产品。现有多年公式、趋势检验、六幅图、两张表及
DOCX 模板保持不变。原 `--workflow-spec` 入口已于 2026-08-31 退役。

## 2. 协议

```json
{
  "schema_version": 1,
  "request_set": "cloud_water_multi_year",
  "request_set_id": "nmg-zxb-cloud-water-2021-2025",
  "shared_request": {
    "data_source": {"kind": "netcdf", "root": "H:\\result_china\\NCEP", "engine": "h5netcdf"},
    "region": {"kind": "shp", "path": "../../data/inputs/内蒙古中西部/内蒙古中西部_7盟市融合研究区.shp"}
  },
  "requests": {
    "annual": {
      "request_id": "nmg-zxb-cloud-water-2021-2025-annual",
      "period": {"scale": "year", "year_range": [2021, 2025]},
      "variables": ["GMv", "GMh", "CWR", "Ps", "Cvh", "CEv", "PEh"],
      "operators": ["mean"],
      "results": [
        {"scope": "region", "format": "csv", "name": "annual_regional"},
        {"scope": "grid", "format": "netcdf", "name": "annual_grids"}
      ]
    },
    "monthly": {
      "request_id": "nmg-zxb-cloud-water-2021-2025-monthly",
      "period": {"scale": "month", "year_range": [2021, 2025], "months": [1,2,3,4,5,6,7,8,9,10,11,12]},
      "variables": ["CWR", "Ps", "Cvh"],
      "operators": ["mean"],
      "results": [
        {"scope": "region", "format": "csv", "name": "monthly_regional"},
        {"scope": "grid", "format": "netcdf", "name": "monthly_grids"}
      ]
    }
  },
  "product": {
    "region_name": "内蒙古中西部七盟市研究区",
    "template": "../../data/templates/Multi-Year_Evaluation_Report-cwr-v1.docx",
    "report_filename": "2021-2025-Year_Evaluation_Report-nmg-zxb.docx",
    "image_width_inches": 4.0,
    "image_widths_inches": {"target_image4": 6.2, "target_image5": 6.2, "target_image6": 6.2}
  },
  "output_root": "../../artifacts/runs/nmg-zxb-cloud-water-multi-year-request-2021-2025"
}
```

## 3. 强制校验

- 顶层和嵌套对象均严格拒绝未知字段。
- `request_set` 固定为 `cloud_water_multi_year`，协议版本固定为 1。
- `requests` 必须且只能包含 `annual`、`monthly`。
- 年度选择必须是连续且不少于五年的完整年份集合。
- 月度选择必须与年度年份完全相同，并覆盖每年 1 至 12 月。
- 两个成员共享同一数据源和必要区域，不接受日尺度或跨尺度重采样。
- 模板必须存在，报告名必须是单一 `.docx` 文件名。

## 4. 唯一执行链

1. 展开并编译两个标准业务请求。
2. 按年发现一个年度产品和十二个月产品，共发现并加载 `13 × 年数` 个文件。
3. 只在首年参考网格上编译一次 mask，后续年份严格校验同一网格并复用 mask。
4. 合并已加载年度和月度 dataset，分别执行标准请求，不重新打开产品。
5. 每年调用一次现有 `derive_cloud_water_year_from_prepared()`，再调用一次多年聚合。
6. 使用现有多年写出与报告 profile 生成指标、空间复合、六幅图和 DOCX。
7. 重定向全部清单路径并校验正式 JSON 不含 staging 路径。
8. 所有产物通过一个 staging 目录一次发布；失败保持原正式目录不变。

## 5. 产物

```text
output_root/
  standard_requests/annual/...
  standard_requests/monthly/...
  mask/mask_bundle.json
  business_metrics/cloud_water_multi_year.json
  spatial_composite/cloud_water_multi_year.nc
  profile_image/target_image1.png ... target_image6.png
  report_inputs/request_set_manifest.json
  report_inputs/report_inputs.json
  report/<report_filename>
```

## 6. 验收与截止

- 合成五年请求生成 5 个年度时段、60 个月度时段及完整专题产物。
- 证明 65 个产品各加载一次、mask 编译一次、每年专题派生一次。
- 缺年度、缺月份、重复产品、年份不一致、非法区域、网格不一致、DOCX 失败和发布失败均严格失败且不覆盖正式目录。
- 普通 `--request` 和单年请求集保持兼容；`--workflow-spec` 已于
  2026-08-31 退役，多年报告统一使用本协议的 `cloud_water_multi_year` 请求集。
- 真实 2021–2025 新旧入口的指标、空间 NC、六幅图和 DOCX 等价。
- 完整测试在 `cwr_py312` 中通过并形成独立提交后阶段截止。

本阶段不新增指标、图型、模板、重采样、缓存、调度、GUI 或 Web UI。
