"""Restore Wii-observed indexed halfword memory operations in the retained fallback."""
import struct


SITES = (0x80361354, 0x803613D4, 0x80361460)
WORD = 0x7C862AEE
LHZUX_SITE = 0x800AC4D8
LHZUX_WORD = 0x7C04026E
STHBRX_SITES = ((0x8036B290, 0x7C60072C), (0x8036B29C, 0x7C001F2C))


def check_dol(dol):
    layout = struct.unpack('>64I', dol[:256])
    for address, word in (*((site, WORD) for site in SITES), (LHZUX_SITE, LHZUX_WORD), *STHBRX_SITES):
        section = next(i for i in range(18)
            if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        offset = layout[section] + address - layout[18 + section]
        assert struct.unpack_from('>I', dol, offset)[0] == word


def adapt(source):
    zero_marker = '        case 279: ctx.gpr[rD] = ctx.mmu.read16(ea_ra0(0) + ctx.gpr[rB]); break;'
    assert source.count(zero_marker) == 1
    zero_addition = '''        case 311: {
            if (rA == 0 || rA == rD || rc) {
                throw std::runtime_error("Invalid lhzux encoding: program exception routing unverified");
            }
            const uint32_t ea = ctx.gpr[rA] + ctx.gpr[rB];
            const uint32_t value = ctx.mmu.read16(ea);
            ctx.gpr[rD] = value;
            ctx.gpr[rA] = ea;
            break;
        }
'''
    source = source.replace(zero_marker, zero_marker + '\n' + zero_addition.rstrip())
    marker = '        case 343: ctx.gpr[rD] = (int32_t)(int16_t)ctx.mmu.read16(ea_ra0(0) + ctx.gpr[rB]); break;'
    assert source.count(marker) == 1
    addition = '''        case 375: {
            if (rA == 0 || rA == rD || rc) {
                throw std::runtime_error("Invalid lhaux encoding: program exception routing unverified");
            }
            const uint32_t ea = ctx.gpr[rA] + ctx.gpr[rB];
            const uint32_t value = uint32_t(int32_t(int16_t(ctx.mmu.read16(ea))));
            ctx.gpr[rD] = value;
            ctx.gpr[rA] = ea;
            break;
        }
'''
    source = source.replace(marker, marker + '\n' + addition.rstrip())
    marker = '        case 407: ctx.mmu.write16(ea_ra0(0) + ctx.gpr[rB], (uint16_t)ctx.gpr[rD]); break;'
    assert source.count(marker) == 1
    addition = '''        case 918: {
            if (rc) {
                throw std::runtime_error("Invalid sthbrx encoding: program exception routing unverified");
            }
            const uint32_t ea = ea_ra0(0) + ctx.gpr[rB];
            const uint16_t value = uint16_t(ctx.gpr[rD]);
            ctx.mmu.write16(ea, uint16_t((value << 8) | (value >> 8)));
            break;
        }
'''
    return source.replace(marker, marker + '\n' + addition.rstrip())
