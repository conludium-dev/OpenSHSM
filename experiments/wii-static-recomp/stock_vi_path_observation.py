"""Read-only milestones and yielded calls within the existing original VI handler."""
import re

def adapt_vi_path(text):
    start = text.index('void func_802280F0(CPUContext& ctx) {')
    end = text.index('\nvoid func_80228900(', start + 1)
    body = text[start:end]
    stages = (0x8022824C, 0x802282AC, 0x802283E8, 0x80228400, 0x8022843C,
        0x80228500, 0x80228520, 0x80228534, 0x80228610, 0x80228630,
        0x80228634, 0x802288E4)
    for address in stages:
        marker = f'loc_{address:08X}: ;'
        assert 1 <= body.count(marker) <= 4
        body = body.replace(marker, marker + f'\n    observe_vi_path(ctx, 0x{address:08X}, false);')
    pattern = r'if \(ctx.pc != (0x[0-9A-F]+)\) return;'
    count = len(re.findall(pattern, body))
    assert count > 0
    body = re.sub(pattern, lambda m: f'if (ctx.pc != {m[1]}) {{ observe_vi_path(ctx, {m[1]}, true); return; }}', body)
    helper = '''static void observe_vi_path(CPUContext& ctx, uint32_t stage, bool yielded) {
    static unsigned records = 0;
    static uint64_t hits[1024] = {};
    auto& bus = nwii::runtime::MMIODispatcher::get();
    const uint32_t token = bus.read32(0xCC00100E);
    const unsigned index = ((stage - 0x802280F0) >> 2) + (yielded ? 512 : 0);
    if (index >= 1024 || (hits[index]++ % 32) != 0 || records++ >= 30000) {
        return;
    }
    fprintf(stderr, "[VIPath] ns=%lld stage=%08x yield=%u pc=%08x lr=%08x r1=%08x r0=%08x r3=%08x r4=%08x ctr=%08x r13=%08x r31=%08x msr=%08x token=%x vi=%x:%x:%x:%x flags=%x:%x\\n",
            (long long)std::chrono::steady_clock::now().time_since_epoch().count(), stage, yielded,
            ctx.pc, ctx.lr, ctx.gpr[1], ctx.gpr[0], ctx.gpr[3], ctx.gpr[4], ctx.ctr, ctx.gpr[13], ctx.gpr[31], ctx.msr, token,
            ctx.mmu.read32(0x8052AD1C), ctx.mmu.read32(0x8052AD20),
            ctx.mmu.read32(0x8052AD48), ctx.mmu.read32(0x8052AD38),
            ctx.mmu.read32(0x8052B264), ctx.mmu.read32(0x8052B268));
}

'''
    assert 'ctx.mmu.write' not in helper and not re.search(r'ctx\.[\w\[\]]+\s*=', helper)
    result = '#include <chrono>\n#include <cstdio>\n#include "runtime/hw/mmio_dispatcher.h"\n' + text[:start] + helper + body + text[end:]
    return result, stages, count
