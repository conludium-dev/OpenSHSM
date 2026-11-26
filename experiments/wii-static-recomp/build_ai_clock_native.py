"""Compile original clock initialization under an explicit bounded PC register profile."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_si_query_native.py'
body = parent.read_text().replace('si-query-native', 'ai-clock-native').replace('si-query-host', 'ai-clock-host').replace('si-query-probe', 'ai-clock-probe')
body = body.replace('verify_si_query_dolphin.py', 'verify_ai_clock_dolphin.py').replace('dolphin-si-query-callback/comparison.json', 'dolphin-ai-clock/comparison.json')
body = body.replace('si_query_frontend.h', 'ai_clock_profile.h').replace('si_query_host.cpp', 'ai_clock_host.cpp')
body = body.replace('experiment_si_query_', 'experiment_ai_clock_')
body = body.replace('si_idle_backend.h', 'ai_clock_profile.h').replace('si_query_backend.h', 'ai_clock_profile.h')
host_marker = "body = (experiment / 'exi_getid_host.cpp').read_text().replace('int main(int argc, char** argv)', 'int unused_getid_main(int argc, char** argv)')"
assert body.count(host_marker) == 1
body = body.replace(host_marker, host_marker + "\nassert body.count('context.inst_count > 100000') == 1\nbody = body.replace('context.inst_count > 100000', 'context.inst_count > 1000000')")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/ai-clock-native')
path = output / 'build.json'
report = json.loads(path.read_text())
report['baseBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['hostInputSha256'] = hashlib.sha256((experiment / 'ai_clock_host.cpp').read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
