# 检查点 1：外包设计回传（未通过，仅作审查记录）

## 1. 基线信息

| 项目 | 值 |
|------|-----|
| 基线分支 | `master` |
| 基线提交 | `8032a6f` |
| Python 环境 | `conda run -n cwr_py312` |
| 测试结果 | **88 passed** in 31.05s |

## 2. 新配置协议 JSON Schema 草案

**协议名称**: `cloud_water_single_year_request_set`（schema_version 1）

**核心设计决策**: 请求集合是纯配置层，不运行统一请求管线。`data_source`、`region`、`year` 是权威数据源声明，`requests` 子块是声明式文档，描述云水内核需要哪些产品。编排器直接调用云水内核进行全部计算，统一请求管线不参与。

```json
{
  "schema_version": 1,
  "request_set": "cloud_water_single_year",
  "request_set_id": "nmg-zxb-cloud-water-2025",
  "year": 2025,
  "region_name": "内蒙古中西部七盟市研究区",
  "data_source": {
    "kind": "netcdf",
    "root": "H:\\result_china\\NCEP",
    "engine": "h5netcdf"
  },
  "region": {
    "kind": "shp",
    "path": "../../data/inputs/内蒙古中西部/内蒙古中西部_7盟市融合研究区.shp"
  },
  "requests": {
    "annual": {
      "role": "annual",
      "variables": ["GMv", "GMh", "CWR", "Ps", "Cvh", "CEv", "PEh", "PEv"],
      "operators": ["mean"],
      "results": [
        {"scope": "region", "format": "csv", "name": "annual_regional"},
        {"scope": "grid", "format": "netcdf", "name": "annual_grids"}
      ]
    },
    "monthly": {
      "role": "monthly",
      "variables": ["GMv", "GMh", "CWR", "Ps", "Cvh", "CEv", "PEh"],
      "operators": ["mean"],
      "results": [
        {"scope": "grid", "format": "netcdf", "name": "monthly_grids"}
      ]
    }
  },
  "template": "../../data/templates/Simple-Year_Evaluation_Report-xizang-cm.docx",
  "output_root": "../../artifacts/runs/nmg-zxb-cloud-water-single-year-2025",
  "report_filename": "2025-Year_Evaluation_Report-nmg-zxb.docx",
  "image_width_inches": 4.0,
  "image_widths_inches": {
    "target_image3": 6.2,
    "target_image4": 6.2,
    "target_image5": 6.2
  }
}
```

**校验规则**:

- `schema_version` 必须为 1
- `request_set` 必须为 `"cloud_water_single_year"`
- `year` 必须为整数
- `requests` 必须包含 `annual` 和 `monthly` 两个键，各自含 `role` 字段
- `data_source` 校验复用统一请求的 `_validate_data_source()`（kind=netcdf, root 非空）
- `region` 校验复用统一请求的 `_validate_region()`（kind 为 shp/existing_mask/bbox）
- 子请求 `variables` 使用统一请求注册表规范名称（`Ps` 而非 `SP`，`Cvh` 而非 `MC`）
- `dxy` 不在子请求中声明——它是云水内核内部变量，仅在 source 产品中读取
- 子请求 `results` 复用统一请求 `_validate_results()` 校验
- 报告字段校验规则与现有 `CloudWaterSingleYearWorkflowSpec` 一致
- 编排器从 `data_source` 构造 `product_source` 传给云水内核（添加 `payload` 包装层）

**region 格式转换**: 统一请求的 `region` 格式（扁平 `{"kind":"shp","path":"..."}`）在编排器内部转换为云水内核的 `region_spec` 格式（`{"kind":"shp","payload":{"path":"..."}}`）。

## 3. 旧 `workflow-spec` 字段到新协议字段逐项归属表

| 旧字段 (`workflow-spec`) | 新字段 (`request_set`) | 归属说明 |
|---|---|---|
| `schema_version` | `schema_version` | 保留，同为 1 |
| `workflow` | `request_set` | 重命名，值 `"cloud_water_single_year"` |
| `task_id` | `request_set_id` | 重命名 |
| `year` | `year` | 上移到顶层，统一请求格式的权威来源 |
| `region_name` | `region_name` | 上移到顶层 |
| `product_source` | `data_source` | 重命名，对齐统一请求术语，编排器内部转换 |
| `region_spec` | `region` | 重命名，对齐统一请求扁平格式，编排器内部包装 `payload` |
| `template` | `template` | 保留 |
| `output_root` | `output_root` | 保留 |
| `report_filename` | `report_filename` | 保留 |
| `image_width_inches` | `image_width_inches` | 保留 |
| `image_widths_inches` | `image_widths_inches` | 保留 |
| *(无)* | `requests.annual` | **新增**：年度产品需求声明（文档用途） |
| *(无)* | `requests.monthly` | **新增**：月度产品需求声明（文档用途） |

## 4. 年度与 12 个月度产品依赖的表达、发现和缺失处理

**表达方式**: 请求集合声明 `year` 字段，`requests` 子块声明角色。编排器内部将 `year` 传递给云水内核。

**发现方式**: 完全沿用现有 `cloud_water_core._discover_direct_product_files()`。该函数使用 `product_source.root` + `annual_pattern`/`monthly_pattern` 进行 glob 发现。编排器不引入新的发现路径。

**缺失处理**: `_discover_direct_product_files` 中 `len(matches) != 1` → `ValueError` → 编排器捕获 → 失败发生在 staging 目录 → 正式输出不变。

## 5. Mask 的创建、复用和传递路径

**Mask 创建**: 云水内核 `_compile_direct_mask()` 在 `derive_cloud_water_year()` 内部完成，从 `region_spec` + 产品经纬度网格编译。无变更。

**传递路径**: 单次 `derive_cloud_water_year()` 调用内部，mask 编译一次后同时用于 annual 和 12 个月度产品的聚合计算。这是现有行为，无需修改。

```
derive_cloud_water_year(data_source, region, year)
  ├── _discover_direct_product_files()        → 1 年产品 + 12 月产品路径
  ├── _load_direct_product(annual)             → annual_dataset
  ├── _compile_direct_mask(region, lat, lon)   → mask (一次性编译)
  ├── _aggregate_direct_product(annual, mask)  → annual record
  ├── for each month:
  │     _load_direct_product(monthly)          → monthly_dataset
  │     _validate_product_grid(ref, dataset)   → 网格一致性校验
  │     _aggregate_direct_product(dataset, mask) → monthly record
  ├── _direct_spatial_composite(annual, monthly, mask) → spatial
  └── return CloudWaterYearResult
```

Mask 在整个调用中只编译一次，由 `derive_cloud_water_year` 内部管理，不需要外部传入或跨调用传递。

## 6. 标准请求清单、专题输入清单和最终报告清单的关系图

```
cloud_water_single_year_request_set.json
  │
  ├─ [编排器] 读取配置，校验 schema
  │
  ├─ [编排器] 转换 data_source → product_source, region → region_spec
  │
  ├─ [云水内核] derive_cloud_water_year(product_source, region_spec, year)
  │   ├── 产品发现 → 1 年产品 + 12 月产品
  │   ├── mask 编译 → 一次性
  │   ├── 年度/月度聚合 → 指标计算
  │   ├── 空间合成 → spatial_composite.nc
  │   └── 图件渲染 → 5 张 PNG
  │
  │   产物：
  │   ├── business_metrics/{name}.json
  │   ├── spatial_composite/{name}.nc
  │   ├── profile_image/target_image{1..5}.png
  │   └── report_inputs/report_inputs.json  ← 唯一清单文件
  │
  ├─ [报告] build_cloud_water_single_year_report()
  │   └── report/{report_filename}.docx
  │
  └─ [编排器] finalize_report_inputs + publish_directory
```

**清单文件唯一性**: 只产生一个 `report_inputs/report_inputs.json`，由云水内核 `build_cloud_water_business_metrics()` 生成，经 `finalize_report_inputs` 重定向路径并追加 `docx_report` 条目。

**请求集引用**: `report_inputs.json` 的 `inputs` 段新增 `request_set_id` 字段，记录使用的请求集标识。

**失败行为**: 任一步失败 → staging 目录清理 → 正式 `output_root` 不变。

## 7. 事务发布和失败回滚流程

与现有 `build_cloud_water_single_year_workflow()` 完全一致：
1. 在 `output_root` 同级创建 `.{name}-staging-*` 临时目录
2. 所有产物（metrics、spatial、figures、report_inputs、docx）写入 staging
3. 全部成功后 `publish_directory(staging, output_root)` 原子替换
4. 失败时 `TemporaryDirectory` 上下文管理器自动清理 staging
5. 已有正式输出不受影响

## 8. 预计新增、修改、删除的文件清单

| 操作 | 文件路径 | 必要性说明 |
|------|---------|-----------|
| **新增** | `src/cwr_engine/workflows/cloud_water_single_year_request_set.py` | 请求集编排器：加载校验配置、转换格式、调用云水内核、组装报告 |
| **新增** | `examples/requests/nmg-zxb-cloud-water-single-year-2025.json` | 新协议示例（迁移自 workflow-spec） |
| **新增** | `tests/test_cloud_water_single_year_request_set.py` | 合成测试、兼容测试、失败测试 |
| **修改** | `src/cwr_engine/cli.py` | 在 `--workflow-spec` 分发中增加 `cloud_water_single_year_request_set` 分支 |
| **不修改** | `src/cwr_engine/pipeline.py` | 不参与此流程，无需 prebuilt_mask 参数 |
| **不修改** | `src/cwr_engine/business_metrics/cloud_water_core.py` | 计算内核不变 |
| **不修改** | `src/cwr_engine/business_metrics/cloud_water.py` | 指标生成不变 |
| **不修改** | `src/cwr_engine/business_metrics/cloud_water_figures.py` | 图件渲染不变 |
| **不修改** | `src/cwr_report/profiles/cloud_water_single_year.py` | 报告组装不变 |
| **不修改** | `src/cwr_engine/workflows/cloud_water_single_year.py` | 旧入口保留兼容 |
| **不修改** | `src/cwr_engine/workflows/cloud_water_shared.py` | 事务发布复用现成函数 |
| **不修改** | `src/cwr_engine/business_metrics/cloud_water_config.py` | 配置校验复用现成函数 |
| **不修改** | `src/cwr_engine/registries/*` | 不新增变量/算子/图型 |
| **不删除** | 任何文件 | 本阶段不删除旧入口 |

**编排器核心逻辑**（伪代码，说明计算路径不重复）：

```python
def build_cloud_water_single_year_request_set(spec_path: Path) -> Path:
    spec = load_request_set(spec_path)  # 新校验逻辑
    # 转换格式：data_source → product_source, region → region_spec
    product_source = _to_product_source(spec.data_source)
    region_spec = _to_region_spec(spec.region)
    # 直接调用云水内核（唯一计算路径）
    metrics_spec = _write_metrics_spec(staging, spec, product_source, region_spec)
    report_inputs = build_cloud_water_business_metrics(metrics_spec)
    # 报告组装
    build_cloud_water_single_year_report(profile_spec)
    # 事务发布
    finalize_report_inputs(...)
    publish_directory(...)
```

**不重复计算**的证明：
- 编排器只调用 `build_cloud_water_business_metrics()` 一次
- `build_cloud_water_business_metrics()` → `derive_cloud_water_business_metrics()` → `derive_cloud_water_year()` 是唯一计算路径
- 产品发现、加载、mask 编译、聚合、空间合成均在此单一路径内完成
- 不调用 `run_business_request()`、`compile_business_request()` 或 `run_engine_task()`
- 子请求（`requests.annual`/`requests.monthly`）是声明式文档，不触发任何计算
