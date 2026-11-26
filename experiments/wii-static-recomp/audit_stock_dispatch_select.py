"""Compare helper-only candidate to the correct-cadence parent using owned packets."""
from pathlib import Path
import json

base = Path('experiments/wii-static-recomp/audit_stock_current_vi_timer.py')
script = base.read_text()
script = script.replace('window-current-vi-timer', 'window-dispatch-select')
script = script.replace('current-vi-timer', 'dispatch-select')
script = script.replace('"parent_path = root / \'window-dec-ee-gate/build.json\'"',
    '"parent_path = root / \'window-vi-busy-latch/build.json\'"')
script = script.replace('window-dec-ee-gate/live-input-audit.json', 'window-vi-busy-latch/live-input-audit.json')
script = script.replace('DEC_EE_GATE_LATE_LIVE_PACKET_VISUAL_AUDIO_AUDITED', 'CURRENT_TIMER_ONLY_LATE_PACKET_VISUAL_AUDIO_AUDITED')
script = script.replace('headless-windowed-dec-ee-gate', 'headless-windowed-vi-busy-latch')
script = script.replace("{'timer_only': False}", "{'timer_only': True}")
script = script.replace('CURRENT_TIMER_MAIN_ONLY_LINK_SOURCE_SDK_MARKERS_VERIFIED',
    'DISPATCH_SELECT_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_EQUAL')
scope = {'__file__': __file__}
exec(compile(script, str(base), 'exec'), scope)
output, packet = scope['output'], scope['packet']
packet.update(result='DISPATCH_SELECT_LIVE_PARENT_PACKETS_SDK_AUDIO_AUDITED',
    baseAuditorSha256=scope['sha'](base), auditorSha256=scope['sha'](Path(__file__)))
packet['limits'].append('Only pure index helper changed; same authoritative routes/master/VI60/deadlines retained. Separate contexts not controlled exclusive FPS gain.')
(output / 'live-input-audit.json').write_text(json.dumps(packet, indent=2) + '\n')
print(packet['result'])
