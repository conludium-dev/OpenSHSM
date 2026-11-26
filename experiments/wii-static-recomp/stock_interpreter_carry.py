"""Restore non-OE addc/adde in the existing fallback; leave other opcode paths intact."""


def adapt(text):
    marker = '        case 266: ctx.gpr[rD] = ctx.gpr[rA] + ctx.gpr[rB];'
    assert text.count(marker) == 1
    addition = '''        case 10: case 138: {
            uint64_t sum = uint64_t(ctx.gpr[rA]) + uint64_t(ctx.gpr[rB]);
            if (xo == 138) {
                sum += (ctx.xer >> 29) & 1u;
            }
            ctx.gpr[rD] = uint32_t(sum);
            ctx.xer = (ctx.xer & ~0x20000000u) | (uint32_t(sum >> 32) << 29);
            if (rc) {
                set_cr0(ctx, int32_t(ctx.gpr[rD]));
            }
            break;
        }
'''
    return text.replace(marker, addition + marker)
