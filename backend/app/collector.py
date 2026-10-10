import asyncio
import fcntl
from .config import Settings
from .inventory import load_tasks
from .store import PostgresStore
from .engine import Engine,WorkerReader,Coordinator
from .receiver import serve

async def main():
    settings=Settings(_env_file=None,component='collector')
    if settings.mode!='production':raise RuntimeError('collector refuses demo source reads')
    settings.socket_path.parent.mkdir(parents=True,exist_ok=True)
    lock=(settings.socket_path.parent/'collector.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    store=PostgresStore(settings.database_url.get_secret_value());await store.ping()
    tasks=load_tasks(settings.inventory_path)
    coordinator=Coordinator(Engine(settings,tasks,store,WorkerReader(settings)))
    server=await serve(settings,tasks,store)
    try:
        async with server:await coordinator.run()
    finally:
        await store.close();lock.close()
if __name__=='__main__':asyncio.run(main())
