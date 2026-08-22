# 检查点 1：上层产品统一请求集成实施设计（定稿）

## 1. 文档状态

- 设计状态：冻结，可进入外包实现。
- 设计负责人：Codex。
- 实现负责人：外包人员。
- 实现范围：仅 `cloud_water_single_year` 单年云水资源报告。
- 变更原则：外包不得自行改变本设计。若设计与真实代码冲突，必须停止实现并回传冲突证据，由设计负责人修订。

`checkpoint-1-contractor-design-rejected.md` 是未通过的外包方案，仅保留为审查记录，不得作为实施依据。本文件是检查点 2 的唯一架构依据。

## 2. 设计结论

采用“两个标准请求、一个共享准备上下文、一次专题派生、三层清单”的结构：

```text
单年产品请求集
  -> 展开并严格校验 annual/monthly 两个 BusinessRequest
  -> 一次性发现并加载 1 个年产品和 12 个月产品
  -> 在年度参考网格上编译一次必要 mask
  -> annual/monthly 通用输出消费共享数据
  -> 云水专题内核消费同一共享数据并派生一次
  -> 两个标准请求清单 + 一个请求集清单 + 一个专题报告清单
  -> DOCX 成功后事务式发布整个目录
```

禁止以下两种替代做法：

- 先完整运行两次 `run_business_request()`，再让云水内核重新发现、加载和计算产品。
- 只把标准请求写进配置但运行时忽略其变量、算子、结果或清单。

## 3. 请求集协议

请求集负责共享字段和产品配置。`annual`、`monthly` 成员在加载时与 `shared_request` 合并，形成两个完整的标准 `BusinessRequest`，随后必须经过统一请求现有的同一套严格校验。

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

### 3.1 展开规则

每个成员展开为：

```text
schema_version = 请求集 schema_version
request_id     = 成员 request_id
data_source    = shared_request.data_source
region         = shared_request.region
period         = 成员 period
variables      = 成员 variables
operators      = 成员 operators
results        = 成员 results
output_root    = 编排器注入的 staging/standard_requests/<role>
```

不得复制统一请求的校验代码。应从 `load_business_request()` 中提取可复用的公开 `parse_business_request(payload, request_path)`，文件加载函数只负责读取 JSON 后调用它。两个展开结果都调用该函数，再调用 `compile_business_request()`。

### 3.2 请求集额外校验

- `schema_version` 只能为 1，未知字段严格失败。
- `request_set` 必须为 `cloud_water_single_year`。
- `requests` 必须且只能包含 `annual`、`monthly`。
- `annual.period` 必须恰好包含一个年份。
- `monthly.period` 必须包含同一年且月份必须恰好为 1 至 12。
- 两个成员使用展开后的同一数据源和同一区域；区域是必要输入。
- 子请求变量、算子和结果由统一注册表及结果协议校验，不能作为说明性死字段。
- `output_root` 只能由请求集编排器注入，成员配置不得自行提供。
- `product.template` 必须存在，报告文件名必须是单一 `.docx` 文件名，图片宽度沿用旧工作流校验。
- 不接受日尺度成员，也不进行任何跨尺度重采样。

专题报告需要的内部源变量由固定 profile 依赖表管理，例如 `dxy` 和边界输送源字段；它们不是用户物理量选择，不添加到通用变量注册表，也不伪装成标准请求变量。

## 4. 唯一执行链

### 4.1 准备阶段

新增不可变结果对象 `PreparedCloudWaterYear`，至少包含：

```text
year
annual_path
monthly_paths[1..12]
annual_dataset
monthly_datasets[1..12]
reference_grid
mask
mask_bundle
annual_source_trace
monthly_source_trace
```

准备函数接收两个已经编译的 `EngineTask`：

1. 以任务的 period 和 data source 为权威来源，发现恰好一个年度文件和十二个月度文件。
2. 每个文件只加载一次；加载变量是“两个标准请求所需源字段”与“云水 profile 固定内部源字段”的并集。
3. 统一坐标名并严格验证年度、月度网格一致。
4. 只在年度参考网格上编译一次 mask，并验证至少包含一个格点。
5. 任何缺失、重复、变量缺失或网格不一致均在正式目录创建前或 staging 内失败。

新入口不得再调用 `_discover_direct_product_files()` 形成第二次发现。旧 `derive_cloud_water_year()` 保留兼容，可继续负责旧入口的发现；新入口调用从共享准备结果派生的公开函数。

### 4.2 通用输出阶段

新增公开的 prepared-context 执行接口，输入为一个已编译 `EngineTask`、对应的已加载 dataset、同一个 mask/mask bundle 和成员输出目录。它跳过 `prepare`、`mask`，只执行该标准请求需要的 `subset`、`transform`、`stat`、`plot`、`export`、`report_inputs`。

约束：

- annual、monthly 的 `variables`、`operators`、`results` 必须真实决定 CSV、NC 或图片产物。
- 算子语义完全沿用现有通用引擎；标准 CSV 的 `mean` 与专题报告中的区域总量是两种不同产物，不得互相冒充。
- annual 和 monthly 使用不同成员目录，清单不得覆盖。
- prepared-context 接口不得重新打开产品文件或重新编译 mask。

### 4.3 专题派生阶段

将现有云水逻辑拆成兼容包装与纯派生两层：

```text
derive_cloud_water_year(...)                   # 旧入口兼容包装
  -> 旧方式发现/加载/mask
  -> derive_cloud_water_year_from_prepared(...)

derive_cloud_water_year_from_prepared(prepared) # 新旧共享的唯一公式入口
  -> 年度/月度区域指标
  -> 季节统计
  -> 空间复合
  -> CloudWaterYearResult
```

专题公式、边界计算、季节定义、空间复合和图件输入不得复制或改变。再将“派生”和“写业务指标、空间 NC、五幅图及专题清单”分离，使新入口可以把已经派生的 `CloudWaterYearResult` 直接交给现有写出逻辑，不得通过临时 JSON/NC 重新读取计算。

同一请求集必须满足：

- 产品发现一次。
- 13 个产品各加载一次。
- mask 编译一次。
- `derive_cloud_water_year_from_prepared()` 调用一次。
- 专题五幅图各生成一次。

## 5. 清单关系与目录

staging 和正式目录使用同一相对结构：

```text
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

`request_set_manifest.json` 是标准请求集合清单，至少包含：

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

专题 `report_inputs.json` 的 `inputs` 新增：

```json
{
  "request_set_id": "nmg-zxb-cloud-water-2025",
  "request_set_manifest": "<final>/report_inputs/request_set_manifest.json"
}
```

发布前统一重定向两个成员清单、请求集清单和专题清单中的 staging 路径。正式清单不得包含临时目录；每个引用必须存在，并位于最终 `output_root` 内。

## 6. 事务边界

请求集编排器是唯一发布者：

1. 在 `output_root` 同级创建唯一 staging 目录。
2. 两个标准请求产物、专题产物、五幅图、DOCX 和全部清单都写入 staging。
3. 完成清单路径重定向和引用存在性检查。
4. 全部成功后调用现有 `publish_directory()` 一次。
5. 任一步失败均删除 staging，并保持已有正式 `output_root` 原样不变。

成员标准请求不得自行发布到正式目录。不得在编排开始前创建正式 `output_root`。

## 7. CLI 与兼容性

- 新请求集仍通过统一用户入口执行：`cwr-engine --request <request-set.json>`。
- `--request` 根据顶层 `request_set` 分发到请求集编排器；普通 `BusinessRequest` 行为保持不变。
- 旧 `cwr-engine --workflow-spec <single-year.json>` 必须继续工作，且不发出强制弃用错误。
- 本阶段不接入多年报告，不删除旧配置和旧测试。

## 8. 允许的代码改动

建议文件边界如下，命名可作不影响职责的微调：

- 新增 `src/cwr_engine/workflows/cloud_water_single_year_request.py`：协议、展开、额外校验、事务编排。
- 修改 `src/cwr_engine/business_request.py`：提取公开 payload 解析函数，不改变普通请求行为。
- 修改 `src/cwr_engine/pipeline.py`：增加严格的 prepared-context 输出接口；现有 `run_engine_task()` 保持兼容。
- 修改 NetCDF 数据源模块：提供可复用的发现、加载和坐标规范化公开接口，禁止复制私有实现。
- 修改 `cloud_water_core.py`：增加 prepared 结果与纯派生入口，旧入口变为兼容包装。
- 修改 `cloud_water.py`：分离派生和产物写出，不改变公式与现有产物。
- 修改 `cloud_water_shared.py`：增加请求集清单写入及多清单路径重定向检查。
- 修改 `cli.py`：仅增加 `--request` 的请求集分发。
- 新增示例、协议文档和专项测试。

不得修改变量、算子和图型注册表，不得修改图件样式、报告 profile、物理公式和多年工作流。

## 9. 检查点 2 必须回传

- 候选分支和独立提交号，工作区必须干净。
- 逐文件变更摘要，以及与本设计章节的对应关系。
- 合成请求执行命令和完整产物树。
- 两个成员标准清单、请求集清单、专题清单的实际 JSON。
- 自动测试证明：产品发现一次、13 个文件各加载一次、mask 一次、专题派生一次。
- 正常、缺年度、缺任一月份、重复产品、非法区域、网格不一致、DOCX 失败和发布失败测试。
- 旧普通 `--request`、旧单年 `--workflow-spec` 的兼容测试。
- 完整测试：`conda run -n cwr_py312 python -m pytest -p no:cacheprovider -q`。

检查点 2 只验收合成数据实现。真实 2025 数据和 DOCX/图件对比属于检查点 3，检查点 2 通过前不得进入。

## 10. 截止条件

本阶段在检查点 2 和检查点 3 均通过、完整测试通过、真实单年报告与旧入口等价并形成独立里程碑提交后截止。截止后停止，不自动接入多年报告。
