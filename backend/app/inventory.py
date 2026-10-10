import json
from pathlib import Path
from .domain import Task

def load_tasks(path: Path) -> list[Task]:
    tasks=[Task.model_validate(x) for x in json.loads(path.read_text())]
    if len({t.key for t in tasks})!=len(tasks):raise ValueError('重复任务标识')
    for t in tasks:
        if t.unit and not t.timer:raise ValueError('systemd任务必须登记timer')
    return tasks
