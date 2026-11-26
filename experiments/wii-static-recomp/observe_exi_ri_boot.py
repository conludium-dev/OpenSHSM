"""Observe the post-memory-protection EXI refusal without accepting another device."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/observe_fp64_boot.py')
body = parent.read_text().replace('mass-ai-clock-boot', 'mass-memory-protection-boot').replace('mass-fp64-boot-observer', 'mass-exi-ri-observer')
body = body.replace("'vi-clock-backend.cpp'):", "'vi-clock-backend.cpp', 'memory-protection-bat-plan.h'):")
start = body.index("    if row['file'] == 'output_1.cpp':")
end = body.index("        source = output / row['file']", start)
replacement = '''    if row['file'] == 'output_62.cpp':
        original = Path(row['source']).read_text()
        start = original.index('void func_8020E310(')
        end = original.index('\\nvoid func_', start + 1)
        def observe(match):
            address, opcode = (int(match[group], 16) for group in (1, 2))
            section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
            assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == opcode
            before = match[0]
            after = before.replace('experiment_si_query_read32', 'experiment_exi_ri_observe')
            changes.append({'address': address, 'opcode': opcode, 'before': before, 'after': after})
            return after
        block = re.sub(r'    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\\n[^\\n]*experiment_si_query_read32[^\\n]*', observe, original[start:end])
        assert changes
'''
body = body[:start] + replacement + body[end:]
body = body.replace('fp64_boot_observer.h', 'exi_ri_observer.h').replace('FP64_REFUSAL', 'EXI_RI_REFUSAL').replace('EXACT_FP64_REFUSAL_RETAINED', 'EXACT_EXI_RI_REFUSAL_RETAINED')
body = body.replace("runtime / 'src/hw/hw_dsp.cpp'", "experiment / 'dsp_startup_backend.cpp'")
body = body.replace("'-include', 'bit', '-DSHSM_SI_EXTERNAL_DELIVERY'", "'-include', 'bit', '-include', str(experiment / 'exi_ri_observer.h'), '-DSHSM_SI_EXTERNAL_DELIVERY'")
body = body.replace("'-I', str(private / 'mass-current'),\n            '-c'", "'-I', str(private / 'mass-current'), '-I', str(output),\n            '-c'")
body = body.replace("environment.pop('SHSM_AI_CLOCK_NO_BUS', None)", "environment.pop('SHSM_AI_CLOCK_NO_BUS', None)\nfor flag in ('SHSM_FLUSH_DISABLED', 'SHSM_FPU_DISABLED', 'SHSM_DSP_DISABLED', 'SHSM_DSP_LOST_DMA', 'SHSM_DSP_LOST_MAIL', 'SHSM_MI_DISABLED', 'SHSM_MI_NO_SIZE_FIXTURE'): environment.pop(flag, None)")
body = body.replace("'Delegates original FP64 guard; no new permission, FPU exception delivery or boot advance.'", "'Delegates existing EXI guard; no new MSR/device permission or boot advance.'")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-exi-ri-observer/observation.json')
report = json.loads(path.read_text())
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
