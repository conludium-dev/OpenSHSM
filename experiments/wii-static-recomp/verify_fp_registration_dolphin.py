"""Check original arithmetic and both global-object registrations, not decompiler aliases."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_fp_initializer_dolphin.py')
body = parent.read_text().replace('fp-initializer','fp-registration').replace(
    'fp_initializer','fp_registration').replace('128 * 736','128 * 800').replace(
    "* 736","* 800").replace('(14,56,56)','(35,140,140)').replace(
    "    assert struct.unpack_from('>I',row,32)[0] == integer",
    "    assert struct.unpack_from('>11I',row,736) == (0,0,0,0,0x8045a6d4,0xdeadbeef,0x801a92bc,0x80529188,0x8045a6c8,0x801a92bc,0x80529190)")
body = body.replace('708,36,32):','708,36,736,752,756,760,764,768,772,776):').replace(
    'mutants == 1152','mutants == 2048').replace('1152 mutations','2048 mutations').replace(
    'original14 instructions','original35 instructions')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
