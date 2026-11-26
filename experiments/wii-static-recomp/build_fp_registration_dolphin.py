"""Execute the unchanged35-instruction constructor and capture its global registrations."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/build_fp_initializer_dolphin.py')
body = parent.read_text().replace('dolphin-fp-initializer','dolphin-fp-registration').replace(
    'run_fp_initializer_dolphin.ps1','run_fp_registration_dolphin.ps1').replace(
    '0x8000c2f4','0x80015234').replace('0x80529158','0x80529180').replace(
    'stride = 0x80600000,0x680000,736','stride = 0x80600000,0x680000,800').replace(
    "'functionBytes':56","'functionBytes':140").replace('14-instruction','35-instruction')
marker = '    returns.append(len(code))'
assert body.count(marker) == 1
body = body.replace(marker,'''    pointer(code,12,0x8052a518)
    pointer(code,0,0xdeadbeef)
    code.append(dform(36,0,12,0))
''' + marker)
marker = '    code.extend(marker)'
assert body.count(marker) == 1
body = body.replace(marker,'''    for field,address in enumerate((0x80529188,0x8052918c,0x80529190,0x80529194,0x8052a518,
        0x8045a6c8,0x8045a6cc,0x8045a6d0,0x8045a6d4,0x8045a6d8,0x8045a6dc)):
        pointer(code,11,address)
        code.extend([dform(32,0,11,0),dform(36,0,12,736 + field * 4)])
''' + marker)
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
