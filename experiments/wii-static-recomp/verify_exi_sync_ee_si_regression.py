"""Replay original SI on the actual EXISync EE objects with STM admission disabled."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_stm_async_si_regression.py')
body = parent.read_text().replace('mass-stm-async-boot', 'mass-exi-sync-ee-boot')
body = body.replace('NEW_ASYNC_OBJECTS_SI16', 'NEW_EXISYNC_EE_OBJECTS_SI16')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
