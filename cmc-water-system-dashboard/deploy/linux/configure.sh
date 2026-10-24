#!/bin/bash
# Reuse protected local configurations; never print credentials.
set -euo pipefail
cd /opt/cmc-water-system-dashboard
export PATH="$HOME/.local/bin:$PATH"
/opt/qc-lims-etl/.venv/bin/python - <<'PY'
from pathlib import Path
from dotenv import dotenv_values
from urllib.parse import urlparse
import json
out=Path('backend/.env')
if out.exists():
    raise SystemExit('backend/.env 已存在，保留原配置；请核对后使用部署入口')
etl=dotenv_values('/opt/qc-lims-etl/.env')
mdm=dotenv_values('/opt/cmab-mdm-platform/backend/.env')
dsn=etl.get('DASHBOARD_ANALYTICS_DSN')
if not dsn or urlparse(dsn).username!='lims_reader' or urlparse(dsn).path!='/cmc_analytics':
    raise SystemExit('缺少经核实的只读分析库连接，未创建配置')
font=Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
if not font.exists():
    raise SystemExit('缺少 Noto CJK 中文字体，先安装官方 fonts-noto-cjk 包')
key=mdm.get('SECRET_KEY');algorithm=mdm.get('JWT_ALGORITHM','HS256')
if algorithm!='HS256' or not key or len(key)<32:
    raise SystemExit('MDM验签设置需人工核对，不创建不完整配置')
values={'APP_ENV':'linux','DATABASE_URL':dsn.replace('postgresql://','postgresql+asyncpg://'),'JWT_ALGORITHM':algorithm,'JWT_VERIFY_KEY':key,'WATER_VIEW_ROLES':'CMC_WATER_VIEWER,CMC_WATER_EXPORTER,SYS_ADMIN','WATER_EXPORT_ROLES':'CMC_WATER_EXPORTER,SYS_ADMIN','PNG_FONT_PATH':str(font),'MAX_ROWS':'100000','STAGING_DATA_ORIGIN':'oracle_etl'}
# Exclusive creation with 0600 from the beginning; quoted dotenv values preserve literals.
import os
fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:
    for k,v in values.items():
        f.write(k+'='+json.dumps(v,ensure_ascii=False)+'\n')
print('已生成受保护配置；未输出凭据')
PY
