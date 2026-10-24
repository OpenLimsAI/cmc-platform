import importlib.util
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('journal_bridge',Path(__file__).parents[2]/'scripts/journal_bridge.py')
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)

def test_registered_unit_only_and_bounded_dates():
    now=datetime.now(timezone.utc)
    valid={'unit':'nova-etl.service','since':(now-timedelta(days=7)).isoformat(),'until':now.isoformat(),'cursor':None}
    assert bridge.arguments(valid,now)[0]=='/usr/bin/journalctl'
    for change in [{'unit':'ssh.service'},{'since':(now-timedelta(days=33)).isoformat()},{'until':(now+timedelta(minutes=2)).isoformat()},{'cursor':'x\n--file=/etc/shadow'},{'since':'2026-10-09T01:00:00'}]:
        with pytest.raises(ValueError):bridge.arguments(valid|change,now)

def test_program_secret_removed_but_invocation_and_page_retained():
    rows=[{'MESSAGE':'password=private Starting arbitrary program','_PID':'100','__CURSOR':'s=1','__REALTIME_TIMESTAMP':'1','UNIT':'nova-etl.service','SECRET':'private'},
          {'MESSAGE':'[time] <<< [night] vicell 完成 password=private','_PID':'200','__CURSOR':'s=2','__REALTIME_TIMESTAMP':'2'},
          {'MESSAGE':'Finished Nova ETL.','_PID':'1','__CURSOR':'s=3','__REALTIME_TIMESTAMP':'3'}]
    out=bridge.sanitize('\n'.join(json.dumps(x) for x in rows))
    assert 'private' not in out and 'SECRET' not in out
    cleaned=[json.loads(x) for x in out.splitlines()]
    assert len(cleaned)==3 and cleaned[0]['MESSAGE']=='[omitted]'
    assert cleaned[1]['MESSAGE']=='<<< [night] vicell 完成'
    assert cleaned[2]['MESSAGE']=='Finished Nova ETL.'
