#include <processor_adapter.h>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <memory>
#include <sstream>
#include <string>

extern "C" void func_8019D434(nwii::runtime::CPUContext&);
extern "C" void scan_probe_dispatch(nwii::runtime::CPUContext&);
namespace nwii::runtime {
extern MMU* g_mmu; extern CPUContext* g_ctx_ptr;
void add_recompiled_range(uint32_t, uint32_t);
}

static std::string decode(const std::string& value) {
    std::string result;
    if (value == "-") { return result; }
    if (value.size() % 2) { throw std::runtime_error("invalid hex"); }
    for (size_t i = 0; i < value.size(); i += 2) {
        result += char(std::stoul(value.substr(i, 2), nullptr, 16));
    }
    return result;
}

int main(int argc, char** argv) {
    if (argc != 2) { return 2; }
    std::ifstream input(argv[1], std::ios::binary);
    std::vector<uint8_t> dol((std::istreambuf_iterator<char>(input)), {});
    auto word = [&](unsigned offset) {
        if (offset + 4 > dol.size()) { throw std::runtime_error("DOL bounds"); }
        return (uint32_t(dol[offset]) << 24) | (uint32_t(dol[offset + 1]) << 16)
            | (uint32_t(dol[offset + 2]) << 8) | dol[offset + 3];
    };
    for (unsigned section = 0; section < 7; ++section) {
        if (word(144 + section * 4)) {
            const uint32_t address = word(72 + section * 4);
            nwii::runtime::add_recompiled_range(address, address + word(144 + section * 4));
        }
    }
    nwii::runtime::add_recompiled_range(0x807F0000, 0x807F0004);
    std::string line;
    while (std::getline(std::cin, line)) {
        auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
        auto& ctx = *owned;
        nwii::runtime::g_mmu = &ctx.mmu; nwii::runtime::g_ctx_ptr = &ctx;
        for (unsigned section = 0; section < 18; ++section) {
            const uint32_t offset = word(section * 4), address = word(72 + section * 4), size = word(144 + section * 4);
            if (uint64_t(offset) + size > dol.size()) { return 3; }
            for (uint32_t i = 0; i < size; ++i) { ctx.mmu.write8(address + i, dol[offset + i]); }
        }
        std::istringstream request(line);
        std::string input_hex, format_hex;
        if (!(request >> input_hex >> format_hex)) { return 4; }
        auto text = decode(input_hex), format = decode(format_hex);
        if (text.size() >= 256 || format.size() >= 256) { return 5; }
        for (uint32_t i = 0; i < 256; ++i) {
            ctx.mmu.write8(0x80600000 + i, i < text.size() ? uint8_t(text[i]) : 0);
            ctx.mmu.write8(0x80600200 + i, i < format.size() ? uint8_t(format[i]) : 0);
            ctx.mmu.write8(0x80600400 + i, 0xCD);
        }
        ctx.gpr[1] = 0x80700000; ctx.gpr[2] = 0x805335E0; ctx.gpr[13] = 0x8052E720;
        ctx.gpr[3] = 0x80600000; ctx.gpr[4] = 0x80600200;
        for (unsigned i = 5; i <= 10; ++i) { ctx.gpr[i] = 0x80600400 + (i - 5) * 16; }
        ctx.msr = 0x2032; ctx.hid2 = 0xA0000000; ctx.pc = 0x8019D434; ctx.lr = 0x807F0000;
        for (unsigned steps = 0; ctx.pc != 0x807F0000 && steps < 200000; ++steps) {
            if (setjmp(ctx.exception_jmp_buf) == 0) { scan_probe_dispatch(ctx); }
        }
        if (ctx.pc != 0x807F0000 || ctx.gpr[1] != 0x80700000) {
            std::cerr << "scan incomplete pc=" << std::hex << ctx.pc << " sp=" << ctx.gpr[1]
                << " lr=" << ctx.lr << " result=" << ctx.gpr[3] << "\n";
            return 6;
        }
        std::cout << "SCAN " << std::dec << ctx.gpr[3] << " ";
        for (unsigned i = 0; i < 128; ++i) {
            std::cout << std::hex << std::setw(2) << std::setfill('0') << unsigned(ctx.mmu.read8(0x80600400 + i));
        }
        std::cout << "\n";
        nwii::runtime::g_mmu = nullptr; nwii::runtime::g_ctx_ptr = nullptr;
    }
}
