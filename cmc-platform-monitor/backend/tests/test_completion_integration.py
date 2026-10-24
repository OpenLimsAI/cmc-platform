import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import socket
import struct

import pytest
from app import receiver
from app.store import MemoryStore
from test_monitor import task


@pytest.mark.parametrize('extra,allowed', [({},True),({'status':'success'},False)])
async def test_registered_sender_ack_after_enqueue_and_result_claim_rejected(monkeypatch,extra,allowed):
    class Sock:
        def getsockopt(self,*args):return struct.pack('3i',42,1000,1000)
    store=MemoryStore()
    class Writer:
        def __init__(self):self.data=b''
        def get_extra_info(self,name):return Sock()
        def write(self,data):
            if b'true' in data:assert store.updates # ACK only after persistence
            self.data+=data
        async def drain(self):pass
        def close(self):pass
        async def wait_closed(self):pass
    class Input:
        async def readline(self):return (json.dumps({'event_id':'e1','task_key':'example',**extra})+'\n').encode()
    monkeypatch.setattr(socket,'SO_PEERCRED',17,raising=False)
    monkeypatch.setattr(receiver.pwd,'getpwuid',lambda uid:SimpleNamespace(pw_name='prometheus'))
    for _ in range(2):
        writer=Writer()
        await receiver.receive(Input(),writer,{'example':task(producer_users=['prometheus'])},store)
        assert (b'true' in writer.data)==allowed
    assert len(store.updates)==int(allowed) # duplicate event does not create another request


@pytest.mark.parametrize('chunks,expected', [
    ([b'{"accepted":',b'true}\n'],True),
    ([b'{"accepted":false}\n'],False),
    ([b'x'*128],False),
    ([b'{"accepted":true}',b''],False),
])
def test_sender_handles_split_or_invalid_ack_with_fixed_bounds(monkeypatch,chunks,expected):
    path=Path(__file__).resolve().parents[2]/'scripts/notify_completion.py'
    spec=importlib.util.spec_from_file_location('completion_sender',path)
    sender=importlib.util.module_from_spec(spec);spec.loader.exec_module(sender)
    class Client:
        def __init__(self):self.chunks=list(chunks)
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def settimeout(self,value):assert 0<value<=2
        def connect(self,path):pass
        def sendall(self,data):
            payload=json.loads(data)
            assert set(payload)=={'task_key','event_id'}
            assert payload['task_key']=='qc-lims'
        def recv(self,limit):
            assert 0<limit<=128
            return self.chunks.pop(0)
    monkeypatch.setattr(sender.socket,'socket',lambda *args:Client())
    assert sender.notify('qc-lims')==expected
