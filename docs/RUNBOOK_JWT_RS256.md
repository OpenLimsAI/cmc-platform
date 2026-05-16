# RUNBOOK：JWT 从 HS256 升级到 RS256（ARCH2）

**适用范围**：CMAB MDM Portal 后端（FastAPI）；生产环境强制 RS256，dev/内测可保留 HS256。

**关联**：
- 架构设计文档 ARCH-MDM-001 §2 安全基线
- 21 CFR Part 11 §11.10(b) 系统验证 / §11.300(d) 私钥隔离
- `backend/app/core/jwt_keys.py`、`backend/app/core/security.py`

---

## 背景

| 项 | HS256（dev 默认） | RS256（生产强制） |
|---|---|---|
| 算法 | HMAC-SHA256 对称 | RSA-2048 非对称 |
| 密钥 | 单个 `SECRET_KEY` 字符串 | 私钥（签发）+ 公钥（验签）分离 |
| 私钥位置 | 与验签服务共存 | 仅签发服务持有 |
| 合规审计常问 | "签发与验签共密钥，密钥泄露即伪造能力" | "私钥隔离，可分发公钥给第三方验签" |

---

## 切换步骤（首次切换 / 密钥轮换通用）

### 1) 在本机或部署机生成密钥对

```bash
make jwt-keys
# 或：bash scripts/gen_jwt_keys.sh /path/to/secrets/dir
```

输出：
- `deploy/jwt/jwt_private.pem`（权限 600，仅 owner 可读）
- `deploy/jwt/jwt_public.pem`（权限 644）

脚本会打印**公钥 SHA-256 指纹**，记录到部署变更单。

### 2) 把密钥注入容器

**生产建议**：私钥用 secrets manager / k8s Secret / HSM 注入，不进 git、不进镜像。
**简易方式**（VM + docker-compose）：

在 `deploy/docker-compose.prod.yml` 的 backend 服务下加：

```yaml
services:
  backend:
    volumes:
      - ./deploy/jwt:/app/secrets:ro   # 只读挂载
```

### 3) 配置环境变量

`.env.prod`：

```env
JWT_ALGORITHM=RS256
JWT_PRIVATE_KEY_PATH=/app/secrets/jwt_private.pem
JWT_PUBLIC_KEY_PATH=/app/secrets/jwt_public.pem
JWT_KEY_ID=2026-05-16   # 可选；密钥轮换时改新日期
```

### 4) 重启后端服务

```bash
docker compose -f deploy/docker-compose.prod.yml up -d --force-recreate backend
```

启动时 `jwt_keys.py` 会 fail-fast 校验：
- 路径必填，否则 RuntimeError 拒启动
- 文件存在 + 可读，否则 RuntimeError 拒启动

### 5) 验证

```bash
# 健康检查
curl -fsS https://mdm.example.com/api/v1/health

# 登录拿 token，检查 header.alg=RS256 + header.kid
curl -s -X POST https://mdm.example.com/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"..."}' \
  | jq -r .data.access_token \
  | cut -d. -f1 | base64 -d | jq
# 期望输出: {"alg":"RS256","typ":"JWT","kid":"2026-05-16"}
```

---

## 影响范围（必须告知用户）

- **所有现存 HS256 token 立即失效**：用户会被自动登出，需重新登录。
- 切换不需要 DB migration / 数据修改。
- 业务功能（CRUD / 状态机 / 签名）行为不变。

---

## 密钥轮换流程（推荐 6-12 个月一次）

1. 生成新密钥对到独立目录：`bash scripts/gen_jwt_keys.sh deploy/jwt-2027-01/`
2. 更新 `JWT_KEY_ID` 到新日期
3. 替换 `JWT_PRIVATE_KEY_PATH` / `JWT_PUBLIC_KEY_PATH` 指向新文件
4. 重启 backend（用户重新登录）
5. 安全归档旧私钥（30 天后销毁，供取证用）

如需**零停机轮换**（dual-key 阶段同时接受新旧）：当前实现不支持，需要 Phase 6 扩展 `decode_token` 多公钥验签 + JWKS 端点。

---

## 回滚到 HS256（应急）

```env
JWT_ALGORITHM=HS256
# 注释掉 JWT_PRIVATE_KEY_PATH / JWT_PUBLIC_KEY_PATH（或保留也不影响）
```

重启 backend 即可。**注意**：HS256 token 的 SECRET_KEY 必须与之前一致，否则同样所有人重新登录。

---

## 合规对照

| 要求 | 对应实现 |
|---|---|
| 21 CFR Part 11 §11.10(b) 系统验证 | `test_jwt_rs256.py` 7 个单元测试覆盖 sign/verify/错误密钥/缺路径/算法切换 |
| 21 CFR Part 11 §11.300(d) 私钥隔离 | 私钥文件 600 权限；分离签发/验签密钥 |
| GAMP 5 V-Model：URS → IQ | URS = ARCH-MDM-001 §2；IQ 检查项见 `deploy/checklist_iq.md`（追加 RS256 检查 5 项） |
