"""Observe the shared original decimal-reader entry/return, not guessed subtitle reachability."""
import struct


def adapt(text, dol, flight=False):
    layout = struct.unpack('>64I', dol[:256])
    for address, word, before in [(0x8019D9FC, 0x9421FF10, True), (0x8019ED1C, 0x4E800020, False)]:
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == word
        marker = f'loc_{address:08X}: ;\n    // 0x{address:08X}: {word:08X}\n'
        assert text.count(marker) == 1
        text = text.replace(marker, marker + f'    stock_numeric_reader::observe(ctx, {str(before).lower()});\n')
    return '#include "' + ('stock_numeric_reader_flight.h' if flight else 'stock_numeric_reader.h') + '"\n' + text


def flight_header(text):
    replacements = [
        ('    bool active = false;\n', '    bool active = false;\n    unsigned id = 0;\n    std::string input;\n'),
        ('static std::array<Pending, 8192> pending{};', 'static std::array<Pending, 64> pending{};'),
        ('static unsigned used = 0;', '''static unsigned used = 0, finished = 0, overwritten = 0;
    static const std::string saved_prefix(prefix);
    struct Finalizer {
        ~Finalizer() {
            std::ofstream file(saved_prefix + "-numeric-flight.json");
            file << "{\\"started\\":" << used << ",\\"finished\\":" << finished
                << ",\\"overwrittenActive\\":" << overwritten << ",\\"pending\\":[";
            bool first = true;
            for (const auto& state : pending) {
                if (!state.active) { continue; }
                file << (first ? "" : ",") << "{\\"id\\":" << state.id << ",\\"sp\\":" << state.sp
                    << ",\\"caller\\":" << state.caller << ",\\"inputHex\\":\\"" << state.input << "\\"}";
                first = false;
            }
            file << "]}\\n";
        }
    };
    static Finalizer finalizer;'''),
        ('        if (used == pending.size()) { return; }\n', ''),
        ('pending[id] = {&ctx, ctx.gpr[1], ctx.lr, true};', '''auto& slot = pending[id % pending.size()];
        if (slot.active) { ++overwritten; }
        slot = {&ctx, ctx.gpr[1], ctx.lr, true, id, ""};'''),
        ('    } else {\n        bool found = false;', '        pending[id % pending.size()].input = input;\n    } else {\n        bool found = false;'),
        ('for (unsigned i = used; i > 0; --i)', 'for (unsigned i = pending.size(); i > 0; --i)'),
        ('id = i - 1; state.active = false; found = true; break;', 'id = state.id; state.active = false; ++finished; found = true; break;'),
        ('    std::ofstream file(std::string(prefix) + "-numeric-reader.jsonl",', '    if (id >= 8192) { return; }\n    std::ofstream file(std::string(prefix) + "-numeric-reader.jsonl",')]
    for old, new in replacements:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    return text
