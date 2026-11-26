"""Read actual native SDK IPC/FS arena bounds without changing boot behavior."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/observe_sysconf_payload.py')
body = parent.read_text().replace('mass-sysconf-payload-observer', 'mass-sysconf-arena-native')
marker = '            const auto bootInfo ='
assert body.count(marker) == 1
observe = '''            std::cout << "SC_NATIVE_ARENA" << std::hex;
            for (uint32_t address : {0x8052afc4u, 0x8052afc8u, 0x8052afb4u, 0x8052afb8u,
                0x8052afacu, 0x8052afa8u, 0x8052afbcu}) {
                std::cout << ' ' << nwii::runtime::bat_memory_read32(context, address);
            }
            std::cout << std::dec << std::endl;
'''
body = body.replace(marker, observe + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-sysconf-arena-native/observation.json')
report = json.loads(path.read_text())
report['arenaObserverParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'].append('Read-only existing native arena bounds, not console original boot or corrected oracle input.')
path.write_text(json.dumps(report, indent=2) + '\n')
