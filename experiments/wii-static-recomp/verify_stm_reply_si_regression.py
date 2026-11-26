"""Run the existing current-object SI regression on the widened reply profile."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_stm_ack_si_regression.py')
body = parent.read_text().replace('stm-irq-native-ack', 'stm-reply-native')
body = body.replace('NEW_ACK_OBJECTS_SI16', 'NEW_REPLY_OBJECTS_SI16').replace('new ACK objects', 'new reply objects')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/stm-reply-native/si-regression.json')
report = json.loads(path.read_text())
report['parentVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
