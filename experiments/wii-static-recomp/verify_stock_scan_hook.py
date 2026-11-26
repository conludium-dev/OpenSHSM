"""Record original string/format/output ABI evidence for a misidentified HLE hook."""
from pathlib import Path
import hashlib
import json
import re
import struct

root = Path('work/private-game/static-recomp').resolve()
stock = root / 'stock-baseline'
output = stock / 'scan-hook-evidence'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
def offset(address):
    section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    return layout[section] + address - layout[18 + section]
mass_path = root / 'mass-current/output_51.cpp'
text = mass_path.read_text()
start = text.index('void func_8019D434(CPUContext& ctx) {')
end = text.index('\nvoid func_', start + 1)
body = text[start:end]
sites = []
for address, opcode in re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', body):
    address, opcode = int(address, 16), int(opcode, 16)
    assert struct.unpack_from('>I', dol, offset(address))[0] == opcode
    sites.append({'address': hex(address), 'opcode': hex(opcode)})
assert len(sites) == 76 and [int(site['address'], 16) for site in sites] == list(range(0x8019D434, 0x8019D564, 4))
(output / 'original-selected.cpp').write_text(body)
current_path = stock / 'window-fp-guard/output_31.cpp'
current = current_path.read_text()
start = current.index('void func_8019D434(nwii::runtime::CPUContext& ctx) {')
end = current.index('\n}', start) + 2
stub = current[start:end]
assert 'OSReport(ctx);' in stub and 'ctx.pc = ctx.lr;' in stub and 'write' not in stub
caller_path = stock / 'window-fp-guard/output_19.cpp'
caller = caller_path.read_text()
caller_sites = []
for address in range(0x8010F304, 0x8010F31C, 4):
    word = int(re.search(rf'// 0x{address:08X}: ([0-9A-F]{{8}})', caller).group(1), 16)
    assert struct.unpack_from('>I', dol, offset(address))[0] == word
    caller_sites.append({'address': hex(address), 'opcode': hex(word)})
fmt_address = 0x8052E720 - 27040
index = offset(fmt_address)
fmt = dol[index:dol.index(b'\0', index)].decode('ascii')
assert fmt == '#%x'
dispatcher = stock / 'window-quantization/main_output.cpp'
assert 'static void dispatch_hle_8019D434(CPUContext& ctx) {\n    OSReport(ctx);' in dispatcher.read_text()
report = {'result': 'WRONG_OSREPORT_HOOK_ORIGINAL_SCAN_ABI_EVIDENCE', 'originalFunction': '8019D434',
    'sites': sites, 'callerSites': caller_sites, 'callerFormat': {'address': hex(fmt_address), 'text': fmt},
    'originalBehavior': ['Caller supplies input stringR3, format#%xR4 and output stack pointerR5, then consumes that stack result.',
        'Original wrapper spills varargs and calls8019C714 with string-reader8019D3AC, input context, format and va_list.'],
    'pcAdaptation': ['Current direct wrapper and dispatcher wrongly replace this function with OSReport, which does not populate caller output.'],
    'inferredBehavior': ['sscanf-family identification follows the source ABI/callee flow; no original debug symbol recovered.',
        'Potential cause of invalid UI parsing/boot progression; full runtime causality not verified yet.'],
    'inputs': {str(path): sha(path) for path in [dol_path, mass_path, current_path, caller_path, dispatcher, Path(__file__)]},
    'limits': ['No original scanning execution or fixed scan function integrated this turn.',
        'Do not replace original scan implementation with host sscanf or disable the real OSReport80213EA0.']}
(output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], '76 original instructions +6 caller words; original#%x→stack-output, currentOSReport mismatch')
