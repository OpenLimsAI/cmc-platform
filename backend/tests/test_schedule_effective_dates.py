from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from app.domain import SH, UTC, Run, Snapshot, Task, assess, current_view
from app.engine import Engine
from app.store import MemoryStore
from test_monitor import config


def at(day, hour, minute=0):
    return datetime(2026, 11, day, hour, minute, tzinfo=SH)


def scheduled_task(**updates):
    return Task(**(dict(key='nova', name='Nova', kind='etl', project='rd-nova-etl',
                       adapter='systemd', times=['02:20', '12:05', '16:20'],
                       slot_effective_dates={'02:20': '2026-11-06'}) | updates))


def completed(start):
    return Run(id=start.isoformat(), task_key='nova', start=start,
               finish=start + timedelta(seconds=30), status='success')


def test_new_slot_is_not_applied_to_the_prior_week():
    planned = scheduled_task().occurrences(at(6, 7), 7)
    nights = [x.astimezone(SH) for x in planned if x.astimezone(SH).hour == 2]
    assert nights == [at(6, 2, 20)]
    assert len(planned) == 17  # Existing daytime slots retain their prior history.


@pytest.mark.parametrize('now,expected', [(at(5, 10), at(5, 12, 5)),
                                        (at(5, 17), at(6, 2, 20)),
                                        (at(6, 2, 20), at(6, 12, 5))])
def test_next_slot_uses_first_effective_date(now, expected):
    assert scheduled_task().next_occurrence(now) == expected


def test_future_only_slot_and_legacy_task():
    future = scheduled_task(times=['02:20'])
    assert future.next_occurrence(at(1, 7)) == at(6, 2, 20)
    assert future.occurrences(at(5, 7)) == []
    legacy = scheduled_task(slot_effective_dates={})
    assert at(5, 2, 20) in legacy.occurrences(at(5, 7))
    assert scheduled_task(times=[], slot_effective_dates={}).next_occurrence(at(5, 7)) is None
    with pytest.raises(ValidationError):
        scheduled_task(slot_effective_dates={'03:00': '2026-11-06'})


def test_no_false_failure_or_staleness_before_effective_date():
    observed = at(5, 7)
    item = assess(scheduled_task(), [completed(at(4, 16, 20))], observed)
    snapshot = Snapshot(id='prior', collected_at=observed, trigger='daily_safety', tasks=[item])
    assert item.state == 'success'
    assert current_view(snapshot, at(5, 10)).tasks[0].state == 'success'
    assert current_view(snapshot, at(6, 3)).tasks[0].state == 'unknown'


def test_effective_slot_must_run_and_observed_completion_stays_valid():
    task = scheduled_task()
    assert assess(task, [completed(at(5, 16, 20))], at(6, 7)).label == '未按计划启动'
    item = assess(task, [completed(at(6, 2, 20))], at(6, 7))
    snapshot = Snapshot(id='done', collected_at=at(6, 7), trigger='daily_safety', tasks=[item])
    assert current_view(snapshot, at(6, 10)).tasks[0].state == 'success'


async def test_collector_does_not_create_retroactive_missed_runs(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return at(6, 7).astimezone(tz or UTC)

    monkeypatch.setattr('app.engine.datetime', Clock)
    task = scheduled_task()
    store = MemoryStore()
    await store.publish(Snapshot(id='old', collected_at=at(1, 7), trigger='daily_safety', tasks=[]), [], [])

    class Reader:
        async def read(self, task, since, now):
            return [completed(x) for x in task.occurrences(now, 7)
                    if x < now and x.astimezone(SH).hour != 2], []

    snapshot = await Engine(config(), [task], store, Reader()).collect()
    missed = [x.start for x in store.runs.values() if x.source_kind == 'schedule']
    assert missed == [at(6, 2, 20)]
    assert snapshot.tasks[0].state == 'failed'
    assert snapshot.tasks[0].last_run.source_kind == 'schedule'
