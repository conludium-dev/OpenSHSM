"""Extend the existing verified carry lowering with non-OE addze only."""
from stock_interpreter_carry import adapt as adapt_carry


def adapt(text):
    text = adapt_carry(text)
    marker = '        case 266: ctx.gpr[rD] = ctx.gpr[rA] + ctx.gpr[rB];'
    assert text.count(marker) == 1
    addition = '''        case 202: {
            uint64_t sum = uint64_t(ctx.gpr[rA]) + ((ctx.xer >> 29) & 1u);
            ctx.gpr[rD] = uint32_t(sum);
            ctx.xer = (ctx.xer & ~0x20000000u) | (uint32_t(sum >> 32) << 29);
            if (rc) {
                set_cr0(ctx, int32_t(ctx.gpr[rD]));
            }
            break;
        }
'''
    return text.replace(marker, addition + marker)
