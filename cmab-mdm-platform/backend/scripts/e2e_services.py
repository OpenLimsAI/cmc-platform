"""Approved five-client synthetic services; fixed official or explicit patched profile.

Only invoked after the owned empty environment and encrypted fixture handoff.
No existing databases, users, credentials or server configuration are accepted.
"""
import io
import json
import re
import secrets
import subprocess
import tarfile
import time
from contextlib import suppress
from pathlib import Path

from scripts.e2e_runtime import APP, LABEL, validate_fixture

ASSETS = Path(__file__).parent / 'e2e_assets'
V4 = 'casbin/casdoor@sha256:de091feff4f50f0749f870808f43e34ea28b3fd589c49d4d473c7b6502c67cd5'

def up(runtime):
    if runtime.manifest['phase'] != 'fixture-ready' or runtime.pm_root is None:
        raise ValueError('Requires a prepared owned run, new fixture and explicit local PM checkout')
    if not (runtime.pm_root / 'backend/app/main.py').is_file():
        raise ValueError('PM checkout is not the expected source tree')
    image = getattr(runtime, 'idp_image', V4)
    if image not in {V4, 'sha256:56e11171cfb2022215a46e2c55b15c9c5734162bdd2f058892cde29e356d42ca'}:
        raise ValueError('Only fixed official or approved restricted v11 images are allowed')
    runtime.verify()
    docker = runtime.docker
    checkpoint = runtime.checkpoint
    prefix = runtime.spec.run_id
    net = runtime.spec.internal
    unit = prefix + '-tools'
    pg = getattr(runtime, 'identity_pg_name', prefix + '-pg')
    out = runtime.spec.directory
    label = LABEL + '=' + prefix
    browser = json.loads(docker('exec', unit, 'cat', '/test-runtime/browser-fixture.json'))
    validate_fixture(browser)
    values = json.loads(docker('exec', unit, 'python', '-c', "import json,os;print(json.dumps({k:os.environ[k] for k in ['POSTGRES_PASSWORD','SECRET_KEY']}))"))
    password = values['POSTGRES_PASSWORD']
    clients = {name: secrets.token_urlsafe(32) for name in runtime.spec.client_names}
    organization = 'mdm-signing-synthetic'
    issuer = runtime.spec.origin('idp')
    public = runtime.spec.origin('mdm') + '/mdm'
    pm_origin, portal_origin = runtime.spec.origin('pm'), runtime.spec.origin('portal')
    runtime.manifest['phase'] = 'starting'
    runtime.save()
    build_ui(runtime)
    for database in ('casdoor_signing_e2e', 'pm_signing_e2e'):
        docker('exec', pg, 'createdb', '-U', 'cmab_app', database)
    docker('exec', '-e', 'TEST_DB=cmab_signing_e2e', unit, 'python', '-m', 'app.scripts.bootstrap_test_db')
    checkpoint('new_synthetic_databases_ready', databases=['casdoor_signing_e2e', 'cmab_signing_e2e', 'pm_signing_e2e'], storage='owned tmpfs', real_data_copied=False)
    callbacks = {'mdm-signing-login': public + '/api/v1/auth/oidc/callback', 'mdm-signing-proof': public + '/signature-callback', 'mdm-signing-pm-delegation': public + '/api/v1/auth/oidc/pm-callback', 'mdm-signing-pm': pm_origin + '/api/v1/auth/callback', 'mdm-signing-portal': portal_origin + '/api/v1/portal/callback'}
    apps = []
    for name, secret in clients.items():
        home = pm_origin if name == 'mdm-signing-pm' else portal_origin if name == 'mdm-signing-portal' else public
        backchannel = '' if name == 'mdm-signing-proof' else 'http://signing-backend:8001/api/v1/auth/backchannel-logout' if name in {'mdm-signing-pm', 'mdm-signing-portal'} else 'http://signing-backend:8000/api/v1/auth/oidc/backchannel-logout'
        apps.append({'owner': 'admin', 'name': name, 'displayName': 'Local synthetic ' + name, 'organization': organization, 'cert': 'synthetic-cert', 'homepageUrl': home, 'enablePassword': True, 'enableSignUp': False, 'disableSignin': False, 'clientId': name, 'clientSecret': secret, 'tags': ['dcr'], 'grantTypes': ['authorization_code'], 'redirectUris': [callbacks[name], home + '/login'], 'tokenFormat': 'JWT', 'tokenFields': [], 'expireInHours': 1, 'cookieExpireInHours': 1, 'enableSigninSession': True, 'enableAutoSignin': True, 'backchannelLogoutUri': backchannel, 'signinMethods': [{'name': 'Password', 'displayName': 'Password', 'rule': 'All'}]})
    if getattr(runtime, 'ordinary_pm_client', False):
        # Only a separately approved isolated fixture; never enabled by default.
        for application in apps:
            if application['name'] == 'mdm-signing-pm':
                application['tags'] = []
    users = [{'owner': organization, 'name': item['username'], 'id': 'synthetic-signing-' + key, 'type': 'normal-user', 'password': item['password'], 'displayName': 'Synthetic ' + key, 'email': key + '@example.com', 'tag': 'dcr', 'isAdmin': False, 'signupApplication': 'mdm-signing-portal'} for key, item in browser['users'].items()]
    if browser.get('mfaFixture') == 'credential-version-v1':
        # Explicit local test variant: one pre-enrolled actor and one actor who
        # must set up MFA. No real account/factor is imported or modified.
        seed = browser['users']['signer'].get('totpSecret', '')
        if not re.fullmatch(r'[A-Z2-7]{32}', seed):
            raise ValueError('Unexpected synthetic TOTP seed')
        for user in users:
            user['mfaItems'] = [{'name': 'app', 'rule': 'Required'}]
            if user['name'] == browser['users']['signer']['username']:
                user['totpSecret'] = seed
                user['preferredMfaType'] = 'app'
    items = [{'name': name, 'visible': True, 'viewRule': 'Self', 'modifyRule': 'Admin'} for name in ['Is forbidden', 'Is deleted']]
    init = {'organizations': [{'owner': 'admin', 'name': organization, 'displayName': 'Temporary synthetic MDM signing', 'passwordType': 'bcrypt', 'passwordOptions': ['AtLeast8'], 'languages': ['en'], 'isProfilePublic': False, 'accountItems': items}], 'applications': apps, 'users': users, 'roles': [{'owner': organization, 'name': role, 'displayName': 'Synthetic ' + role, 'isEnabled': True, 'users': [organization + '/' + browser['users'][key]['username']], 'roles': []} for role, key in [('cmc_lead', 'signer'), ('rd', 'other')]], 'certs': [{'owner': 'admin', 'name': 'synthetic-cert', 'displayName': 'Temporary synthetic key', 'scope': 'JWT', 'type': 'x509', 'cryptoAlgorithm': 'RS256', 'bitSize': 2048, 'expireInYears': 1}]}
    conf = (ASSETS / 'casdoor.conf.template').read_text(encoding='utf-8')
    values = {'httpport': '8000', 'runmode': 'prod', 'driverName': 'postgres', 'dataSourceName': json.dumps(f'user=cmab_app password={password} host=postgres port=5432 sslmode=disable dbname=casdoor_signing_e2e'), 'dbName': 'casdoor_signing_e2e', 'showSql': 'false', 'origin': json.dumps(issuer), 'originFrontend': '', 'staticBaseUrl': json.dumps(issuer), 'socks5Proxy': '', 'forceLanguage': '"en"', 'defaultLanguage': '"en"', 'defaultApplication': 'mdm-signing-login', 'initDataFile': '"/runtime/init.json"', 'initDataNewOnly': 'false', 'initAdminPassword': json.dumps(secrets.token_urlsafe(36)), 'logConfig': '{"adapter":"file","filename":"/runtime/casdoor.log","level":3,"maxdays":1}'}
    if getattr(runtime, 'identity_pg_host', None):
        values['dataSourceName'] = json.dumps(f'user=cmab_app password={password} host={runtime.identity_pg_host} port=5432 sslmode=disable dbname=casdoor_signing_e2e')
    self_logout_clients = getattr(runtime, 'dcr_self_logout_clients', ())
    if self_logout_clients:
        if set(self_logout_clients) != {'mdm-signing-login','mdm-signing-portal','mdm-signing-pm'} or len(self_logout_clients)!=3:
            raise ValueError('Only the three explicitly approved local self-logout clients are allowed')
        values['dcrSelfLogoutApplications'] = json.dumps(','.join(organization+'/'+name for name in sorted(self_logout_clients)))
    if getattr(runtime, 'approved_own_policy_v9', False):
        if set(self_logout_clients) != {'mdm-signing-login','mdm-signing-portal','mdm-signing-pm'}:
            raise ValueError('Scoped logout requires the original approved exact triple')
        values['openlimsSelfPolicyApplications'] = json.dumps(organization+'/mdm-signing-pm,'+organization+'/mdm-signing-portal')
        values['dcrSelfLogoutDeviceApplications'] = values['dcrSelfLogoutApplications']
        values['openlimsScopedLogout'] = 'true'
        values['openlimsSelfPolicyDelegationBindings'] = json.dumps(organization+'/mdm-signing-pm='+organization+'/mdm-signing-pm-delegation')
    configure_fixture = getattr(runtime, 'configure_identity_fixture', None)
    if configure_fixture:
        configure_fixture(init, values)
    for key, value in values.items():
        expression = '^' + re.escape(key) + '\\s*=.*$'
        conf = re.sub(expression, lambda _, k=key, v=value: k + ' = ' + v, conf, flags=re.M) if re.search(expression, conf, re.M) else conf + '\n' + key + ' = ' + value + '\n'
    docker('run', '-d', '--name', prefix + '-idp', '--network', net, '--network-alias', 'signing-idp', '--label', label, '--entrypoint', 'sh', '--tmpfs', '/runtime:rw,noexec,nosuid,mode=1777', '--tmpfs', '/conf:rw,noexec,nosuid,mode=1777', image, '-c', 'while [ ! -f /runtime/ready ]; do sleep 1; done; exec /server')
    tarbytes = io.BytesIO()
    with tarfile.open(fileobj=tarbytes, mode='w') as archive:
        for path, text in [('conf/app.conf', conf), ('runtime/init.json', json.dumps(init)), ('runtime/ready', 'ready')]:
            entry = tarfile.TarInfo(path)
            data = text.encode()
            entry.size = len(data)
            entry.mode = 384
            entry.uid = entry.gid = 1000
            archive.addfile(entry, io.BytesIO(data))
    docker('exec', '-i', '-u', '0', prefix + '-idp', 'tar', 'xf', '-', '-C', '/', data=tarbytes.getvalue())
    checkpoint('fixed_idp_started', image=image, synthetic_business_users=2, clients=list(clients))
    env = {'DATABASE_URL': f'postgresql+asyncpg://cmab_app:{password}@postgres/cmab_signing_e2e', 'DATABASE_URL_SYNC': f'postgresql://cmab_app:{password}@postgres/cmab_signing_e2e', 'SECRET_KEY': secrets.token_hex(32), 'REDIS_URL': 'redis://redis:6379/6', 'APP_ENV': 'development', 'APP_LOG_LEVEL': 'ERROR', 'RATE_LIMIT_ENABLED': 'false', 'MDM_OIDC_ENABLED': 'true', 'MDM_NATIVE_LOGIN_ENABLED': 'false', 'MDM_SIGNATURE_MODE': 'oidc_fresh', 'MDM_PUBLIC_URL': public, 'MDM_OIDC_ISSUER_URL': issuer, 'MDM_OIDC_INTERNAL_URL': 'http://signing-idp:8000', 'MDM_OIDC_ORGANIZATION': organization, 'MDM_OIDC_ACCOUNT_STATUS_VISIBLE': 'true', 'MDM_OIDC_ACCOUNT_STATUS_MODE': 'casdoor_v4_userinfo', 'MDM_OIDC_CLIENT_ID': 'mdm-signing-login', 'MDM_OIDC_CLIENT_SECRET': clients['mdm-signing-login'], 'MDM_OIDC_SIGNATURE_CLIENT_ID': 'mdm-signing-proof', 'MDM_OIDC_SIGNATURE_CLIENT_SECRET': clients['mdm-signing-proof'], 'CORS_ORIGINS': 'http://localhost:19090', 'PM_PUBLIC_URL': 'http://localhost:19091', 'PM_REFERENCE_API_URL': 'http://127.0.0.1:8001', 'MDM_PM_API_URL': 'http://127.0.0.1:8001', 'MDM_PM_SOURCE_ID': 'mdm-signing-joint', 'MDM_OIDC_PM_CLIENT_ID': 'mdm-signing-pm-delegation', 'MDM_OIDC_PM_CLIENT_SECRET': clients['mdm-signing-pm-delegation']}
    if getattr(runtime, 'approved_own_policy_v9', False):
        env['MDM_OIDC_DEVICE_LOGOUT_ENABLED'] = 'true'
    if getattr(runtime, 'password_only_signing', False):
        env['MDM_OIDC_SIGNATURE_PASSWORD_ONLY'] = 'true'
    env['CORS_ORIGINS'], env['PM_PUBLIC_URL'] = runtime.spec.origin('mdm'), pm_origin
    args = ['run', '-d', '--name', prefix + '-backend', '--network', net, '--network-alias', 'signing-backend', '--label', label, '--mount', 'type=bind,source=' + str(APP / 'backend') + ',target=/app', '--tmpfs', '/runtime:rw', '-w', '/app']
    for key, value in env.items():
        args.extend(['-e', key + '=' + value])
    docker(*args, '--entrypoint', 'sleep', runtime.mdm_image, 'infinity')
    docker('exec', prefix + '-backend', 'alembic', 'upgrade', 'head')
    docker('exec', prefix + '-backend', 'python', '-m', 'app.scripts.seed_data')
    subjects = None
    for _attempt in range(75):
        result = subprocess.run(['docker', 'exec', pg, 'psql', '-U', 'cmab_app', '-d', 'casdoor_signing_e2e', '-Atc', "SELECT json_object_agg(name,id) FROM public.user WHERE owner='mdm-signing-synthetic' AND name IN ('e2e.signer','e2e.other')"], capture_output=True)
        if result.returncode == 0:
            with suppress(ValueError, TypeError):
                subjects = json.loads(result.stdout)
            if isinstance(subjects, dict) and set(subjects) == {'e2e.signer', 'e2e.other'}:
                break
        time.sleep(0.4)
    else:
        raise RuntimeError('Synthetic subject initialization not ready; inspect before retry')
    mapping = "import asyncio,json,sys\nfrom datetime import UTC,datetime,timedelta\nfrom sqlalchemy import select\nfrom app.core.database import AsyncSessionLocal\nfrom app.domains.auth.models import User\nfrom app.domains.auth.oidc.service import OIDCService\nsubjects=json.load(sys.stdin)\nasync def main():\n async with AsyncSessionLocal() as db:\n  admin=(await db.execute(select(User).where(User.user_id==1))).scalar_one()\n  service=OIDCService(db)\n  for name,uid in [('e2e.signer',1),('e2e.other',5)]:\n   await service.bind_identity(subjects[name],uid,actor=admin,reason='Explicit new synthetic joint test identity')\n  admin.force_password_change=True\n  admin.password_expires_at=datetime.now(UTC)-timedelta(days=1)\n  await db.commit()\nasyncio.run(main())\n"
    docker('exec', '-i', prefix + '-backend', 'python', '-c', mapping, data=json.dumps(subjects).encode())
    pm_env = {'DATABASE_URL': f'postgresql+psycopg://cmab_app:{password}@postgres:5432/pm_signing_e2e', 'AUTO_SEED': 'false', 'APP_ENV': 'development', 'APP_SECRET': secrets.token_hex(32), 'LOG_LEVEL': 'WARNING', 'STATIC_DIR': '', 'APP_CORS_ORIGINS': 'http://localhost:19091,http://localhost:19092', 'CASDOOR_ENDPOINT': issuer, 'CASDOOR_INTERNAL_URL': 'http://signing-idp:8000', 'CASDOOR_ORG': organization, 'CASDOOR_CLIENT_ID': 'mdm-signing-pm', 'CASDOOR_CLIENT_SECRET': clients['mdm-signing-pm'], 'PMS_PUBLIC_URL': 'http://localhost:19091', 'PORTAL_PUBLIC_URL': 'http://localhost:19092', 'PORTAL_CLIENT_ID': 'mdm-signing-portal', 'PORTAL_CLIENT_SECRET': clients['mdm-signing-portal'], 'MDM_PUBLIC_URL': public + '/', 'MDM_DELEGATION_CLIENT_ID': 'mdm-signing-pm-delegation', 'MDM_SOURCE_NAMESPACE': 'mdm-signing-joint', 'OIDC_GLOBAL_LOGOUT_ENABLED': 'true', 'CASDOOR_ACCOUNT_STATUS_VISIBLE': 'true', 'CASDOOR_ACCOUNT_STATUS_MODE': 'casdoor_v4_userinfo', 'IAM_COOKIE_SECURE': 'false', 'IAM_SESSION_SECONDS': '3600', 'INFORMATION_WORKER_ENABLED': 'false', 'AI_SETTINGS_PATH': '/runtime/no-ai.json', 'INFORMATION_DATA_DIR': '/runtime/information'}
    pm_env.update(APP_CORS_ORIGINS=pm_origin + ',' + portal_origin, PMS_PUBLIC_URL=pm_origin, PORTAL_PUBLIC_URL=portal_origin)
    if getattr(runtime, 'identity_pg_host', None):
        pm_env['DATABASE_URL'] = f'postgresql+psycopg://cmab_app:{password}@{runtime.identity_pg_host}:5432/pm_signing_e2e'
    if getattr(runtime, 'approved_own_policy_v9', False):
        pm_env['CASDOOR_ACCOUNT_STATUS_MODE'] = 'casdoor_v4_self_policy'
        pm_env['OIDC_DEVICE_LOGOUT_ENABLED'] = 'true'
    pm_env['ASSISTANT_REQUEST_WORKER_ENABLED'] = 'false'
    pm_env['AUTO_MIGRATE_SCHEMA'] = 'false' if getattr(runtime, 'pm_schema_owner_tool', False) else 'true'
    pm_source = runtime.pm_root / 'backend'
    args = ['run', '-d', '--name', prefix + '-pm', '--network', 'container:' + prefix + '-backend', '--label', label, '--mount', 'type=bind,source=' + str(pm_source / 'app') + ',target=/code/app,readonly', '--mount', 'type=bind,source=' + str(pm_source / 'alembic') + ',target=/code/alembic,readonly', '--mount', 'type=bind,source=' + str(pm_source / 'alembic.ini') + ',target=/code/alembic.ini,readonly', '--tmpfs', '/runtime:rw', '-w', '/code']
    for key, value in pm_env.items():
        args.extend(['-e', key + '=' + value])
    docker(*args, '--entrypoint', 'sleep', runtime.pm_image, 'infinity')
    if getattr(runtime, 'pm_schema_owner_tool', False):
        docker('exec', prefix + '-pm', 'python', '-m', 'app.db.upgrade', '--schema-only')
    else:
        docker('exec', prefix + '-pm', 'alembic', 'upgrade', 'head')
    seed = "import json,sys\nfrom app.db.session import SessionLocal\nfrom app.models import User\nfrom app.models.iam import IAMIdentity\nsubjects=json.load(sys.stdin)\nwith SessionLocal() as db:\n assert db.query(User).count()==0\n for name,uid,role in [('e2e.signer','joint-signer','cmc_lead'),('e2e.other','joint-other','rd')]:\n  db.add(User(id=uid,username=name,display_name='Synthetic '+name.removeprefix('e2e.'),email=name+'@example.com',role=role,is_active=True))\n db.flush()\n for name,uid in [('e2e.signer','joint-signer'),('e2e.other','joint-other')]:\n  db.add(IAMIdentity(issuer='http://localhost:19081',subject=subjects[name],user_id=uid))\n db.commit()\n"
    seed = seed.replace('http://localhost:19081', issuer)
    docker('exec', '-i', prefix + '-pm', 'python', '-c', seed, data=json.dumps(subjects).encode())
    docker('exec', '-d', prefix + '-pm', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8001', '--no-access-log', '--log-level', 'error')
    checkpoint('pm_started', pm_source_head=subprocess.run(['git', '-C', str(runtime.pm_root), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip(), synthetic_users=2, roles=['cmc_lead', 'rd'], business_projects_seeded=0, shared_test_network_namespace=True)
    docker('exec', '-d', prefix + '-backend', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000', '--no-access-log', '--log-level', 'error')
    docker('cp', prefix + '-mdm-ui:/app/dist/.', str(out / 'web/mdm'))
    docker('cp', prefix + '-pm-ui:/app/dist-pm/.', str(out / 'web/pm'))
    docker('cp', prefix + '-pm-ui:/app/dist-portal/.', str(out / 'web/portal'))
    proxy = (ASSETS / 'nginx.conf').read_text(encoding='utf-8')
    proxy = proxy.replace('http://localhost:19091', pm_origin)
    (out / 'nginx.conf').write_text(proxy, encoding='utf-8', newline='\n')
    docker('network', 'create', '--label', label, prefix + '-edge')
    bindings = runtime.spec.port_bindings
    docker('run', '-d', '--name', prefix + '-proxy', '--network', net, '--label', label, '-p', bindings['idp'] + ':8081', '-p', bindings['mdm'] + ':9090', '-p', bindings['pm'] + ':9091', '-p', bindings['portal'] + ':9092', '--mount', 'type=bind,source=' + str(out / 'nginx.conf') + ',target=/etc/nginx/nginx.conf,readonly', '--mount', 'type=bind,source=' + str(out / 'web') + ',target=/web,readonly', 'nginx:1.25-alpine')
    docker('network', 'connect', prefix + '-edge', prefix + '-proxy')
    import urllib.error
    import urllib.request
    loopback = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    checks = {'mdm': public + '/api/v1/health', 'pm': pm_origin + '/health', 'portal': portal_origin + '/', 'idp': issuer + '/.well-known/openid-configuration'}
    health = {}
    for _ in range(35):
        for key, url in checks.items():
            try:
                with loopback.open(url, timeout=2) as response:
                    health[key] = response.status
            except (urllib.error.URLError, OSError):
                health[key] = None
        if all(value == 200 for value in health.values()):
            break
        time.sleep(.3)
    if not all(value == 200 for value in health.values()):
        checkpoint('health_failed', statuses=health)
        raise RuntimeError('Owned services not healthy; no browser acceptance success')
    runtime.manifest['phase'] = 'ready'
    runtime.save()
    checkpoint('ready', mdm=public + '/', portal=portal_origin + '/', pm=pm_origin + '/', signature_mode='oidc_fresh', native_login=False, health=health)

def build_ui(runtime):
    """Offline locked-dependency cache; all source/config changes stay in containers."""
    import os
    for suffix, image, root in [('mdm-ui', 'cmc-mdm-phase2-frontend:local', APP / 'frontend'), ('pm-ui', getattr(runtime, 'pm_ui_image', 'cmc-pm-phase2-fe-verify:local'), runtime.pm_root)]:
        name = runtime.spec.run_id + '-' + suffix
        runtime.docker('image', 'inspect', image)
        runtime.docker('run', '-d', '--name', name, '--network', 'none', '--label', LABEL + '=' + runtime.spec.run_id, '--entrypoint', 'sleep', image, 'infinity')
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w') as arc:
            for folder, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', 'dist', 'backend', 'deploy', '.local-e2e', '.ruff_cache'}]
                for filename in files:
                    if filename == '.git' or filename.startswith('.env') or filename.endswith('.tsbuildinfo'):
                        continue
                    path = Path(folder) / filename
                    arc.add(path, arcname=path.relative_to(root).as_posix())
        runtime.docker('exec', '-i', name, 'tar', 'xf', '-', '-C', '/app', data=buffer.getvalue())
        if suffix == 'mdm-ui':
            commands = [('mdm-front-unit', ['pnpm', 'test:unit']), ('mdm-front-lint', ['pnpm', 'lint']), ('mdm-front-build', ['pnpm', 'build'])]
            for stage, command in commands:
                output = runtime.docker('exec', name, *command, timeout=180)
                runtime.spec.output(stage + '.txt').write_bytes(output)
                runtime.checkpoint(stage, passed=True)
        else:
            patch = "const fs=require('fs');const p='/app/src/lib/site.ts';let s=fs.readFileSync(p,'utf8');if(!s.includes('https://www.openlims.ai')||!s.includes('https://pm.openlims.ai'))throw Error('Unexpected loopback fixture source');s=s.replace('https://www.openlims.ai',process.argv[1]).replace('https://pm.openlims.ai',process.argv[2]);fs.writeFileSync(p,s);"
            runtime.docker('exec', name, 'node', '-e', patch, runtime.spec.origin('portal'), runtime.spec.origin('pm'))
            for mode in ('pm', 'portal'):
                output = runtime.docker('exec', '-e', 'VITE_APP_MODE=' + mode, '-e', 'VITE_USE_API=true', '-e', 'VITE_DEVICE_LOGOUT_ENABLED=' + ('true' if getattr(runtime, 'approved_own_policy_v9', False) else 'false'), name, 'npm', 'run', 'build', timeout=180)
                runtime.spec.output(mode + '-front-build.txt').write_bytes(output)
                runtime.docker('exec', name, 'cp', '-a', '/app/dist', '/app/dist-' + mode)
                runtime.checkpoint(mode + '-front-build', passed=True, real_api=True)
