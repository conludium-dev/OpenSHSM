"""Identify the exact memory-protection write; do not grant access."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/observe_fp64_boot.py')
body = parent.read_text().replace('mass-ai-clock-boot', 'mass-audio-init-boot').replace('mass-fp64-boot-observer', 'mass-memory-protection-observer')
start = body.index("    if row['file'] == 'output_1.cpp':")
end = body.index("        source = output / row['file']", start)
replacement = '''    if row['file'] == 'output_63.cpp':
        original = Path(row['source']).read_text()
        before = '    // 0x802186AC: B0044020\\n    nwii::runtime::bat_memory_write16(ctx, ctx.gpr[4] + 16416, (uint16_t)ctx.gpr[0]); // sth'
        after = before.replace('bat_memory_write16(ctx,', 'experiment_memory_protection_observe(ctx,').replace('(uint16_t)ctx.gpr[0]);', '(uint16_t)ctx.gpr[0], 0x802186ac);')
        assert original.count(before) == 1
        section = next(i for i in range(7) if layout[18 + i] <= 0x802186ac < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[section] + 0x802186ac - layout[18 + section])[0] == 0xb0044020
        changes.append({'address': 0x802186ac, 'opcode': 0xb0044020, 'before': before, 'after': after})
'''
body = body[:start] + replacement + body[end:]
body = body.replace('source.write_text(original[:start] + block + original[end:])', 'source.write_text(original.replace(before, after))')
body = body.replace('fp64_boot_observer.h', 'memory_protection_observer.h').replace('FP64_REFUSAL', 'MI_INIT_REFUSAL').replace('EXACT_FP64_REFUSAL_RETAINED', 'EXACT_MI_INIT_REFUSAL_RETAINED')
body = body.replace("runtime / 'src/hw/hw_dsp.cpp'", "experiment / 'dsp_startup_backend.cpp'")
body = body.replace("'-include', 'bit', '-DSHSM_SI_EXTERNAL_DELIVERY'", "'-include', 'bit', '-include', str(experiment / 'memory_protection_observer.h'), '-DSHSM_SI_EXTERNAL_DELIVERY'")
body = body.replace("environment.pop('SHSM_AI_CLOCK_NO_BUS', None)", "environment.pop('SHSM_AI_CLOCK_NO_BUS', None)\nfor flag in ('SHSM_FLUSH_DISABLED', 'SHSM_FPU_DISABLED', 'SHSM_DSP_DISABLED', 'SHSM_DSP_LOST_DMA', 'SHSM_DSP_LOST_MAIL'): environment.pop(flag, None)")
body = body.replace("'Delegates original FP64 guard; no new permission, FPU exception delivery or boot advance.'", "'Delegates existing BAT write16 guard; no new MI permission or boot advance.'")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-memory-protection-observer/observation.json')
report = json.loads(path.read_text())
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
