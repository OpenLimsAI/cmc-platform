# `cmc-oidc-auth`

迈博药业（Mabpharm / CMAB）`cmc-platform` 后端共享 Casdoor OIDC 认证与安全会话底座，直接抽取并提炼自标杆项目 `cmab-mdm-platform` 的生产验证范式。

## 核心安全能力

1. **OIDC + PKCE (S256) 授权与状态绑定（`oidc.py`）**：
   - 生成密码学安全的 `code_verifier`、`code_challenge`、`state` 与 `nonce`；
   - 将待完成登录事务加密封入短生命周期 `HttpOnly` 状态 Cookie，回调时常量时间比对 `state` 并还原 `code_verifier`；
   - 支持 GxP 电子签名二次认证（`oidc_fresh`，校验 `auth_time` 与独立签名客户端 `audience`）；
   - 严格防开放重定向（`sanitize_return_to`）与固定 `RS256` / 2048-bit+ JWK 验签。
2. **路径隔离加密会话 Cookie 编解码器（`cookie_session.py`）**：
   - 基于 `HKDF-SHA256`（绑定 `purpose` 与子路径 `Path=/<prefix>/`）派生密钥，结合 `Fernet`（`AES-128-CBC + HMAC-SHA256`）对会话载荷加密与完整性签名，浏览器侧零明文 JWT；
   - 强制锁定 `HttpOnly; SameSite=Lax; Secure; Path=/<prefix>/` 属性，跨子系统（如 `/water/` 与 `/ops/`）Cookie 互不串用；
   - 内置同源写操作守卫 `require_same_origin`（校验 `Origin` 并在缺失时支持受控 `Referer` 回退）。
3. **Fail-Closed 生产启动校验器（`config.py`）**：
   - 生产环境下强制要求 `https://` Issuer 与 Public URL、非占位符高熵密钥（`session_secret >= 32` 字符）、固定组织名及独立签名受众，任何缺失或弱默认值在启动期立即失败拦截。
