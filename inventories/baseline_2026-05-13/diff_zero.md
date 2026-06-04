# PostgreSQL 结构差异报告：`cmc_data_platform`

- 左侧（mac）：pg_inventory_mac_2026-05-13_after_align\inventory_full.json
- 右侧（linux）：pg_inventory_linux_2026-05-13_after_align\inventory_full.json

> 含义：
> - **只在 mac 有** = 这条对象只存在于左侧，右侧没有
> - **只在 linux 有** = 这条对象只存在于右侧，左侧没有
> - **不同** = 两边都有但属性有差异

## 0. 差异概览

| 维度 | 只在左 | 只在右 | 内容不同 |
|---|---:|---:|---:|
| 扩展 | 0 | 0 | 0 |
| schema | 0 | 0 | 0 |
| 表/视图/物化视图 | 0 | 0 | 0 |
| 列（按表） | 0 | 0 | 0 |
| 约束 | 0 | 0 | 0 |
| 索引 | 0 | 0 | 0 |
| 序列 | 0 | 0 | 0 |
| 视图定义 | 0 | 0 | 0 |
| 函数 | 0 | 0 | 0 |

**总差异条目数：0**

两边结构完全一致 ✅


---