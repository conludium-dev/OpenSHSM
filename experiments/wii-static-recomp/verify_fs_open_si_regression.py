"""Replay original SI on actual FS OPEN profile objects with IPC admission off."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_stm_ack_si_regression.py')
body = parent.read_text().replace('stm-irq-native-ack', 'mass-fs-open-boot').replace("'attempt.json'", "'build.json'")
body = body.replace('NEW_ACK_OBJECTS_SI16', 'NEW_FS_OPEN_OBJECTS_SI16')
body = body.replace("host.write_text('#include ", "host.write_text('#include \"stm_async_dispatch.h\"\\n#include \"ipc_open_packet.h\"\\n#include ", 1)
marker = 'sources = [host,'
assert body.count(marker) == 1
injection = "host.write_text(host.read_text() + '\\nnamespace nwii::runtime { void experiment_stm_submit(CPUContext&, uint32_t) { throw std::runtime_error(\"Unexpected IPC in SI regression\"); } }\\n')\n"
body = body.replace(marker, injection + "sources = [output / 'stm_device.cpp', host,", 1)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
