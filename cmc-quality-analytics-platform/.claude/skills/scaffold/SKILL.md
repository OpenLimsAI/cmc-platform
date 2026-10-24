---
name: scaffold
description: Bootstrap the QAP backend or frontend project skeleton exactly per the architecture design doc. Use when starting implementation of a layer that doesn't exist yet.
disable-model-invocation: true
---

# 搭建 QAP 项目骨架

按 `docs/QAP-SAD-001_System_Architecture_Design.md` 中的设计，搭建一个全新的项目骨架。每一层（backend/frontend）只搭建一次；未经确认不要覆盖已存在的骨架。

`$ARGUMENTS` 用于指定目标：`backend`、`frontend`，或留空（留空则询问要搭建哪一层）。

## 步骤

1. 阅读 `docs/QAP-SAD-001_System_Architecture_Design.md`，确认规范的目录布局、技术栈版本和各项约定。该文档是权威依据——若与下文有冲突，以文档为准并指出差异。
2. 确认目标目录中尚不存在骨架。若已存在，停止并报告。
3. 先给出简短方案（要创建的文件/目录、关键依赖、开发/运行命令），获得批准后再写入——遵循仓库「先方案、后实现」的工作方式。
4. 创建骨架：
   - **backend** —— 在 `backend/app/` 下搭建 FastAPI 应用，包含 `main.py` 以及 `api/v1`、`core`、`models`、`services`、`schemas` 等包；一个 `tests/` 目录；接入 SQLAlchemy + Alembic + Pydantic；通过只读角色 `qap_reader` 连接 PostgreSQL 16；将 `{ data, meta, errors }` 响应信封作为共享 schema。Python 3.11+。
   - **frontend** —— 在 `frontend/` 下搭建 React 18 + Vite + TypeScript，包含 `src/{pages,components,services,hooks,types}`；提供一个消费 `/api/v1/` 信封格式的 API 客户端。
5. 为新增的这一层补充最小化的 README/运行说明，并报告你接入的 build/test/run 命令——这些命令将来可作为 format/lint hook 的候选（之后可重新运行 `/init` 重新扫描）。

遵守 CLAUDE.md 中的数据模型约定（5 层 schema 前缀、`batch_number` 连接键、参数化 SQL）。
