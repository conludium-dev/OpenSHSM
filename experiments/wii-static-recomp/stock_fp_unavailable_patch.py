"""Component-stage scalar transfer trap and SPRG support on the existing interpreter."""


def adapt_interpreter(text, complete=False):
    replacements = [
        ('#include "processor_adapter.h"\n',
         '#include "processor_adapter.h"\n#include "stock_fp_unavailable.h"\n'),
        ('    uint32_t op = insn >> 26;\n',
         '    uint32_t op = insn >> 26;\n'
         '    if (op >= 48 && op <= 55 && !stock_scalar_fp_available(ctx, pc)) {\n'
         '        return true;\n'
         '    }\n'),
        ('            else if (spr == 27) ctx.gpr[rD] = ctx.srr1;\n',
         '            else if (spr == 27) ctx.gpr[rD] = ctx.srr1;\n'
         '            else if (spr >= 272 && spr <= 275) { ctx.gpr[rD] = ctx.sprg[spr - 272]; }\n'),
        ('            else if (spr == 27) ctx.srr1 = ctx.gpr[rD];\n',
         '            else if (spr == 27) ctx.srr1 = ctx.gpr[rD];\n'
         '            else if (spr >= 272 && spr <= 275) { ctx.sprg[spr - 272] = ctx.gpr[rD]; }\n')
    ]
    for before, after in replacements:
        assert text.count(before) == 1, before
        text = text.replace(before, after)
    if complete:
        before = ('    if (op >= 48 && op <= 55 && !stock_scalar_fp_available(ctx, pc)) {\n'
                  '        return true;\n'
                  '    }\n')
        assert text.count(before) == 1
        text = text.replace(before, '    stock_fp_preinstruction(ctx, insn, pc);\n')
        before = '            ctx.dispatch_saved_ctx = 0; \n'
        assert text.count(before) == 1
        text = text.replace(before, '')
    return text
