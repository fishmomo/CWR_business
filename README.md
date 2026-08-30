# CWR 通用计算引擎

## 运行环境

项目开发、测试和自动化任务统一使用 Conda 环境 `cwr_py312`（Python 3.12）。

```powershell
conda env update -n cwr_py312 -f environment.yml --prune
conda run -n cwr_py312 python -m pip install -e . --no-deps
conda run -n cwr_py312 python -m pytest -p no:cacheprovider -q
```

通过已安装的命令行工具运行底层标准任务：

```powershell
conda run -n cwr_py312 cwr-engine --task tests/fixtures/minimal_task.json --output-root artifacts/runs/smoke
```

对于常见业务计算，建议使用简化的业务请求协议，不需要手工填写底层时间切片、
工作步骤和内部输出类型：

```powershell
conda run -n cwr_py312 cwr-engine --request examples/requests/nmg-zxb-annual-2025.json
```

业务请求字段以及年、月、日时段选择方式见
`docs/unified-business-request-contract.md`。

真实 NetCDF 产品目录及其 `D/M/Y` 目录约定见
`docs/real-product-data-source-contract.md`。

标准序列图、分布图和对比图请求见 `docs/standard-plot-contract.md`。

正式图件的默认字体、标签、子图、标题、热力图和 colorbar 验收规则见
`docs/figure-visual-acceptance-rules.md`。

根据 `report_inputs.json` 和单一模板生成 DOCX 的方法见
`docs/report-product-contract.md`。

```powershell
conda run -n cwr_py312 cwr-report --spec path/to/report_spec.json
```

现有单年云水资源业务模板通过专用报告配置协议支持，具体见
`docs/cloud-water-single-year-profile-contract.md`。

标准化产品指标生成方式见 `docs/cloud-water-business-metrics-contract.md`。

```powershell
conda run -n cwr_py312 cwr-engine --business-metrics-spec path/to/metrics.json
```

```powershell
conda run -n cwr_py312 cwr-report --profile-spec path/to/profile.json
```

单年云水资源报告通过统一请求集入口运行。请求集以同一数据源和必要区域为
权威输入，分别声明年度与月度标准请求，并在一次事务中生成标准结果、专题指标、
五幅图和 DOCX。具体见 `docs/cloud-water-single-year-request-set-protocol.md`。

```powershell
conda run -n cwr_py312 cwr-engine --request examples/requests/nmg-zxb-cloud-water-single-year-2025.json
```

已验收的多年流程接受至少五个完整连续年份，起止年份均包含。每年需要一个年产品
和十二个月产品，并以事务方式发布标准指标、空间复合数据、六幅图、两张报告表格
和完整 DOCX。具体见 `docs/cloud-water-multi-year-report-contract.md`。

多年报告统一请求集使用同一数据源和必要区域驱动年度、月度标准结果及专题报告：

```powershell
conda run -n cwr_py312 cwr-engine --request examples/requests/nmg-zxb-cloud-water-multi-year-2021-2025.json
```

单年和多年请求集共享的协议校验、数据准备、mask 元数据及兼容入口政策见
`docs/cloud-water-request-set-contract-consolidation.md`。

逐日降水专题使用日产品和必要区域生成标准结果、区域降水与效率序列、降水等级
格点结果、汇总表和三幅专题图：

```powershell
conda run -n cwr_py312 cwr-engine --request examples/requests/nmg-zxb-daily-precipitation-2025.json
```

协议、计算口径和正确 mask 的验收差异见
`docs/daily-precipitation-request-set-protocol.md`。

## 仓库数据

- `data/inputs/`：纳入版本管理的代表性输入数据。
- `examples/legacy-configs/`：引擎建立前的历史业务配置记录，不属于当前引擎任务协议。
- `artifacts/examples/`：经过整理的参考产物。
- `artifacts/runs/`：新流水线运行结果目录，已由 Git 忽略。

## 开发阶段

项目开发遵循明确的阶段门控规则。每个阶段在开始实现前都要声明范围、验收条件和
截止条件。当前阶段边界见 `docs/project-stage-gates.md`。
