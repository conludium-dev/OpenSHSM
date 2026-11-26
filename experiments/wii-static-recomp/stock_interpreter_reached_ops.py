"""Extend the retained interpreter for three omissions observed in owned play logs."""


def adapt(text):
    marker = '        case 23:  ctx.gpr[rD] = ctx.mmu.read32(ea_ra0(0) + ctx.gpr[rB]);'
    assert text.count(marker) == 1
    addition = '''        case 55: {
            if (rA == 0 || rA == rD || rc) {
                throw std::runtime_error("Invalid lwzux encoding: program exception routing unverified");
            }
            const uint32_t ea = ctx.gpr[rA] + ctx.gpr[rB];
            const uint32_t value = ctx.mmu.read32(ea);
            ctx.gpr[rD] = value;
            ctx.gpr[rA] = ea;
            break;
        }
'''
    text = text.replace(marker, addition + marker)
    marker = '        case 266: ctx.gpr[rD] = ctx.gpr[rA] + ctx.gpr[rB];'
    assert text.count(marker) == 1
    addition = '''        case 8: case 136: {
            const uint64_t carry = xo == 8 ? 1u : ((ctx.xer >> 29) & 1u);
            const uint64_t sum = uint64_t(~ctx.gpr[rA]) + uint64_t(ctx.gpr[rB]) + carry;
            ctx.gpr[rD] = uint32_t(sum);
            ctx.xer = (ctx.xer & ~0x20000000u) | (uint32_t(sum >> 32) << 29);
            if (rc) {
                set_cr0(ctx, int32_t(ctx.gpr[rD]));
            }
            break;
        }
'''
    return text.replace(marker, addition + marker)
