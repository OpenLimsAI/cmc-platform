<!--
  本文件由 scripts/docs/extract_md.py 从 docx 自动派生，请勿手工修改。
  源文件:CMAB_MDM_Portal_API接口规范_V1_1.docx
  重新生成:make docs-extract
  一致性校验:make docs-check
-->

**CMAB MDM Portal**

**API 接口规范**

*API Specification Document*

*OpenAPI 3.0 · REST · JSON · JWT*

|              |                   |
|--------------|-------------------|
| **文档编号** | API-MDM-001       |
| **版本**     | V1.1              |
| **状态**     | Draft             |
| **发布日期** | 2026-05-11        |
| **编制**     | CMC IT 架构组     |
| **上位文档** | ARCH-MDM-001 V1.1 |
| **关联文档** | DM-MDM-001 V1.1   |
| **API 标准** | OpenAPI 3.0       |

# 修订记录

| **版本** | **日期** | **修订人** | **修订内容** |
|----|----|----|----|
| V1.0 | 2026-05-11 | CMC IT 架构组 | 初始版本，定义 API 设计原则、所有 endpoint、错误码、认证流程 |
| V1.1 | 2026-05-12 | CMC IT 架构组 | V1.0→V1.1：修订认证路线图、权限组合、审计上下文、错误码 / meta.error.type 字典、SRS/ARS 推迟端点与资产状态机端点。 |

## 适用范围

- 本文档为 CMAB MDM Portal 后端 REST API 设计依据

- 覆盖认证、SRS / PRS / ARS / MM / REF / 审计 等所有业务模块

- 作为前端 API Client 实现依据

- 作为 FastAPI 路由与 Pydantic Schema 实现依据

- 作为下游系统（ELN / LIMS / RAGFlow 等）集成依据

# 1. API 设计原则

## 1.1 整体原则

1.  RESTful 风格：资源导向，HTTP 动词语义化

2.  API-First：先定义 OpenAPI 契约，前后端基于契约并行开发

3.  版本化：URL 中包含版本号 /api/v1/，重大不兼容变更升级版本

4.  无状态：除认证 Cookie 外，每个请求自包含完整上下文

5.  JSON 为主：请求体与响应体统一 JSON，UTF-8 编码

6.  一致性：所有 endpoint 遵循统一的命名、分页、过滤、错误响应格式

7.  自描述：所有 endpoint 通过 OpenAPI 自动生成文档（FastAPI 原生支持）

8.  向后兼容：尽量通过新增字段、可选参数演进，避免破坏性变更

## 1.2 URL 命名规范

### 1.2.1 基本规则

- 全小写、kebab-case（连字符分词）

- 资源名使用复数形式：/substances 而非 /substance

- 使用业务编码而非数字 ID 作为外部资源标识

- 不超过 5 层嵌套，复杂关系通过查询参数表达

- 不在 URL 中使用动词，动作通过 HTTP method 表达；特殊操作用子资源（如 /approve）

### 1.2.2 URL 结构

```text
基本结构：/api/v{version}/{domain}/{resource}/{id}/{sub-resource} 常规示例：GET    /api/v1/substances                       # 列表POST   /api/v1/substances                       # 创建GET    /api/v1/substances/{substance_code}      # 详情PUT    /api/v1/substances/{substance_code}      # 更新DELETE /api/v1/substances/{substance_code}      # 软删除 子资源示例：GET    /api/v1/substances/{substance_code}/projects        # 关联项目GET    /api/v1/substances/{substance_code}/xrefs           # 标识符POST   /api/v1/substances/{substance_code}/xrefs           # 添加标识符GET    /api/v1/substances/{substance_code}/audit-logs      # 审计历史 特殊操作（不能用 CRUD 表达的动作）：POST   /api/v1/substances/{substance_code}:approve         # 审批POST   /api/v1/substances/{substance_code}:deprecate       # 弃用POST   /api/v1/substances/{substance_code}:merge           # 合并POST   /api/v1/substances:check-sameness                   # 同一性判定（当前基于序列哈希 / xref 规则；复杂 fuzzy matching 与 merge 治理工具列入 Phase 5）
```

> 💡 资源标识符策略
> 对外 API 使用业务编码（substance_code='SUB-0000123'）作为资源标识，而非数据库内部 ID。
> 理由：1) 业务编码语义清晰；2) 调用方友好；3) URL 可直接分享与复制。
> 数据库内部 ID（substance_id）仅用于：① 内部 JOIN 关联；② 引用关系表外键；③ 跨服务事件。
> 关联的 schema 也始终包含 *_code 字段供调用方使用。

## 1.3 HTTP 方法语义

| **方法** | **用途** | **幂等性** | **请求体** | **成功状态码** |
|----|----|----|----|----|
| GET | 查询资源 | ✓ | 无 | 200 OK |
| POST | 创建资源 / 自定义动作 | ✗ | JSON | 201 Created / 200 OK |
| PUT | 完整更新资源 | ✓ | JSON | 200 OK |
| PATCH | 部分更新资源 | 条件性 | JSON Patch | 200 OK |
| DELETE | 软删除资源 | ✓ | 无 / JSON（含原因） | 204 No Content |

## 1.4 通用响应格式

### 1.4.1 成功响应

所有成功响应统一包装在 envelope 中（除 204 外）：

```json
{
  "code": 0,                           // 业务码，0 表示成功
  "message": "OK",                     // 消息
  "data": { ... },                     // 业务数据（对象 / 数组 / null）
  "meta": {                            // 元信息（分页、版本等）
    "request_id": "req_abc123xyz",
    "timestamp": "2026-05-11T10:30:00Z",
    "api_version": "v1"
  }
}

# 列表查询时，data 为数组，meta 含分页：
{
  "code": 0,
  "message": "OK",
  "data": [, ],
  "meta": {
    "request_id": "req_abc123xyz",
    "timestamp": "2026-05-11T10:30:00Z",
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 137,
      "total_pages": 7
    }
  }
}
```

### 1.4.2 错误响应

```json
{
  "code": 40301,                                // 业务错误码
  "message": "权限不足，无法访问该资源",          // 用户友好消息
  "data": null,
  "meta": {
    "request_id": "req_abc123xyz",
    "timestamp": "2026-05-11T10:30:00Z",
    "error": {
      "type": "permission_denied",              // 错误类型（机器可读）
      "details": [                              // 详细错误（如校验失败的字段）
        {
          "field": "preferred_name",
          "message": "必填字段不能为空"
        }
      ],
      "trace_id": "trace_xyz"                   // 链路追踪 ID（仅 dev 环境）
    }
  }
}
```

## 1.5 时间格式

- 所有时间字段使用 ISO 8601 格式带时区：2026-05-11T10:30:00.000Z

- 数据库存储 UTC，API 返回也是 UTC（前端按用户时区展示）

- 日期类型（无时间）使用 YYYY-MM-DD 格式

- 禁止使用 Unix 时间戳（除非特殊场景）

## 1.6 字段命名规范

- 使用 snake_case：substance_code、created_at、is_active

- 布尔字段以 is\_ / has\_ / can\_ 开头

- 时间字段以 \_at 结尾（created_at），日期字段以 \_date 结尾（approval_date）

- ID 字段：业务编码用 \*\_code，数据库 ID 用 \*\_id

- 数量字段：count（次数）、total（总数）、quantity（数量）+ \_unit

# 2. 认证与授权

## 2.1 认证方式

采用 JWT（JSON Web Token）方式，分 Access Token 和 Refresh Token：

| **项目** | **Access Token**                 | **Refresh Token** |
|----------|----------------------------------|-------------------|
| 有效期   | 30 分钟                          | 7 天              |
| 存储位置 | 前端内存 / sessionStorage        | HttpOnly Cookie   |
| 传递方式 | Authorization: Bearer {token}    | 自动 Cookie       |
| 内容     | user_id, roles, permissions, exp | user_id, jti, exp |
| 签名算法 | HS256（开发）/ RS256（生产）     | 同左              |
| 撤销机制 | 短有效期自然过期                 | Redis 黑名单 jti  |

## 2.2 认证 Endpoint

|          |                        |
|:--------:|------------------------|
| **POST** | **/api/v1/auth/login** |

用户登录，获取 Access Token 与 Refresh Token。

#### 请求体

```json
{
  "username": "qingcheng",
  "password": "********"
}
```

#### 成功响应（200）

```json
{
  "code": 0,
  "message": "登录成功",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer",
    "expires_in": 1800,
    "user": {
      "user_id": 123,
      "username": "qingcheng",
      "full_name": "李清城",
      "department": "CMC R&D",
      "title": "CMC Head",
      "roles": ["SYS_ADMIN", "SUBSTANCE_STEWARD"],
      "permissions": ["substance:create", "substance:read", "substance:approve", ...]
    }
  },
  "meta": { ... }
}

# Refresh Token 通过 Set-Cookie 自动写入（HttpOnly + Secure + SameSite=Strict）
```

#### 失败响应

```json
# 401 - 用户名或密码错误
{
  "code": 40101,
  "message": "用户名或密码错误",
  "data": null
}

# 423 - 账户锁定（连续失败超 5 次）
{
  "code": 42301,
  "message": "账户已锁定，请 30 分钟后重试或联系管理员",
  "data": null
}

# 403 - 账户被禁用
{
  "code": 40302,
  "message": "账户已被禁用",
  "data": null
}
```

⚠ Phase 4 补：V1.0 阶段未实现 refresh token 流转，当前 access_token 30 min 过期后由前端引导重新登录；Phase 4 安全收尾时补该端点完整实现。

|          |                                                  |
|:--------:|--------------------------------------------------|
| **POST** | /api/v1/auth/refresh ⏳ Phase 4 补 — V1.0 未实现 |

刷新 Access Token（使用 Cookie 中的 Refresh Token）。

#### 成功响应（200）

```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "access_token": "eyJhbGc...",
    "token_type": "Bearer",
    "expires_in": 1800
  }
}
```

|          |                         |
|:--------:|-------------------------|
| **POST** | **/api/v1/auth/logout** |

登出，撤销 Refresh Token 并清除 Cookie。

#### 成功响应（204 No Content）

无响应体。

|          |                                  |
|:--------:|----------------------------------|
| **POST** | **/api/v1/auth/change-password** |

修改密码（需登录）。

#### 请求体

```json
{
  "old_password": "********",
  "new_password": "********"
}
```

#### 成功响应（200）

```json
{
  "code": 0,
  "message": "密码修改成功，请重新登录",
  "data": null
}
```

#### 失败场景

- 旧密码错误：401 / 40105 / old_password_wrong

- 新密码强度不足：400 / 40010

- 新密码与最近 5 个历史密码重复：400 / 40011

|         |                     |
|:-------:|---------------------|
| **GET** | **/api/v1/auth/me** |

获取当前用户信息（含角色、权限、偏好设置）。

#### 成功响应（200）

```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "user_id": 123,
    "username": "qingcheng",
    "email": "qingcheng@cmab.com",
    "full_name": "李清城",
    "full_name_en": "Li Qingcheng",
    "department": "CMC R&D",
    "title": "CMC Head",
    "phone": "+86-13800000000",
    "status": "active",
    "mfa_enabled": false,
    "last_login_at": "2026-05-11T08:30:00Z",
    "password_expires_at": "2026-08-11T00:00:00Z",
    "roles": [
      {
        "role_id": 1,
        "role_code": "SYS_ADMIN",
        "role_name": "系统管理员"
      }
    ],
    "permissions": ["substance:create", "substance:read", ...],
    "preferences": {
      "locale": "zh-CN",
      "timezone": "Asia/Shanghai",
      "theme": "light"
    }
  }
}
```

## 2.3 授权头

除登录、刷新、密码重置等公开 endpoint 外，所有 API 请求必须携带 Access Token：

```http
GET /api/v1/substances HTTP/1.1
Host: mdm.cmab.internal
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json
X-Request-ID: req_abc123xyz
```

## 2.4 权限模型与 Endpoint 权限映射

每个 endpoint 通过 FastAPI 依赖注入声明所需权限：

```python
# 后端实现示例
from fastapi import APIRouter, Depends
from app.shared.permissions import require_permission

router = APIRouter()

@router.post("/substances", dependencies=[Depends(require_permission("substance:create"))])
async def create_substance(...): ...

@router.get("/substances", dependencies=[Depends(require_permission("substance:read"))])
async def list_substances(...): ...

@router.post("/substances/{code}:approve", dependencies=[Depends(require_permission("substance:approve"))])
async def approve_substance(...): ...
```

V1.1 新增：require_all_permissions(...) 多权限组合工厂

针对 21 CFR Part 11 §11.50 关键不可逆动作（如 ARS terminate），endpoint 需要同时校验"操作权限 + 签名权限"：

@router.post("/assets/{code}:terminate", dependencies=\[Depends(require_all_permissions("asset:update", "asset:sign"))\])

async def terminate_asset(...): ...

角色映射示例：PROJECT_MANAGER + QA_REVIEWER 默认持有 asset:sign / substance:sign / project:sign；普通操作角色仅持 \*:update。单权限不足以触发签名流。

## 2.5 数据级权限

- Substance 保密等级（confidentiality）：public / internal / restricted

- restricted 类型仅限有特定权限的用户查看

- Project 保密项目仅团队成员可见

- 数据级权限通过 Service 层 + 查询过滤器实现

## 2.6 应用层会话上下文（用于审计）

V1.1 已禁用 SET LOCAL GUC 方案——在 asyncpg 连接池模式下，PostgreSQL 连接级会话变量可能在连接复用时产生残留 / 泄漏风险（M2.5.1 曾发现状态历史行误带上一事务 e_signature_id 的问题）。\
\
V1.1 推荐做法：使用 Python 调用栈中的 ContextVar + AuditContextMiddleware 传递 user / IP / request_id；service 层在写入业务记录时显式维护 created_by / updated_by / e_signature_id 等审计字段。审计触发器不再依赖 PostgreSQL session GUC 读取操作者身份。

```json
# middleware 伪代码（V1.1 推荐：ContextVar，不使用 SET LOCAL GUC）from contextvars import ContextVaraudit_context = ContextVar("audit_context", default={})async def audit_context_middleware(request, call_next):    user = get_current_user(request)    token = audit_context.set({        "user_id": user.user_id,        "username": user.username,        "request_id": request.state.request_id,        "ip_address": request.client.host,    })    try:        return await call_next(request)    finally:        audit_context.reset(token)# service 层从 audit_context 获取 actor，并显式写入 created_by / updated_by / e_signature_id。
```

此后审计 actor 信息由 service 层显式传入审计写入逻辑或业务字段；DB 触发器仍负责记录数据变更差异，但不从 PostgreSQL session 变量读取操作者身份（详见 DM-MDM-001 §6.5）。

# 3. 通用约定

## 3.1 分页

### 3.1.1 分页参数

| **参数**  | **类型**   | **默认值** | **说明**                     |
|-----------|------------|------------|------------------------------|
| page      | int ≥ 1    | 1          | 页码（从 1 开始）            |
| page_size | int 1–100  | 20         | 每页大小，最大 100           |
| sort      | string     | —          | 排序字段，多个字段逗号分隔   |
| order     | asc / desc | desc       | 排序方向（按 sort 字段顺序） |

### 3.1.2 排序示例

```http
# 按更新时间倒序（默认）
GET /api/v1/substances?sort=updated_at&order=desc

# 按状态升序、再按创建时间倒序
GET /api/v1/substances?sort=status,-created_at

# - 前缀表示倒序，无前缀或 + 前缀表示升序
# 当 sort 多字段时，order 参数被忽略
```

## 3.2 过滤与搜索

### 3.2.1 简单过滤

```http
# 单字段精确匹配
GET /api/v1/substances?substance_type=mab&status=active

# 多值过滤（in 语义）
GET /api/v1/substances?substance_type=mab,bispecific

# 范围过滤（gte/lte/gt/lt 后缀）
GET /api/v1/substances?created_at__gte=2026-01-01&created_at__lt=2026-06-01

# 模糊匹配（contains 后缀）
GET /api/v1/substances?preferred_name__contains=PD-1

# 不为空 / 为空
GET /api/v1/substances?internal_code__not_null=true
GET /api/v1/substances?deleted_at__is_null=true
```

### 3.2.2 全文搜索

```text
# 跨字段全文搜索（substance_code/internal_code/preferred_name/INN/CAS 等）GET /api/v1/substances?q=Trastuzumab # 全局搜索（V1.1 实现 entity_type ∈ {substance, project, asset} 3 类；material 推迟至 Phase 4 MM 域开发）（跨所有 schema）GET /api/v1/search?q=PD-1&types=substance,project,asset
```

### 3.2.3 字段筛选

```http
# 仅返回部分字段（减少传输量）
GET /api/v1/substances?fields=substance_code,preferred_name,status

# 嵌入关联资源（默认仅返回 ID/code）
GET /api/v1/substances/SUB-0000123?expand=protein,xrefs,projects

# 排除字段
GET /api/v1/substances?exclude=extra,description
```

## 3.3 批量操作

```json
# 批量创建
POST /api/v1/substances:batch-create
Body: { "items": [,, ] }

# 批量更新（按 ID）
POST /api/v1/substances:batch-update
Body: { "items": [ {"substance_code": "SUB-001", ...}, ... ] }

# 批量软删除
POST /api/v1/substances:batch-delete
Body: { "codes": ["SUB-001", "SUB-002"], "reason": "去重合并" }
```

批量响应格式：每条 item 单独返回成功/失败状态。

```json
{
  "code": 0,
  "message": "处理完成",
  "data": {
    "total": 3,
    "succeeded": 2,
    "failed": 1,
    "results": [
      { "index": 0, "status": "success", "data": { "substance_code": "SUB-0000124" } },
      { "index": 1, "status": "success", "data": { "substance_code": "SUB-0000125" } },
      { "index": 2, "status": "error",   "error": { "code": 40010, "message": "校验失败：preferred_name 必填" } }
    ]
  }
}
```

## 3.4 幂等性

- GET / PUT / DELETE 天然幂等

- POST 创建：通过 Idempotency-Key 头实现幂等（24 小时窗口）

- 批量操作：每条 item 独立处理，部分失败不回滚成功项

```http
POST /api/v1/substances HTTP/1.1
Idempotency-Key: 7f8a9c2e-1234-5678-90ab-cdef12345678
Content-Type: application/json

{ "preferred_name": "...", ... }

# 后端检查 Redis：若同 key + 同请求体哈希存在，直接返回上次结果
# 若 key 存在但请求体不同，返回 409 Conflict
```

## 3.5 速率限制

| **调用方**                | **限制**             | **响应头**     |
|---------------------------|----------------------|----------------|
| 未认证（登录端点）        | 10 次 / 分钟 / IP    | X-RateLimit-\* |
| 普通用户                  | 300 次 / 分钟 / 用户 | 同上           |
| 内部服务（Service Token） | 1000 次 / 分钟       | 同上           |
| 批量操作                  | 10 次 / 分钟 / 用户  | 同上           |

响应头：

```http
X-RateLimit-Limit: 300
X-RateLimit-Remaining: 287
X-RateLimit-Reset: 1715424600

# 超限响应（429 Too Many Requests）
Retry-After: 30
{ "code": 42901, "message": "请求过于频繁，请 30 秒后重试" }
```

## 3.6 链路追踪

- 每个请求自动分配 X-Request-ID（如客户端未提供）

- 响应中通过 meta.request_id 返回，便于日志关联

- 贯穿审计日志、应用日志、慢 SQL 日志

## 3.7 国际化

```text
# 客户端通过 Accept-Language 指定
Accept-Language: zh-CN

# 影响：
# - 错误消息语言（zh-CN / en-US）
# - lookup_value 返回 lookup_name 还是 lookup_name_en
# - 默认值：用户偏好 → Accept-Language → zh-CN
```

# 4. 错误码体系

## 4.1 错误码结构

错误码采用 5 位整数，结构为 HTTPABB：

| **位**  | **含义**    | **示例**                               |
|---------|-------------|----------------------------------------|
| 前 3 位 | HTTP 状态码 | 400, 401, 403, 404, 409, 422, 429, 500 |
| 后 2 位 | 业务子码    | 01-99，按域细分                        |

例如：40301 = HTTP 403 + 业务码 01（权限不足）

## 4.2 通用错误码

| **错误码** | **HTTP** | **类型**              | **说明**                          |
|------------|----------|-----------------------|-----------------------------------|
| 0          | 200/201  | —                     | 成功                              |
| 40000      | 400      | bad_request           | 请求格式错误                      |
| 40001      | 400      | validation_failed     | 校验失败（详见 details）          |
| 40002      | 400      | missing_required      | 必填参数缺失                      |
| 40003      | 400      | invalid_value         | 字段值不合法                      |
| 40010      | 400      | weak_password         | 密码强度不足                      |
| 40011      | 400      | password_in_history   | 新密码与历史重复                  |
| 40020      | 400      | code_format_invalid   | 业务编码格式错误                  |
| 40101      | 401      | invalid_credentials   | 用户名或密码错误                  |
| 40102      | 401      | token_expired         | Token 已过期                      |
| 40103      | 401      | token_invalid         | Token 无效                        |
| 40104      | 401      | token_missing         | 缺少 Token                        |
| 40105      | 401      | old_password_wrong    | 旧密码错误                        |
| 40106      | 401      | signature_invalid     | 电子签名密码错误 / 内容哈希不一致 |
| 40301      | 403      | permission_denied     | 权限不足                          |
| 40302      | 403      | account_disabled      | 账户已禁用                        |
| 40303      | 403      | data_access_denied    | 数据级权限不足                    |
| 40304      | 403      | operation_not_allowed | 当前状态下不允许此操作            |
| 40400      | 404      | not_found             | 资源不存在                        |
| 40401      | 404      | user_not_found        | 用户不存在                        |
| 40402      | 404      | substance_not_found   | Substance 不存在                  |
| 40403      | 404      | project_not_found     | 项目不存在                        |
| 40404      | 404      | asset_not_found       | 资产不存在                        |
| 40405      | 404      | material_not_found    | 物料不存在                        |
| 40901      | 409      | conflict              | 资源冲突                          |
| 40902      | 409      | duplicate_code        | 业务编码重复                      |
| 40903      | 409      | duplicate_name        | 名称重复                          |
| 40904      | 409      | version_conflict      | 乐观锁冲突（被他人修改）          |
| 40905      | 409      | duplicate_request     | 幂等键冲突                        |
| 42201      | 422      | state_invalid         | 状态机不允许的状态变更            |
| 42202      | 422      | reference_in_use      | 资源被引用，无法删除              |
| 42203      | 422      | signature_required    | 当前操作要求电子签名但未提供      |
| 42301      | 423      | account_locked        | 账户已锁定                        |
| 42901      | 429      | rate_limit_exceeded   | 请求过于频繁                      |
| 50001      | 500      | internal_error        | 服务器内部错误                    |
| 50002      | 500      | database_error        | 数据库错误                        |
| 50301      | 503      | service_unavailable   | 服务暂时不可用                    |

## 4.3 域专属错误码（各域分配 100 段）

各域可在通用基础上扩展业务码（HTTP 后两位 + 域偏移）：

| **域** | **偏移段** | **示例** |
|----|----|----|
| SRS（substance） | +1000 | 41001 - 序列哈希冲突；41002 - sameness 判定失败 |
| PRS（project） | +2000 | 42001 - 项目时间冲突；42002 - 父子项目循环引用 |
| ARS（asset） | +3000 | 43001 - 资产已申报，不可修改 INN |
| MM（material） | +4000 | 44001 - 物料批号重复；44002 - 物料已耗尽 |
| REF | +5000 | 45001 - 引用关系已存在；45002 - 跨域引用不一致 |
| AUDIT | +6000 | 46001 - 电子签名验证失败 |

4.4 meta.error.type 字典与前端处置约定（V1.1 新增）

所有 401 / 403 / 422 响应通过 meta.error.type 字段区分错误语义，前端按此字段分流处置（不按 HTTP 状态码一刀切跳登录）。

meta.error.type 全字典：

· invalid_credentials — 40101 / 401 — 用户名或密码错误 → 登录表单提示

· token_expired — 40102 / 401 — JWT 过期 → 静默 refresh（Phase 4 补）/ 跳登录

· token_invalid — 40103 / 401 — JWT 格式无效 → 清 token 跳登录

· token_missing — 40104 / 401 — 请求未携带 token → 跳登录

· old_password_wrong — 40105 / 401 — 修改密码时旧密码错误 → 就地提示

· signature_invalid — 40106 / 401 — 电子签名密码错误 → 弹密码二次确认对话框，不清 token

· permission_denied — 40301 / 403 — 无操作权限 → 禁止提示

· account_disabled — 40302 / 403 — 账号已停用 → 提示联系管理员

· account_locked — 42301 / 423 — 账号已锁定（连续失败 5 次）→ 提示等待解锁

· state_invalid — 42201 / 422 — 状态机前置条件不满足 → 就地提示当前状态

· signature_required — 42203 / 422 — 当前操作要求电子签名但未提供 → 弹签名对话框

前端核心约定：按 meta.error.type 分流，不按 HTTP 状态码一刀切。会话失效（token\_\*）跳登录；业务身份再验证（signature_invalid）就地提示，不清 token。

> ⚠ 错误码使用准则
> • 客户端按 type 判断错误类型（机器可读），不要按 message 判断
> • message 仅用于展示给用户，文案可调整
> • 校验失败统一用 40001 + details 数组返回所有失败字段
> • 不要泄露敏感信息（如 SQL 错误详情、stack trace），生产环境屏蔽
> • 每个 4xx 错误必须可由客户端纠正后重试，5xx 错误才允许稍后重试

# 5. Endpoint 总索引

## 5.1 按域分组

### 5.1.1 认证（auth）

| **方法** | **路径** | **说明** | **权限** |
|----|----|----|----|
| POST | /api/v1/auth/login | 登录 | 公开 |
| POST | /api/v1/auth/refresh ⏳ Phase 4 补 — V1.0 未实现 | 刷新 Token | 公开 |
| POST | /api/v1/auth/logout | 登出 | 已登录 |
| POST | /api/v1/auth/change-password | 修改密码 | 已登录 |
| GET | /api/v1/auth/me | 当前用户信息 | 已登录 |

### 5.1.2 用户与权限管理

| **方法** | **路径**                                | **说明** | **权限**    |
|----------|-----------------------------------------|----------|-------------|
| GET      | /api/v1/users                           | 用户列表 | user:manage |
| POST     | /api/v1/users                           | 创建用户 | user:manage |
| GET      | /api/v1/users/{username}                | 用户详情 | user:manage |
| PUT      | /api/v1/users/{username}                | 更新用户 | user:manage |
| POST     | /api/v1/users/{username}:lock           | 锁定用户 | user:manage |
| POST     | /api/v1/users/{username}:unlock         | 解锁用户 | user:manage |
| POST     | /api/v1/users/{username}:reset-password | 重置密码 | user:manage |
| GET      | /api/v1/users/{username}/roles          | 用户角色 | user:manage |
| PUT      | /api/v1/users/{username}/roles          | 分配角色 | user:manage |
| GET      | /api/v1/roles                           | 角色列表 | role:manage |
| POST     | /api/v1/roles                           | 创建角色 | role:manage |
| GET      | /api/v1/permissions                     | 权限列表 | role:manage |

### 5.1.3 SRS（Substance Registration）

| **方法** | **路径** | **说明** | **权限** |
|----|----|----|----|
| GET | /api/v1/substances | Substance 列表 | substance:read |
| POST | /api/v1/substances | 创建 Substance | substance:create |
| GET | /api/v1/substances/{code} | 详情 | substance:read |
| PUT | /api/v1/substances/{code} | 更新 | substance:update |
| DELETE | /api/v1/substances/{code} | 软删除 | substance:update |
| POST | /api/v1/substances/{code}:approve | 审核通过 | substance:approve |
| POST | /api/v1/substances/{code}:reject ⏳ Phase 4 视需补 — V1.0 未实现 | 审核驳回 | substance:approve |
| POST | /api/v1/substances/{code}:deprecate | 弃用 | substance:approve |
| POST | /api/v1/substances/{code}:merge ⏳ Phase 5 数据治理工具阶段补 — V1.0 未实现 | 合并 | substance:approve |
| GET | /api/v1/substances/{code}/protein | 蛋白属性 | substance:read |
| PUT | /api/v1/substances/{code}/protein | 更新蛋白属性 | substance:update |
| GET | /api/v1/substances/{code}/adc | ADC 属性 | substance:read |
| PUT | /api/v1/substances/{code}/adc | 更新 ADC | substance:update |
| GET | /api/v1/substances/{code}/xrefs | 标识符列表 | substance:read |
| POST | /api/v1/substances/{code}/xrefs | 添加标识符 | substance:update |
| DELETE | /api/v1/substances/{code}/xrefs/{xref_id} | 删除标识符 | substance:update |
| GET | /api/v1/substances/{code}/projects | 关联项目 | substance:read |
| GET | /api/v1/substances/{code}/assets | 关联资产 | substance:read |
| GET | /api/v1/substances/{code}/materials | 关联物料 | substance:read |
| GET | /api/v1/substances/{code}/audit-logs | 审计历史 | audit:read |
| GET | /api/v1/substances/{code}/status-history | 状态历史 | substance:read |
| POST | /api/v1/substances:check-sameness | 同一性判定 | substance:read |

### 5.1.4 PRS（Project Registration）

| **方法** | **路径** | **说明** | **权限** |
|----|----|----|----|
| GET | /api/v1/projects | 项目列表 | project:read |
| POST | /api/v1/projects | 创建项目 | project:create |
| GET | /api/v1/projects/{code} | 详情 | project:read |
| PUT | /api/v1/projects/{code} | 更新 | project:update |
| DELETE | /api/v1/projects/{code} | 软删除 | project:update |
| POST | /api/v1/projects/{code}:approve | 审核通过 | project:approve |
| POST | /api/v1/projects/{code}:terminate | 终止 | project:approve |
| GET | /api/v1/projects/{code}/milestones | 里程碑列表 | project:read |
| POST | /api/v1/projects/{code}/milestones | 添加里程碑 | project:update |
| PUT | /api/v1/projects/{code}/milestones/{ms_id} | 更新里程碑 | project:update |
| GET | /api/v1/projects/{code}/team | 团队成员 | project:read |
| POST | /api/v1/projects/{code}/team | 添加成员 | project:update |
| DELETE | /api/v1/projects/{code}/team/{user_id} | 移除成员 | project:update |
| GET | /api/v1/projects/{code}/substances | 关联物质 | project:read |
| POST | /api/v1/projects/{code}/substances | 关联物质 | project:update |
| DELETE | /api/v1/projects/{code}/substances/{sub_code} | 解除关联 | project:update |
| GET | /api/v1/projects/{code}/assets | 关联资产 | project:read |
| POST | /api/v1/projects/{code}/assets | 关联资产 | project:update |
| GET | /api/v1/projects/{code}/audit-logs | 审计历史 | audit:read |
| GET | /api/v1/projects/{code}/status-history | 状态历史 | project:read |

### 5.1.5 ARS（Asset Registration）

| **方法** | **路径** | **说明** | **权限** |
|----|----|----|----|
| GET | /api/v1/assets | 资产列表 | asset:read |
| POST | /api/v1/assets | 创建资产 | asset:create |
| GET | /api/v1/assets/{code} | 详情 | asset:read |
| PUT | /api/v1/assets/{code} | 更新 | asset:update |
| DELETE | /api/v1/assets/{code} | 软删除 | asset:update |
| POST | /api/v1/assets/{code}:advance-phase ⏳ Phase 5 视需补 — V1.0 未实现 | 推进阶段 | asset:update |
| GET | /api/v1/assets/{code}/market-ids | 市场标识符 | asset:read |
| POST | /api/v1/assets/{code}/market-ids | 添加市场标识符 | asset:update |
| GET | /api/v1/assets/{code}/substances | 关联物质 | asset:read |
| POST | /api/v1/assets/{code}/substances | 关联物质 | asset:update |
| GET | /api/v1/assets/{code}/projects | 关联项目 | asset:read |
| POST | /api/v1/assets/{code}:hold | 暂停资产 | asset:update |
| POST | /api/v1/assets/{code}:resume | 恢复资产 | asset:update |
| POST | /api/v1/assets/{code}:terminate | 终止资产（不可逆，需电子签名） | asset:update + asset:sign |

### 5.1.6 MM（Material Master）

| **方法** | **路径** | **说明** | **权限** |
|----|----|----|----|
| GET | /api/v1/materials | 物料列表 | material:read |
| POST | /api/v1/materials | 创建物料 | material:create |
| GET | /api/v1/materials/{code} | 详情 | material:read |
| PUT | /api/v1/materials/{code} | 更新 | material:update |
| DELETE | /api/v1/materials/{code} | 软删除 | material:update |
| GET | /api/v1/materials/{code}/batches | 批次列表 | material:read |
| POST | /api/v1/materials/{code}/batches | 添加批次 | material:update |
| PUT | /api/v1/materials/{code}/batches/{batch_id} | 更新批次 | material:update |

### 5.1.7 全局功能

| **方法** | **路径**                  | **说明**             | **权限**           |
|----------|---------------------------|----------------------|--------------------|
| GET      | /api/v1/search            | 全局搜索             | 已登录             |
| GET      | /api/v1/lookups/{type}    | 枚举字典             | 已登录             |
| GET      | /api/v1/audit-logs        | 审计日志查询         | audit:read         |
| POST     | /api/v1/audit-logs:export | 审计日志导出         | audit:read         |
| GET      | /api/v1/signatures        | 电子签名记录         | audit:read         |
| POST     | /api/v1/signatures        | 执行电子签名         | 对应资源 sign 权限 |
| GET      | /health                   | 健康检查（无需认证） | 公开               |
| GET      | /api/v1/system/info       | 系统信息             | 已登录             |

# 6. SRS Endpoint 详细规范

## 6.1 列表查询

|         |                        |
|:-------:|------------------------|
| **GET** | **/api/v1/substances** |

查询 Substance 列表，支持分页、排序、过滤、字段筛选。

#### 查询参数

| **参数** | **类型** | **说明** |
|----|----|----|
| page | int | 页码，默认 1 |
| page_size | int | 每页大小，默认 20 |
| sort | string | 排序字段（updated_at / created_at / preferred_name 等） |
| q | string | 全文搜索（substance_code / internal_code / preferred_name / INN / CAS） |
| substance_type | string | 类型过滤，多值逗号分隔 |
| status | string | 状态过滤 |
| target | string | 靶点过滤 |
| confidentiality | string | 保密等级 |
| created_at\_\_gte | datetime | 创建时间起 |
| created_at\_\_lt | datetime | 创建时间止 |
| expand | string | 展开关联资源（protein, adc, xrefs, projects, assets） |
| fields | string | 字段筛选 |

#### 成功响应（200）

```json
{
  "code": 0,
  "message": "OK",
  "data": [
    {
      "substance_code": "SUB-0000123",
      "substance_type": "mab",
      "internal_code": "CMAB-101",
      "preferred_name": "Trastuzumab biosimilar",
      "preferred_name_en": "Trastuzumab biosimilar",
      "target": "HER2",
      "status": "active",
      "confidentiality": "internal",
      "inn": "trastuzumab",
      "cas_number": "180288-69-1",
      "project_count": 3,
      "asset_count": 1,
      "material_count": 12,
      "created_at": "2025-08-15T03:22:11Z",
      "updated_at": "2026-04-30T08:14:55Z"
    },
    { ... }
  ],
  "meta": {
    "request_id": "req_abc",
    "timestamp": "2026-05-11T10:30:00Z",
    "pagination": {
      "page": 1, "page_size": 20, "total": 137, "total_pages": 7
    }
  }
}
```

## 6.2 创建 Substance

|          |                        |
|:--------:|------------------------|
| **POST** | **/api/v1/substances** |

创建 Substance（默认状态 draft，需 Steward 后续审核激活）。

#### 请求体（mAb 示例）

```json
{
  "substance_type": "mab",
  "internal_code": "CMAB-203",
  "preferred_name": "Anti-PD-L1 mAb",
  "preferred_name_en": "Anti-PD-L1 monoclonal antibody",
  "target": "PD-L1",
  "target_type": "受体",
  "modality": "IgG1 monoclonal antibody",
  "is_proprietary": true,
  "confidentiality": "restricted",
  "description": "针对实体瘤的人源化 IgG1 抗 PD-L1 单抗",
  "notes": "立项编号 CMAB-203-PJ",
  "extra": {
    "discovery_date": "2025-12-10",
    "lead_optimization_round": 3
  },

  "protein": {
    "heavy_chain_sequence": "EVQLVQSGAEVKKPGASVKVSCKAS...",
    "light_chain_sequence": "DIQMTQSPSSLSASVGDRVTITC...",
    "isotype": "IgG1",
    "expression_system": "CHO-K1",
    "cell_line": "CHO-K1-203",
    "molecular_weight_da": 148000.50,
    "glycosylation_sites": ["N297"],
    "ptm_info": {
      "n_terminal": "Q to pE cyclization",
      "c_terminal": "K clipped"
    }
  },

  "xrefs": [
    { "xref_type": "PROJECT_CODE", "xref_value": "CMAB-203-PJ", "xref_source": "internal" }
  ]
}
```

#### 成功响应（201 Created）

```json
{
  "code": 0,
  "message": "Substance 创建成功",
  "data": {
    "substance_id": 124,
    "substance_code": "SUB-0000124",          // 自动生成
    "substance_type": "mab",
    "internal_code": "CMAB-203",
    "preferred_name": "Anti-PD-L1 mAb",
    "status": "draft",                        // 默认 draft
    "external_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "version": 1,
    "created_at": "2026-05-11T10:30:00Z",
    "created_by": 123,
    "updated_at": "2026-05-11T10:30:00Z",
    "updated_by": 123,

    "protein": { ... },
    "xrefs": [ ... ]
  },
  "meta": { ... }
}

# Location 头：
Location: /api/v1/substances/SUB-0000124
```

#### 失败场景

- 400 / 40001：必填字段缺失（preferred_name / substance_type）

- 400 / 40003：substance_type 不在允许枚举值

- 403 / 40301：缺少 substance:create 权限

- 409 / 40903：internal_code 已存在

## 6.3 详情查询

|         |                               |
|:-------:|-------------------------------|
| **GET** | **/api/v1/substances/{code}** |

通过 substance_code 查询详情。

#### 查询参数

- expand：可选 protein, adc, small_molecule, xrefs, status_history, projects, assets, materials, statistics

- 不传 expand 时仅返回主表字段

#### 成功响应（200）

```json
# GET /api/v1/substances/SUB-0000124?expand=protein,xrefs,projects
{
  "code": 0,
  "message": "OK",
  "data": {
    "substance_id": 124,
    "substance_code": "SUB-0000124",
    "substance_type": "mab",
    "internal_code": "CMAB-203",
    "preferred_name": "Anti-PD-L1 mAb",
    "preferred_name_en": "Anti-PD-L1 monoclonal antibody",
    "target": "PD-L1",
    "status": "active",
    "confidentiality": "restricted",
    "external_uuid": "550e8400-...",
    "description": "...",
    "notes": "...",
    "extra": { ... },
    "version": 5,
    "created_at": "2026-05-11T10:30:00Z",
    "created_by": 123,
    "created_by_name": "李清城",
    "updated_at": "2026-05-15T14:20:00Z",
    "updated_by": 123,
    "registered_at": "2026-05-12T09:00:00Z",
    "registered_by": 456,
    "registered_by_name": "张管家",

    "protein": {
      "heavy_chain_sequence": "EVQLVQSGA...",
      "light_chain_sequence": "DIQMTQSPS...",
      "sequence_length_hc": 446,
      "sequence_length_lc": 213,
      "sequence_hash_hc": "a3f5c8e9d2b1...",
      "isotype": "IgG1",
      "architecture": null,
      "expression_system": "CHO-K1",
      "molecular_weight_da": 148000.50,
      "glycosylation_sites": ["N297"],
      "ptm_info": { ... }
    },

    "xrefs": [
      {
        "xref_id": 501,
        "xref_type": "INN",
        "xref_value": "atezolizumab biosimilar",
        "xref_source": "WHO",
        "is_primary": true,
        "effective_date": "2025-12-01"
      }
    ],

    "projects": [
      {
        "project_code": "PRJ-2026-0042",
        "project_name": "PD-L1 mAb CMC 开发",
        "status": "active",
        "relation_type": "primary"
      }
    ],

    "statistics": {
      "project_count": 1,
      "asset_count": 0,
      "material_count": 5,
      "study_count": 12
    }
  },
  "meta": { ... }
}
```

## 6.4 更新 Substance

|         |                               |
|:-------:|-------------------------------|
| **PUT** | **/api/v1/substances/{code}** |

完整更新（PUT）或部分更新（PATCH）Substance 主属性。

> ⚠ 乐观锁机制
> 更新请求体必须包含 version 字段，与服务器版本对比：
> • 一致 → 更新成功，version 自增
> • 不一致 → 返回 409 / 40904 version_conflict，提示用户刷新后重试
> 防止并发覆盖，对 Steward 多人协作场景至关重要。

#### 请求体

```json
{
  "version": 5,                       // 必填，乐观锁
  "preferred_name": "Anti-PD-L1 mAb (humanized)",
  "target": "PD-L1",
  "modality": "humanized IgG1 mAb",
  "description": "更新后的描述",
  "extra": { ... },
  "change_reason": "INN 注册后更新首选名称"     // 关键字段变更必填原因
}
```

#### 成功响应（200）

```json
{
  "code": 0,
  "message": "更新成功",
  "data": {
    "substance_code": "SUB-0000124",
    "version": 6,                     // 自增
    "updated_at": "2026-05-15T14:25:00Z",
    "updated_by": 123,
    ...
  }
}
```

## 6.5 状态变更

|          |                                       |
|:--------:|---------------------------------------|
| **POST** | **/api/v1/substances/{code}:approve** |

Substance Steward 审核通过，状态从 draft → registered → active。

#### 请求体

```json
{
  "comment": "结构信息完整，与 INN 一致，批准注册",
  "signature": {                      // 电子签名（必填）
    "password": "********",
    "meaning": "approve",
    "reason": "结构信息已审核确认"
  }
}
```

#### 成功响应（200）

```json
{
  "code": 0,
  "message": "审核通过",
  "data": {
    "substance_code": "SUB-0000124",
    "old_status": "draft",
    "new_status": "registered",
    "registered_at": "2026-05-12T09:00:00Z",
    "registered_by": 456,
    "signature_id": 1024
  }
}
```

|          |                                         |
|:--------:|-----------------------------------------|
| **POST** | **/api/v1/substances/{code}:deprecate** |

弃用 Substance（如发现重复或决定终止）。

#### 请求体

```json
{
  "reason": "经评估与 SUB-0000089 为同一物质，合并",
  "merged_to_substance_code": "SUB-0000089",   // 可选，合并目标
  "signature": {
    "password": "********",
    "meaning": "approve",
    "reason": "同一性判定确认重复"
  }
}
```

|  |  |
|:--:|----|
| **POST** | /api/v1/substances/{code}:merge ⏳ Phase 5 数据治理工具阶段补 — V1.0 未实现 |

说明：本接口为 Phase 5 数据治理工具阶段的目标接口草案，Phase 1–3 当前不实现，不作为当前版本前后端联调契约。Phase 5 正式实施前，应结合物质合并治理流程、引用转移规则、审计追踪、电子签名与 QA 审批要求重新评审并冻结接口契约。

将当前 Substance 合并到目标 Substance（目标设计：按经批准的合并策略转移或更新引用关系；具体规则 Phase 5 实施前评审冻结）。

#### 请求体

```json
{
  "target_substance_code": "SUB-0000089",
  "reason": "序列完全一致，确认为同一物质",
  "transfer_xrefs": true,            // 是否转移当前 substance 的 xrefs 到目标
  "transfer_references": true,       // 是否更新所有 ref 引用到目标
  "signature": { ... }
}
```

#### 成功响应（200）

```json
{
  "code": 0,
  "message": "合并成功",
  "data": {
    "source_substance_code": "SUB-0000124",
    "target_substance_code": "SUB-0000089",
    "transferred_xrefs_count": 3,
    "transferred_projects_count": 2,
    "transferred_assets_count": 0,
    "transferred_materials_count": 5,
    "source_new_status": "deprecated"
  }
}
```

## 6.6 同一性判定

|          |                                       |
|:--------:|---------------------------------------|
| **POST** | **/api/v1/substances:check-sameness** |

基于序列哈希、InChI Key、内部代号等规则判定输入物质与现有 Substance 是否为同一物质。

#### 请求体（mAb 场景）

```json
{
  "substance_type": "mab",
  "heavy_chain_sequence": "EVQLVQSGAEVKKPGASVKVSCKAS...",
  "light_chain_sequence": "DIQMTQSPSSLSASVGDRVTITC...",
  "internal_code": "CMAB-203",        // 可选
  "tolerance": "exact"                // exact / fuzzy（fuzzy 留待 Phase 5 实现）
}
```

#### 成功响应（200）

```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "matched": true,
    "match_type": "sequence_exact",
    "matches": [
      {
        "substance_code": "SUB-0000089",
        "preferred_name": "Anti-PD-L1 mAb",
        "match_score": 1.00,
        "match_evidence": {
          "heavy_chain_hash": "a3f5c8e9d2b1...",
          "light_chain_hash": "b9c4a7f2e8d6..."
        }
      }
    ],
    "recommendation": "建议关联到现有 SUB-0000089，避免重复登记"
  }
}
```

## 6.7 子资源 endpoint

V1.1 实施侧简化：详情查询端点 GET /api/v1/substances/{code}?expand=protein,adc,xrefs,projects,assets,materials 已可一次返回全部子资源数据，建议前端优先使用 expand 参数；本节定义的独立 GET 子资源端点保留作为兼容路径。写操作（POST / PUT / DELETE）独立子资源端点保持必要，不得用 expand 替代。

|         |                                     |
|:-------:|-------------------------------------|
| **GET** | **/api/v1/substances/{code}/xrefs** |

获取标识符列表。

|          |                                     |
|:--------:|-------------------------------------|
| **POST** | **/api/v1/substances/{code}/xrefs** |

#### 请求体

```json
{
  "xref_type": "INN",
  "xref_value": "atezolizumab biosimilar",
  "xref_source": "WHO",
  "region": "Global",
  "is_primary": false,
  "effective_date": "2026-01-15"
}
```

|         |                                        |
|:-------:|----------------------------------------|
| **GET** | **/api/v1/substances/{code}/projects** |

获取关联的项目列表（反向查询）。

#### 成功响应

```json
{
  "code": 0,
  "data": [
    {
      "project_code": "PRJ-2026-0042",
      "project_name": "PD-L1 mAb CMC 开发",
      "project_type": "cmc",
      "status": "active",
      "project_manager": { "username": "wangwu", "full_name": "王五" },
      "relation_type": "primary",
      "linked_at": "2026-05-12T10:00:00Z"
    }
  ],
  "meta": { ... }
}
```

# 7. PRS Endpoint 详细规范

## 7.1 列表查询

|         |                      |
|:-------:|----------------------|
| **GET** | **/api/v1/projects** |

#### 查询参数（除分页外）

| **参数**          | **类型** | **说明**                                |
|-------------------|----------|-----------------------------------------|
| q                 | string   | 全文搜索（project_code / project_name） |
| project_type      | string   | 项目类型                                |
| status            | string   | 状态                                    |
| project_manager   | string   | 项目经理 username                       |
| substance_code    | string   | 关联指定 substance 的项目               |
| asset_code        | string   | 关联指定 asset 的项目                   |
| start_date\_\_gte | date     | 开始日期起                              |
| end_date\_\_lt    | date     | 结束日期止                              |
| my_projects       | bool     | 仅我参与的项目                          |
| confidentiality   | string   | 保密等级                                |

## 7.2 创建项目

|          |                      |
|:--------:|----------------------|
| **POST** | **/api/v1/projects** |

#### 请求体

```json
{
  "project_name": "PD-L1 mAb CMC 开发",
  "project_name_en": "PD-L1 mAb CMC Development",
  "project_type": "cmc",
  "project_phase": "phase_1",

  "planned_start_date": "2026-06-01",
  "planned_end_date": "2027-12-31",

  "project_manager_username": "wangwu",
  "sponsor_username": "qingcheng",
  "department": "CMC R&D",

  "budget_total": 5000000.00,
  "budget_currency": "CNY",

  "objective": "完成 PD-L1 mAb 的 CMC 开发，支持 IND 申报",
  "scope": "细胞株稳定性、工艺开发、分析方法、稳定性研究",
  "deliverables": "DS/DP 工艺包、IND CMC section",
  "success_criteria": "通过 IND 受理",

  "priority": "high",
  "confidentiality": "internal",

  "related_substances": [
    { "substance_code": "SUB-0000124", "relation_type": "primary" }
  ],
  "related_assets": [
    { "asset_code": "AST-0023", "relation_type": "primary" }
  ],

  "team": [
    { "username": "wangwu",   "role": "PM",    "function_area": "CMC", "allocation_pct": 60 },
    { "username": "lisi",     "role": "Lead",  "function_area": "USP", "allocation_pct": 100 },
    { "username": "zhangsan", "role": "Member","function_area": "DSP", "allocation_pct": 80 }
  ]
}
```

#### 成功响应（201）

```json
{
  "code": 0,
  "message": "项目创建成功",
  "data": {
    "project_id": 42,
    "project_code": "PRJ-2026-0042",       // 自动生成
    "project_name": "PD-L1 mAb CMC 开发",
    "project_type": "cmc",
    "status": "proposed",                  // 默认 proposed
    "version": 1,
    "created_at": "2026-05-11T10:30:00Z",
    ...
  }
}
```

## 7.3 详情

|         |                             |
|:-------:|-----------------------------|
| **GET** | **/api/v1/projects/{code}** |

expand 参数支持：milestones, team, substances, assets, status_history, statistics。

## 7.4 更新与状态变更

|         |                             |
|:-------:|-----------------------------|
| **PUT** | **/api/v1/projects/{code}** |

更新项目，需 version 乐观锁。

|          |                                     |
|:--------:|-------------------------------------|
| **POST** | **/api/v1/projects/{code}:approve** |

批准项目从 proposed → initiated。

|          |                                       |
|:--------:|---------------------------------------|
| **POST** | **/api/v1/projects/{code}:terminate** |

#### 请求体

```json
{
  "reason": "管线优化决定终止该项目",
  "termination_date": "2026-09-30",
  "signature": {
    "password": "********",
    "meaning": "approve",
    "reason": "管线评审会决议"
  }
}
```

## 7.5 子资源

|          |                                        |
|:--------:|----------------------------------------|
| **GET**  | **/api/v1/projects/{code}/milestones** |
| **POST** | **/api/v1/projects/{code}/milestones** |

#### 请求体

```json
{
  "milestone_name": "细胞株锁定",
  "milestone_type": "gate",
  "planned_date": "2026-08-31",
  "description": "完成 RCB 细胞株评估并锁定"
}
```

|         |                                                |
|:-------:|------------------------------------------------|
| **PUT** | **/api/v1/projects/{code}/milestones/{ms_id}** |

#### 请求体（标记完成）

```json
{
  "actual_date": "2026-08-25",
  "status": "completed",
  "description": "细胞株 CL-203-A03 已选定"
}
```

|          |                                  |
|:--------:|----------------------------------|
| **POST** | **/api/v1/projects/{code}/team** |

#### 请求体

```json
{
  "username": "newmember",
  "role": "Member",
  "function_area": "Analytical",
  "allocation_pct": 50,
  "joined_at": "2026-06-01"
}
```

|          |                                        |
|:--------:|----------------------------------------|
| **POST** | **/api/v1/projects/{code}/substances** |

#### 请求体

ref.project_asset 关系端点（V1.1 新增）

GET /api/v1/projects/{code}/assets — 列表，响应含 asset_code / internal_name / current_phase / relation_type / linked_at

POST /api/v1/projects/{code}/assets — 新增关联，请求体 { asset_code, relation_type (默认 primary，建议值 primary/supporting/derivative/reference) }

PUT /api/v1/projects/{code}/assets/{asset_code} — 修改 relation_type（属性可变，不入 PK）

DELETE /api/v1/projects/{code}/assets/{asset_code} — 软删除关系

权限：project:update

```json
{
  "substance_code": "SUB-0000125",
  "relation_type": "control",
  "notes": "对照品"
}
```

# 8. ARS / MM / 全局 Endpoint

## 8.1 ARS 关键 endpoint

|          |                    |
|:--------:|--------------------|
| **POST** | **/api/v1/assets** |

#### 请求体

```json
{
  "internal_name": "PD-L1 mAb",
  "trade_name": null,
  "inn_name": "atezolizumab biosimilar",

  "asset_type": "mab",
  "therapeutic_area": "oncology",
  "indication": "实体瘤（NSCLC, UC, HCC）",
  "dosage_form": "注射用浓溶液",
  "strength": "1200 mg/20 mL",
  "route_of_administration": "IV",

  "current_phase": "phase_1",
  "is_commercial": false,

  "description": "针对 PD-L1 的人源化单抗（生物类似药）",

  "related_substances": [
    {
      "substance_code": "SUB-0000124",
      "component_role": "main_component",
      "is_active_ingredient": true
    }
  ]
}
```

|  |  |
|:--:|----|
| **POST** | /api/v1/assets/{code}:advance-phase ⏳ Phase 5 视需补 — V1.0 未实现 |
|  |  |
|  |  |
|  |  |

#### 请求体

```json
{
  "to_phase": "phase_2",
  "phase_change_date": "2026-08-01",
  "reason": "Phase I 试验完成，正式进入 Phase II",
  "signature": { ... }
}
```

|          |                                      |
|:--------:|--------------------------------------|
| **POST** | **/api/v1/assets/{code}/market-ids** |

#### 请求体

```json
{
  "market_code": "CN",
  "id_type": "NMPA_APPROVAL",
  "id_value": "国药准字 SXXXXXXX",
  "issuing_authority": "国家药品监督管理局",
  "application_date": "2025-03-01",
  "approval_date": "2026-04-15",
  "status": "approved"
}
```

ARS 状态机端点（V1.1 新增）

POST /api/v1/assets/{code}:hold — 暂停资产

前置条件：status = active → on_hold

权限：asset:update

请求体：{ "reason": "string (≥5字)" }

POST /api/v1/assets/{code}:resume — 恢复资产

前置条件：status = on_hold → active

权限：asset:update

请求体：{ "reason": "string (≥5字)" }

POST /api/v1/assets/{code}:terminate — 终止资产（不可逆）

前置条件：status ∈ {active, on_hold} → terminated

权限：asset:update + asset:sign（双权限，21 CFR Part 11 §11.50）

请求体：{ "reason": "string", "signature": { "password": "string", "meaning": "string" } }

失败场景：422/42201 state_invalid — 状态机前置条件不满足；422/42203 signature_required — 未提供签名；401/40106 signature_invalid — 签名密码错误

角色映射：PROJECT_MANAGER + QA_REVIEWER 默认持有 asset:sign

ref.asset_substance 关系端点（V1.1 新增）

GET /api/v1/assets/{code}/substances — 列表，响应含 substance_code / component_role / is_active_ingredient / linked_at

POST /api/v1/assets/{code}/substances — 新增关联，请求体 { substance_code, component_role ∈ main_component/antibody/linker/payload/excipient/impurity, is_active_ingredient }

PUT /api/v1/assets/{code}/substances/{substance_code} — 修改 component_role / is_active_ingredient

DELETE /api/v1/assets/{code}/substances/{substance_code} — 软删除关系

备注：terminated 资产禁止新建关联（service 层校验，422 错误）

## 8.2 MM 关键 endpoint

|          |                       |
|:--------:|-----------------------|
| **POST** | **/api/v1/materials** |

#### 请求体

> `material_code` 必填，由用户输入公司内既有编码（max 20 chars）。
> `material_type` 4 值：`reagent / consumable / standard / column`。
> `category` 公司 15 值扁平枚举：一般耗材 / 关键耗材 / 关键试剂 / 内包材 / 外包材 /
> 劳保 / 原辅料 / 参比品 / 对照品 / 工艺用水/气 / 标准品 / 细胞种子 / 自制包材 /
> 试剂 / 运输包装材料。

```json
{
  "material_code": "51001",
  "material_name": "PBS 10× 缓冲液",
  "material_type": "reagent",
  "category": "试剂",
  "unit": "瓶",
  "manufacturer": "Gibco / Thermo Fisher",
  "catalog_no": "70011-044",
  "package_spec": "500 mL/瓶",
  "physical_form": "solution",
  "storage_condition": "2-8°C",
  "source_type": "vendor",
  "source_name": "Gibco / Thermo Fisher",
  "grade": "GR"
}
```

|          |                                      |
|:--------:|--------------------------------------|
| **POST** | **/api/v1/materials/{code}/batches** |

#### 请求体

```json
{
  "batch_number": "EB-001-2026-001",
  "quantity_value": 50.0,
  "quantity_unit": "mL",
  "manufacture_date": "2026-04-20",
  "expiry_date": "2027-04-19",
  "storage_location": "Bldg A / Room 3 / Freezer #5",
  "status": "in_stock"
}
```

## 8.3 全局搜索

|         |                    |
|:-------:|--------------------|
| **GET** | **/api/v1/search** |

#### 查询参数

| **参数** | **类型** | **说明**                                               |
|----------|----------|--------------------------------------------------------|
| q        | string   | 搜索关键词                                             |
| types    | string   | 限定类型，逗号分隔（substance,project,asset,material） |
| limit    | int      | 每个类型返回数量，默认 10                              |

#### 成功响应

```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "query": "PD-L1",
    "total": 18,
    "results": {
      "substance": {
        "total": 4,
        "items": [
          { "substance_code": "SUB-0000124", "preferred_name": "Anti-PD-L1 mAb", ... },
          ...
        ]
      },
      "project": {
        "total": 8,
        "items": [
          { "project_code": "PRJ-2026-0042", "project_name": "PD-L1 mAb CMC 开发", ... },
          ...
        ]
      },
      "asset": {
        "total": 2,
        "items": [ ... ]
      },
      "material": {          // Phase 4 MM 域启用后返回，Phase 1-3 不返回此节
        "total": 4,
        "items": [ ... ]
      }
    }
  }
}
```

命中字段与排序权重（V1.1 新增）

substance 命中字段：substance_code / preferred_name / internal_code / aliases

project 命中字段：project_code / project_name / internal_code / description

asset 命中字段：asset_code / internal_name / trade_name / inn_name / indication；trade_name / inn_name 排序权重 = 5

权限过滤：按 \<entity\>:read 权限过滤（SYS_ADMIN bypass）

## 8.4 枚举字典

|         |                            |
|:-------:|----------------------------|
| **GET** | **/api/v1/lookups/{type}** |

type 例：substance_status, substance_type, project_status, project_type, asset_phase 等。

#### 成功响应

```json
# GET /api/v1/lookups/substance_status
{
  "code": 0,
  "data": [
    { "code": "draft",       "name": "草稿",     "name_en": "Draft",      "sort_order": 10 },
    { "code": "registered",  "name": "已注册",   "name_en": "Registered", "sort_order": 20 },
    { "code": "active",      "name": "活跃",     "name_en": "Active",     "sort_order": 30 },
    { "code": "restricted",  "name": "受限",     "name_en": "Restricted", "sort_order": 40 },
    { "code": "deprecated",  "name": "已弃用",   "name_en": "Deprecated", "sort_order": 50 },
    { "code": "obsoleted",   "name": "已废止",   "name_en": "Obsoleted",  "sort_order": 60 }
  ]
}
```

## 8.5 审计日志

|         |                        |
|:-------:|------------------------|
| **GET** | **/api/v1/audit-logs** |

#### 查询参数

| **参数** | **类型** | **说明** |
|----|----|----|
| user | string | 用户名过滤 |
| action | string | 动作类型（CREATE/UPDATE/DELETE/APPROVE/SIGN/LOGIN 等） |
| entity_schema | string | schema 过滤（srs/prs/ars/mm） |
| entity_table | string | 表名 |
| entity_code | string | 业务编码精确匹配 |
| timestamp\_\_gte | datetime | 时间起 |
| timestamp\_\_lt | datetime | 时间止 |
| ip_address | string | IP 地址 |

#### 成功响应

```json
{
  "code": 0,
  "data": [
    {
      "log_id": 100423,
      "timestamp": "2026-05-15T14:25:00Z",
      "username": "qingcheng",
      "full_name": "李清城",
      "department": "CMC R&D",
      "action": "UPDATE",
      "entity_schema": "srs",
      "entity_table": "substance",
      "entity_id": 124,
      "entity_code": "SUB-0000124",
      "change_summary": "preferred_name updated",
      "reason": "INN 注册后更新首选名称",
      "ip_address": "10.0.0.5",
      "request_id": "req_xyz",
      "field_changes": "preferred_name: "Anti-PD-L1 mAb" → "Anti-PD-L1 mAb (humanized)""
    }
  ],
  "meta": {
    "pagination": { "page": 1, "page_size": 50, "total": 12345, "total_pages": 247 }
  }
}
```

|          |                               |
|:--------:|-------------------------------|
| **POST** | **/api/v1/audit-logs:export** |

导出审计日志（异步任务，返回任务 ID，前端轮询或 WebSocket 接收完成通知）。

#### 请求体

```json
{
  "format": "xlsx",                 // xlsx / csv / pdf
  "filters": { ... },               // 同 GET 查询参数
  "fields": ["timestamp", "username", "action", "entity_code", "field_changes", "reason"]
}
```

#### 成功响应（202 Accepted）

```json
{
  "code": 0,
  "message": "导出任务已提交",
  "data": {
    "task_id": "export_task_abc123",
    "status": "pending",
    "estimated_seconds": 30,
    "result_url": null              // 完成后返回下载链接
  }
}
```

## 8.6 电子签名

|          |                        |
|:--------:|------------------------|
| **POST** | **/api/v1/signatures** |

独立签名 endpoint（也可通过资源动作内嵌完成）。

#### 请求体

```json
{
  "entity_schema": "srs",
  "entity_table": "substance",
  "entity_code": "SUB-0000124",
  "signature_meaning": "approve",
  "signature_reason": "我已审核确认结构信息正确",
  "password": "********",          // 密码二次确认（21 CFR Part 11 要求）
  "signed_content": {              // 被签名的内容快照
    "substance_code": "SUB-0000124",
    "version": 6,
    "key_attributes": { ... }
  }
}
```

#### 成功响应

```json
{
  "code": 0,
  "message": "签名成功",
  "data": {
    "signature_id": 1024,
    "signed_at": "2026-05-12T09:00:00Z",
    "signature_hash": "a3f5c8e9d2b1...",       // SHA-256
    "signed_content_hash": "b9c4a7f2e8d6..."
  }
}
```

#### 失败场景

- 401 / 40105：密码错误（连续 3 次失败锁定签名功能 30 分钟）

- 403 / 40301：缺少对应资源 sign 权限

- 422 / 46001：签名内容哈希与服务器计算不一致（防篡改）

## 8.7 健康检查

|         |             |
|:-------:|-------------|
| **GET** | **/health** |

无需认证，用于负载均衡器和监控系统探活。

#### 成功响应（200）

```json
{  "status": "healthy",  "version": "1.1.0",  "checks": {    "database": "ok",    "redis": "ok"  },  "timestamp": "2026-05-11T10:30:00Z"} # 任一组件异常返回 503，前端不应展示给最终用户
```

# 9. Pydantic Schema 对齐

## 9.1 命名规范

- 基础 Schema：\<Entity\>Base（共享字段）

- 创建：\<Entity\>Create（POST 请求体）

- 更新：\<Entity\>Update（PUT 请求体，全字段可选 + version）

- 响应（详情）：\<Entity\>（含所有字段 + 关联）

- 响应（列表）：\<Entity\>Brief（精简字段）

- 查询参数：\<Entity\>Filter

## 9.2 通用响应包装

```python
from typing import Generic, TypeVar, Any
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime

T = TypeVar("T")

class Pagination(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int

class ResponseMeta(BaseModel):
    request_id: str
    timestamp: datetime
    api_version: str = "v1"
    pagination: Pagination | None = None

class Response(BaseModel, Generic[T]):
    code: int = 0
    message: str = "OK"
    data: T | None = None
    meta: ResponseMeta

class ListResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "OK"
    data: list[T] = Field(default_factory=list)
    meta: ResponseMeta

class ErrorDetail(BaseModel):
    field: str | None = None
    message: str

class ErrorInfo(BaseModel):
    type: str
    details: list[ErrorDetail] = Field(default_factory=list)
    trace_id: str | None = None

class ErrorResponseMeta(ResponseMeta):
    error: ErrorInfo

class ErrorResponse(BaseModel):
    code: int
    message: str
    data: None = None
    meta: ErrorResponseMeta
```

## 9.3 Substance Schema 示例

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from uuid import UUID
from typing import Literal


# 类型别名
SubstanceType = Literal["mab", "bispecific", "adc", "fusion", "small_molecule", "oligonucleotide", "other"]
SubstanceStatus = Literal["draft", "registered", "active", "restricted", "deprecated", "obsoleted"]
Confidentiality = Literal["public", "internal", "restricted"]


class SubstanceBase(BaseModel):
    """共享字段基类"""
    model_config = ConfigDict(from_attributes=True)

    substance_type: SubstanceType
    internal_code: str | None = Field(None, max_length=64)
    preferred_name: str = Field(..., max_length=255)
    preferred_name_en: str | None = Field(None, max_length=255)
    target: str | None = Field(None, max_length=128)
    target_type: str | None = Field(None, max_length=64)
    modality: str | None = Field(None, max_length=64)
    is_proprietary: bool = True
    confidentiality: Confidentiality = "internal"
    description: str | None = None
    notes: str | None = None
    extra: dict | None = None


class ProteinExtensionInput(BaseModel):
    """蛋白属性输入"""
    heavy_chain_sequence: str | None = None
    light_chain_sequence: str | None = None
    additional_chains: dict | None = None
    isotype: str | None = Field(None, max_length=32)
    architecture: str | None = Field(None, max_length=64)
    expression_system: str | None = Field(None, max_length=64)
    cell_line: str | None = Field(None, max_length=128)
    molecular_weight_da: float | None = Field(None, ge=0)
    glycosylation_sites: list[str] | None = None
    ptm_info: dict | None = None

    @field_validator("heavy_chain_sequence", "light_chain_sequence")
    @classmethod
    def validate_sequence(cls, v):
        if v is None:
            return v
        # 保留有效字符（氨基酸 + 间隔符），校验大写字母
        cleaned = "".join(c for c in v if c.isalpha())
        if not cleaned.isupper():
            raise ValueError("序列必须为大写氨基酸单字母代码")
        return v


class SubstanceXrefInput(BaseModel):
    xref_type: Literal["INN", "USAN", "CAS", "UNII", "GSRS_UUID", "ChEMBL",
                       "DRUGBANK", "TRADE_NAME", "GENERIC_NAME",
                       "HISTORICAL_CODE", "PROJECT_CODE", "OTHER"]
    xref_value: str = Field(..., max_length=255)
    xref_source: str | None = Field(None, max_length=64)
    region: str | None = Field(None, max_length=16)
    is_primary: bool = False
    effective_date: str | None = None     # YYYY-MM-DD


class SubstanceCreate(SubstanceBase):
    """POST 请求体"""
    protein: ProteinExtensionInput | None = None
    adc: dict | None = None              # ADC 扩展（详细 schema 略）
    small_molecule: dict | None = None   # 小分子扩展
    xrefs: list[SubstanceXrefInput] = Field(default_factory=list)


class SubstanceUpdate(BaseModel):
    """PUT 请求体（全部可选，需带 version 乐观锁）"""
    version: int = Field(..., description="乐观锁版本号")
    change_reason: str | None = Field(None, description="变更原因")

    preferred_name: str | None = None
    preferred_name_en: str | None = None
    target: str | None = None
    target_type: str | None = None
    modality: str | None = None
    confidentiality: Confidentiality | None = None
    description: str | None = None
    notes: str | None = None
    extra: dict | None = None
    # internal_code 不可修改


class SubstanceBrief(BaseModel):
    """列表项精简字段"""
    model_config = ConfigDict(from_attributes=True)

    substance_code: str
    substance_type: SubstanceType
    internal_code: str | None
    preferred_name: str
    preferred_name_en: str | None
    target: str | None
    status: SubstanceStatus
    confidentiality: Confidentiality
    inn: str | None = None
    cas_number: str | None = None
    project_count: int = 0
    asset_count: int = 0
    material_count: int = 0
    created_at: datetime
    updated_at: datetime


class Substance(SubstanceBase):
    """详情响应"""
    substance_id: int
    substance_code: str
    status: SubstanceStatus
    external_uuid: UUID
    version: int

    created_at: datetime
    created_by: int
    created_by_name: str | None = None
    updated_at: datetime
    updated_by: int
    updated_by_name: str | None = None
    registered_at: datetime | None = None
    registered_by: int | None = None
    registered_by_name: str | None = None

    # 可展开
    protein: dict | None = None
    adc: dict | None = None
    xrefs: list[dict] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    assets: list[dict] = Field(default_factory=list)
    statistics: dict | None = None
```

## 9.4 自动 OpenAPI 生成

FastAPI 基于 Pydantic 自动生成 OpenAPI 3.0 规范，无需手写 YAML：

```text
# main.pyfrom fastapi import FastAPIfrom app.api.v1 import auth, substances, projects, assets, materials app = FastAPI(    title="CMAB MDM Portal API",    version="1.1.0",    description="生物制药主数据管理平台 API",    docs_url="/api/v1/docs",    redoc_url="/api/v1/redoc",    openapi_url="/api/v1/openapi.json",) app.include_router(auth.router,        prefix="/api/v1/auth",        tags=["auth"])app.include_router(substances.router,  prefix="/api/v1/substances",  tags=["substances"])app.include_router(projects.router,    prefix="/api/v1/projects",    tags=["projects"])app.include_router(assets.router,      prefix="/api/v1/assets",      tags=["assets"])app.include_router(materials.router,   prefix="/api/v1/materials",   tags=["materials"]) # 启动后访问：#   http://localhost:8000/api/v1/docs    Swagger UI#   http://localhost:8000/api/v1/redoc   ReDoc#   http://localhost:8000/api/v1/openapi.json  原始 OpenAPI 3.0 JSON
```

## 9.5 前端 TypeScript 类型生成

```tsx
# 前端从后端 OpenAPI 自动生成 TypeScript 类型
# 安装：pnpm add -D openapi-typescript

# package.json scripts:
{
  "scripts": {
    "gen:api": "openapi-typescript http://localhost:8000/api/v1/openapi.json -o src/api/schema.d.ts"
  }
}

# 生成后前端可用：
import type { paths, components } from '@/api/schema';

type Substance = components['schemas']['Substance'];
type SubstanceCreate = components['schemas']['SubstanceCreate'];

const createSubstance = async (data: SubstanceCreate): Promise<Substance> => {
  const res = await api.post<Response<Substance>>('/api/v1/substances', data);
  return res.data.data;
};
```

> 💡 前后端类型同步流程
> 1. 后端定义 Pydantic Schema
> 2. FastAPI 启动后 /openapi.json 暴露契约
> 3. 前端 pnpm gen:api 生成 TS 类型
> 4. 前端用强类型调用 API，IDE 自动补全
> 5. 后端 schema 变更 → 前端重新生成 → 编译时发现不兼容
> → 这是 API-First + 前后端类型一致的核心保证

# 10. 集成与版本演进

## 10.1 下游系统集成

### 10.1.1 集成模式

- RESTful API（推荐）：实时查询、轻量级集成

- Webhook（计划）：事件驱动，主数据变更时主动通知下游

- 批量导出（已有）：审计日志、报表导出

- 数据库直连：仅 cmc_data_platform 内部模块，schema 隔离

### 10.1.2 服务到服务认证（M2M）

非用户登录场景（如 ELN 后端调用 MDM API），使用 Service Account：

```json
# 1. 管理员为下游系统创建 Service Account
POST /api/v1/users
{
  "username": "svc_eln",
  "user_type": "service",
  "full_name": "ELN Service Account",
  "roles": ["READ_ONLY_USER"]
}

# 2. 生成长期 API Key（替代密码）
POST /api/v1/users/svc_eln/api-keys
{
  "name": "ELN production key",
  "expires_at": "2027-05-11T00:00:00Z"
}
# 返回（仅返回一次）：
{
  "api_key": "cmab_mdm_pk_xxxxxxxxxxxxxxxxxxxx",
  "expires_at": "2027-05-11T00:00:00Z"
}

# 3. ELN 调用 API 时携带
Authorization: Bearer cmab_mdm_pk_xxxxxxxxxxxxxxxxxxxx
```

### 10.1.3 RAGFlow 集成示例

RAGFlow 知识库可调用以下 endpoint 索引主数据：

```http
# 增量同步 substance 摘要供 RAG 检索
GET /api/v1/substances?fields=substance_code,preferred_name,target,description&updated_at__gte=2026-04-01

# 项目摘要
GET /api/v1/projects?fields=project_code,project_name,objective,status&updated_at__gte=2026-04-01

# 由 RAGFlow 端定期拉取，写入向量库
```

## 10.2 版本演进策略

### 10.2.1 版本号语义

- URL 版本（v1, v2）：重大不兼容变更（删除字段、改语义、改 URL）

- 文档版本（V1.0, V1.1）：跟踪 API 文档迭代

- 应用版本（1.1.0）：完整产品语义化版本（Semver）

### 10.2.2 兼容性规则

v1 内允许的演进（向后兼容）：

- 新增 endpoint

- 新增可选字段（请求体）

- 新增字段（响应体）

- 放宽校验规则

- 新增枚举值（客户端必须容错处理未知值）

v1 内禁止的变更（必须升级到 v2）：

- 删除字段

- 改字段类型

- 改字段语义

- 改必填/选填

- 删除枚举值

- 改 URL 路径

- 改 HTTP 方法

### 10.2.3 弃用流程

```http
# Step 1: 在响应中标记弃用，给前端提前预警
HTTP/1.1 200 OK
Sunset: Wed, 31 Dec 2026 23:59:59 GMT
Deprecation: true
Link: </api/v2/substances>; rel="successor-version"

# Step 2: 至少保留 6 个月并在文档明确标注
# Step 3: 新版本上线后通知所有调用方
# Step 4: 6 个月后正式下线
```

## 10.3 OpenAPI 规范导出

- dev / test 环境：/api/v1/openapi.json 始终可访问

- 生产环境：默认关闭文档 endpoint，只在管理员认证后可访问

- 纳入版本控制：每次重大版本（V1.0, V1.1）导出 OpenAPI YAML 归档到 docs/api/

## 10.4 API 治理

- 所有新增 endpoint 必须经评审，符合本文档规范

- URL 格式审查 + Pydantic schema 审查 + 权限定义审查

- 自动化检查：在 CI 中跑 OpenAPI Linter（如 Spectral）

- 性能 SLA：列表 P95 \< 500ms，详情 P95 \< 200ms，写入 P95 \< 800ms

# 11. 附录

## 11.1 完整 endpoint 索引（按方法）

可用作前端 API Client 模块化的基础。具体清单见第 5 章。

## 11.2 状态机参考

### 11.2.1 Substance 状态机

```text
     ┌──────────┐   approve    ┌────────────┐
     │  draft   │ ───────────► │ registered │
     └────┬─────┘              └──────┬─────┘
          │ reject                    │ activate (auto)
          ▼                           ▼
       (deleted)                ┌──────────┐
                                │  active  │
                                └─────┬────┘
                ┌───────────────┬─────┼──────────────┐
                │               │     │              │
                ▼               ▼     ▼              ▼
           ┌──────────┐   ┌────────┐   ┌────────────┐
           │restricted│   │deprecat│   │ obsoleted  │
           └──────────┘   │   ed   │   └────────────┘
                          └────────┘
```

### 11.2.2 Project 状态机

```text
     ┌──────────┐  approve   ┌────────────┐  start  ┌────────┐
     │ proposed │ ─────────► │ initiated  │ ──────► │ active │
     └────┬─────┘            └────┬───────┘         └───┬────┘
          │ reject                │ terminate           │
          ▼                       ▼                     ▼
       (deleted)              ┌──────────┐         ┌─────────┐
                              │terminated│         │ on_hold │
                              └──────────┘         └────┬────┘
                                                        │ resume
                                                        ▼
                                                    (active)
                              ┌──────────┐ complete    ▲
                              │completed │ ◄───────────┘
                              └──────────┘
```

## 11.3 cURL 调用示例

```json
# 1. 登录
curl -X POST https://mdm.cmab.internal/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"qingcheng","password":"********"}'

# 2. 创建 Substance
TOKEN="eyJhbGc..."
curl -X POST https://mdm.cmab.internal/api/v1/substances \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d @substance.json

# 3. 查询
curl "https://mdm.cmab.internal/api/v1/substances?substance_type=mab&status=active&page=1&page_size=20" \
  -H "Authorization: Bearer $TOKEN"

# 4. 详情
curl "https://mdm.cmab.internal/api/v1/substances/SUB-0000124?expand=protein,xrefs,projects" \
  -H "Authorization: Bearer $TOKEN"

# 5. 审核
curl -X POST "https://mdm.cmab.internal/api/v1/substances/SUB-0000124:approve" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"comment":"已审核","signature":{"password":"...","meaning":"approve","reason":"..."}}'
```

## 11.4 后端实现示例

```python
# backend/app/api/v1/substances.py

from fastapi import APIRouter, Depends, Query, HTTPException, status
from app.shared.permissions import require_permission, get_current_user
from app.shared.responses import Response, ListResponse
from app.domains.srs.services import SubstanceService
from app.domains.srs.schemas import (
    Substance, SubstanceBrief, SubstanceCreate, SubstanceUpdate,
    SubstanceFilter
)

router = APIRouter()

@router.get(
    "",
    response_model=ListResponse[SubstanceBrief],
    summary="Substance 列表",
)
async def list_substances(
    filter: SubstanceFilter = Depends(),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str | None = None,
    current_user = Depends(require_permission("substance:read")),
    service: SubstanceService = Depends(),
):
    items, total = await service.list(filter, page, page_size, sort, current_user)
    return ListResponse(
        data=items,
        meta=make_meta(pagination=Pagination(
            page=page, page_size=page_size,
            total=total, total_pages=ceil(total / page_size)
        ))
    )

@router.post(
    "",
    response_model=Response[Substance],
    status_code=status.HTTP_201_CREATED,
    summary="创建 Substance",
)
async def create_substance(
    payload: SubstanceCreate,
    idempotency_key: str | None = Header(None),
    current_user = Depends(require_permission("substance:create")),
    service: SubstanceService = Depends(),
):
    substance = await service.create(payload, current_user, idempotency_key)
    return Response(data=substance, meta=make_meta())

@router.get(
    "/{code}",
    response_model=Response[Substance],
    summary="Substance 详情",
)
async def get_substance(
    code: str,
    expand: str | None = None,
    current_user = Depends(require_permission("substance:read")),
    service: SubstanceService = Depends(),
):
    substance = await service.get_by_code(code, expand=expand_list(expand))
    if substance is None:
        raise HTTPException(404, detail={"code": 40402, "message": "Substance 不存在"})
    return Response(data=substance, meta=make_meta())
```

## 11.5 后续文档清单

| **文档编号**   | **文档名称**                           | **依赖本文档** |
|----------------|----------------------------------------|----------------|
| UI-MDM-001     | UI 信息架构与线框图                    | ✓              |
| DEV-MDM-001    | 开发规范（Service 层、错误处理、日志） | ✓              |
| TEST-MDM-001   | 测试策略与计划（含 API 测试）          | ✓              |
| INTEG-MDM-001  | 下游系统集成手册                       | ✓              |
| DEPLOY-MDM-001 | 部署与运维手册                         | ✓              |

## 11.6 参考

- CMAB 内部文档：ARCH-MDM-001 V1.1、DM-MDM-001 V1.1

- OpenAPI 3.0 规范：https://spec.openapis.org/oas/v3.0.3

- FastAPI 文档：https://fastapi.tiangolo.com/

- Pydantic v2 文档：https://docs.pydantic.dev/2.0/

- REST API Design Best Practices（Microsoft、Google API Design Guide）

- 21 CFR Part 11 / Annex 11（核对最新版）

- RFC 7234 HTTP Caching、RFC 6585 Additional HTTP Status Codes

11.7 路线图：Phase 4 / Phase 5 端点（V1.1 新增）

R1: POST /auth/refresh — JWT 刷新 — 当前 access_token 30min 自然过期已覆盖 dev/UAT — 重新登录 — Phase 4 安全收尾

R2: POST /substances/{code}:reject — 物质驳回 — 业务必要性待评估 — DELETE 软删除替代 — Phase 4 视需

R3: POST /substances/{code}:merge — 物质合并 — 需配合 merged_to_substance_code 字段 — 手工 DBA 迁移 — Phase 5

R4: POST /assets/{code}:advance-phase — 阶段流转 — 状态机校验需求未明 — PUT 直接更新 current_phase — Phase 5

R5: POST /{domain}:batch-\* — 批量操作 — 单条 CRUD + 幂等键已覆盖 90% 场景 — 循环单条调用 — Phase 5
