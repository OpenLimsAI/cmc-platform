# -*- coding: utf-8 -*-
"""pytest 配置：让回归测试能导入旧 Streamlit 工具的"原始统计函数"，用于新旧对齐。

难点：旧工具的 analytics/__init__.py、components/__init__.py 会 import streamlit/plotly
（看板/导出层），而我们只想要纯统计子模块（stat_core / equivalence_test / utils）。

做法：在导入前，把 `analytics` 与 `components` 预注册为"命名空间包"（带 __path__、空 __init__），
这样 `import analytics.stat_core` 只加载该子模块文件，**跳过真实 __init__.py 的重依赖**。
子模块本身只依赖 scipy/statsmodels/pandas/numpy/yaml（后端 venv 已具备）。

旧工具路径可用环境变量 QAP_OLD_TOOL_PATH 覆盖；缺失时回归测试会被 skip。
"""
import os
import sys
import types
from pathlib import Path

_DEFAULT_OLD = Path(__file__).resolve().parents[3] / "quality_analysis_dashboard"
OLD_TOOL_PATH = Path(os.environ.get("QAP_OLD_TOOL_PATH", str(_DEFAULT_OLD)))

if OLD_TOOL_PATH.is_dir():
    p = str(OLD_TOOL_PATH)
    # 追加到末尾（不能插到最前）：旧工具根目录有 app.py，会遮蔽我们的 app 包。
    # 放末尾既能 import analytics/components 子模块，又让本项目 app 包优先。
    if p not in sys.path:
        sys.path.append(p)

    # 预注册命名空间包，绕过重依赖的真实 __init__.py
    for pkg in ("analytics", "components"):
        if pkg not in sys.modules:
            mod = types.ModuleType(pkg)
            mod.__path__ = [str(OLD_TOOL_PATH / pkg)]  # 使其成为包，可加载子模块
            sys.modules[pkg] = mod
