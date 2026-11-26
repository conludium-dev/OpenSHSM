"""Compile-check the complete generated inventory; retain failures rather than reporting a playable port."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import collections
import hashlib
import json
import re
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--objects', action='store_true')
args = parser.parse_args()
output = Path('work/private-game/static-recomp/mass-current')
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
generation = json.loads((output / 'generation.json').read_text())
files = (output / 'generated-files.txt').read_text().splitlines()
assert generation['result'] == 'PASS' and len(files) == generation['generatedFiles']
assert all(hashlib.sha256((output / name).read_bytes()).hexdigest() == generation['generatedSha256'][name] for name in files)
version = subprocess.run(['clang++', '--version'], capture_output=True, text=True, check=True).stdout
flags = ['-std=c++20', '-O0', '-ferror-limit=0', '-Wno-unknown-pragmas',
         '-I', str(upstream / 'nWiiRuntime/include'), '-I', str(output)]
if not args.objects:
    flags.append('-fsyntax-only')


def compile_file(name):
    path = output / name
    try:
        compile_arguments = ['-c', '-o', str(output / (name + '.o'))] if args.objects else []
        result = subprocess.run(['clang++', *flags, *compile_arguments, str(path)], capture_output=True, text=True, timeout=120)
        log = result.stdout + result.stderr
        code = result.returncode
    except subprocess.TimeoutExpired as error:
        log = 'Compiler timeout\n' + str(error.stderr or '')
        code = -1
    (output / (name + ('.object.log' if args.objects else '.compile.log'))).write_text(log)
    errors = re.findall(r'error: (.+)', log)
    record = {'file': name, 'exitCode': code, 'errors': errors, 'warnings': len(re.findall(r'warning:', log)),
              'sourceSha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    if args.objects and code == 0:
        record['objectSha256'] = hashlib.sha256((output / (name + '.o')).read_bytes()).hexdigest()
    return record


records = []
with ThreadPoolExecutor(max_workers=2) as executor:
    futures = [executor.submit(compile_file, name) for name in files]
    for future in as_completed(futures):
        records.append(future.result())
        if len(records) % 5 == 0 or len(records) == len(files):
            print(f'Checked {len(records)}/{len(files)} files; failures={sum(record["exitCode"] != 0 for record in records)}', flush=True)
records.sort(key=lambda record: record['file'])
categories = collections.Counter(error for record in records for error in record['errors'])
generated_counts = collections.Counter()
entry_file = None
for name in files:
    text = (output / name).read_text()
    generated_counts['functionDefinitions'] += len(re.findall(r'^void func_[0-9A-F]{8}\(', text, re.MULTILINE))
    generated_counts['unimplementedSites'] += text.count('UNIMPLEMENTED')
    generated_counts['interpreterRequests'] += text.count('interpret_step(ctx)')
    generated_counts['stubComments'] += len(re.findall(r'//[^\n]*stub', text))
    generated_counts['approximationComments'] += len(re.findall(r'//[^\n]*(?:approxim|ignore)', text))
    if re.search(r'^void func_80006310\(', text, re.MULTILINE):
        entry_file = name
report = {'result': 'PASS' if all(record['exitCode'] == 0 for record in records) else 'INCOMPLETE',
          'scope': 'Complete generated C++ object compilation inventory; no linking/execution/gameplay acceptance.' if args.objects else
                   'Complete generated C++ syntax compilation inventory only; no linking, execution or gameplay acceptance.',
          'records': records, 'filesChecked': len(records), 'failedFiles': sum(record['exitCode'] != 0 for record in records),
          'compilerVersion': version, 'flags': flags, 'errorCategories': dict(categories),
          'generatedMarkers': dict(generated_counts), 'entryFile': entry_file,
          'generationReportSha256': hashlib.sha256((output / 'generation.json').read_bytes()).hexdigest(),
          'limits': ['Successful compilation does not verify original instruction semantics, HLE bindings, initialization, GX/audio/IOS/input or game assets.',
                     'Static marker counts locate unsupported/approximate paths; interpreter requests also include entry-dispatch guards and are not executed fallback counts.']}
(output / ('objects.json' if args.objects else 'compilation.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], 'whole generation syntax gate:', report['filesChecked'], 'files;', report['failedFiles'], 'failed;', dict(generated_counts), flush=True)
