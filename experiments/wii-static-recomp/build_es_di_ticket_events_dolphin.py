"""Observe all four original requests without overlapping private ticket output."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_di_burst_events_dolphin.py')
body = parent.read_text().replace("root / 'dolphin-di-burst'", "root / 'dolphin-es-di-ticket'").replace(
    'verify_di_burst_dolphin.py', 'verify_es_di_ticket_dolphin.py').replace(
    'dolphin-di-burst-events', 'dolphin-es-di-ticket-events').replace(
    'run_di_burst_events_disc_dolphin.ps1', 'run_es_di_ticket_events_disc_dolphin.ps1').replace(
    '0x806d1000, 0x806e0000', '0x806d1000, 0x80740000').replace(
    "(9, 0x8021a8d0, 0x38632a70, 'SelectThread_idle_context_prepare')",
    "(9, 0x8021a8d0, 0x38632a70, 'SelectThread_idle_context_prepare'), (13, 0x80249a90, 0x81410000, 'ESP_DiGetTicketView_return')")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-es-di-ticket-events/generation.json')
report = json.loads(path.read_text())
report['ticketEventsParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'][-2] = 'Ten non-branch replay observers preserve r0/r11/r12/CR/MSR; original displaced words replayed, no service behavior injected.'
report['limits'].append('Event arena80740000 avoids LAB ticket output806F4000; all endpoints/payloads must match unobserved control.')
path.write_text(json.dumps(report, indent=2) + '\n')
