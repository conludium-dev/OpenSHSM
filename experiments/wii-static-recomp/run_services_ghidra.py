"""Independent Ghidra disassembly of the original PPC service object, isolated from first milestone."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('.').resolve()
tools = root / '_scratch/tmp/wii-static-recomp-tools'
sdk = tools / 'ghidra-sdk/ghidra_12.1.4_PUBLIC'
jdk = tools / 'jdk-sdk/jdk-21.0.12.1+1/Contents/Home'
output = root / 'work/private-game/static-recomp/phone-services'
obj = root / 'work/private-game/static-recomp/dtk-output/obj/auto_03_800E6590_text.o'
command = [str(jdk / 'bin/java'), '-Xmx2G', '-Djava.awt.headless=true',
           '-Djava.system.class.loader=ghidra.GhidraClassLoader',
           '-Dapplication.settingsdir=' + str(tools / 'ghidra-settings'),
           '-Dapplication.cachedir=' + str(tools / 'ghidra-cache'),
           '-cp', str(sdk / 'Ghidra/Framework/Utility/lib/Utility.jar'),
           'ghidra.Ghidra', 'ghidra.app.util.headless.AnalyzeHeadless', str(output), 'services-ppc32',
           *(['-process', obj.name] if (output / 'services-ppc32.gpr').exists() else
             ['-import', str(obj), '-processor', 'PowerPC:BE:32:default', '-cspec', 'default']),
           '-scriptPath', str(root / 'experiments/wii-static-recomp'),
           '-postScript', 'ExportServicesCheck.java', str(output), '-analysisTimeoutPerFile', '180']
result = subprocess.run(command, capture_output=True, text=True, timeout=300)
log = result.stdout + result.stderr
(output / 'ghidra.log').write_text(log)
assert result.returncode == 0 and 'SHSM_SERVICES_GHIDRA_PASS:45+320instructions' in log, log[-4000:]
report = {'result': 'PASS', 'instructions': 365, 'objectSha256': hashlib.sha256(obj.read_bytes()).hexdigest(),
          'scriptSha256': hashlib.sha256((root / 'experiments/wii-static-recomp/ExportServicesCheck.java').read_bytes()).hexdigest(),
          'outputsSha256': {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in output.glob('*-ghidra.*')},
          'limits': ['Original relocatable PPC object; supplied dtk symbol lengths guide sequential disassembly.',
                     'Inferred Ghidra function body sizes recorded separately; successful decompilation does not establish complete switch CFG or audio behavior.',
                     'Behavioral comparison uses original DOL bytes in an independent PPC oracle; no Ghidra MCP/server or user config change.']}
(output / 'ghidra.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS:Ghidra365original service instructions decoded; inferred CFG scope remains explicit')
