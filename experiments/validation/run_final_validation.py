"""Fresh processes for complete regressions; captured outcomes for determinism."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from extensions.context_authority.registry import load_registry
from extensions.context_authority.resolver import resolve
from extensions.context_authority.context_pack import build_context_pack, validate_context_pack
from extensions.context_authority.verifiers import build_default_verifiers

HERE=Path(__file__).resolve().parent
REGISTRY=ROOT/'extensions/context_authority/data/claims.jsonl'
def main():
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    claims=load_registry(REGISTRY)
    defaults=build_default_verifiers(str(ROOT))
    captures={}
    for c in claims:
        if c['type']=='VERIFIED_FACT' and c['key'] in defaults:
            captures[c['id']]=defaults[c['key']](c)
    verifiers={key:(lambda c:captures[c['id']]) for key in defaults}
    state=resolve(claims,verifiers=verifiers)
    encoded=json.dumps(state,sort_keys=True,ensure_ascii=False)
    assert all(json.dumps(resolve(claims,verifiers=verifiers),sort_keys=True,ensure_ascii=False)==encoded for _ in range(100))
    assert json.dumps(resolve(list(reversed(claims)),verifiers=verifiers),sort_keys=True,ensure_ascii=False)==encoded
    with patch('extensions.context_authority.context_pack.build_default_verifiers',return_value=verifiers):
        pack=build_context_pack('map proposal',str(ROOT),REGISTRY,revision=revision)
        validate_context_pack(pack,expected_revision=revision)
        assert all(build_context_pack('map proposal',str(ROOT),REGISTRY,revision=revision)==pack for _ in range(20))
        assert build_context_pack('map proposal',str(ROOT),REGISTRY,revision=revision)==pack
    for name,data in [('FINAL_CONTEXT_PACK.json',pack),('FINAL_CURRENT_STATE.json',state),('VERIFIER_CAPTURE.json',captures)]:
        (HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    outcomes=[]
    logs=HERE/'regression_runs';logs.mkdir(exist_ok=True)
    for i in range(1,4):
        proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
        output=proc.stdout+proc.stderr
        (logs/f'run_{i}.log').write_text(output,encoding='utf-8')
        result={'run':i,'exit_code':proc.returncode,'log':f'regression_runs/run_{i}.log','sha256':hashlib.sha256(output.encode()).hexdigest()}
        outcomes.append(result)
        print(f'Complete regression {i}: exit={proc.returncode}',flush=True)
        if proc.returncode: break
    result={'project_revision':revision,'registry_hash':state['registry_hash'],'resolve_repeats':100,'reorder_equal':True,'pack_repeats':20,'determinism_basis':'same registry/task/revision and captured verifier outcomes including timestamps','complete_regressions':outcomes,'pass':len(outcomes)==3 and all(x['exit_code']==0 for x in outcomes),'pack_bytes_compact':len(json.dumps(pack,ensure_ascii=False,separators=(',',':')).encode('utf-8'))}
    (HERE/'FINAL_VALIDATION.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    return 0 if result['pass'] else 1
if __name__=='__main__':raise SystemExit(main())
