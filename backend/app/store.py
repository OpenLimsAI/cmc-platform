import asyncio
import json
from copy import deepcopy
from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy import DateTime, String, select, delete, update, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from .domain import Snapshot, Run, UTC

class Base(DeclarativeBase): pass
class SnapshotRow(Base):
    __tablename__ = 'collection_batch'
    __table_args__ = {'schema': 'ops_monitor'}
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[dict] = mapped_column(JSONB)
class RunRow(Base):
    __tablename__ = 'run_reference'
    __table_args__ = {'schema': 'ops_monitor'}
    id: Mapped[str] = mapped_column(String(240), primary_key=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    task_key: Mapped[str] = mapped_column(String(64), index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[dict] = mapped_column(JSONB)
class AuditRow(Base):
    __tablename__ = 'access_audit_log'
    __table_args__ = {'schema': 'ops_monitor'}
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[dict] = mapped_column(JSONB)
class UpdateRow(Base):
    __tablename__ = 'update_event'
    __table_args__ = {'schema': 'ops_monitor'}
    id: Mapped[str] = mapped_column(String(240), primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    lease_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JSONB)
    snapshot_id: Mapped[str | None] = mapped_column(String(36))

class MemoryStore:
    """Explicit isolated demo/test only. Production never silently falls back here."""
    def __init__(self):
        self.snapshots = {}; self.runs = {}; self.versions = []; self.updates = {}; self.audits = []
        self.lock = asyncio.Lock()
    async def ping(self): pass
    async def close(self): pass
    async def latest(self, sid=None):
        if sid: return self.snapshots.get(sid)
        return max(self.snapshots.values(), key=lambda x: x.collected_at, default=None)
    async def monitoring_started_at(self):
        return min((x.collected_at for x in self.snapshots.values()),default=None)
    async def publish(self, snap, runs, ids):
        async with self.lock:
            self.snapshots[snap.id] = snap
            for r in runs:
                self.runs[r.id] = r
                self.versions.append((snap.collected_at, r.model_copy(deep=True)))
            for i in ids:
                self.updates[i].update(status='done', snapshot_id=snap.id)
    async def history(self, key, start, end, offset=0, limit=100):
        versions = {}
        for observed, run in sorted(self.versions, key=lambda x:x[0]):
            if observed < end: versions[run.id] = run
        floor=await self.monitoring_started_at()
        rows = sorted((r for r in versions.values() if r.task_key == key and start <= r.start < end and
                       (r.source_kind!='schedule' or (floor is not None and r.start>=floor))), key=lambda r: (r.start,r.id), reverse=True)
        return rows[offset:offset+limit], len(rows)
    async def audit(self, entry): self.audits.append(deepcopy(entry))
    async def enqueue(self, payload, event_id=None):
        async with self.lock:
            i = event_id or str(uuid4())
            if i in self.updates:
                if self.updates[i]['payload'].get('task_key') != payload.get('task_key'): raise ValueError('event identity conflict')
                return i
            self.updates[i] = {'id': i, 'at': datetime.now(UTC), 'status':'pending','payload':payload,'snapshot_id':None}
            return i
    async def get_update(self, i): return self.updates.get(i)
    async def pending(self): return sum(u['status'] != 'done' for u in self.updates.values())
    async def claim(self):
        async with self.lock:
            rows = [r for r in self.updates.values() if r['status']=='pending'][:100]
            for r in rows: r['status']='processing'
            return deepcopy(rows)
    async def requeue(self, ids):
        for i in ids: self.updates[i]['status']='pending'
    async def recover(self):
        for u in self.updates.values():
            if u['status']=='processing': u['status']='pending'
    async def prune(self): pass

class PostgresStore:
    def __init__(self, url):
        self.engine = create_async_engine(url, pool_pre_ping=True, connect_args={'timeout':5,'command_timeout':5})
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
    async def ping(self):
        # Never create schema/tables at application startup.
        async with self.sessions() as s: await s.execute(select(SnapshotRow.id).limit(1))
    async def close(self): await self.engine.dispose()
    async def latest(self, sid=None):
        async with self.sessions() as s:
            q=select(SnapshotRow).where(SnapshotRow.id==sid) if sid else select(SnapshotRow).order_by(SnapshotRow.at.desc()).limit(1)
            row=(await s.execute(q)).scalar_one_or_none()
            return Snapshot.model_validate(row.payload) if row else None
    async def monitoring_started_at(self):
        async with self.sessions() as s:
            return (await s.execute(select(func.min(SnapshotRow.at)))).scalar_one()
    async def publish(self, snap, runs, ids):
        from sqlalchemy.dialects.postgresql import insert
        async with self.sessions.begin() as s:
            s.add(SnapshotRow(id=snap.id, at=snap.collected_at, payload=snap.model_dump(mode='json')))
            for r in runs:
                # Append observed versions: later terminal evidence cannot rewrite old views.
                stmt=insert(RunRow).values(id=r.id,observed_at=snap.collected_at,task_key=r.task_key,at=r.start,payload=r.model_dump(mode='json'))
                await s.execute(stmt.on_conflict_do_nothing(index_elements=['id','observed_at']))
            if ids: await s.execute(update(UpdateRow).where(UpdateRow.id.in_(ids)).values(status='done', snapshot_id=snap.id))
    async def history(self, key, start, end, offset=0, limit=100):
        async with self.sessions() as s:
            floor=select(func.min(SnapshotRow.at)).scalar_subquery()
            valid_schedule=(RunRow.payload['source_kind'].astext!='schedule') | (RunRow.at>=floor)
            versions=select(RunRow.id,RunRow.at,RunRow.payload).where(RunRow.task_key==key,RunRow.at>=start,RunRow.at<end,RunRow.observed_at<end,valid_schedule).distinct(RunRow.id).order_by(RunRow.id,RunRow.observed_at.desc()).subquery()
            rows=(await s.execute(select(versions.c.payload).order_by(versions.c.at.desc(),versions.c.id.desc()).offset(offset).limit(limit))).scalars().all()
            total=(await s.execute(select(func.count()).select_from(versions))).scalar_one()
            return [Run.model_validate(r) for r in rows],total
    async def audit(self, entry):
        async with self.sessions.begin() as s: s.add(AuditRow(id=str(uuid4()),at=datetime.now(UTC),payload=entry))
    async def enqueue(self, payload, event_id=None):
        from sqlalchemy.dialects.postgresql import insert
        i=event_id or str(uuid4())
        async with self.sessions.begin() as s:
            stmt=insert(UpdateRow).values(id=i,at=datetime.now(UTC),status='pending',payload=payload).on_conflict_do_nothing(index_elements=['id'])
            await s.execute(stmt)
            row=await s.get(UpdateRow,i)
            if row.payload.get('task_key') != payload.get('task_key'): raise ValueError('event identity conflict')
        return i
    async def get_update(self,i):
        async with self.sessions() as s:
            r=await s.get(UpdateRow,i)
            return {'id':r.id,'at':r.at,'status':r.status,'snapshot_id':r.snapshot_id,'payload':r.payload} if r else None
    async def pending(self):
        async with self.sessions() as s:
            return (await s.execute(select(func.count()).select_from(UpdateRow).where(UpdateRow.status!='done'))).scalar_one()
    async def claim(self):
        async with self.sessions.begin() as s:
            rows=(await s.execute(select(UpdateRow).where(UpdateRow.status=='pending').order_by(UpdateRow.at).limit(100).with_for_update(skip_locked=True))).scalars().all()
            for r in rows: r.status='processing'; r.lease_at=datetime.now(UTC)
            return [{'id':r.id,'payload':r.payload} for r in rows]
    async def requeue(self,ids):
        async with self.sessions.begin() as s:
            await s.execute(update(UpdateRow).where(UpdateRow.id.in_(ids)).values(status='pending',lease_at=None))
    async def recover(self):
        # Singleton collector is enforced by a process lock. Startup recovers its interrupted batch.
        async with self.sessions.begin() as s: await s.execute(update(UpdateRow).where(UpdateRow.status=='processing').values(status='pending',lease_at=None))
    async def prune(self):
        async with self.sessions.begin() as s:
            for cls,days in ((SnapshotRow,90),(RunRow,90),(UpdateRow,90),(AuditRow,180)):
                q=delete(cls).where(cls.at < datetime.now(UTC)-timedelta(days=days))
                if cls is UpdateRow: q=q.where(cls.status=='done')
                await s.execute(q)
