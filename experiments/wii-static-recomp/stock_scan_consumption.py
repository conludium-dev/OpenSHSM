"""Extend the existing bounded scan observer to actual caller destination stores."""
import struct

IMPLEMENTATION = '''
namespace stock_scan_observation {
void consume(nwii::runtime::CPUContext& ctx, uint32_t pc) {
    static std::array<bool, 32> consumed{};
    const char* prefix = std::getenv("NWII_THPDUMP");
    if (!prefix) {
        return;
    }
    const uint32_t caller = pc == 0x8010168C ? 0x80101664 : 0x8010F110;
    const uint64_t target = pc == 0x8010168C ? uint64_t(ctx.gpr[31]) + 4 : uint64_t(ctx.gpr[29]) + 24;
    const unsigned size = pc == 0x8010168C ? 4 : 16;
    if (target > 0xFFFFFFFFu) {
        return;
    }
    const uint8_t* data = ram(ctx, uint32_t(target), size);
    if (!data) {
        return;
    }
    for (unsigned index = 0; index < used; ++index) {
        const auto& state = snapshots[index];
        if (consumed[index] || state.pending || state.context != &ctx || state.sp != ctx.gpr[1] || state.lr != caller) {
            continue;
        }
        std::ofstream file(std::string(prefix) + "-consumed.jsonl", std::ios::app);
        if (!file) {
            return;
        }
        file << "{\\"index\\":" << index << ",\\"pc\\":" << pc << ",\\"target\\":" << target
            << ",\\"sp\\":" << ctx.gpr[1] << ",\\"bytes\\":\\"" << hex_bytes(data, size) << "\\",\\"arguments\\":[";
        for (unsigned i = 0; i < (size == 4 ? 3u : 4u); ++i) {
            const uint8_t* argument = ram(ctx, state.destinations[i], 4);
            file << (i ? "," : "") << "\\"" << (argument ? hex_bytes(argument, 4) : "") << "\\"";
        }
        file << "]}\\n";
        file.close();
        consumed[index] = true;
    }
}
}
'''


def adapt_caller(text, dol):
    layout = struct.unpack('>64I', dol[:256])
    for address, word in ((0x8010F130, 0x7FC3F378),):
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == word
        marker = f'loc_{address:08X}: ;\n    // 0x{address:08X}: {word:08X}\n'
        assert text.count(marker) == 2
        text = text.replace(marker, marker + f'    stock_scan_observation::consume(ctx, 0x{address:08X});\n')
    return '#include "stock_scan_consumption.h"\n' + text


def adapt_interpreter(text):
    marker = 'void interpret_step(CPUContext& ctx) {\n'
    assert text.count(marker) == 1
    hook = '    if (ctx.pc == 0x8010168C) { stock_scan_observation::consume(ctx, ctx.pc); }\n'
    text = text.replace(marker, marker + hook)
    marker = '        interpret_one(ctx);\n'
    assert text.count(marker) == 1
    text = text.replace(marker, marker + '    ' + hook)
    return '#include "stock_scan_consumption.h"\n' + text
