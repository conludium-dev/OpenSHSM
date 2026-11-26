"""Compare this whole constructor on the real125-object module against its original capture."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_fp_initializer_native.py')
body = parent.read_text().replace('fp-initializer','fp-registration').replace(
    'fp_initializer','fp_registration').replace('FP_INITIALIZER_PROBE','FP_REGISTRATION_PROBE').replace(
    'index * 736','index * 800').replace('(index + 1) * 736','(index + 1) * 800')
marker = "struct.unpack_from('>Q',row,200)[0],struct.unpack_from('>Q',row,456)[0]])"
assert body.count(marker) == 1
body = body.replace(marker,"struct.unpack_from('>Q',row,200)[0],struct.unpack_from('>Q',row,456)[0],*struct.unpack_from('>11I',row,736)])")
body = body.replace('Whole14-instruction','Whole35-instruction').replace('actual boot module','actual boot module, including two global object records and destructor-chain order')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
