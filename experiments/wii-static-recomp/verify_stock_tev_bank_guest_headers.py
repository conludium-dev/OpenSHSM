"""Check retained generated translation-unit include closures before ABI handoff."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'headless-tev-banks'
manifest = output / 'build.json'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base = json.loads(manifest.read_text())
arguments = json.loads((root / 'window-fp-guard/output_38.cpp.record.json').read_text())['arguments']
prefixes = {}
sources = {}
for value in base['linkCommand']:
    path = Path(value)
    if path.name.startswith('output_') and path.suffix == '.o':
        source = path.with_suffix('')
        text = source.read_text()
        prefix = '\n'.join(line for line in text.splitlines() if line.startswith('#include'))
        prefixes[(prefix, str(source.parent))] = True
        sources[str(source)] = sha(source)
for prefix, parent in prefixes:
    local_arguments = []
    for name in re.findall(r'^#include "([^"/]+)"', prefix, re.M):
        if (Path(parent) / name).exists() or (public / name).exists():
            continue
        candidates = list(root.glob('*/' + name))
        if candidates:
            assert len({sha(path) for path in candidates}) == 1, ('Ambiguous inherited helper', name)
            local_arguments.extend(['-I', str(candidates[0].parent)])
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', '-I', str(output / 'include'),
        '-I', parent, '-I', str(public), *local_arguments, *arguments, '-MM', '-x', 'c++', '-'],
        input=prefix, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, (parent, result.stderr[-1500:])
    assert 'gx_state.h' not in result.stdout, ('Retained guest needs GXState rebuild', parent)
(output / 'guest-header-verification.json').write_text(json.dumps({'result': 'RETAINED_GUEST_INCLUDE_CLOSURE_NO_GXSTATE',
    'buildSha256': sha(manifest), 'units': len(sources), 'includeSets': len(prefixes), 'sources': sources,
    'verifierSha256': sha(Path(__file__).resolve()),
    'limits': ['All direct include directives from retained generated units, recursively preprocessed.',
        'Runtime members separately preprocessed/rebuilt by build script; not gameplay or GPU correctness proof.']}, indent=2) + '\n')
print('RETAINED_GUEST_INCLUDE_CLOSURE_NO_GXSTATE', len(sources), len(prefixes))
