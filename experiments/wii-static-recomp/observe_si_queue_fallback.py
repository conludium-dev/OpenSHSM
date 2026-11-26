"""Print the native stack at the forbidden fallback; never execute an interpreter."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_si_queue_boot.py')
source = parent.read_text().replace('mass-si-queue-boot', 'mass-si-queue-fallback-observer')
marker = "exec(compile(body, str(parent), 'exec'), {'__file__': __file__})"
assert source.count(marker) == 1
before = 'void interpret_step(CPUContext&) { stop("Interpreter fallback forbidden"); }'
after = '''void interpret_step(CPUContext& context) {
    void* frames[24];
    const int count = backtrace(frames, 24);
    char** names = backtrace_symbols(frames, count);
    std::cout << "FALLBACK_SITE pc=" << std::hex << context.pc << " lr=" << context.lr << std::dec << '\\n';
    if (names) {
        for (int index = 0; index < count; ++index) {
            std::cout << "FALLBACK_FRAME " << index << ' ' << names[index] << '\\n';
        }
        std::free(names);
    }
    stop("Interpreter fallback forbidden");
}'''
injection = '''entry_path = output / 'mass_boot.cpp'
entry = entry_path.read_text()
before = BEFORE
after = AFTER
assert entry.count(before) == 1
entry_path.write_text('#include <execinfo.h>\\n#include <cstdlib>\\n' + entry.replace(before, after))
'''.replace('BEFORE', repr(before)).replace('AFTER', repr(after))
source = source.replace(marker, "body = body.replace(\"for row in build['records']:\", " + repr(injection) + " + \"for row in build['records']:\", 1)\n" + marker)
exec(compile(source, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-si-queue-fallback-observer')
path = output / 'build.json'
report = json.loads(path.read_text())
report['entrySha256'] = hashlib.sha256((output / 'mass_boot.cpp').read_bytes()).hexdigest()
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'].append('Diagnostic stack only at existing interpreter refusal; no original function body changed.')
path.write_text(json.dumps(report, indent=2) + '\n')
print('\n'.join(line for line in (output / 'observed-boot.log').read_text().splitlines() if line.startswith('FALLBACK_')))
