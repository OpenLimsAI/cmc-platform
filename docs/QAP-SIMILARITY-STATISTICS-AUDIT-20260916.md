# 相似性统计口径核对记录

日期：2026-09-16。状态：代码审计与合成算例核对，待业务口径确认。

**后续修正状态：** 本文保留修正前的审计证据。负责人随后要求先修新版统计层，已完成CI/alpha、角色方向、真实方差方法、Tier统一参数及异常状态修正，详见[修正记录](QAP-SIMILARITY-STATISTICS-FIX-20260916.md)。下文“已移植函数保留旧行为”及新版源码行号属于修正前快照；页面尚未接入推断统计这一点仍然成立。

## 1. 结论与证据边界

当前新页面实现的是原始数值的描述性比较。均值、样本标准差、个体差、最小/最大差值、参考 SD 带及带内比例已有实现；置信区间、TOST、Tier1/Tier2 判定尚未接入页面。不能据此认定新旧相似性分析已经全面一致。

旧版有可直接从调用关系确认的错误：所选置信度与 TOST 的 alpha 换算不一致、均值差方向在不同图之间相反、方差方法标签未对应实际算法、Tier1 与主表使用的参数不同。视觉复刻不应同时复制这些错误。

本记录仅依据 Mac 本地实际代码和人工构造的数组；未查询数据库，未修改数据库、历史记录、业务规则或统计代码，未操作 Linux。合成算例只验证本记录指出的计算行为，不等于真实业务数据验收。旧代码中的默认参数、注释及文献名称均不代表已经批准的业务规则。

源码位置及行号以本次审计时文件为准；后续修改可能使行号移动。

## 2. 当前页面调用链

| 对象 | 实际状态及证据 |
|---|---|
| 新相似性接口 | `backend/app/api/v1/similarity.py:13-22` 调用 `analyze_similarity`，返回 `analysis_scope=descriptive_raw_values`、`judgement=not_evaluated`、差值方向 `comparison_minus_reference` |
| 新描述统计服务 | `backend/app/services/dashboards/similarity_service.py:13-66`，没有调用 TOST 或 Tier 判定 |
| 新请求参数 | `backend/app/schemas/similarity.py:6-17`；只有筛选、参比/比较产线和探索参考带倍数，不含置信度、Tier、方差阈值、手动等效界值或判定比例阈值 |
| 已移植统计函数 | `backend/app/services/stats/equivalence.py:14-72` 和 `backend/app/services/stats/similarity.py:115-197` 保留旧算法；文件存在不代表页面已经接入或算法已经验证可用 |

以上本项目文件绝对根路径为 `/Users/qingcheng/code/cmc-quality-analytics-platform/`。下文“旧项目”的绝对根路径为 `/Users/qingcheng/code/quality_analysis_dashboard/`。

## 3. 相同的描述统计公式

记 R 为参比组，T 为比较组；n 为当前分组内有效数值观察的条数。以下“一致”要求两版输入的记录集合完全相同，不能只比较相同的项目名或指标名。

| 统计项 | 公式/实现 | 一致范围 |
|---|---|---|
| 均值 Mean | `mean = sum(x) / n` | 新旧一致 |
| 样本 SD | `s = sqrt(sum((x - mean)^2) / (n - 1))`，即 `ddof=1` | 新旧一致；n 小于 2 时不可计算 |
| 个体差 | `d_i = x_Ti - mean_R` | 新旧个体差图一致 |
| 差值范围 | `[min(x_T) - mean_R, max(x_T) - mean_R]` | 新旧一致，不是置信区间 |
| 参考 SD 带 | `[mean_R - k * s_R, mean_R + k * s_R]` | 同一 k 和同一输入下相同；默认 k 为 3 仅是现有探索参数 |
| 带内比例 | `sum(lower <= x_Ti <= upper) / n_T` | 新旧均包含边界；新版只报告比例，不给出“相似/不相似” |

证据：

- 新 `/Users/qingcheng/code/cmc-quality-analytics-platform/backend/app/services/dashboards/similarity_service.py:31-53`。
- 旧 `/Users/qingcheng/code/quality_analysis_dashboard/dashboards/similarity_dashboard.py:90-101,221-247`。
- 旧 `/Users/qingcheng/code/quality_analysis_dashboard/analytics/similarity_plot.py:419-423,469-479`。
- 旧 `/Users/qingcheng/code/quality_analysis_dashboard/analytics/equivalence_test.py:270-278`。

## 4. 输入记录与计算粒度不同

| 项目 | 旧页面 | 新页面 | 影响 |
|---|---|---|---|
| 汇总粒度 | 项目、指标、产线；查询未取得样品类型、方法、单位、子批等字段 | 先按指标名、原指标名、样品类型、检测类别、方法、单位、放置状态、子批分面，再按产线比较 | 同一项目/指标的 N、Mean、SD 可能不同；新面板可能缺少同条件参比组 |
| 数据来源 | 来源多选，可混合后计算 | 单一来源分析；Excel 历史适配目前仅接受源表 `data_source=QC_LIMS` | 必须选相同来源才能对账，不应把来源范围不同误认为计算错误 |
| 重复记录 | 保留查询所得行，没有按批号去重或先取批均值 | 同样保留每条观察及来源结果编号 | N 是观察条数，不能直接解释为独立批次数 |
| 单位 | 旧查询未读取结果单位，按储存值计算 | 分单位展示；旧 Excel 源表没有结果单位，因此显示未知并保留原值 | 均未在该相似性流程中将 Excel 原值自动乘 100；百分比显示与等效界值仍须确认 |
| 参比 N<2 或 SD=0 | 跳过该指标/参比组合 | 保留描述数据和警告，不生成参考带或比例 | 新版不以缺少 SD 为由隐藏全部原始观察 |

具体证据：

- 旧查询与汇总：`/Users/qingcheng/code/quality_analysis_dashboard/dashboards/similarity_dashboard.py:70-75,127-147,215-232`。
- 新分面字段与分组：`/Users/qingcheng/code/cmc-quality-analytics-platform/backend/app/services/dashboards/similarity_service.py:10,16-40,54-65`。
- 新 Excel 来源限制、原值及未知单位处理：`/Users/qingcheng/code/cmc-quality-analytics-platform/backend/app/repositories/legacy_excel_repository.py:45-76`。

当前分面规则避免将不同样品、方法或单位直接混合，但 `sub_lot` 等字段是否应作为每次产线比较的强制分面，仍需业务确认。不能为得到图形而自动合并不相同的条件。批内平行测定、复测、更正记录如何取舍，也不能仅靠“保持旧版一致”决定。

## 5. 置信区间与图 0 的口径

旧图 0 的误差线来自参比均值的双侧置信区间。若选择的置信度为 C：

```text
SE_R = s_R / sqrt(n_R)
q = t.ppf((1 + C) / 2, df=n_R - 1)
CI_R = [mean_R - q * SE_R, mean_R + q * SE_R]
```

依据：`/Users/qingcheng/code/quality_analysis_dashboard/dashboards/similarity_dashboard.py:242-258`。

本次核对时，新图 0 使用的是 ±样本 SD，没有实现均值 CI。SD 描述单条观察的分散程度，均值 CI 表示均值估计的不确定范围，两者不能互相替代，也不能只把图名改成 CI 来实现“对齐”。当前新 API 不返回 CI，后续视觉调整应继续明确误差线类型。

## 6. 旧版 TOST 与判定问题

### 6.1 所选置信度与 alpha 换算错误

旧页面传入 `alpha = 1 - conf_level`，而底层函数使用双侧 CI 水平 `1 - 2 * alpha`：

| 页面所选置信度 | 实际传入 alpha | 底层实际 CI 水平 |
|---|---:|---:|
| 90% | 0.10 | 80% |
| 95% | 0.05 | 90% |

依据：

- `/Users/qingcheng/code/quality_analysis_dashboard/dashboards/similarity_dashboard.py:280-285`。
- `/Users/qingcheng/code/quality_analysis_dashboard/analytics/stat_core.py:847-852`。

若用户所选 C 指该函数的双侧置信度，应由 `alpha = (1 - C) / 2` 推导。该修正来自现有被调用函数的定义；不能继续显示 90% 而计算 80%。

### 6.2 差值方向在旧图之间相反

旧 TOST 调用顺序为 `(ref_vals, test_vals)`，底层计算 `mean(x1) - mean(x2)`，得到“参比 − 比较”；旧个体差、差值范围图却计算“比较 − 参比”。

依据：

- `/Users/qingcheng/code/quality_analysis_dashboard/dashboards/similarity_dashboard.py:280-282`。
- `/Users/qingcheng/code/quality_analysis_dashboard/analytics/stat_core.py:828`。
- `/Users/qingcheng/code/quality_analysis_dashboard/analytics/similarity_plot.py:423,476`。

新版描述比较统一“比较 − 参比”，见 `/Users/qingcheng/code/cmc-quality-analytics-platform/backend/app/services/dashboards/similarity_service.py:49-51`。建议后续 CI、TOST 也使用这一方向，并在图轴及统计表明确显示，避免同一组差异在不同图上正负相反。

### 6.3 方差方法标签没有对应实际算法

旧 Brown–Forsythe 使用中位数中心，传统 Levene 使用均值中心；BF 的 p 值大于 0.05 标记为 TOST2，否则为 TOST1。但底层 TOST 始终使用合并方差，未根据该标签切换为不等方差算法：

```text
s_p^2 = ((n_R - 1) * s_R^2 + (n_T - 1) * s_T^2) / (n_R + n_T - 2)
SE = sqrt(s_p^2) * sqrt(1 / n_R + 1 / n_T)
df = n_R + n_T - 2
d = mean_R - mean_T             # 旧调用方向
t_lower = (d + delta) / SE
t_upper = (d - delta) / SE
p_TOST = max(1 - t.cdf(t_lower, df), t.cdf(t_upper, df))
equivalent = (p_TOST < alpha)
```

此外，侧栏允许输入 BF 阈值 `bf_p_th`，但此变量后续未参与调用，实际仍固定比较 0.05。

依据：

- `/Users/qingcheng/code/quality_analysis_dashboard/analytics/equivalence_test.py:65-70`。
- `/Users/qingcheng/code/quality_analysis_dashboard/dashboards/similarity_dashboard.py:196-197,269-270`。
- `/Users/qingcheng/code/quality_analysis_dashboard/analytics/stat_core.py:826-852`。

新版已移植的底层函数保留相同行为，见 `/Users/qingcheng/code/cmc-quality-analytics-platform/backend/app/services/stats/equivalence.py:36-58,177-183`；当前页面未调用，因此尚未把这个问题带入新页面判定。后续必须让实际方差公式与显示方法一致。

### 6.4 Tier1 与主表 Equivalent 使用不同参数

旧主表 TOST 使用页面选择的 alpha 和手动/自动 delta；另一次 Tier1 判定则使用默认 `alpha=0.05`、`delta=1.5 * SD_ref`。调用 Tier1 判定时没有传入页面所选置信度或手动 delta，因此可以出现主表等效、Tier1 不相似的同屏冲突。

旧 Tier2 独立使用 `[mean_R - k * SD_R, mean_R + k * SD_R]`、默认命中比例不低于 90% 的规则，手动 delta 同样不改变该规则。旧代码对单点比较还另设 `abs(x_T - mean_R) <= k * SD_R` 的相似标签；这不是运行了 TOST，不能用相同标签掩盖证据类型不同。

依据：

- `/Users/qingcheng/code/quality_analysis_dashboard/dashboards/similarity_dashboard.py:234-238,280-297`。
- `/Users/qingcheng/code/quality_analysis_dashboard/analytics/equivalence_test.py:86-88,234-278`。

### 6.5 旧函数在返回前舍入

旧 TOST 将均值差和 CI 舍入至小数点后 4 位、p 值舍入至 5 位后返回。对很小量纲的指标，这会压缩显示精度；后续应保留完整计算精度，在展示层控制格式。

依据：`/Users/qingcheng/code/quality_analysis_dashboard/analytics/stat_core.py:854-863`。等效布尔值在舍入前计算，因此本条不表示舍入直接改变旧布尔判定，但舍入后的数字可能难以解释临界结论。

## 7. 合成复现：同一旧页面可以给出矛盾结论

本算例不含任何业务数据。代码审计确认旧函数与本项目已移植函数使用相同公式；在本项目 Python 环境中调用该纯统计函数，复现旧页面的参数传递方式。

输入：

```text
ref = [98, 99, 100, 101, 102]
test = [98.7, 99.7, 100.7, 101.7, 102.7]
n_R = n_T = 5
mean_R = 100
mean_T = 100.7
SD_R = 1.5811388300841898
delta = 1.5 * SD_R = 2.3717082451262845
```

实测输出（CI 等字段沿用旧函数返回的舍入位数）：

| 调用 | mean_diff | p_TOST | CI | 结论 |
|---|---:|---:|---|---|
| 旧页选择 90%，传 alpha=0.10 | -0.7 | 0.06656 | [-2.0968, 0.6968]，实际 80% CI | `Equivalent=True` |
| 旧页选择 95%，传 alpha=0.05 | -0.7 | 0.06656 | [-2.5595, 1.1595]，实际 90% CI | `Equivalent=False` |
| 同一指标的旧 Tier1 默认调用 | 同上 | 同上 | 内部 alpha=0.05 | `Not Similar` |

因此旧页选 90% 时，主表 `Equivalent=True` 与同一比较的 `Tier_Judgement=Not Similar` 可以同时出现。新版当前描述均值差为 `+0.7`，采用“比较 − 参比”方向，未生成上述判定。

复现核心调用：

```python
import numpy as np
from app.services.stats.equivalence import perform_tost
from app.services.stats.similarity import tier_similarity_judge

ref = np.array([98, 99, 100, 101, 102])
test = ref + 0.7
sd = float(np.std(ref, ddof=1))
for confidence in (0.90, 0.95):
    print(perform_tost(
        ref, test, delta=1.5 * sd,
        alpha=1 - confidence, return_detail=True,
    ))
print(tier_similarity_judge("x", ["x"], ref.mean(), sd, ref, test))
```

## 8. 接入推断统计前的业务确认与实施边界

需负责人确认的内容：

1. **独立样本是什么**：按批均值比较，还是允许每条检验观察作为样本；平行测定、复测、更正及剔除记录如何处理。
2. **可比较范围是什么**：不同样品、方法、子批和放置状态能否合并；来源是否允许混合；单位及百分比口径是否相同。
3. **哪些指标进入 Tier1/Tier2**：旧版默认字段仅供核对，不自动视为已批准的分层。
4. **等效界值来自哪里**：逐指标的绝对 delta，或经确认的参考 SD 倍数；不能默认为所有项目沿用旧 1.5SD/3SD。
5. **判定参数与结果用途**：双侧置信度、方差处理方式、Tier2 命中阈值、最低独立样本量；明确探索比较与正式质量结论的边界。

可先完成的技术修正：统一差值方向，按所选双侧置信度推导 alpha，使方差算法与方法名称一致，让主表、CI 图与 Tier 结果使用同一套明确参数，保留不足以判断的状态。接入后应用独立手算/合成样本覆盖边界，再用已确认筛选条件的 Mac 记录对账。

本次不自动启用旧 TOST/Tier 默认值，不生成批准状态，不执行数据库迁移或部署。视觉和布局的后续对齐，应在总核对文档单独记录，不能代替本节的统计验收。
