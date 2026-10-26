# 统一退出确认后的固定应用返回：TDD 记录

2026-10-26，ThinkpadT14-Le。此次仅调整 MDM OIDC logout API 的成功返回地址和对应测试，未修改提供方确认算法、权限或运行态。

## 行为与 Cookie 边界

主任务在官方 Casdoor 3.154.4 的真实联调中确认，POST logoutAll 已撤销 IdP 服务端会话，而随后浏览器访问无会话的 `GET /api/logout` 可只返回 JSON，并不跳回应用。继续把该 GET 作为完成导航，会让已完成退出的用户停留在 JSON 页面。

MDM 仍只在 `provider.global_logout` 完成严格确认后报告成功：当前令牌注销前有效、logoutAll 响应正常、随后 introspection 明确 active=false。成功时 `logout_url` 直接等于已验证配置的 `public_url + /login?reason=logout`，不接受请求提供的返回地址，不把令牌或客户端密钥放入 URL。

logoutAll 撤销的是 IdP 服务端会话。IdP 域下旧浏览器 session Cookie 未被 MDM 主动擦除，但已不指向有效会话；不能把这个返回行为表述为“MDM 已清除 IdP Cookie”。MDM 自己的会话及 LOGIN Cookie 按原逻辑清除。其他应用的真实退出和后续重新登录结果由主验收报告逐一记录，不能只凭当前令牌失效扩大声称全部应用已验证。

若提供方仍返回 active=true，或注销后的确认请求失败，则依旧是本地退出成功、统一退出未确认，保留原 warning 且不返回成功 logout_url。没有以本地导航伪装为全局成功。

## 实际 Red → Green

先新增三个参数化用例，采用真实 `OIDCProvider.global_logout` 确认算法、明确的 HTTP 边界替身，以及新隔离 PostgreSQL 会话：

```text
docker exec -e LOGURU_LEVEL=WARNING -e APP_LOG_LEVEL=WARNING cmc-mdm-phase2-unit-backend \
  python scripts/run_phase2_tests.py \
  tests/test_oidc_sessions.py::test_confirmed_global_logout_returns_only_fixed_local_login
```

修复前实际 `1 failed, 2 passed, 1 warning in 5.74s`，exit 1。已确认 inactive 的成功分支仍返回 IdP `/api/logout`，与固定 MDM 登录页断言不符；仍 active、确认不可用两条 partial 用例已通过。前置 ruff/mypy 均通过。

随后只替换成功分支的返回地址并纠正 Cookie 语义注释，同命令实际 `3 passed, 1 warning in 4.92s`，exit 0。断言同时覆盖只有确认成功才返回固定 URL、partial warning、不泄露 token，以及本地 session/LOGIN Cookie 清除与服务端会话撤销。

## 完整回归与限制

完整第二阶段 `python scripts/run_phase2_tests.py` 实际完成：`285 passed, 1 warning in 134.73s (0:02:14)`，exit 0；前置 ruff、mypy 均通过。285 项是本阶段所选后端回归集合，不是整个仓库或真实浏览器验收结果。

测试始终通过项目原 `scripts/run_tests.sh`，只重建本阶段专用 `cmab_test` 并迁移 0068；此次未访问或更改真实 IdP、身份配置、运行态、截图或 PR。上述三个自动测试不是对真实浏览器导航的替代。已测文件快照见 [logout-return-source-hashes.json](logout-return-source-hashes.json)；最终版本须使用主任务的合并提交和完整验收来源清单。
