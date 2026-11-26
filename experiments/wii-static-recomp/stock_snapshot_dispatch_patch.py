"""Add a cooperative snapshot checkpoint to the existing dispatcher, including idle callbacks."""


HEADER = '#include "stock_snapshot_barrier.h"\n'
HOOK = '''        stock_thp_snapshot::cpu_barrier.checkpoint(ctx);
        if (!ctx.is_running.load()) { break; }
'''
SETJMP = '      if (_setjmp(ctx.exception_jmp_buf) == 0) {\n'


def patch(text):
    start = text.index('extern "C" void run_game(nwii::runtime::CPUContext& ctx) {')
    end = text.index('\nextern "C" int sdk_enable_route', start)
    body = text[start:end]
    idle_start = body.index('      if (ctx.pc == 0) {')
    setjmp_start = body.index(SETJMP)
    idle = body[idle_start:setjmp_start]
    if body.count(SETJMP) != 1 or not idle.endswith('      }\n'):
        raise ValueError('Original dispatcher idle/setjmp structure differs')
    changed = body[:idle_start] + body[setjmp_start:]
    changed = changed.replace(SETJMP, SETJMP + HOOK + idle, 1)
    result = HEADER + text[:start] + changed + text[end:]
    if reverse(result, idle) != text:
        raise ValueError('Snapshot checkpoint reverse patch differs')
    return result, idle


def reverse(text, idle):
    if not text.startswith(HEADER) or text.count(HOOK) != 1:
        raise ValueError('Snapshot dispatcher checkpoint missing')
    return text[len(HEADER):].replace(SETJMP + HOOK + idle, idle + SETJMP, 1)
