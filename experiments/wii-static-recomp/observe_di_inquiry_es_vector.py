"""Read the actual next ES request after native Inquiry without admitting it."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/observe_di_burst_es_vector.py')
body = parent.read_text().replace('mass-di-burst-cache-boot', 'mass-di-inquiry-boot').replace(
    'mass-di-burst-es-vector-observer', 'mass-di-inquiry-es-vector-observer').replace(
    'audit_di_burst_cache_boot.py', 'audit_di_inquiry_boot.py').replace(
    'nwii::runtime::stmSubmitted == 36', 'nwii::runtime::stmSubmitted == 38')
body = body.replace("env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'",
    "env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'\\n"
    "env['SHSM_ES_TICKET_PATH'] = 'work/private-game/disc/DATA/ticket.bin'\\n"
    "env['SHSM_DI_LAB_INQUIRY_PATH'] = 'work/private-game/static-recomp/di-inquiry-device/dolphin-lab-inquiry.bin'")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
