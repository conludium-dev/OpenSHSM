"""Account proven finite work separately while retaining the existing scheduler validation."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_memory936_boot.py'
body = parent.read_text().replace("base = private / 'mass-mem2-loader-boot'", "base = private / 'mass-memory936-boot'")
body = body.replace("output = private / 'mass-memory936-boot'", "output = private / 'mass-finite-mem2-boot'")
start = body.index("removed = ")
end = body.index('records = []', start)
body = body[:start] + '''removed = ''
(output / 'finite_mem2_clear.h').write_bytes((experiment / 'finite_mem2_clear.h').read_bytes())
entry_path = output / 'mass_boot.cpp'
entry = entry_path.read_text()
marker = '    nwii::runtime::experiment_sram_attach_memory(context);'
assert entry.count(marker) == 1
entry_path.write_text(entry.replace(marker, marker + '\\n    nwii::runtime::experimentFiniteMem2 = !std::getenv("SHSM_FINITE_MEM2_DISABLED");'))
wrapper_path = output / 'boot-wrapper.cpp'
wrapper = wrapper_path.read_text()
marker = '    const int result = original_boot_main(3, argv);'
assert wrapper.count(marker) == 1
wrapper_path.write_text(wrapper.replace(marker, marker + '\\n    std::cout << "BOOT_FINITE_MEM2 steps=" << nwii::runtime::experimentFiniteMem2Steps << " returned=" << nwii::runtime::experimentFiniteMem2Returned << "\\\\n";'))
''' + body[end:]
old = '        merged = source.replace(old_body, new_body, 1)\n        assert merged.replace(new_body, old_body, 1) == source'
assert body.count(old) == 1
body = body.replace(old, '''        function_start = source.index('void func_80213060(CPUContext& ctx) {')
        function_end = source.index('void func_80213090(CPUContext& ctx) {', function_start)
        original_function = source[function_start:function_end]
        before_poll = '        if (process_pending_callbacks(ctx)) return;'
        after_poll = '        if (nwii::runtime::experiment_finite_mem2_poll(ctx, process_pending_callbacks)) return;'
        before_return = '    ctx.pc = ctx.lr; return;'
        after_return = '    nwii::runtime::experiment_finite_mem2_return(ctx);\\n' + before_return
        assert original_function.count(before_poll) == original_function.count(before_return) == 1
        changed_function = original_function.replace(before_poll, after_poll).replace(before_return, after_return)
        merged = source[:function_start] + changed_function + source[function_end:]
        assert merged.replace(changed_function, original_function, 1) == source''')
body = body.replace("str(output / 'dc_zero_frontend.h')", "str(output / 'finite_mem2_clear.h')")
body = body.replace("'SHSM_MEM2_LOADER_DISABLED')", "'SHSM_MEM2_LOADER_DISABLED', 'SHSM_FINITE_MEM2_DISABLED')")
body = body.replace("environment['SHSM_MI_DISABLED'] = '1'", "environment['SHSM_FINITE_MEM2_DISABLED'] = '1'")
body = body.replace("'BOOT_DCZERO ')", "'BOOT_DCZERO ', 'BOOT_FINITE_MEM2 ')")
body = body.replace("output / 'dc_zero_frontend.h', output / 'reset_code_frontend.h']", "output / 'dc_zero_frontend.h', output / 'reset_code_frontend.h', output / 'finite_mem2_clear.h']")
body = body.replace('MEMORY936_BOOT_REQUIRES_AUDIT', 'FINITE_MEM2_BOOT_REQUIRES_AUDIT')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
