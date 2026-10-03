"""Evidence-backed seed completeness corrections; retains append-only history."""
import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from extensions.context_authority.registry import load_registry, save_registry

BASE='repos/LingweiXingzhi/projectmind-core'
def gh(endpoint):return json.loads(subprocess.check_output(['gh','api',endpoint],cwd=ROOT).decode('utf-8'))
def main():
    registry=ROOT/'extensions/context_authority/data/claims.jsonl'
    claims=load_registry(registry)
    if any(c['id']=='claim-c-observed-status' for c in claims):
        raise SystemExit('Completeness corrections already appended; no duplication')
    main_head=gh(BASE+'/commits/main')['sha']
    heads={f'PR{n}':gh(BASE+f'/pulls/{n}')['head']['sha'] for n in (21,22)}
    heads['main']=main_head
    trees={name:gh(BASE+f'/git/trees/{sha}?recursive=1') for name,sha in heads.items()}
    if any(tree.get('truncated') for tree in trees.values()):raise ValueError('Tree truncated: cannot claim absence')
    paths={name:[row['path'] for row in tree['tree']] for name,tree in trees.items()}
    now=datetime.now(timezone.utc).isoformat()
    appended=[]
    for letter,directory in [('c','map_proposal'),('d','handoff')]:
        observed={name:[p for p in listed if f'extensions/{directory}/' in p] for name,listed in paths.items()}
        if any(observed.values()):raise ValueError(f'{directory} exists; do not infer NOT_IMPLEMENTED')
        appended.append({'id':f'claim-{letter}-observed-status','key':f'implementation.{directory}_snapshot',
                         'value':{'status':'NOT_IMPLEMENTED','checked_revisions':heads,'checked_directory':f'extensions/{directory}/','limit':'Only the three explicitly observed immutable trees; other branches and future revisions are unknown'},
                         'type':'VERIFIED_FACT','scope':'observed main / PR21 / PR22 snapshots',
                         'source':{'kind':'gh_api','ref':'; '.join(BASE+f'/git/trees/{sha}?recursive=1' for sha in sorted(set(heads.values()))),'revision':main_head},
                         'verified_at':now,'notes':'Version-bound absence evidence, not a statement about every branch or future commit.'})
    files=gh(BASE+'/pulls/21/files?per_page=100')
    appended.append({'id':'claim-pr21-contents','key':'implementation.pr_21_contents_snapshot',
                     'value':{'head':heads['PR21'],'change':'V1 role mapping and current human review boundaries documented','files':sorted(f['filename'] for f in files),'limit':'Contents at this head, not merger or team approval'},
                     'type':'VERIFIED_FACT','scope':f"PR21@{heads['PR21']}",
                     'source':{'kind':'gh_api','ref':BASE+f"/compare/{main_head}...{heads['PR21']}",'revision':heads['PR21']},'verified_at':now})
    old=next(c for c in claims if c['id']=='claim-codefacts-input')
    corrected=copy.deepcopy(old)
    corrected.update(id='claim-codefacts-input-units',supersedes=[old['id']],verified_at=now,notes='CA transcription correction: 40/64 characters of lowercase hex, not 40/64 bits. Formal B source is unchanged.')
    corrected['value']['revision']='full 40/64-character lowercase hexadecimal SHA resolving directly to a commit; HEAD / short SHA / uppercase / tags rejected'
    appended.append(corrected)
    save_registry(registry,appended)
    evidence={'observed_at':now,'heads':heads,'observed_business_directories':{name:[p for p in listed if 'extensions/' in p] for name,listed in paths.items()},'pr21_files':files,'appended_claims':appended,'reason':'Fresh frozen-pack agents q05/q17 independently reported missing facts; explicit version-bound evidence added rather than inferred from absent fields. q19 contains a CA units transcription error. Existing twenty questions/GT unchanged.'}
    (Path(__file__).resolve().parent/'SEED_COMPLETENESS_EVIDENCE.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Appended four provenance-bound completeness/units corrections; formal source unchanged')
if __name__=='__main__':main()
