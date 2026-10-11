from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field, field_validator

UTC = timezone.utc
SH = ZoneInfo('Asia/Shanghai')
Kind = Literal['etl', 'backup', 'monitor', 'sync']

class Task(BaseModel):
    model_config = ConfigDict(extra='forbid')
    key: str = Field(pattern=r'^[a-z0-9][a-z0-9_-]{0,63}$')
    name: str
    kind: Kind
    project: str
    scope: str = 'Linux / 正式'
    host: str = '172.19.0.105'
    environment: str = 'production'
    enabled: bool | None = True
    times: list[str] = []
    grace_minutes: int = 5
    timeout_minutes: int = 30
    unit: str | None = None
    timer: str | None = None
    adapter: Literal['systemd', 'lucullus', 'rd_lims', 'training', 'unconnected']
    db_source: Literal['rd', 'gmp'] | None = None
    ledger: Literal['meta', 'vicell', 'nova'] | None = None
    jobs: list[str] = []
    instance: str | None = None
    log_dir: str | None = None
    log_pattern: str = '*.log'
    backup_dir: str | None = None
    backup_pattern: str = '*.dump'
    watermark_path: str | None = None
    notes: list[str] = []
    producer_users: list[str] = []

    def occurrences(self, now: datetime, days: int = 1) -> list[datetime]:
        local = now.astimezone(SH)
        return sorted(datetime.combine((local - timedelta(days=d)).date(), datetime.strptime(t, '%H:%M').time(), SH).astimezone(UTC)
                      for d in range(days + 1) for t in self.times)

class Run(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    task_key: str
    start: datetime
    finish: datetime | None = None
    status: Literal['success', 'partial_failed', 'failed', 'running', 'unknown']
    message: str = ''
    duration_seconds: float | None = None
    rows: int | None = None
    files: int | None = None
    size_bytes: int | None = None
    children: list[dict] = []
    evidence: list[dict] = []
    integrity: str | None = None
    restore: str | None = None
    verification: dict | None = None
    source_kind: str = 'unknown'

    @field_validator('start','finish')
    @classmethod
    def utc_time(cls,value):
        if value is None:return value
        if value.tzinfo is None:raise ValueError('运行时间必须带已核实的时区')
        return value.astimezone(UTC)

class Observation(BaseModel):
    task: Task
    observed_at: datetime
    collection_status: str
    state: Literal['success', 'failed', 'warning', 'unknown', 'disabled'] = 'unknown'
    label: str = '当前未知'
    reasons: list[str] = []
    last_run: Run | None = None
    next_at: datetime | None = None
    gaps: list[str] = []

class Snapshot(BaseModel):
    id: str
    collected_at: datetime
    trigger: str
    tasks: list[Observation]
    mode: str = 'production'
    inventory_version: str = '2026-10-10'
    rule_version: str = 'v1'
    gaps: list[str] = []

class Event(BaseModel):
    model_config = ConfigDict(extra='forbid')
    event_id: str = Field(pattern=r'^[a-zA-Z0-9_.:-]{1,160}$')
    task_key: str = Field(pattern=r'^[a-z0-9][a-z0-9_-]{0,63}$')
    # Events wake the collector; producer's alleged result is deliberately excluded.
    invocation_id: str | None = Field(None, max_length=160)
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def assess(task: Task, runs: list[Run], now: datetime, gaps: list[str] | None = None) -> Observation:
    gaps = gaps or []
    runs = sorted(runs, key=lambda r: r.start, reverse=True)
    last = runs[0] if runs else None
    next_at = next((t for t in task.occurrences(now) if t > now), None)
    if not next_at and task.times:
        next_at = min(t + timedelta(days=1) for t in task.occurrences(now, 0))
    o = Observation(task=task, observed_at=now, collection_status='ok', last_run=last, next_at=next_at, gaps=gaps)
    if gaps:
        o.collection_status = 'unavailable'; o.label = '当前未知'; o.reasons = list(gaps)
        if last and last.status=='failed':o.reasons.insert(0,'最后已知失败，当前未核实')
        return o
    if task.enabled is False:
        o.state = 'disabled'; o.label = '已停用'; return o
    if task.enabled is None:
        o.label = '计划尚未核实'; o.reasons = ['调度或开关未知']; return o
    grace = timedelta(minutes=task.grace_minutes)
    due = [t for t in task.occurrences(now) if t + grace < now or
           (t <= now and any(t <= r.start <= min(t + grace, now) for r in runs))]
    # A manual recent success must not satisfy a different scheduled window.
    if due:
        expected = due[-1]
        matches = [r for r in runs if expected <= r.start <= expected + grace]
        if not matches:
            o.state = 'failed'; o.label = '未按计划启动'; o.reasons = ['该计划窗口无启动证据']; return o
        scheduled = max(matches, key=lambda r:r.start)
        if scheduled.status in ('failed','partial_failed') and last is not scheduled:
            o.state = 'failed';o.label = '最近计划执行异常';o.reasons = ['后续手工成功不能代替该计划窗口的失败'];return o
    if not last:
        o.label = '尚无运行记录'; return o
    seconds = (last.finish or now).timestamp() - last.start.timestamp()
    if last.status == 'running':
        if seconds > task.timeout_minutes * 60:
            o.state = 'failed'; o.label = '运行时间过长'; o.reasons = ['已超过耗时上限，尚未结束']
        else:
            o.label = '本次尚未完成'
        return o
    if last.status == 'unknown':
        o.label = '当前未知'; o.reasons = ['结束证据不足或冲突']; return o
    if last.status == 'failed':
        o.state = 'failed'; o.label = '执行失败'; o.reasons = [last.message or '任务执行失败']; return o
    warnings = []
    if last.status == 'partial_failed': warnings.append('部分步骤或记录失败')
    if last.message: warnings.append(last.message)
    if seconds > task.timeout_minutes * 60: warnings.append('已完成，耗时偏长')
    if task.kind == 'backup':
        if last.verification:
            v = last.verification
            if v.get('status') == 'unknown':
                o.label='验证结果未知';o.reasons=['备份执行结果已保留，验证证据不可读或不匹配'];return o
            if v.get('status') == 'failed':
                o.state='failed';o.label='备份完成，验证失败';o.reasons=[v.get('reason','恢复验证失败')];return o
            if v.get('cleanup_status') == 'failed':warnings.append('临时环境清理异常')
            if v.get('status') in ('pending','running','incomplete'):warnings.append(v.get('reason','验证尚未完成'))
        if last.integrity != 'verified': warnings.append('完整性验证不足')
        if last.restore != 'verified': warnings.append('恢复未验证')
    o.state = 'warning' if warnings else 'success'
    o.label = ('备份完成，验证不足' if task.kind == 'backup' and warnings else '执行完成，有提醒') if warnings else '执行成功'
    if task.key=='mdm-backup' and not warnings and last.verification:
        o.label='备份完成，恢复验证通过'
    o.reasons = warnings
    return o


def current_view(snapshot: Snapshot, now: datetime) -> Snapshot:
    """Overdue updates become unknown even when the collector itself has disappeared."""
    if snapshot.mode=='demo' or snapshot.trigger=='none':return snapshot
    copy=snapshot.model_copy(deep=True)
    local=now.astimezone(SH)
    safety=datetime.combine(local.date(),datetime.strptime('07:00','%H:%M').time(),SH).astimezone(UTC)
    # 07:05 is the deadline for the 07:00 check, not a second required check.
    if now<safety+timedelta(minutes=5):safety-=timedelta(days=1)
    for item in copy.tasks:
        if item.task.enabled is False:continue
        ends=[]
        run=item.last_run
        for planned in item.task.occurrences(now):
            deadline=planned+timedelta(minutes=item.task.timeout_minutes+item.task.grace_minutes)
            if deadline>=now:continue
            # An observed terminal result already covers this scheduled window.
            # Retain success, warning or failure; never reuse it for the next run.
            covered=(item.collection_status=='ok' and run is not None
                     and run.status in ('success','partial_failed','failed')
                     and planned<=run.start<=planned+timedelta(minutes=item.task.grace_minutes)
                     and run.finish is not None and run.start<=run.finish<=item.observed_at)
            if not covered:ends.append(deadline)
        cutoff=max([safety]+ends)
        if item.observed_at<cutoff:
            item.state='unknown';item.label='更新逾期，当前未核实';item.collection_status='stale'
            item.reasons=['上次观测之后缺少应有更新，不能确认当前执行结果']
            if item.last_run and item.last_run.status=='failed':item.reasons.insert(0,'最后已知失败，当前未核实')
    return copy
