# 原生认证残留入口：本地 TDD 记录

2026-10-27，Thinkpad；基于合并提交 `7c3fbd51f1ad30ab09e9cdfe763ac1f06aa735f6` 的独立分支 `codex/maibo-mdm-oidc-only`。本记录仅涉及安全修复，不是 maibo 发布完成报告。

## 隔离与运行入口

仅新建本轮 `mdm-maibo-oidc-unit-20261027-*` PostgreSQL/Redis/backend 容器，私有 internal 网络，无宿主发布端口，数据使用 tmpfs。后端源码只读挂载，通过项目 `scripts/run_tests.sh` / CI `scripts/run_phase2_tests.py` 创建和重建此专用 `cmab_test`。没有把测试重建脚本运行到 maibo 或原有数据库。

最初两次没有进入 pytest：第一次 Windows CRLF 导致 Bash 初始化退出；第二次缺少迁移要求的 `cmab_audit_reader`。仅在容器临时目录规范化脚本行尾、在新测试 PG 创建 NOLOGIN 审计角色后继续；不把这两次环境失败冒充功能 red。

## 实际 red → green

1. 后端先新增 7 个用例，实际 **6 failed / 1 passed**；再加故障提示用例，实际 **7 failed / 1 passed**，失败明确触及 native refresh、本地 Bearer、底层签发和错误的恢复入口提示。随后实现统一策略，**8 passed**。
2. 前端先补配置禁用时清理旧身份、迟到结果拒绝、native 参数和 Cookie 恢复用例，实际 **4 failed / 26 passed**；实现后 **30 passed**。
3. 再补登录展示策略，实际 **1 failed / 30 passed**；实现显式部署权限判断后 **31 passed**。
4. 手工整理测试导入，严格 Ruff 通过；没有自动格式化或降低规则。前端 31 测试、类型检查、完整 lint 和生产构建通过。

## 补充真实 HTTP 回归

此项在初轮实现后补充，**不声称它先于实现运行**。使用真实临时 PostgreSQL 和两个实际 uvicorn 服务：兼容模式先由正常登录 API 签发票据，第二个服务禁用 native 且 OIDC 故意未配置；真实发送密码、旧 Bearer、旧 refresh 请求，均应拒绝，不改 Cookie；随后兼容服务实际 refresh 仍成功。没有 dependency override 或假 repository。

首次扩展回归 **190 passed / 1 setup error**，该错误是第二个服务冷启动尚未监听。按既有健康启动等待尺度调整为最长 30 秒，并保持所有鉴权断言后，策略单元加真实 HTTP **9 passed**。这证明本地票据拒绝与兼容边界，**没有验证成功的 Casdoor 登录**。

## 剩余门槛

仓库 CI 同一入口的完整适用回归本地通过：**294 passed**，严格 Ruff 与现有范围的 mypy（8 个源文件）通过；最终前端 **31 passed**、类型、完整 lint 和构建通过。代码提交 `83eb477` 及首轮证据提交 `d8838e0` 的 PR #3 两项 CI 均已通过。本轮真实 Casdoor 浏览器 SSO、退出、旧浏览器状态，以及同范围重建后补测的无权限、IdP 故障和恢复均完成，详见 [browser-report.md](browser-report.md)。后续报告提交需单独核对最新 CI；未将修复部署到 maibo。

`evidence/` 保存本轮脱敏自动测试输出及哈希清单；它们不是截图或完整浏览器 E2E 证据。初轮环境问题与 HTTP 冷启动错误已如实在上文记录，没有删断言或关闭鉴权换取通过。

密码签名复核及全部历史身份/审计保持原样；用户要求与 PM/知识库一致，没有选定独立签名密码。已核实其普通操作采用会话授权，不能冒称同类再次认证；尚未确认的签名语义修改或替代方案均不纳入本修复。
