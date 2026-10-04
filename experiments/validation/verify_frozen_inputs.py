"""Check active freeze hashes on disk, or exact staged/published Git blobs."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FREEZES = [('ca_experiment', 'INPUT_FREEZE.json'),
           ('ca_experiment', 'FINAL_INPUT_FREEZE.json'),
           ('validation', 'STUDY_FREEZE.json'),
           ('validation', 'HARDENED_STUDY_FREEZE.json')]

def main():
    source = sys.argv[1] if len(sys.argv) > 1 else None
    total = 0
    for folder, name in FREEZES:
        root = ROOT/'experiments'/folder
        freeze = json.loads((root/name).read_text(encoding='utf-8'))
        for relative, expected in freeze['sha256'].items():
            path = root/relative.replace('\\', '/')
            if source:
                repo_path = path.relative_to(ROOT).as_posix()
                spec = ':'+repo_path if source == '--index' else source+':'+repo_path
                data = subprocess.check_output(['git', 'show', spec], cwd=ROOT)
            else:
                data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError(f'Frozen bytes differ: {folder}/{relative}; source={source or "disk"}')
            total += 1
    print(f'PASS: {total} active frozen fingerprints; source={source or "disk"}')

if __name__ == '__main__': main()
