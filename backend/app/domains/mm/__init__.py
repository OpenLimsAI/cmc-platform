"""MM (Material Master Lite) 域

对齐 DM-MDM-001 V1.1 §10。

与 SRS/ARS/PRS 的关键差异：
  - 无状态机：status 5 值（active/quarantine/released/rejected/retired）直接 PUT
  - 无电子签名：无 GxP 关键转移
  - 无 status_history 表（V1.1 §10 未列）
  - 0065 起主记录保存核对开页版本；批次编辑沿用既有规则
"""
