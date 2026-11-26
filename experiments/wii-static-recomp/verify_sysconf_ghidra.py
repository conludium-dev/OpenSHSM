"""Decode the original IOS/ISFS/NAND/SC callback chain and initial buffer preparation."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_es_datadir_ghidra.py')
body = parent.read_text().replace('es-datadir-source/ghidra', 'sysconf-source/ghidra')
names = [('IOS_OpenAsync', 71, 284), ('ISFS_OpenAsync', 46, 184), ('_isfsFuncCb', 96, 384),
    ('nandOpenCallback', 30, 120), ('SCReloadConfFileAsync', 69, 276), ('OpenCallbackFromReload', 52, 208),
    ('fn_80247800', 58, 232), ('SCInit', 40, 160)]
body = body.replace("[('ESP_GetDataDir', 'auto_03_802045CC_text.o', 38, 152)]",
    repr([(name, 'auto_03_802045CC_text.o', count, size) for name, count, size in names]))
body = body.replace('ES data-dir span38instructions/152bytes', 'SYSCONF chain462instructions/1848bytes').replace(
    'ORIGINAL_ES_DATADIR_SPAN38_INSTRUCTIONS152_BYTES_DECODED', 'ORIGINAL_SYSCONF_CHAIN462_INSTRUCTIONS1848_BYTES_DECODED')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/sysconf-source/ghidra/verification.json')
report = json.loads(path.read_text())
report['sysconfParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Original decomp-toolkit spans and independently discovered Ghidra bodies; callback ownership/preparation/static read extent evidence.',
    'No original async OPEN/read/callback execution, contents/physical IOS/full retail proof. Headless Ghidra; MCP unavailable.']
path.write_text(json.dumps(report, indent=2) + '\n')
