"""Snapshot source and run zero-call gates away from the user's real run files."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'state_map_v3_checks'
OUT.mkdir(exist_ok=True)
snapshot=Path(tempfile.mkdtemp(prefix='wonderland-map-v3-'))
files=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
for relative in sorted(set(files)):
    if not relative or relative.startswith('state') or relative.startswith('.env'):
        continue
    source=ROOT/relative
    if source.is_file():
        target=snapshot/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
env={k:v for k,v in os.environ.items() if not k.startswith('DUNGEON_')}
env.update(PYTHONUTF8='1',DUNGEON_ACTION_MODE='menu',DUNGEON_BRAIN_BACKEND='dummy',
           DUNGEON_SKILLS='0',DUNGEON_TRPG_COMBAT='0',DUNGEON_RANDOM_SKILL='0')
names=(re.findall(r'\bverify_[a-z0-9_]+\b',(ROOT/'_run_gates.sh').read_text(encoding='utf-8'))
       if '--all' in sys.argv else sys.argv[1:])
names=list(dict.fromkeys(names))
if not names:
    names=['verify_town_v3','verify_town_spaces','verify_town','verify_guild','verify_partyform',
           'verify_people','verify_worlds','verify_townsight','verify_entities','verify_companion','verify_resume']
summary=dict(snapshot=str(snapshot),gates=[],llmCalls=0)
(OUT/'latest.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print('Snapshot: '+str(snapshot),flush=True)
for name in names:
    p=subprocess.run([sys.executable,name+'.py'],cwd=snapshot,env=env,capture_output=True,
                     text=True,encoding='utf-8',errors='replace',timeout=300)
    output=p.stdout+'\n'+p.stderr
    (OUT/(name+'.log')).write_text(output,encoding='utf-8')
    ok=p.returncode==0 and 'ALL PASS' in p.stdout
    summary['gates'].append(dict(name=name,passed=ok,exit=p.returncode))
    (OUT/'latest.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(('PASS ' if ok else 'FAIL ')+name,flush=True)
print('%d/%d PASS' % (sum(g['passed'] for g in summary['gates']),len(names)),flush=True)
sys.exit(0 if all(g['passed'] for g in summary['gates']) else 1)
