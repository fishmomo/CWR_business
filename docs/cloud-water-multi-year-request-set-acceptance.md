# 多年报告统一请求集验收记录

## 结论

- 阶段：多年报告统一请求集成。
- 日期：2026-08-30。
- 结论：通过，阶段截止。
- 实施边界：仅接入现有多年报告，不新增公式、图件、模板或重采样。

## 验证命令

```powershell
conda run -n cwr_py312 cwr-engine --request examples/requests/nmg-zxb-cloud-water-multi-year-2021-2025.json
conda run -n cwr_py312 python -m pytest -p no:cacheprovider -q
```

原 `--workflow-spec` 命令是本次历史验收的对照入口，已于 2026-08-31
退役；当前多年报告只使用上述 `--request` 命令。

## 合成验收

- 年度标准结果包含 5 个时段，月度标准结果包含 60 个时段。
- 产品加载次数为 65，mask 编译次数为 1，年度专题派生次数为 5。
- 覆盖未知字段、非连续年份、月份不完整、缺年度、缺月份、重复年度产品、
  网格不一致、DOCX 失败和发布失败。
- 失败时原正式目录保持不变，正式 JSON 不包含 staging 或临时目录路径。
- 多年请求集专项测试 13 项通过，完整测试 132 项通过。

## 真实数据验收

- 产品：`H:\result_china\NCEP` 中 2021–2025 年 5 个年度和 60 个月度产品。
- 区域：内蒙古中西部七盟市研究区 SHP，使用同一内部 mask。
- 新入口：`artifacts/runs/nmg-zxb-cloud-water-multi-year-request-2021-2025`。
- 历史兼容基线：`artifacts/runs/nmg-zxb-cloud-water-multi-year-2021-2025`。
- 业务指标 JSON、空间 NetCDF 和六幅 PNG 的 SHA-256 均一致。
- DOCX 正文 66 段、2 张表、6 幅图一致；全部 OOXML 部件一致，占位符为 0。
- 新入口额外产出年度/月度标准 CSV、标准 NetCDF、成员清单和请求集清单。

## 可靠性修复

多变量、多时段的标准格点结果曾因 SciPy NetCDF3 继承 unlimited-dimension
编码而产生无效文件头。标准格点导出改用环境中已声明的 `h5netcdf`，输出为
NetCDF4/HDF5；现有格点导出、业务请求和目录数据源测试均已同步验证。

## 环境限制

本轮以 DOCX 的 OOXML 部件和六个嵌入媒体逐字节一致作为结构等价依据；对照报告
此前已完成页面验收。
