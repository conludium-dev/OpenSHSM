"""Reuse the boot observer builder to identify the exact refused DSP write."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/observe_fp64_boot.py')
body = parent.read_text().replace('mass-ai-clock-boot', 'mass-flush-syscall-boot').replace('mass-fp64-boot-observer', 'mass-dsp-access-observer')
start = body.index("    if row['file'] == 'output_1.cpp':")
end = body.index('        source = output / row[\'file\']', start)
replacement = '''    if row['file'] == 'output_63.cpp':
        original = Path(row['source']).read_text()
        before = '    // 0x80212D40: B0035012\\n    nwii::runtime::bat_memory_write16(ctx, ctx.gpr[3] + 20498, (uint16_t)ctx.gpr[0]); // sth'
        after = before.replace('bat_memory_write16(ctx,', 'experiment_dsp_write_observe(ctx,').replace('(uint16_t)ctx.gpr[0]);', '(uint16_t)ctx.gpr[0], 0x80212d40);')
        assert original.count(before) == 1
        section = next(i for i in range(7) if layout[18 + i] <= 0x80212d40 < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[section] + 0x80212d40 - layout[18 + section])[0] == 0xb0035012
        changes.append({'address': 0x80212d40, 'opcode': 0xb0035012, 'before': before, 'after': after})
'''
body = body[:start] + replacement + body[end:]
body = body.replace('source.write_text(original[:start] + block + original[end:])', 'source.write_text(original.replace(before, after))')
body = body.replace('fp64_boot_observer.h', 'dsp_access_observer.h').replace('FP64_REFUSAL', 'DSP_ACCESS_REFUSAL').replace('EXACT_FP64_REFUSAL_RETAINED', 'EXACT_DSP_ACCESS_REFUSAL_RETAINED')
body = body.replace("environment.pop('SHSM_AI_CLOCK_NO_BUS', None)", "environment.pop('SHSM_AI_CLOCK_NO_BUS', None)\nenvironment.pop('SHSM_FLUSH_DISABLED', None)\nenvironment.pop('SHSM_FPU_DISABLED', None)")
body = body.replace("'Delegates original FP64 guard; no new permission, FPU exception delivery or boot advance.'", "'Delegates existing BAT write16 guard; no new MMIO permission or boot advance.'")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-dsp-access-observer/observation.json')
report = json.loads(path.read_text())
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
