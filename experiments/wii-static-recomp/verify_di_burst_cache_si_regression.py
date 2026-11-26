"""Replay original SI on the exact cache/ES native objects, not physical hardware."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_fs_open_si_regression.py')
body = parent.read_text().replace('mass-fs-open-boot', 'mass-di-burst-cache-boot').replace(
    'NEW_FS_OPEN_OBJECTS_SI16', 'NEW_DI_BURST_CACHE_OBJECTS_SI16')
body = body.replace('void experiment_stm_submit(CPUContext&, uint32_t) {',
    'void experiment_di_burst_ack(CPUContext&, uint32_t) { throw std::runtime_error(std::string()); } void experiment_stm_submit(CPUContext&, uint32_t) {')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
