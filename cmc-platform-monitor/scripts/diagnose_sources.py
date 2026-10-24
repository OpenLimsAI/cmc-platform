#!/usr/bin/env python3
"""Bounded read-only diagnostics under the actual collector identity; no store writes."""
import asyncio
from datetime import datetime,timedelta
import time
from app.config import Settings
from app.domain import UTC
from app.inventory import load_tasks
from app.security import redact
from app.sources import Reader

async def main():
    settings=Settings(_env_file=None,component='reader');reader=Reader(settings)
    now=datetime.now(UTC)
    try:
        for task in load_tasks(settings.inventory_path):
            if task.enabled is False or task.adapter=='unconnected':continue
            start=time.monotonic()
            try:
                rows,gaps=await asyncio.wait_for(reader.read(task,now-timedelta(days=7),now),10)
                print(task.key,'records',len(rows),'gaps',gaps,'seconds',round(time.monotonic()-start,2),flush=True)
            except Exception as e:
                print(task.key,type(e).__name__,redact(str(e))[:300],'seconds',round(time.monotonic()-start,2),flush=True)
    finally:await reader.close()

if __name__=='__main__':asyncio.run(main())
