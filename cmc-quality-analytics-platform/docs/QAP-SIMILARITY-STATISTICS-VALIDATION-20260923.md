# 相似性汇总表：公式复核与方法适用性

日期：2026-09-23。范围：当前工作树的相似性统计服务、页面汇总表与 Excel 探索报告。只验证代码和人工构造的数值例子；不讨论上游结果筛选，也不把探索参数认定为批准标准。

## 结论

当前汇总表的**算术和程序传递**已通过独立算例：原始观察生成的 N、均值、样本方差、均值差、SE、自由度、CI、TOST p 值、Brown–Forsythe/Levene p 值、Δ、Tier2 命中数和比例均与独立公式或 `statsmodels`/SciPy 结果一致；Excel 报告中的关键数字也与手算值一致。专项测试覆盖自动/手动 Δ、合并方差/Welch、90%/95% CI、常量值、样本不足和边界值。**公式正确不等于当前默认方法适合用来确认产品相似。**

建议目前继续作为探索看板。若将来要给出正式相似性结论，需要先定每个属性的比较目标、界值及分析方法，再考虑确认性判定。旧版留下的 Tier1 `1.5×参比SD`、Tier2 `3×参比SD` 和 `90%` 命中阈值，在本项目中没有找到可证明适用于每个属性的统计依据。

## 34 列逐类核对

记参比为 R、比较为 T，`d = mean(T) − mean(R)`，`n` 为入图的有效数值条数；样本方差分母为 `n−1`。表由 `backend/app/services/dashboards/similarity_service.py::_exploratory_row` 生成；页面直接读取该行，Excel 由同一服务重新计算后写入。

| 列 | 当前计算或含义 | 核对结果 |
|---|---|
| `Project`, `Attribute`, `Reference`, `Test_Group`, `Sample_Type`, `Test_Type`, `Method_Code`, `Unit`, `Placement_Status`, `Sub_Lot` | 请求和当前分面/产线标识，不是统计量。 | 代码路径确认。 |
| `N_Ref`, `N_Test` | R/T 有效数值观察条数。 | 合成例与 Excel 均核对。 |
| `Ref_Mean`, `Test_Mean`, `Ref_Var`, `Test_Var` | 组均值与样本方差；`Var = SD²`。 | 独立数组核对。 |
| `Mean_Diff` | `d = mean(T)−mean(R)`；正数表示比较组较高。 | 独立数组及方向互换用例核对。 |
| `Brown-Forsythe p-value`, `Levene p-value` | 分别以组中位数、组均值为中心的 Levene 方差齐性检验 p 值。 | 与 SciPy 独立调用核对；它们不是相似性 p 值。 |
| `TOST Method` | BF p 大于所选阈值时为合并方差，否则 Welch；两种方法实际 SE/DF 也对应切换。 | 阈值两侧独立算例核对；**选择策略本身需修改或论证**。 |
| `SE`, `DF` | 合并法：`SE² = sp²(1/nR+1/nT)`、`DF=nR+nT−2`；Welch：`SE²=sR²/nR+sT²/nT`，DF 为 Welch–Satterthwaite。 | 与手算及 `statsmodels` 核对。 |
| `alpha`, `conf_level` | `alpha=(1−C)/2`；C=90% 对应单侧 0.05，C=95% 对应单侧 0.025。 | 两档独立算例核对。 |
| `ci_lower`, `ci_upper` | `d ± t(1−alpha, DF)×SE`，是均值差的双侧 C% CI。 | 与 `statsmodels` 核对；图1读取同一行。 |
| `pTOST`, `Equivalent` | 两个单侧检验的较大 p 值；仅当 `pTOST < alpha` 才是 `Equivalent`。 | 与 `statsmodels.ttost_ind` 核对；`Not Equivalent` 仅表示**未证实等效**。 |
| `Delta` | 手动模式为所填正数；自动模式 Tier1=`1.5×SD_R`、Tier2=`k×SD_R`。 | 合成例和图5带核对；界值的业务合理性尚未确定。 |
| `Tier_Level`, `Tier_Judgement` | Tier1 重用同一次 TOST；Tier2 检查每条 T 是否落入 `mean(R)±Delta`，比例达到所填阈值为 `Similar`。 | 边界、自动/手动、常量值例核对；Tier2 是样本命中规则，并非 TOST。 |
| `Calculation_Status`, `Calculation_Reason` | Tier1 为 TOST 的可计算状态；Tier2 为范围法的可计算状态。 | 样本不足及常量值例核对。 |
| `Approval_Status` | 固定“探索性计算，未批准”。 | 代码及 Excel 核对。 |

图0所示参比均值 CI 另按 `mean(R) ± t((1+C)/2,nR−1)×SD_R/√nR` 计算，已由独立例核对。图5的带与 Tier2 用同一 Δ、同一参比均值和包含边界的比较式；2026-09-23 修复了原先仅由浮点均值最后一位差异造成的图表矛盾。

## 这些统计指标是否适用

1. **均值、SD、方差、单条观察和范围图**适合先描述当前样本。它们不需要假定已经存在一个“通过”标准。均值 CI 表示组均值的不确定性，不代表单条未来结果会落入 CI。
2. **TOST 是合理的均值等效性检验框架，但有条件。** 要回答的是“比较与参比的总体均值差是否小于事先合理设定的 ±Δ”；要有适当的分析单位、近似适用的均值模型，以及预先规定的方法和界值。它不能证明整个分布、方差、每个批次或产品整体都相似。FDA 2026 年生物等效性指南阐述 TOST 与 `100(1−2α)%` 等尾 CI 的数学关系；该指南面向生物等效性研究，**不能把其中的具体接受界值直接搬到这里的质量属性**。[FDA TOST 指南](https://www.fda.gov/media/163638/download)
3. **当前“BF p 决定 pooled/Welch”只说明旧规则已正确实现，不足以证明方法选择合理。** BF/Levene 检验的是方差齐性；p 值大不能证明方差相等。先用同一数据检验方差、再决定均值检验方法，可能改变整体检验性质。建议确认性方案事先固定适当方法；在没有充分的齐方差依据时，优先评估始终使用 Welch，并保留 BF/Levene 作为诊断指标。当前不擅自改变旧报表字段或判定路径。[NIST Levene 定义](https://itl.nist.gov/div898/handbook/eda/section3/eda35a.htm)、[预检方法影响的原始研究](https://pubmed.ncbi.nlm.nih.gov/17971268/)
4. **自动用本次参比 SD 生成 Δ 是探索性界值。** 用正在比较的样本自身决定容许差，再报告普通 TOST 的 p 值，不能直接宣称已控制预期的确认性错误率；尤其参比样本较少时，SD 和带宽不稳定。EMA 关于质量属性比较的反思文件明确区分总体的 `均值±k×SD` 与用有限样本估出来的范围，后者不能自动作覆盖率承诺。应按属性的质量意义和既有知识预先论证界值。[EMA 质量属性统计反思文件](https://www.ema.europa.eu/en/documents/scientific-guideline/reflection-paper-statistical-methodology-comparative-assessment-quality-attributes-drug-development_en.pdf)、[ICH Q5E/FDA](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/q5e-comparability-biotechnologicalbiological-products-subject-changes-their-manufacturing-process)
5. **Tier2 的“落带 90%”是样本比例，不是总体覆盖率的统计证明。** 例如 9/10 在代码中为 90%，但样本少时不确定性很大；`±3×样本SD` 也不是自动包含未来结果 99% 的容许区间。若要作总体概率或未来批次的承诺，应另设计容许区间或二项比例的置信下限等方法，并论证批次数。[EMA 质量属性统计反思文件](https://www.ema.europa.eu/en/documents/scientific-guideline/reflection-paper-statistical-methodology-comparative-assessment-quality-attributes-drug-development_en.pdf)
6. **“未通过”不能反向解释成已经证明不同。** TOST 的 `Not Equivalent` 仅是未证实等效，Tier 的 `Not Similar` 仅是未达到当前规则；页面和 Excel 的说明已按此澄清。多个指标和多个比较产线同时进行时，还需事先规定是逐项通过、整体判断还是探索筛查，避免挑选有利的 p 值。[ASA p 值声明](https://www.amstat.org/asa/files/pdfs/p-valuestatement.pdf)

## 已执行验证

- `backend/.venv/bin/python -m pytest tests/test_similarity.py tests/test_equivalence_corrected.py -q`：**71 passed**。新增两档 BF 阈值核对全部关键数值列，并检查 Excel 中的均值、方差、差值、Δ、N。
- `frontend/` 执行 `pnpm build`：通过；仅有既有的大包体提示。
- `git diff --check`：通过。

六图的桌面、窄屏及参数联动已随后在浏览器中验收，详见[浏览器图形验收](QAP-SIMILARITY-BROWSER-ACCEPTANCE-20260923.md)。该验收不代表统计方法已经获得业务批准；建议路径见[统计方法建议方案](QAP-SIMILARITY-STATISTICAL-METHOD-PROPOSAL-20260923.md)。
