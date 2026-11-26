"""Launch local Ghidra without changing the user's launcher/JDK preference files."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('.').resolve()
tools = root / '_scratch/tmp/wii-static-recomp-tools'
sdk = tools / 'ghidra-sdk/ghidra_12.1.4_PUBLIC'
jdk = tools / 'jdk-sdk/jdk-21.0.12.1+1/Contents/Home'
private = root / 'work/private-game/static-recomp'
output = private / 'nwii-current'
command = [str(jdk / 'bin/java'), '-Xmx2G', '-Djava.awt.headless=true',
           '-Djava.system.class.loader=ghidra.GhidraClassLoader',
           '-Dapplication.settingsdir=' + str(tools / 'ghidra-settings'),
           '-Dapplication.cachedir=' + str(tools / 'ghidra-cache'),
           '-cp', str(sdk / 'Ghidra/Framework/Utility/lib/Utility.jar'),
           'ghidra.Ghidra', 'ghidra.app.util.headless.AnalyzeHeadless', str(private), 'shsm-probe-ppc32',
           *(['-process', 'auto_03_800F2228_text.o'] if (private / 'shsm-probe-ppc32.gpr').exists() else
             ['-import', str(private / 'dtk-output/obj/auto_03_800F2228_text.o'), '-processor', 'PowerPC:BE:32:default', '-cspec', 'default']),
           '-scriptPath', str(root / 'experiments/wii-static-recomp'),
           '-postScript', 'ExportRecompCheck.java', str(output), '-analysisTimeoutPerFile', '180']
result = subprocess.run(command, capture_output=True, text=True, timeout=300)
log = result.stdout + result.stderr
(private / 'ghidra-analysis.log').write_text(log)
assert result.returncode == 0 and 'SHSM_RECOMP_GHIDRA_PASS:24instructions/96bytes/decompiler' in log, log[-3000:]
report = {'result': 'PASS', 'version': '12.1.4', 'boundaryBytes': 96, 'instructions': 24,
          'objectSha256': hashlib.sha256((private / 'dtk-output/obj/auto_03_800F2228_text.o').read_bytes()).hexdigest(),
          'decompilerExecutableSha256': hashlib.sha256((sdk / 'Ghidra/Features/Decompiler/os/mac_arm_64/decompile').read_bytes()).hexdigest(),
          'scriptSha256': hashlib.sha256((root / 'experiments/wii-static-recomp/ExportRecompCheck.java').read_bytes()).hexdigest(),
          'decompiledSha256': hashlib.sha256((output / 'ghidra-selected.c').read_bytes()).hexdigest(),
          'limits': ['Independent Ghidra PPC instruction/decompiler check of dtk relocatable object; relocations change imported addresses.',
                     'Ghidra MCP is not configured; local headless verifier used without network service or app-config changes.']}
(private / 'ghidra-verification.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS:Ghidra24instructions/96bytes/decompiler with local settings/cache')
