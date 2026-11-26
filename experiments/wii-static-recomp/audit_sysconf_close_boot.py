"""Check original first file CLOSE reply, callback ownership and continuation to product OPEN."""
from pathlib import Path
import ast
import hashlib
import json

parent = Path('experiments/wii-static-recomp/audit_sysconf_read_boot.py')
body = parent.read_text().replace('mass-sysconf-read-boot', 'mass-sysconf-close-boot').replace(
    'mass-sysconf-open-boot', 'mass-sysconf-read-boot').replace('build_sysconf_read_boot.py', 'build_sysconf_close_boot.py')
node = next(node for node in ast.parse(body).body if isinstance(node, ast.FunctionDef) and node.name == 'check')
check = '''def check(lines, enabled):
    def one(prefix):
        matches = [line[len(prefix) + 1:].split() for line in lines if line.startswith(prefix + ' ')]
        assert len(matches) == 1, prefix
        return matches[0]
    assert one('SC_OPEN_API_RETURN') == ['0', 'a032', '1', '31']
    assert 'BOOT_STM_ASYNC dispatched=1 pending=1 6 1 324927520 4096 4796512 32 4796544 32' in lines
    assert 'BOOT_ES_CLOSE_STATE ffffffff 935e0060 50' in lines
    assert 'BOOT_NAND_INIT_STATE 2' in lines
    boundary = ' '.join(one('BOOT_BOUNDARY'))
    if not enabled:
        assert 'BOOT_STM submitted=20 produced=9' in lines
        assert boundary.startswith('pc=80212ff4 lr=80242240 msr=32')
        assert not any(line.startswith('SC_CLOSE_CALLBACK ') for line in lines)
        return
    assert 'BOOT_STM submitted=22 produced=10' in lines
    assert one('BOOT_FLUSH') == ['entries=26', 'phase=0', 'barriers=1a']
    assert 'BOOT_SI_DELIVERY entries=25 callbacks=4' in lines
    sequence = [line for line in lines if line.startswith(('SC_CLOSE_FREE ', 'SC_CLOSE_CALLBACK '))]
    assert sequence == ['SC_CLOSE_FREE 1 935e1180 32', 'SC_CLOSE_FREE 0 935e00e0 32',
        'SC_CLOSE_CALLBACK 80240680 0 935e1020 32', 'SC_CLOSE_CALLBACK 80245af0 0 804b3094 32',
        'SC_CLOSE_CALLBACK 802478f0 0 804b3094 32']
    for address in ('80240680', '80245af0', '802478f0'):
        for view, offset in (('CACHED', 64), ('PHYSICAL', 128)):
            expected = bytearray(events[75][offset:offset + 64])
            expected[24:28] = bytes.fromhex('80540010')
            assert bytes(map(int, one('SC_CLOSE_REPLY_' + view + ' ' + address))) == expected
    assert one('SC_PRODUCT_OPEN_ARGUMENTS') == ['935e1180', '1', '80240680', '935e1180', '32']
    assert bytes(map(int, one('SC_PRODUCT_OPEN_PATH'))) == b'/title/00000001/00000002/data/setting.txt'.ljust(64, b'\\0')
    assert boundary.startswith('pc=80212ff4 lr=8024250c msr=32')
    assert 'Flush syscall CPU/site/profile unverified' in boundary
'''
body = body.replace(ast.get_source_segment(body, node), check)
body = body.replace('SHSM_SYSCONF_READ_DISABLED', 'SHSM_SYSCONF_CLOSE_DISABLED')
a = body.index("for prefix in ('SC_READ_FREE 1'")
b = body.index('    changed =', a)
body = body[:a] + "for prefix in ('SC_CLOSE_FREE 1', 'SC_CLOSE_FREE 0', 'SC_CLOSE_CALLBACK 80240680', 'SC_CLOSE_CALLBACK 80245af0',\n    'SC_CLOSE_CALLBACK 802478f0', 'SC_CLOSE_REPLY_CACHED 80240680', 'SC_CLOSE_REPLY_PHYSICAL 80240680',\n    'SC_PRODUCT_OPEN_ARGUMENTS', 'SC_PRODUCT_OPEN_PATH', 'BOOT_STM_ASYNC dispatched='):\n" + body[b:]
body = body.replace('NATIVE_NESTED_READ_16384_CALLBACK2_MSR32_ORIGINAL_BYTES_OWNERSHIP_PASS',
    'NATIVE_FIRST_FILE_CLOSE_CALLBACK3_ORIGINAL_REPLIES_READ_FREES_PRODUCT_CONTINUATION_PASS')
body = body.replace('PASS native nestedREAD16384/both full buffers/original64replies/callback2-MSR32/oldOPEN frees ordered/STM/disabled;10mutants',
    'PASS native actualfileCLOSE/original64replies/callback3-MSR32/READfrees/productOPEN/STM/disabled;10mutants')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-sysconf-close-boot/audit.json')
report = json.loads(path.read_text())
report['parentVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['First close reply equals original event75 with explicit ignored pointer relocation.',
    'Higher close callback entry arguments are native dynamic evidence plus original prepared callback metadata, not new original entry captures.',
    'PC handshake/timing adaptation retained. Next product OPEN stops before path flush; no SC completion/full retail proof.']
path.write_text(json.dumps(report, indent=2) + '\n')
