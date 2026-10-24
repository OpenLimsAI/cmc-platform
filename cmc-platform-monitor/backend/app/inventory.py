import json
from pathlib import Path
from .domain import Task

def load_tasks(path: Path) -> list[Task]:
    tasks=[Task.model_validate(x) for x in json.loads(path.read_text())]
    if len({t.key for t in tasks})!=len(tasks):raise ValueError('重复任务标识')
    for t in tasks:
        if t.unit and not t.timer:raise ValueError('systemd任务必须登记timer')
        if (t.adapter=='archive_device') != bool(t.archive_device):raise ValueError('设备归档身份不完整')
        if t.slot_timeouts and (set(t.slot_timeouts)!=set(t.times) or any(v<1 or v>1440 for v in t.slot_timeouts.values())):
            raise ValueError('逐计划耗时上限不完整或无效')
    return tasks
