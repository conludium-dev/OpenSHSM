"""Validate the one-FS-member derivative and its independent original/native configuration proofs."""
from pathlib import Path
import hashlib
import json
import subprocess
from stock_sysconf_patch import adapt


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(path, parent_path, parent):
    build = json.loads(path.read_text())
    return validate_record(path, parent_path, parent, build)


def validate_record(path, parent_path, parent, build):
    assert build['result'] == 'SYSCONF_EXISTING_FS_NATIVE_CHAIN_COMPILED_LINKED_NOT_LIVE_VERIFIED'
    assert Path(build['parentBuildPath']) == parent_path and build['parentBuildSha256'] == sha(parent_path)
    for file, digest in {**build['dependencies'], **build['retainedLinkInputs']}.items():
        assert sha(file) == digest, file
    original = Path(build['originalSourcePath'])
    source = Path(build['sourcePath'])
    assert sha(original) == build['originalSourceSha256']
    assert source.read_text() == adapt(original.read_text()) and sha(source) == build['sourceSha256']
    public = Path(__file__).resolve().parent
    root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
    assert sha(path.parent / 'stock_sysconf.h') == sha(public / 'stock_sysconf.h')
    assert sha(path.parent / 'stock_fs_rename_commands.inc') == sha(original.parent / 'stock_fs_rename_commands.inc')
    obj = path.parent / 'fs_device.cpp.o'
    assert sha(obj) == build['objectSha256']
    args = json.loads((root / 'input-snapshot-research/build.json').read_text())['arguments']
    assert build['compileCommand'] == ['/Library/Developer/CommandLineTools/usr/bin/c++', '-H', *args,
        '-c', str(source), '-o', str(obj)]
    assert str(path.parent / 'stock_sysconf.h') in (path.parent / 'compile.log').read_text()
    proof_path = Path(build['originalProofPath'])
    assert sha(proof_path) == build['originalProofSha256']
    proof = json.loads(proof_path.read_text())
    assert proof['result'] == 'ORIGINAL_WII_SYSCONF_PARSER_ASPECT_CHAIN_PASS' and proof['suppliedServiceHooks'] == 0
    for file, digest in proof['dependencies'].items():
        assert sha(file) == digest
    native = build['nativeProbe']
    assert 'EXISTING_FS_NATIVE_ORIGINAL_PARSER_WIDESCREEN_BYTE_PASS' in native['output']
    assert sha(native['executablePath']) == native['executableSha256']
    prepared = Path(native['preparedSysconfPath'])
    assert prepared.stat().st_size == 0x4000
    assert sha(prepared) == native['preparedSysconfSha256']
    assert sha(prepared) == next(row['inputSha256'] for row in proof['cases'] if row['name'] == 'byte-1')
    previous = Path(parent['archivePath'])
    assert sha(previous) == parent['archiveSha256']
    archive = Path(build['archivePath'])
    assert sha(archive) == build['archiveSha256']
    names = subprocess.check_output(['/usr/bin/ar', 't', str(previous)], text=True).splitlines()
    assert names == subprocess.check_output(['/usr/bin/ar', 't', str(archive)], text=True).splitlines()
    retained = {}
    for name in names:
        if name.startswith('__.SYMDEF'):
            continue
        before = subprocess.check_output(['/usr/bin/ar', '-p', str(previous), name])
        after = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), name])
        if name == 'fs_device.cpp.o':
            assert hashlib.sha256(before).hexdigest() == build['originalObjectSha256']
            assert hashlib.sha256(after).hexdigest() == build['objectSha256']
        else:
            assert before == after
            retained[name] = hashlib.sha256(after).hexdigest()
    assert retained == build['retainedRuntimeMembers']
    exe = Path(build['executablePath'])
    assert exe.parent == path.parent and exe.name == 'OpenSHSM-0.0.42'
    expected = list(parent['linkCommand'])
    expected[expected.index(str(previous))] = str(archive)
    expected[expected.index('-o') + 1] = str(exe)
    assert expected == build['linkCommand'] and sha(exe) == build['executableSha256']
    assert b'OpenSHSM BUILD 0.0.42\0' in exe.read_bytes()
    probe_expected = list(expected)
    main_obj = next(arg for arg in expected if Path(arg).name == 'main.cpp.o')
    probe_expected[probe_expected.index(main_obj)] = str(root / 'window-quantization/contract-entry.cpp.o')
    probe_expected.insert(1, str(path.parent / 'probe.cpp.o'))
    probe_expected[probe_expected.index('-o') + 1] = native['executablePath']
    assert probe_expected == native['linkCommand']
    return exe
