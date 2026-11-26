"""Synchronize the guest instruction PC at SC before entering the existing HLE seam."""
import re
import struct

def adapt(text, dol):
    header = struct.unpack('>64I', dol[:256])
    sites = []
    pattern = r'(    // 0x([0-9A-F]{8}): 44000002\n    // sc \(System Call\)\n)(    nwii::runtime::handle_syscall\(ctx\);)'
    def replace(match):
        address = int(match[2], 16)
        section = next(i for i in range(18) if header[18 + i] <= address
            and address + 4 <= header[18 + i] + header[36 + i])
        offset = header[section] + address - header[18 + section]
        assert struct.unpack_from('>I', dol, offset)[0] == 0x44000002
        sites.append(address)
        return match[1] + f'    ctx.pc = 0x{address:08X};\n' + match[3]
    result = re.sub(pattern, replace, text)
    assert sites, 'No unsynchronized original SC sites found'
    assert result.count('nwii::runtime::handle_syscall(ctx);') == len(sites), 'Unsupported SC lowering shape'
    return result, sites

def adapt_emitter(text):
    marker = '    out << "    // sc (System Call)\\n";\n'
    assert text.count(marker) == 1
    return text.replace(marker, marker + '    out << "    ctx.pc = 0x" << std::hex << inst.address << std::dec << ";\\n";\n')
