# 变更记录

## 2026-10-11 — 运维磁贴前移

用户要求将已完成的运维看板放到第一行第二个，并检查 Mac/GitHub/Linux 同步。注册表中 ops 紧随 MDM，其余应用保持相对顺序；仅 SYS_ADMIN 可见，响应式与权限过滤逻辑不变。更新既有设计方案说明。未修改监控业务代码、数据或调度。

验证：Hub TypeScript 检查及 Vite 构建通过；构建有既有包体积提示。发布前 Hub 与 monitor 的 Mac/GitHub/Linux 完整 SHA 一致、工作区干净。Mac monitor 为模拟预览，Linux 为真实监控。Hub 排序改动将按 commit/push → Linux 既有部署脚本发布，最终版本和服务构建核验以本次交付报告为准。
