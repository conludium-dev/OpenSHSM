"""Use the original Wii TV phone-audio option in desktop input mode only."""
import struct


def adapt(text, dol):
    address, expected = 0x800C771C, 0x4E800020
    header = struct.unpack('>64I', dol[:256])
    section = next(i for i in range(18) if header[18 + i] <= address
        and address + 4 <= header[18 + i] + header[36 + i])
    word = struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0]
    marker = f'loc_{address:08X}: ;\n'
    if word != expected or text.count(marker) != 1 or f'// 0x{address:08X}: {word:08X}' not in text:
        raise ValueError('Original Wii phone audio option getter changed')
    return '#include "stock_pc_phone_audio.h"\n' + text.replace(marker,
        marker + '    openshsm::experiment::pc_phone_audio_option(ctx);\n', 1)
