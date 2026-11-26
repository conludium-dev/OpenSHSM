"""Discover estimate sites in actual retained units and recover their existing compile recipes."""
from pathlib import Path
import hashlib
import json
import re
from stock_paired_estimate_patch import adapt


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plans(base, root, dol, all_units):
    result = []
    for value in base['linkCommand']:
        obj = Path(value)
        if not obj.name.startswith('output_') or obj.suffix != '.o':
            continue
        source = obj.with_suffix('')
        text = source.read_text()
        fatal_count = len(re.findall(r'UNIMPLEMENTED Opcode 4 \(ps_\*\) XO " << (?:24|26) <<', text))
        if not fatal_count or (not all_units and obj.name != 'output_8.cpp.o'):
            continue
        assert sha(obj) == base['retainedLinkInputs'][str(obj)]
        record_path = source.with_suffix('.cpp.record.json')
        dependencies = {}
        if record_path.exists():
            record = json.loads(record_path.read_text())
            assert sha(source) == record['sourceSha256'] and sha(obj) == record['objectSha256']
            arguments = record['arguments']
            dependencies.update(record['dependencies'])
        elif obj.parent == root / 'window-input-sdk':
            record_path = obj.parent / 'build.json'
            record = json.loads(record_path.read_text())
            row = next(item for item in record['compiled'] if item['source'] == source.name)
            assert sha(source) == row['sourceSha256'] and sha(obj) == row['objectSha256']
            original_recipe = root / 'window-fp-guard' / (source.name + '.record.json')
            original = json.loads(original_recipe.read_text())
            arguments = ['-I', str(root / 'input-snapshot-research/include'), *original['arguments']]
            dependencies.update(record['dependencies'])
            dependencies[str(original_recipe)] = sha(original_recipe)
            cache_path = source.with_name(source.name + '.cache.json')
            cache = json.loads(cache_path.read_text())
            assert cache['key']['arguments'] == arguments and cache['objectSha256'] == sha(obj)
            assert cache['key']['sourceSha256'] == sha(source)
            dependencies.update(cache['key']['dependencies'])
            dependencies[str(cache_path)] = sha(cache_path)
        elif obj.parent == root / 'window-scan-consume' and obj.name == 'output_19.cpp.o':
            record_path = obj.parent / 'build.json'
            record = json.loads(record_path.read_text())
            assert sha(source) == record['caller']['sourceSha256'] and sha(obj) == record['caller']['objectSha256']
            arguments = record['caller']['arguments']
            header = Path(__file__).resolve().parent / 'stock_scan_consumption.h'
            assert sha(header) == record['consumptionHeaderSha256']
            dependencies[str(header)] = sha(header)
        else:
            raise AssertionError(f'Unproven source/recipe: {source}')
        for file, digest in dependencies.items():
            assert sha(file) == digest, file
        patched, sites = adapt(text, dol)
        assert len(sites) == fatal_count, (source, fatal_count, len(sites))
        assert not re.search(r'UNIMPLEMENTED Opcode 4 \(ps_\*\) XO " << (?:24|26) <<', patched)
        dependencies[str(record_path)] = sha(record_path)
        result.append({'originalSourcePath': str(source), 'originalSourceSha256': sha(source),
            'originalObjectPath': str(obj), 'originalObjectSha256': sha(obj),
            'arguments': arguments, 'sites': sites, 'dependencies': dependencies, 'patched': patched})
    assert result
    return result
