# 云水资源单年报告请求集协议

## 概述

请求集协议用于配置云水资源单年报告的完整执行流程。通过单一配置文件，同时驱动：
- 年度和月度两个标准请求
- 云水资源专题指标派生
- DOCX 报告生成
- 事务式发布

## 协议版本

当前协议版本为 `1`。

## 配置格式

```json
{
  "schema_version": 1,
  "request_set": "cloud_water_single_year",
  "request_set_id": "nmg-zxb-cloud-water-2025",
  "shared_request": {
    "data_source": {
      "kind": "netcdf",
      "root": "H:\\result_china\\NCEP",
      "engine": "h5netcdf"
    },
    "region": {
      "kind": "shp",
      "path": "../../data/inputs/内蒙古中西部/内蒙古中西部_7盟市融合研究区.shp"
    }
  },
  "requests": {
    "annual": {
      "request_id": "nmg-zxb-cloud-water-2025-annual",
      "period": {"scale": "year", "years": [2025]},
      "variables": ["GMv", "GMh", "CWR", "Ps", "Cvh", "CEv", "PEh"],
      "operators": ["mean"],
      "results": [
        {"scope": "region", "format": "csv", "name": "annual_regional"},
        {"scope": "grid", "format": "netcdf", "name": "annual_grids"}
      ]
    },
    "monthly": {
      "request_id": "nmg-zxb-cloud-water-2025-monthly",
      "period": {
        "scale": "month",
        "years": [2025],
        "months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
      },
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
    "template": "../../data/templates/Simple-Year_Evaluation_Report-xizang-cm.docx",
    "report_filename": "2025-Year_Evaluation_Report-nmg-zxb.docx",
    "image_width_inches": 4.0,
    "image_widths_inches": {
      "target_image3": 6.2,
      "target_image4": 6.2,
      "target_image5": 6.2
    }
  },
  "output_root": "../../artifacts/runs/nmg-zxb-cloud-water-single-year-2025"
}
```

## 字段说明

### 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `schema_version` | integer | 是 | 协议版本，固定为 `1` |
| `request_set` | string | 是 | 请求集类型，固定为 `"cloud_water_single_year"` |
| `request_set_id` | string | 是 | 请求集唯一标识符 |
| `shared_request` | object | 是 | 共享请求配置（数据源和区域） |
| `requests` | object | 是 | 子请求配置（annual 和 monthly） |
| `product` | object | 是 | 产品配置（模板、报告文件名等） |
| `output_root` | string | 是 | 输出目录路径 |

### shared_request

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `data_source` | object | 是 | 数据源配置（见下方字段说明） |
| `region` | object | 是 | 区域配置（`{"kind": "shp", "path": "..."}` 或 `{"kind": "existing_mask", "path": "..."}` 等） |

### shared_request.data_source

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `kind` | string | 是 | 数据源类型，固定为 `"netcdf"` |
| `root` | string | 是 | 产品根目录路径 |
| `engine` | string | 否 | NetCDF 引擎（如 `"scipy"`, `"h5netcdf"`） |
| `coordinate_map` | object | 否 | 坐标名映射 |
| `variable_map` | object | 否 | 变量名映射 |

> **限制**：统一请求支持的 `pattern` 字段在单年请求集中**不被接受**。产品发现使用固定的 `annual_pattern`/`monthly_pattern`，不读取外部 pattern 配置。

### requests.annual

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `request_id` | string | 是 | 年度请求标识符 |
| `period` | object | 是 | 时期配置：`{"scale": "year", "years": [YYYY]}` |
| `variables` | array[string] | 是 | 请求的变量列表 |
| `operators` | array[string] | 是 | 算子列表 |
| `results` | array[object] | 是 | 结果配置列表 |

### requests.monthly

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `request_id` | string | 是 | 月度请求标识符 |
| `period` | object | 是 | 时期配置：`{"scale": "month", "years": [YYYY], "months": [1..12]}` |
| `variables` | array[string] | 是 | 请求的变量列表 |
| `operators` | array[string] | 是 | 算子列表 |
| `results` | array[object] | 是 | 结果配置列表 |

### product

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `region_name` | string | 是 | 区域名称（用于报告文本） |
| `template` | string | 是 | DOCX 模板文件路径 |
| `report_filename` | string | 是 | 输出报告文件名（必须以 `.docx` 结尾） |
| `image_width_inches` | number | 否 | 默认图片宽度（英寸），默认为 `4.0` |
| `image_widths_inches` | object | 否 | 各图片槽位宽度覆盖 |

## 校验规则

1. `schema_version` 必须为 `1`
2. `request_set` 必须为 `"cloud_water_single_year"`
3. `requests` 必须且只能包含 `annual` 和 `monthly`
4. `annual.period` 必须恰好包含一个年份
5. `monthly.period` 必须包含同一年且月份必须恰好为 1 至 12
6. 两个成员使用展开后的同一数据源和同一区域
7. `product.template` 必须存在
8. `report_filename` 必须是单一 `.docx` 文件名
9. 不接受日尺度成员，也不进行任何跨尺度重采样

## 执行流程

```
请求集配置
  ↓
加载并校验协议
  ↓
展开 annual/monthly 两个 BusinessRequest
  ↓
编译为 EngineTask
  ↓
一次性发现并加载 1 个年产品和 12 个月产品
  ↓
在年度参考网格上编译一次 mask
  ↓
执行年度标准请求（subset → transform → stat → plot → export → report_inputs）
  ↓
执行月度标准请求（subset → transform → stat → plot → export → report_inputs）
  ↓
派生云水资源专题指标（调用一次 derive_cloud_water_year_from_prepared）
  ↓
生成五幅专题图
  ↓
生成 DOCX 报告
  ↓
重定向所有清单路径（从 staging 到最终目录）
  ↓
事务式发布（全部成功后原子替换）
```

## 产物目录结构

```
output_root/
  standard_requests/
    annual/
      export/...
      report_inputs/request_manifest.json
    monthly/
      export/...
      report_inputs/request_manifest.json
  business_metrics/...
  spatial_composite/...
  profile_image/target_image1.png ... target_image5.png
  report_inputs/
    request_set_manifest.json
    report_inputs.json
  report/<report_filename>
```

## 清单文件

### request_set_manifest.json

```json
{
  "schema_version": 1,
  "request_set_id": "nmg-zxb-cloud-water-2025",
  "request_set": "cloud_water_single_year",
  "members": [
    {
      "role": "annual",
      "request_id": "nmg-zxb-cloud-water-2025-annual",
      "manifest": "<final>/standard_requests/annual/report_inputs/request_manifest.json"
    },
    {
      "role": "monthly",
      "request_id": "nmg-zxb-cloud-water-2025-monthly",
      "manifest": "<final>/standard_requests/monthly/report_inputs/request_manifest.json"
    }
  ],
  "product_report_inputs": "<final>/report_inputs/report_inputs.json"
}
```

## 执行命令

```bash
conda run -n cwr_py312 cwr-engine --request examples/requests/nmg-zxb-cloud-water-single-year-2025.json
```

## 兼容性

- 新请求集仍通过统一用户入口执行：`cwr-engine --request <request-set.json>`
- `--request` 根据顶层 `request_set` 分发到请求集编排器；普通 `BusinessRequest` 行为保持不变
- `--workflow-spec` 已于 2026-08-31 退役；原单年配置应迁移为本协议的
  `cloud_water_single_year` 请求集。
