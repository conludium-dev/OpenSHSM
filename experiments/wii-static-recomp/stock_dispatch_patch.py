"""Replace generated dispatcher switch with an exactly equivalent sorted address table."""
import re


def adapt_dispatch(text):
    start = text.index('        switch (target) {')
    fallback = text.index('            default: {', start)
    cases = text[start:fallback]
    rows = re.findall(r'^            case (0x[0-9A-F]+): (func_[0-9A-F]+)\(ctx\); break;$', cases, re.M)
    hle_rows = re.findall(r'^            case (0x[0-9A-F]+): ([A-Za-z_][A-Za-z_0-9]*)\(ctx\); ctx.pc = ctx.lr; break;$', cases, re.M)
    assert {name for _, name in hle_rows} == {'OSReport', 'IOS_Open', 'IOS_IoctlvAsync'}
    assert rows and len(rows) + len(hle_rows) == cases.count('case ')
    wrappers = ''
    for address, name in hle_rows:
        wrapper = 'dispatch_hle_' + address[2:]
        wrappers += 'static void ' + wrapper + '(CPUContext& ctx) {\n    ' + name + '(ctx);\n    ctx.pc = ctx.lr;\n}\n'
        rows.append((address, wrapper))
    addresses = [int(address, 16) for address, _ in rows]
    assert len(addresses) == len(set(addresses))
    rows.sort(key=lambda row: int(row[0], 16))
    marker = '// --- Entry Point Wrapper ---'
    assert text.count(marker) == 1
    table = '''struct DispatchRoute { uint32_t address; void(*function)(CPUContext&); };
static const DispatchRoute g_dispatch_routes[] = {
'''
    table += ''.join('    {' + address + ', ' + function + '},\n' for address, function in rows)
    table += '''};

static void(*lookup_dispatch(uint32_t target))(CPUContext&) {
    size_t first = 0;
    size_t last = sizeof(g_dispatch_routes) / sizeof(g_dispatch_routes[0]);
    while (first < last) {
        size_t middle = first + (last - first) / 2;
        if (g_dispatch_routes[middle].address < target) {
            first = middle + 1;
        } else {
            last = middle;
        }
    }
    if (first < sizeof(g_dispatch_routes) / sizeof(g_dispatch_routes[0]) &&
        g_dispatch_routes[first].address == target) {
        return g_dispatch_routes[first].function;
    }
    return nullptr;
}

'''
    replacement = '''        if (auto function = lookup_dispatch(target)) {
            function(ctx);
        } else {'''
    text = text[:start] + replacement + text[fallback + len('            default: {'):]
    closing = '''            }
        }
      } else {
          continue;
'''
    assert text.count(closing) == 1
    text = text.replace(closing, '''        }
      } else {
          continue;
''')
    return text.replace(marker, wrappers + table + marker), rows
