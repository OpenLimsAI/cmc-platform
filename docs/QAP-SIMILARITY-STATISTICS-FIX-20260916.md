# 相似性统计层修正记录

2026-09-16，负责人要求先在新版修正旧版错误。本批仅修改 Mac QAP 的纯统计函数和测试；没有修改旧看板、数据库、Linux，也没有提交或推送。

## 已修正

| 问题 | 新版处理 |
|---|---|
| 选90%却算80%差值区间 | 新相似性入口直接接收双侧置信度C，内部唯一换算为 `alpha=(1-C)/2`；90%对应0.05，95%对应0.025。禁止同时传alpha和置信度。 |
| 参比与比较差值方向相反 | `compare_equivalence(reference, comparison, ...)`固定计算比较−参比；通用底层`perform_tost(x1,x2)`仍保留数学上的x1−x2，避免悄悄翻转其他消费者。 |
| TOST1/2只改名称不改算法 | 提供实际`pooled`与`welch`计算；Welch使用各组方差及Satterthwaite自由度。可显式选`brown_forsythe`按BF阈值分支，返回实际采用的方法、阈值及p值；该选择策略不自动视为批准规则。 |
| BF阈值没有生效 | `bf_threshold`进入真实分支判断；同一输入改变阈值可改变实际方差公式，已有独立测试。旧函数返回TOST1/2仅为兼容，新结果使用明确的pooled/welch字段。 |
| 主表与Tier1各算一次、参数不一致 | 新统一入口`evaluate_similarity_pair`只计算一次，CI/p/等效布尔值与Tier1判断共享结果；显式接收置信度、方法和delta。 |
| 手动界值被Tier忽略 | 显式delta进入统一结果；Tier1作为TOST界限，Tier2作为参考带半宽。不同界值必须明确配置，不在另一路径暗中回到旧默认。 |
| 计算前过早舍入 | 内部保留完整浮点精度，展示时再格式化；尾概率使用sf，避免`1-cdf`数值抵消。 |
| 不足以判断却显示不等效/单点相似 | 样本不足、标准误为零、溢出等返回`not_evaluable`及原因，`equivalent=None`、Tier为Unknown。单点不再标成相似。 |
| CI辅助判定边界不一致 | 区间必须严格位于±delta内部，与现有`p<alpha`约定一致；倒置、无限区间不作结论。 |

## 公式与接口

合并方差：`sp²=((nT−1)sT²+(nR−1)sR²)/(nT+nR−2)`，`SE²=sp²(1/nT+1/nR)`，`df=nT+nR−2`。

Welch：`SE²=sT²/nT+sR²/nR`，`df=SE⁴/[(sT²/nT)²/(nT−1)+(sR²/nR)²/(nR−1)]`。实现用归一化比值计算自由度，减少中间平方溢出。

两者均使用差值`d=meanT−meanR`，`t1=(d+delta)/SE`，`t2=(d−delta)/SE`，`p=max(t.sf(t1),t.cdf(t2))`；CI为`d±t.ppf(1−alpha,df)×SE`。样本必须是一维，NaN/Inf排除并计数，不按批号去重、不换算单位。

独立对照使用项目已安装的statsmodels 0.14.5 `CompareMeans.ttost_ind`及`tconfint_diff`，不是旧项目算法。方法含义核对：[statsmodels官方TOST说明](https://www.statsmodels.org/stable/generated/statsmodels.stats.weightstats.CompareMeans.ttost_ind.html)、[SciPy官方等方差/Welch说明](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html)。网页版本与本地锁定依赖可能不同，测试以本地锁定版本执行。

新调用应使用：

```python
result = evaluate_similarity_pair(
    reference, comparison,
    tier="Tier1", delta=explicit_delta,
    confidence_level=selected_confidence,
    variance_method=selected_method,
)
# 图、表读取result中的mean_diff/ci_low/ci_high/p_tost/equivalent/judgement，勿另算一次。
```

`tier_similarity_judge`保留旧位置参数以兼容纯函数调用，但从参比原始值重新求统计量，不依赖外传缓存的均值/SD。默认1.5SD/3SD等仅留在旧兼容入口，不作为新页面的批准规则。新统一入口要求显式delta、置信度及方法；Tier2另需显式命中阈值。

## 修复前后算例

仅合成数据：参比`[98,99,100,101,102]`，比较=参比+0.7，delta=`1.5×sqrt(2.5)`，选择90%。

| 项目 | 旧调用 | 新统一调用（pooled） |
|---|---|---|
| 差值 | −0.7 | +0.7 |
| 实际双侧CI | 80%，[−2.0968,0.6968] | 90%，约[−1.159548,2.559548] |
| 单侧alpha | 0.10 | 0.05 |
| pTOST | 约0.06656 | 约0.06656 |
| 主结果 | Equivalent=True | equivalent=False |
| Tier1 | Not Similar，与主结果矛盾 | Not Similar，与主结果一致 |

把显式delta改为3，两者统一变成等效/Similar；说明手动界值确实进入了同一计算。Tier2保留含边界的命中比例计算，独立测试验证其显式delta和阈值。

## 验证与未完成事项

- 新独立专项42项通过：手算90%/95%CI、两种方差法与statsmodels对照、参比互换、BF阈值、主结果/Tier1一致性、手动delta、比例边界、极小量纲、无效输入及无法判断状态。
- 已替换21项仅要求TOST/Tier与旧代码完全一致的测试；其他旧回归继续保留，未跳过失败来掩盖变化。
- 完整命令：在`backend`运行`.venv/bin/python -m pytest tests app/services/stats -q`，**253项通过**，14项警告来自原有稳定性/混合模型及其doctest，本批相似性专项无警告。
- 当前`/analysis/similarity`仍返回描述性比较，页面仍未调用本批推断统计函数；因此**统计层已修正，不等于图0/图1已接入CI或页面已显示Tier判定**。本批没有前端修改，不重新构建前端或重启服务冒充接入。
- 后续接入仍需明确独立样本、复测/子批取舍、单位、参比资格、逐指标Tier/delta及结果用途；没有批准状态或业务记录变更。
