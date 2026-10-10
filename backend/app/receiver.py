import asyncio
import json
import os
import pwd
import socket
import struct
from .domain import Event

async def receive(reader,writer,tasks,store):
    try:
        sock=writer.get_extra_info('socket')
        if not hasattr(socket,'SO_PEERCRED'):raise PermissionError('requires Linux peer credentials')
        _,uid,_=struct.unpack('3i',sock.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
        user=pwd.getpwuid(uid).pw_name
        raw=await asyncio.wait_for(reader.readline(),2)
        if len(raw)>4096 or not raw.endswith(b'\n'):raise ValueError('invalid event size')
        event=Event.model_validate_json(raw)
        task=tasks.get(event.task_key)
        if not task or user not in task.producer_users:raise PermissionError('producer not registered')
        payload={'trigger':'event','task_key':task.key,'producer_uid':uid,'invocation_id':event.invocation_id}
        ident=f'event:{uid}:{event.event_id}'
        await store.enqueue(payload,ident)
        # ACK after commit. Producer is never asked to wait for collection.
        writer.write(b'{"accepted":true}\n');await writer.drain()
    except Exception:
        writer.write(b'{"accepted":false}\n')
        try:await writer.drain()
        except Exception:pass
    finally:
        writer.close();await writer.wait_closed()

async def serve(settings,tasks,store):
    if not hasattr(socket,'SO_PEERCRED'):raise RuntimeError('生产事件接收器仅支持Linux身份校验')
    path=settings.socket_path
    if path.exists():path.unlink()  # singleton lock obtained before this call
    server=await asyncio.start_unix_server(lambda r,w:receive(r,w,{t.key:t for t in tasks},store),path=str(path),limit=4096)
    os.chmod(path,0o660)
    return server
