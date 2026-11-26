"""Record existing DSP integration gaps and source-level compatibility risks."""
from pathlib import Path
import hashlib
import json
import re

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'mass-dsp-access-observer'
base = private / 'mass-flush-syscall-boot'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
observation = json.loads((output / 'observation.json').read_text())
assert observation['builderSha256'] == sha(experiment / 'observe_dsp_access.py')
assert observation['observerSha256'] == sha(experiment / 'dsp_access_observer.h')
assert observation['parentBuilderSha256'] == sha(experiment / 'observe_fp64_boot.py')
assert observation['baseBootSha256'] == sha(base / 'boot.json')
assert observation['logSha256'] == sha(output / 'boot.log')
assert observation['executableSha256'] == sha(output / 'openshsm-mass-boot')
assert observation['diagnostic'] == 'DSP_ACCESS_REFUSAL instruction=80212d40 address=cc005012 physical=c005012 value=43 msr=2032 lr=80212d38 wimg=5 slot=1 width=2'
assert len(observation['records']) == 125 and len(observation['changes']) == 1
change = observation['changes'][0]
for row in observation['records']:
    assert row['sourceSha256'] == sha(Path(row['source'])) and row['objectSha256'] == sha(Path(row['object']))
    if row['file'] == 'output_63.cpp':
        original = Path(row['inputSource']).read_text()
        assert sha(Path(row['inputSource'])) == row['inputSourceSha256']
        assert original.count(change['before']) == 1
        assert Path(row['source']).read_text() == original.replace(change['before'], change['after'])
for path, digest in observation['sourceHashes'].items():
    assert sha(Path(path)) == digest
log = (output / 'boot.log').read_text()
assert re.search(r'^BOOT_BOUNDARY pc=80212d38 lr=80212d38 msr=2032 calls=\d+ reason=BAT MMIO/locked-cache/unmapped backing access unavailable$', log, re.M)
assert 'BOOT_FLUSH entries=1 phase=0 barriers=1\n' in log
assert 'BOOT_FPU entries=1 vector=0 resume=800060f4\n' in log
source_path = runtime / 'src/hw/hw_dsp.cpp'
source = source_path.read_text()
anchors = ['dispatcher.register_region(0xCC005000, 0xCC0050FF,', 'static uint16_t dsp_control = 0x0800;',
    'bool was_halted = (dsp_control & 0x0800) != 0;', 'ar_size = val & 0xFFFF;',
    'dsp_mbox_dsp_hi = 0xDCD1;', 'EventScheduler::get().schedule_recurring(g_ctx_ptr->tb_freq / 200, adma_event_cb);']
assert all(anchor in source for anchor in anchors)
entry = (base / 'mass_boot.cpp').read_text()
wrapper = (base / 'boot-wrapper.cpp').read_text()
assert 'register_dsp(' not in entry + wrapper
assert 'g_mmu =' not in entry + wrapper and 'g_ctx_ptr =' not in entry + wrapper
(output / 'backend-audit.json').write_text(json.dumps({'result': 'EXACT_DSP_REFUSAL_AND_EXISTING_BACKEND_GAPS_RECORDED',
    'auditorSha256': sha(Path(__file__)), 'observationSha256': sha(output / 'observation.json'),
    'vendorSource': str(source_path), 'vendorSourceSha256': sha(source_path), 'anchors': anchors,
    'facts': ['DSP is linked but not registered by this boot wrapper; BAT write16 still refuses the mapped register.',
        'Vendor uses0x0800 for initial/was_halted state; Dolphin UDSPControl defines DSPHalt bit2 (0x0004), DSPInit bit11.',
        'Vendor AR info writes retain16bits; Dolphin reference mask is0x007F. Current measured access value0x43 does not expose that difference.',
        'Mailbox replies are protocol shortcuts; AR/audio DMA depend on existing global RAM/CPU pointers and scheduler not bound by this wrapper.'],
    'referenceSources': ['https://raw.githubusercontent.com/dolphin-emu/dolphin/master/Source/Core/Core/HW/DSP.cpp',
        'https://raw.githubusercontent.com/dolphin-emu/dolphin/master/Source/Core/Core/HW/DSP.h'],
    'limits': ['Vendor/reference source comparison, not dynamic original SHSM DSP behavior or physical Wii proof.',
        'No DSP permission/registration, vendor edit, new backend or boot advance.'],
    'next': 'Measure original AIInit DSP reset/register/DMA/mailbox path before routing a bounded contract into existing backend.'}, indent=2) + '\n')
print('PASS exact DSP access/refusal retained; existing backend registration, masks, mailbox and scheduler gaps recorded')
