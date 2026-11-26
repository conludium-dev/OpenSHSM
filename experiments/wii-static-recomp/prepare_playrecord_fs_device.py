"""Extend the existing private FS class for the observed OPEN/READ/SEEK shape."""
from pathlib import Path
import base64
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-playrecord-open-flush-boot'
output = root / 'playrecord-fs-device'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_playrecord_events_dolphin.py')], check=True)
build = json.loads((base / 'build.json').read_text())
for name in ('fs_device.cpp', 'stm_device.cpp', 'di_device.cpp', 'es_device.cpp'):
    path = base / name
    assert sha(path) == build['sourceHashes'][str(path)]
    (output / name).write_bytes(path.read_bytes())
for path in base.glob('*.h'):
    assert sha(path) == build['headerHashes'][str(path)]
    (output / path.name).write_bytes(path.read_bytes())
capture_path = root / 'dolphin-playrecord-events-disc/fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
seed = base64.b64decode(capture['playrecordLabFile'])
assert len(seed) == 128
lab = output / 'pc-owned-playrecord.bin'
if lab.exists():
    assert lab.read_bytes() == seed, 'Refusing to overwrite existing PC-owned experiment data'
else:
    lab.write_bytes(seed)
path = output / 'fs_device.cpp'
text = path.read_text()


def replace(old, new):
    global text
    assert text.count(old) == 1, (old, text.count(old))
    text = text.replace(old, new)


replace('    std::ifstream m_sysconf;', '    std::ifstream m_sysconf;\n    bool m_playrecord = false;')
marker = '        if ((path != "/shared2/sys/SYSCONF"'
assert text.count(marker) == 1
start = text.index(marker)
text = text[:start] + '''        if (path == "/title/00000001/00000002/data/play_rec.dat") {
            if (mode != 3 || m_sysconf.is_open()) {
                throw std::runtime_error("Play-record OPEN outside observed mode/lifetime");
            }
            const auto* source = std::getenv("SHSM_PLAYRECORD_LAB_FILE");
            if (!source || !*source) {
                throw std::runtime_error("Explicit PC-owned play-record LAB file required");
            }
            m_sysconf.clear();
            m_sysconf.open(source, std::ios::binary);
            if (!m_sysconf || m_sysconf.seekg(0, std::ios::end).tellg() != 128) {
                m_sysconf.close();
                m_sysconf.clear();
                throw std::runtime_error("Play-record LAB file unavailable or wrong length");
            }
            m_sysconf.seekg(0);
            if (!m_sysconf) {
                m_sysconf.close();
                m_sysconf.clear();
                throw std::runtime_error("Play-record initial seek failed");
            }
            m_readLength = 128;
            m_readTarget = 0x493120;
            m_playrecord = true;
            return 20;
        }
''' + text[start:]
replace('        const bool product =', '        m_playrecord = false;\n        const bool product =')
replace('        if (fd == 20) {\n            if (!m_sysconf.is_open() || m_sysconf.tellg() != m_readLength)',
    '        if (fd == 20) {\n            if (m_playrecord) { throw std::runtime_error("Play-record CLOSE not yet observed"); }\n            if (!m_sysconf.is_open() || m_sysconf.tellg() != m_readLength)')
marker = '    int32_t seek(CPUContext& ctx, uint32_t fd, int32_t offset, int32_t whence) override {\n'
replace(marker, marker + '''        if (fd == 20 && m_playrecord) {
            if (!m_sysconf.is_open() || offset != 0 || whence != 0 || m_sysconf.tellg() != 128) {
                throw std::runtime_error("Play-record SEEK outside observed post-read rewind");
            }
            m_sysconf.seekg(0);
            if (!m_sysconf) { throw std::runtime_error("Play-record rewind failed"); }
            return 0;
        }
''')
path.write_text(text)
(output / 'preparation.json').write_text(json.dumps({'preparerSha256':sha(Path(__file__)),
    'parentBuildSha256':sha(base / 'build.json'), 'oracleCaptureSha256':sha(capture_path),
    'pcOwnedSeedSha256':sha(lab),
    'sourceHashes':{str(path):sha(path) for path in output.glob('*.cpp')},
    'headerHashes':{str(path):sha(path) for path in output.glob('*.h')},
    'limits':['Same FS class/shared stream/kernel, no second registry or vendor changes.',
        'Original mode3 accepted for measured OPEN/READ128/SEEK0 only; WRITE and CLOSE intentionally refuse.',
        'Read-only stream over separate PC-owned LAB copy; not a public game asset/NAND dependency.',
        'Device component only; original PPC submission/IRQ/callback integration remains required.']}, indent=2) + '\n')
print('Prepared SAME FS play-record OPEN3/READ128/SEEK0 with separate PC-owned LAB seed; WRITE/CLOSE refused')
