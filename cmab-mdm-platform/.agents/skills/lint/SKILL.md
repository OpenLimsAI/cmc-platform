---
name: lint
description: Run backend (ruff + mypy) and frontend (eslint) lint for this repo and report findings grouped by rule, distinguishing real bugs from pure style. Use when the user asks to check lint, lint errors, or code-quality warnings.
---

# Lint 排查

本项目工具链全在 Docker 容器内,通过 docker exec 调用(不要在宿主机直接跑 ruff/eslint)。

## 步骤

1. **后端 ruff** —— 先看统计,再按需展开:
   ```bash
   docker exec cmab-mdm-backend ruff check . --statistics
   ```
   需要定位某规则时:`docker exec cmab-mdm-backend ruff check . --select <CODE>`

2. **后端 mypy**(可选,较慢):
   ```bash
   docker exec cmab-mdm-backend mypy app
   ```

3. **前端 eslint**:
   ```bash
   docker exec -e CI=1 cmab-mdm-frontend pnpm lint
   ```

## 报告方式

- 按规则码归类,给出每类数量与可自动修复数(`ruff check . --fix` 能修哪些)。
- **区分真 bug 与纯风格**:对 F821(未定义名)、F841(未用变量)、B 类等可能是真问题的,逐条读实际代码复核——很多是字符串注解/运行时局部导入造成的误报,不要直接当 bug。结论先行,告诉用户哪些值得改、哪些是风格噪音。
- 不要擅自 `--fix` 或改代码;先报告,由用户决定是否修。

## 修复(用户确认后)

- 自动项:`docker exec cmab-mdm-backend ruff check . --fix`
- 改完验证:重跑对应 `--select`,并 `docker exec cmab-mdm-backend python -c "import app.main"` 冒烟,改了测试就 `make test-be`。
- 本项目无 `ruff format`,不要引入格式化器。
