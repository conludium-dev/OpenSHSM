"""Extract official tool runtime app-locally; never run the Microsoft installer."""
from pathlib import Path, PureWindowsPath
import hashlib
import json
import shutil
import struct
import subprocess
import xml.etree.ElementTree as ET

tools = Path('_scratch/tmp/dolphin-runtime-tools')
archive = tools / 'vc_redist.x64.exe'
seven = tools / '7zz'
raw = archive.read_bytes()
subprocess.run([str(seven), 'e', str(archive), '0', '-o' + str(tools / 'manifest'), '-y'], check=True, capture_output=True)
manifest = ET.fromstring((tools / 'manifest/0').read_text(encoding='utf-8-sig'))
payloads = [node.attrib for node in manifest.iter() if node.tag.endswith('Payload')]
cabinets = [(offset, struct.unpack_from('<I', raw, offset + 8)[0]) for offset in range(len(raw) - 36) if raw[offset:offset + 4] == b'MSCF']
assert len(cabinets) == 2
offset, size = cabinets[1]
assert offset + size <= len(raw)
attached = tools / 'attached.cab'
attached.write_bytes(raw[offset:offset + size])
subprocess.run([str(seven), 'x', str(attached), '-o' + str(tools / 'payloads'), '-y'], check=True, capture_output=True)
cab_records = []
for payload in payloads:
    if '_amd64\\' in payload['FilePath'].lower() and payload['FilePath'].lower().endswith('.cab'):
        source = tools / 'payloads' / payload['SourcePath']
        assert len(source.read_bytes()) == int(payload['FileSize'])
        assert hashlib.sha1(source.read_bytes()).hexdigest().upper() == payload['Hash']
        directory = tools / PureWindowsPath(payload['FilePath']).parent.name
        subprocess.run([str(seven), 'x', str(source), '-o' + str(directory), '-y'], check=True, capture_output=True)
        cab_records.append({'cab': payload['FilePath'], 'directory': str(directory), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
lab = Path('_scratch/tmp/dolphin-static-recomp-lab')
shutil.copytree('work/research/dolphin/Dolphin-x64', lab, dirs_exist_ok=True)
records = []
for cab in cab_records:
    for source in Path(cab['directory']).iterdir():
        contents = source.read_bytes()
        if contents[:2] != b'MZ':
            continue
        pe = struct.unpack_from('<I', contents, 0x3c)[0]
        if struct.unpack_from('<H', contents, pe + 4)[0] != 0x8664:
            continue
        result = subprocess.run([str(seven), 'l', str(source)], capture_output=True, text=True, check=True)
        names = [line.split(':', 1)[1].strip() for line in result.stdout.splitlines() if line.startswith('OriginalFilename:')]
        assert len(names) == 1 and names[0].lower().endswith('.dll'), result.stdout[:1500]
        target = lab / names[0]
        shutil.copyfile(source, target)
        records.append({'file': names[0], 'sha256': hashlib.sha256(contents).hexdigest(), 'cab': cab['cab']})
assert records
report = {'result': 'EXTRACTED_ONLY', 'installerNotExecuted': True, 'runtimeInstallerSha256': hashlib.sha256(raw).hexdigest(),
          'runtimeUrl': 'https://aka.ms/vc14/vc_redist.x64.exe',
          'sevenZipUrl': 'https://github.com/ip7z/7zip/releases/download/26.04/7z2604-mac.tar.xz',
          'sevenZipSha256': hashlib.sha256((tools / '7z-mac.tar.xz').read_bytes()).hexdigest(),
          'records': records, 'cabinets': cab_records,
          'sourceDolphinSha256': hashlib.sha256(Path('work/research/dolphin/Dolphin-x64/Dolphin.exe').read_bytes()).hexdigest(),
          'labDolphinSha256': hashlib.sha256((lab / 'Dolphin.exe').read_bytes()).hexdigest(),
          'scriptSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'scope': 'Private local tools only, no system installation or redistribution.'}
Path('work/private-game/static-recomp/dolphin-probe/runtime-provenance.json').write_text(json.dumps(report, indent=2) + '\n')
print('Extracted', len(records), 'Microsoft x64 DLLs into isolated Dolphin lab; installer not executed')
