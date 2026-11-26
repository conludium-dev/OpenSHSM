"""Reuse verified bias arithmetic at the next original constructor; retain all other code."""
from pathlib import Path
import re
import struct

experiment = Path('experiments/wii-static-recomp')
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assembly = Path('work/private-game/static-recomp/dtk-output/asm/auto_fn_80015234_text.s').read_text()
words = re.findall(r'/\* ([0-9A-F]{8}) ([0-9A-F]{8})  ((?:[0-9A-F]{2} ){3}[0-9A-F]{2}) \*/',assembly)
assert len(words) == 35
for address,offset,word in words:
    assert original[int(offset,16):int(offset,16) + 4] == bytes.fromhex(word)
layout = struct.unpack('>64I',original[:256])
def dol_bytes(address,size):
    for index in range(18):
        if layout[18 + index] <= address and address + size <= layout[18 + index] + layout[36 + index]:
            offset = layout[index] + address - layout[18 + index]
            return original[offset:offset + size]
    raise AssertionError('Unmapped original constant')
assert dol_bytes(0x8052b778,8) == bytes.fromhex('4330000080000000')
parent = experiment / 'build_fs_open_boot.py'
body = parent.read_text().replace("base = root / 'mass-exi-sync-ee-boot'", "base = root / 'mass-playrecord-dec-boot'").replace(
    "output = root / 'mass-fs-open-boot'", "output = root / 'mass-fp-registration-boot'").replace(
    "('audit_exi_sync_ee_boot.py', 'verify_fs_pending_dolphin.py', 'verify_fs_ack_dolphin.py')",
    "('audit_playrecord_dec_boot.py', 'verify_fp_registration_dolphin.py')").replace(
    "'stm_device.cpp', 'boot-quarantine.tsv'", "'stm_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'di_device.cpp', 'boot-quarantine.tsv'")
start,end = body.index("packet = output / 'ipc_open_packet.h'"),body.index('records = [dict(row)')
body = body[:start] + '''
front = output / 'ipc_ack_frontend.h'
wrapper = output / 'boot-wrapper.cpp'
(output / 'fp_registration_probe.h').write_bytes((experiment / 'fp_registration_probe.h').read_bytes())
replace(wrapper, 'int main(int argc, char** argv) {',
    '#include "fp_registration_probe.h"\\nint main(int argc, char** argv) {\\n    if (argc == 2 && std::string(argv[1]) == "--fp-registration-probe") { return experiment_fp_registration_probe(); }')
fs_source = runtime / 'src/hle/devices/fs_device.cpp'
''' + body[end:]
body = body.replace("('output_62.cpp', 'output_67.cpp')", "('output_2.cpp',)")
marker = "    source.write_bytes(Path(row['source']).read_bytes())"
assert body.count(marker) == 1
body = body.replace(marker,marker + '''
    replace(source, '    nwii::runtime::experiment_ni_guard(ctx, 0xec000828, 0x8001526c);\\n    ctx.fpr[0] = (float)(ctx.fpr[0] - ctx.fpr[1]); // fsubs',
        '    if (std::getenv("SHSM_FP_REGISTRATION_DISABLED")) { nwii::runtime::experiment_ni_guard(ctx, 0xec000828, 0x8001526c); }\\n    nwii::runtime::experiment_fsubs_integer_bias(ctx, 0xec000828);')
    replace(source, 'loc_800152BC: ;', 'loc_800152BC: ;\\n    if (ctx.msr == 0xa032 && nwii::runtime::stmSubmitted == 48) { std::cout << "FP_REGISTRATION_RETURN " << std::hex << ctx.fpscr << " " << nwii::runtime::bat_memory_read32(ctx,0x80529180) << " " << nwii::runtime::bat_memory_read32(ctx,0x80529184) << std::dec << std::endl; }')
''')
body = body.replace("output / 'stm_device.cpp', output / 'fs_device.cpp'", "output / 'stm_device.cpp', output / 'fs_device.cpp', output / 'es_device.cpp', output / 'di_device.cpp'")
body = body.replace("env['SHSM_FS_OPEN_DISABLED'] = '1'", "env['SHSM_FP_REGISTRATION_DISABLED'] = '1'")
body = body.replace("result = subprocess.run([str(exe),", "env.update(SHSM_PLAYRECORD_LAB_FILE='work/private-game/static-recomp/playrecord-fs-device/pc-owned-playrecord.bin',SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin',SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',SHSM_ES_LAB_CONSUMPTION='1',SHSM_DI_LAB_INQUIRY_PATH='work/private-game/static-recomp/di-inquiry-device/dolphin-lab-inquiry.bin',SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')\n    result = subprocess.run([str(exe),")
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
