#!/usr/bin/env python3
"""One-time 2026-11-05 release. Changes timers, never executes source ETL."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def properties(unit, *names):
    raw = command('systemctl', 'show', unit, '--property=' + ','.join(names))
    return dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)


def calendars(path):
    return re.findall(r'^OnCalendar=\*-\*-\* (\d\d:\d\d):00$', path.read_text(), re.M)


def conditions(name):
    # systemctl prints even an empty complex array as "[unprintable]" on systemd 255.
    unit_path = '/org/freedesktop/systemd1/unit/' + name.replace('-', '_2d') + '_2eservice'
    return json.loads(command('busctl', '--json=short', 'get-property',
                             'org.freedesktop.systemd1', unit_path,
                             'org.freedesktop.systemd1.Unit', 'Conditions'))['data']


def main():
    if os.geteuid() != 0 or len(sys.argv) != 4:
        raise SystemExit('Usage via sudo: deploy_night_etl_schedule.py MONITOR_SHA NOVA_SHA VICELL_SHA')
    now = datetime.now(ZoneInfo('Asia/Shanghai'))
    # The tested guard is for adding a past slot before today's next original slot.
    if now.strftime('%Y-%m-%d') != '2026-11-05' or not 7 <= now.hour < 11:
        raise SystemExit('Outside the reviewed 2026-11-05 07:00–11:00 release window')
    roots = [Path('/opt/cmc-platform-monitor'), Path('/opt/nova-etl'), Path('/opt/vicell-etl')]
    for root, sha in zip(roots, sys.argv[1:]):
        assert re.fullmatch('[0-9a-f]{40}', sha)
        assert command('sudo', '-u', 'prometheus', 'git', '-C', str(root), 'rev-parse', 'HEAD') == sha
        assert not command('sudo', '-u', 'prometheus', 'git', '-C', str(root), 'status', '--porcelain', '--untracked-files=no')
    tasks = json.loads((roots[0] / 'config/tasks.json').read_text())
    for task in tasks:
        if task['key'] in ('nova', 'vicell'):
            assert task['times'] == ['02:20', '12:05', '16:20']
            assert task['slot_effective_dates'] == {'02:20': '2026-11-06'}
    names = ['nova-etl', 'vicell-etl']
    observed = ['ExecMainStartTimestampMonotonic', 'ExecMainExitTimestampMonotonic', 'ExecMainPID']
    before = {name: properties(name + '.service', *observed) for name in names}
    original_conditions = {name: conditions(name) for name in names}
    catch_up = []
    for name, root in zip(names, roots[1:]):
        assert properties(name + '.service', 'ActiveState')['ActiveState'] == 'inactive'
        assert properties(name + '.timer', 'ActiveState')['ActiveState'] == 'active'
        assert calendars(Path('/etc/systemd/system') / (name + '.timer')) == ['12:05', '16:20']
        assert calendars(root / 'deploy' / (name + '.timer')) == ['02:20', '12:05', '16:20']
        last = properties(name + '.timer', 'LastTriggerUSec')['LastTriggerUSec']
        stamp = re.search(r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d', last)
        assert stamp, 'Missing actual timer trigger history'
        if stamp[0] < '2026-11-05 02:20:00':
            catch_up.append(name)
    backup = Path('/var/backups/cmc-platform-monitor') / now.strftime('night-etl-%Y%m%d-%H%M%S')
    backup.mkdir(mode=0o700, parents=True, exist_ok=False)
    (backup / 'before.json').write_text(json.dumps(before, indent=2) + '\n')
    guards = [Path('/run/systemd/system') / (n + '.service.d') / '90-night-schedule-rollout.conf' for n in names]
    hold = Path('/run/cmc-night-schedule-rollout.hold')
    assert not hold.exists() and not any(g.exists() for g in guards)
    for name in names:
        shutil.copy2(Path('/etc/systemd/system') / (name + '.timer'), backup / (name + '.timer'))
    completed = False
    command('systemctl', 'stop', 'cmc-platform-monitor-collector.service')
    try:
        hold.touch(mode=0o600)
        for guard in guards:
            guard.parent.mkdir(exist_ok=True)
            guard.write_text('[Unit]\nConditionPathExists=!' + str(hold) + '\n')
        for name, root in zip(names, roots[1:]):
            target = Path('/etc/systemd/system') / (name + '.timer')
            shutil.copyfile(root / 'deploy' / (name + '.timer'), target)
            target.chmod(0o644)
        command('systemd-analyze', 'verify', *(str(Path('/etc/systemd/system') / (n + '.timer')) for n in names))
        command('systemctl', 'daemon-reload')
        # Any timer catch-up is skipped by the explicit condition, not reported as ETL success.
        for _ in range(20):
            if all(properties(n + '.service', 'ConditionResult')['ConditionResult'] == 'no' for n in catch_up):
                break
            time.sleep(0.5)
        else:
            raise RuntimeError('Expected guarded catch-up was not observed; restore timers for review')
        assert before == {n: properties(n + '.service', *observed) for n in names}
        for guard in guards:
            guard.unlink()
        hold.unlink()
        command('systemctl', 'daemon-reload')
        time.sleep(2)
        assert before == {n: properties(n + '.service', *observed) for n in names}
        for name in names:
            state = properties(name + '.timer', 'NextElapseUSecRealtime', 'RandomizedDelayUSec', 'Persistent', 'ActiveState')
            assert '2026-11-05 12:05:00' in state['NextElapseUSecRealtime']
            assert state['RandomizedDelayUSec'] == '0' and state['Persistent'] == 'yes' and state['ActiveState'] == 'active'
            assert conditions(name) == original_conditions[name]
            print(name, json.dumps(state))
        completed = True
        print('PASS: timer calendars installed; source ETL execution timestamps/PIDs unchanged; guards removed')
        print('BACKUP', backup)
    finally:
        if not completed:
            for name in names:
                shutil.copy2(backup / (name + '.timer'), Path('/etc/systemd/system') / (name + '.timer'))
        for guard in guards:
            if guard.exists():
                guard.unlink()
        if hold.exists():
            hold.unlink()
        command('systemctl', 'daemon-reload')
        command('systemctl', 'restart', 'cmc-platform-monitor-api.service', 'cmc-platform-monitor-collector.service')
    (backup / 'result.json').write_text(json.dumps({'completed': completed, 'source_execution': before}, indent=2) + '\n')


if __name__ == '__main__':
    main()
