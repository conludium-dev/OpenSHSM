"""Prepare an opt-in observer in the existing VI callback; do not build or promote."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-dec-ee-gate/build.json'
parent = json.loads(parent_path.read_text())
source_path = Path(parent['sourcePath'])
assert sha(source_path) == parent['sourceSha256']
source = source_path.read_text()
start = source.index('          nwii::runtime::EventScheduler::get().schedule_recurring(')
end = source.index('\n      }\n      nwii::runtime::EventScheduler::get().advance', start)
before = source[start:end]
expected = '''          nwii::runtime::EventScheduler::get().schedule_recurring(
              vi_period, [](CPUContext& c, uint64_t) {

                  
                  
                  if ((nwii::runtime::hw::pi_intmr & 0x100) && !c.in_callback &&
                      !(nwii::runtime::hw::pi_intsr & 0x100) &&
                      (c.dispatch_saved_ctx == 0 || c.mmu.read32(0x800000E4) == 0)) {
                      nwii::runtime::hw::vi_trigger_interrupt();
                  }
              });'''
assert before == expected
after = '''          stock_vi_timer_profile::observer().registration(vi_period, ctx.tb_freq);
          nwii::runtime::EventScheduler::get().schedule_recurring(
              vi_period, [](CPUContext& c, uint64_t late) {
                  const auto reason = stock_vi_timer_profile::classify(
                      c, nwii::runtime::hw::pi_intmr, nwii::runtime::hw::pi_intsr);
                  stock_vi_timer_profile::observer().record(reason, late, c.tb_freq);
                  if (reason == stock_vi_timer_profile::Reason::Raised) {
                      nwii::runtime::hw::vi_trigger_interrupt();
                  }
              });'''
include = '#include "stock_vi_timer_profile.h"\n'
candidate = include + source.replace(before, after, 1)
assert candidate.removeprefix(include).replace(after, before, 1) == source
cache = Path(tempfile.mkdtemp(prefix='openshsm-vi-profile-', dir='/private/tmp'))
prepared = cache / 'ios.cpp'
prepared.write_text(candidate)
header = public / 'stock_vi_timer_profile.h'
probe = public / 'stock_vi_timer_profile_probe.cpp'
exe = cache / 'vi-gate-probe'
command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
    '-isysroot', '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
    '-UNDEBUG', str(probe), '-o', str(exe)]
subprocess.run(command, check=True, capture_output=True, timeout=30)
results = []
for enabled in [False, True]:
    environment = dict(os.environ)
    environment.pop('NWII_VI_TIMER_PROFILE', None)
    if enabled:
        environment['NWII_VI_TIMER_PROFILE'] = '1'
    result = subprocess.run([str(exe)], env=environment, capture_output=True, text=True,
        timeout=10, check=True)
    assert 'VI_GATE_CASES=32 MMU_READ_COUNTS_EQUAL' in result.stdout
    assert ('[VI_TIMER]' in result.stderr) == enabled
    results.append({'enabled': enabled, 'stdout': result.stdout, 'stderr': result.stderr})
output = root / 'vi-timer-profile'
output.mkdir(exist_ok=True)
runtime_object = cache / 'ios.cpp.o'
runtime_command = ['/Library/Developer/CommandLineTools/usr/bin/c++', *parent['arguments'],
    '-c', str(prepared), '-o', str(runtime_object)]
runtime_compile = subprocess.run(runtime_command, capture_output=True, text=True, timeout=90)
assert runtime_compile.returncode == 0, runtime_compile.stderr[-4000:]
report = {
    'result': 'VI_TIMER_PROFILE_IOS_COMPILED_GATE32_ENABLED_DISABLED_EQUAL',
    'parentBuildSha256': sha(parent_path), 'originalSourcePath': str(source_path),
    'originalSourceSha256': sha(source_path), 'preparedSourcePath': str(prepared),
    'preparedSourceSha256': sha(prepared), 'patch': [before, after],
    'compileCommand': command, 'executableSha256': sha(exe), 'runs': results,
    'runtimeCompileCommand': runtime_command, 'runtimeObjectPath': str(runtime_object),
    'runtimeObjectSha256': sha(runtime_object), 'runtimeCompilerStderr': runtime_compile.stderr,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), header, probe]},
    'limits': ['Actual current IOS object compiled, no archive/game executable linked or promoted.',
        '32 native truth-table cases preserve acceptance and MMU read count; not actual asynchronous IRQ proof.',
        'Existing recurring source, ordering, queue and VI trigger retained; optional diagnostic only.',
        'Actual callback regression fixtures and live reason counts remain pending.']}
(output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], prepared)
