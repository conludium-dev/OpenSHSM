"""Re-express historical build metadata through the verified SSD symlink."""
from pathlib import Path
import copy
import json
from stock_debug_font_build import sha


def equivalent(old, new):
    old_path, new_path = Path(old), Path(new)
    assert old_path.is_absolute() and new_path.is_absolute()
    assert old_path.resolve(strict=True) == new_path.resolve(strict=True), (old, new)
    assert sha(old_path) == sha(new_path)


def save(original_path, data, category):
    destination = original_path.with_name('build-ssd-' + category + '-' + sha(original_path)[:12] + '.json')
    content = json.dumps(data, indent=2) + '\n'
    if destination.exists():
        assert destination.read_text() == content
    else:
        destination.write_text(content)
    return destination


def psq(original_path, parent_path, current_root):
    original = json.loads(original_path.read_text())
    parent = json.loads(parent_path.read_text())
    assert original['result'] == 'INDEXED_PSQ_FLOAT_ALL_CALLERS_COMPILED_LINKED_NOT_LIVE_VERIFIED'
    assert Path(original['parentBuildPath']) == parent_path
    replacements = {change['originalObjectPath'] for change in original['unitChanges']}
    expected = {}
    for value in parent['linkCommand']:
        if value.endswith(('.o', '.a')) and value not in replacements:
            path = Path(value) if Path(value).is_absolute() else current_root / 'export/build' / value
            expected[str(path)] = sha(path)
    previous = original['retainedLinkInputs']
    assert len(expected) == len(previous)
    canonical_previous = {str(Path(path).resolve(strict=True)): digest for path, digest in previous.items()}
    canonical_expected = {str(Path(path).resolve(strict=True)): digest for path, digest in expected.items()}
    assert len(canonical_previous) == len(previous)
    assert len(canonical_expected) == len(expected)
    assert canonical_previous == canonical_expected
    for path, digest in expected.items():
        assert sha(path) == digest
    relocated = copy.deepcopy(original)
    relocated['retainedLinkInputs'] = expected
    return save(original_path, relocated, 'psq')


def sysconf(original_path, parent_path, current_root):
    original = json.loads(original_path.read_text())
    parent = json.loads(parent_path.read_text())
    assert original['result'] == 'SYSCONF_EXISTING_FS_NATIVE_CHAIN_COMPILED_LINKED_NOT_LIVE_VERIFIED'
    assert Path(original['parentBuildPath']) == parent_path
    expected = list(parent['linkCommand'])
    expected[expected.index(parent['archivePath'])] = original['archivePath']
    expected[expected.index('-o') + 1] = original['executablePath']
    main = next(value for value in expected if Path(value).name == 'main.cpp.o')
    expected[expected.index(main)] = str(current_root / 'window-quantization/contract-entry.cpp.o')
    expected.insert(1, str(original_path.parent / 'probe.cpp.o'))
    expected[expected.index('-o') + 1] = original['nativeProbe']['executablePath']
    previous = original['nativeProbe']['linkCommand']
    assert len(previous) == len(expected)
    for old, new in zip(previous, expected):
        if old != new:
            equivalent(old, new)
    relocated = copy.deepcopy(original)
    relocated['nativeProbe']['linkCommand'] = expected
    return save(original_path, relocated, 'sysconf')
