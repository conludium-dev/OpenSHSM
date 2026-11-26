"""Separate COW own-disc/profile for original play-record start; old captures protected."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/prepare_es_di_ticket_disc.py')
body = parent.read_text().replace('dolphin-es-di-ticket','dolphin-playrecord-start')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
output = Path('work/private-game/static-recomp/dolphin-playrecord-start-disc')
profile = Path('_scratch/tmp/dolphin-playrecord-start-disc-user')
lab = profile/'Wii/title/00000001/00000002/data/play_rec.dat'
assert lab.is_file() and lab.stat().st_size == 128
path = output/'playrecord-lab-preparation.json'
if not path.exists():
    path.write_text(json.dumps({'preparerSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'initialFileSha256':hashlib.sha256(lab.read_bytes()).hexdigest(),'initialFileBytes':128,
        'limits':['Independent cloned LAB file/profile, not a game asset or physical NAND dependency.']},indent=2)+'\n')
