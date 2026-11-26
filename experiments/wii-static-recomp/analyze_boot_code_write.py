"""Record static exception-template patch evidence without permitting code writes."""
from pathlib import Path
import hashlib
import json
import struct

private = Path('work/private-game/static-recomp')
live_path = private / 'mass-ni-guard/live-boot.json'
live = json.loads(live_path.read_text())
register_line = next(line for line in live['stdout'].splitlines() if line.startswith('BOOT_REGISTERS '))
registers = list(map(int, register_line.split()[1:]))
assert len(registers) == 32
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
header = struct.unpack('>64I', dol[:256])

def word(address):
    index = next(index for index in range(7) if header[18 + index] <= address < header[18 + index] + header[36 + index])
    return struct.unpack_from('>I', dol, header[index] + address - header[18 + index])[0]

assert word(0x802119a8) == 0x901c0000
assert registers[28] == 0x80211c08 and registers[0] == word(registers[28]) == 0x38600000
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'result': 'STATIC_EXCEPTION_TEMPLATE_WRITE_CANDIDATE_RUNTIME_INSTRUCTION_PC_UNVERIFIED',
          'candidateInstruction': '0x802119a8', 'originalOpcode': hex(word(0x802119a8)),
          'observedR28Target': hex(registers[28]), 'observedR0Value': hex(registers[0]),
          'initialOriginalWord': hex(word(registers[28])), 'firstWriteWouldBeIdempotent': True,
          'templateSourceR26': hex(registers[26]), 'copySizeR25': registers[25],
          'nearbyCodeWords': {hex(address): hex(word(address)) for address in range(0x802119a0, 0x80211a7c, 4)},
          'liveSha256': sha(live_path), 'originalSha256': sha(dol_path), 'scriptSha256': sha(Path(__file__)),
          'limits': ['R28/R0 correlate with original stw r0,0(r28); printed ctx.pc is a retained return PC, not exact faulting instruction.',
                     'Nearby original loop patches/copies a template; exception-vector purpose is inferred static behavior.',
                     'Later iterations can change template words. No write/dispatch/interpreter policy relaxed.',
                     'Requires exact write observation and independent original execution before adaptation.']}
(private / 'mass-ni-guard/code-write-analysis.json').write_text(json.dumps(report, indent=2) + '\n')
print('STATIC candidate802119A8 writes38600000 to80211C08; initialword same; later template mutation/runtime PC unresolved')
