"""Enable only the measured second flush caller in the existing startup profile."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/build_flush_ee_boot.py')
body = parent.read_text().replace("root / 'flush-ee-profile'", "root / 'flush-packet-profile'")
body = body.replace("root / 'mass-flush-ee-boot'", "root / 'mass-flush-packet-boot'")
body = body.replace('verify_flush_ee_native.py', 'verify_flush_packet_native.py')
marker = 'sources = [output /'
injection = '''entry = entry_path.read_text()
assert entry.count(marker) == 1
entry_path.write_text(entry.replace(marker, marker + '\\n    nwii::runtime::experimentFlushPacket = !std::getenv("SHSM_FLUSH_PACKET_DISABLED");'))
'''
assert body.count(marker) == 1
body = body.replace(marker, injection + marker, 1)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
