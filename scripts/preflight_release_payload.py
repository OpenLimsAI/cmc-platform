#!/usr/bin/env python3
"""Fail closed on secrets/runtime files; stage only the hashed source allowlist."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
files={ROOT/'README.md',ROOT/'AGENTS.md',ROOT/'.gitignore'}
for folder,pattern in [('backend/app','*.py'),('backend/tests','*.py'),('frontend/src','*'),('frontend/tests','*.mjs'),('docs','*.md'),('scripts','*.py'),('scripts','*.sh'),('scripts','*.cjs'),('deploy','*.service'),('deploy','*.timer'),('deploy','*.conf'),('deploy','*.plist')]:
    files.update(p for p in (ROOT/folder).rglob(pattern) if p.is_file())
for name in ['backend/pyproject.toml','backend/uv.lock','backend/.env.example','backend/.env.collector.example',
             'frontend/package.json','frontend/package-lock.json','frontend/tsconfig.json','frontend/vite.config.ts','frontend/index.html',
             'config/tasks.json','integration/README.md','integration/permissions.sql.example','integration/notifications/cron-exit-trap.sh.example',
             'deploy/linux/release-20261010.json','docs/board-preview.jpg','docs/mac-hub-preview.png','docs/mac-task-groups.png']:
    files.add(ROOT/name)
manifest={}
for p in sorted(files):
    rel=str(p.relative_to(ROOT))
    if p.is_symlink() or any(x in p.parts for x in ['node_modules','dist','.venv','__pycache__','.local']) or p.name in ['.env','api.env','collector.env']:
        raise RuntimeError('runtime/symlink payload refused: '+rel)
    data=p.read_bytes()
    if p.suffix not in ['.png','.jpg']:
        value=data.decode('utf-8')
        if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}',value):
            raise RuntimeError('credential pattern refused: '+rel)
        for password in re.findall(r'postgres(?:ql)?(?:\+\w+)?://[^\s:@]+:([^\s@]+)@',value):
            if password not in ['CHANGE_ME','private','__FILL_ME__','{passwords[role]}']:
                raise RuntimeError('database secret refused: '+rel)
        if re.search(r'(?:SECRET_KEY|OPS_JWT_VERIFY_KEY)\s*=\s*[\"\'](?!CHANGE_ME)[A-Za-z0-9_/-]{32,}',value):
            raise RuntimeError('literal signing key refused: '+rel)
    elif not (data.startswith(b'\x89PNG') or data.startswith(b'\xff\xd8')):
        raise RuntimeError('unexpected binary payload: '+rel)
    manifest[rel]=hashlib.sha256(data).hexdigest()
out=ROOT/'.local/release-payload.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(manifest,indent=2)+'\n')
print('PASS: explicit source/document/synthetic screenshot payload',len(manifest),'files; no runtime environment, dependencies or private keys')

if __name__=='__main__' and '--stage' in __import__('sys').argv:
    for rel,digest in manifest.items():
        if hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()!=digest:raise RuntimeError('payload changed after validation')
    subprocess.run(['git','add','--',*manifest],cwd=ROOT,check=True)
    staged=subprocess.check_output(['git','diff','--cached','--name-only'],cwd=ROOT,text=True).splitlines()
    if set(staged)-set(manifest):raise RuntimeError('unapproved staged file')
    subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=True)
    print('PASS: staged payload matches checked allowlist')
