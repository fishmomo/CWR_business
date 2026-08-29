# 检查点 3：真实数据终验

## 结论

- 审查轮次：检查点 3 终验。
- 基线/候选提交：旧入口与统一请求集候选提交 `0f21738`。
- 结论：通过。
- P0/P1/P2：发现并修复 1 个 P1，正式 `mask_bundle.json` 曾保留 staging 路径；修复后全部正式 JSON 均无临时路径。
- 是否允许阶段截止：是。

## 执行环境与命令

- 环境：Conda `cwr_py312`，Python 3.12。
- 官方产品：`H:\result_china\NCEP`。
- 区域：`data/inputs/内蒙古中西部/内蒙古中西部_7盟市融合研究区.shp`。
- 模板：`data/templates/Simple-Year_Evaluation_Report-xizang-cm.docx`。

```powershell
conda run -n cwr_py312 cwr-engine --workflow-spec examples/workflows/nmg-zxb-cloud-water-single-year.json
conda run -n cwr_py312 cwr-engine --request examples/requests/nmg-zxb-cloud-water-single-year-2025.json
conda run -n cwr_py312 python -m pytest -p no:cacheprovider -q
```

旧入口对照产物保存在忽略目录
`artifacts/runs/nmg-zxb-cloud-water-single-year-2025-legacy-baseline-0f21738`；
新入口正式产物保存在
`artifacts/runs/nmg-zxb-cloud-water-single-year-2025`。

## 等价性结果

- `business_metrics/cloud_water_single_year.json`：SHA-256 一致。
- `spatial_composite/cloud_water_single_year.nc`：SHA-256 一致。
- `profile_image/target_image1.png` 至 `target_image5.png`：五幅图的 SHA-256 均一致，因此无像素或样式差异。
- DOCX：58 个正文段落和两张表格文本完全一致，均包含五个内嵌图片且媒体哈希一致；两份 DOCX 的全部 OOXML 部件逐字节一致。
- DOCX 占位符：未解析 `<<...>>` 槽位为 0。
- 新入口额外生成年度/月度标准 CSV、标准 NetCDF、两个成员清单、请求集清单和 mask 清单；这些是协议要求的新增产物，不属于旧入口差异。
- 正式 JSON 路径检查：未发现 staging、临时目录或 `.tmp` 路径。
- 完整测试：119 项全部通过。

## 环境限制

当前 Windows 账户未发现 LibreOffice 安装记录或 `soffice.exe`，因此本轮未重新生成
DOCX 页面 PNG。该限制不影响本轮等价性判断：新旧 DOCX 的全部 OOXML 部件和五个
嵌入媒体均一致，且对照 DOCX 属于此前已完成页面验收的兼容入口产物。

## 截止范围

本阶段在单年报告边界截止，不接入多年报告。下一候选阶段为“多年报告统一请求集成”，
当前仅规划、未激活。
