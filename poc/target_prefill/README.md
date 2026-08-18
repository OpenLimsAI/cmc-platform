# poc/target_prefill —— 靶点/分子域自动预填 PoC（2026-08-17）

独立验证脚本，**不依赖也不改动**现有 MDM 代码/数据库。

- `prefill_target.py` —— PoC 脚本（Python 3.9+ 标准库，无第三方依赖；显式绕开系统代理直连）
- `mock_dim_target.json` —— 模拟 dim.target（预置 Q9NPF7 = IL-23A，验证"命中→只建关联"分支）
- `output/<inn>/` —— 每个用例的原始响应存档（`01_…`/`02_…`/`03_…`/`05_…`）+ `prefill_form.json` + `run_result.json`
- `output/run_summary.json` —— 5 个用例汇总
- `test_report.md` —— 功能验证报告
- `compatibility_assessment.md` —— 与现有代码库的兼容性评估 + 工作量

运行：

```bash
python3 poc/target_prefill/prefill_target.py                        # 5 个内置用例
python3 poc/target_prefill/prefill_target.py risankizumab nivolumab  # 任意 INN
```

外部调用只读 GET，只访问 `www.ebi.ac.uk`（ChEMBL）与 `rest.uniprot.org`（UniProt）。
