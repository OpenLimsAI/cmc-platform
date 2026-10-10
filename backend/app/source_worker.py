"""Isolate filesystem/NAS reads so a stuck source cannot block other sources."""
import asyncio
import json
import sys
from .config import Settings
from .inventory import load_tasks
from .sources import Reader, dt

async def main():
    settings=Settings(_env_file=None,component='reader')
    if settings.mode!='production':raise RuntimeError('source reader refuses demo mode')
    tasks={t.key:t for t in load_tasks(settings.inventory_path)}
    reader=Reader(settings)
    try:
        runs,gaps=await reader.read(tasks[sys.argv[1]],dt(sys.argv[2]),dt(sys.argv[3]))
        result={'runs':[r.model_dump(mode='json') for r in runs],'gaps':gaps}
    except Exception:
        result={'runs':[],'gaps':['来源读取失败或证据覆盖不足，请检查受限采集日志与权限']}
    finally:
        await reader.close()
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':asyncio.run(main())
