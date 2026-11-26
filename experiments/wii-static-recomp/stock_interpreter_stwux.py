"""Restore the Wii-observed indexed word store with address update."""
import struct


SITE = 0x802D8974
WORD = 0x7CFC416E


def check_dol(dol):
    layout = struct.unpack('>64I', dol[:256])
    section = next(i for i in range(18)
        if layout[18 + i] <= SITE < layout[18 + i] + layout[36 + i])
    offset = layout[section] + SITE - layout[18 + section]
    if struct.unpack_from('>I', dol, offset)[0] != WORD or \
            WORD >> 26 != 31 or (WORD >> 1) & 1023 != 183:
        raise ValueError('Wii stwux instruction differs')


def adapt(source):
    marker = '        case 151: ctx.mmu.write32(ea_ra0(0) + ctx.gpr[rB], ctx.gpr[rD]); break;'
    if source.count(marker) != 1:
        raise ValueError('Interpreter indexed store site differs')
    addition = '''        case 183: {
            if (rA == 0 || rc) {
                throw std::runtime_error("Invalid stwux encoding: program exception routing unverified");
            }
            const uint32_t ea = ctx.gpr[rA] + ctx.gpr[rB];
            const uint32_t value = ctx.gpr[rD];
            ctx.mmu.write32(ea, value);
            ctx.gpr[rA] = ea;
            break;
        }
'''
    return source.replace(marker, marker + '\n' + addition.rstrip(), 1)
