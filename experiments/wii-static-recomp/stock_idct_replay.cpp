#include "processor_adapter.h"
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <string>

extern "C" void func_8020AFD0(nwii::runtime::CPUContext& ctx);
extern "C" void func_8020B460(nwii::runtime::CPUContext& ctx);

int main(int argc, char** argv) {
    if (argc != 3) {
        return 8;
    }
    nwii::runtime::ProcessorContext ctx;
    std::ifstream dol_file(argv[1], std::ios::binary);
    const std::vector<uint8_t> dol{std::istreambuf_iterator<char>(dol_file), std::istreambuf_iterator<char>()};
    if (dol.size() < 256) {
        return 8;
    }
    auto word = [&](size_t offset) {
        return uint32_t(dol[offset]) << 24 | uint32_t(dol[offset + 1]) << 16
            | uint32_t(dol[offset + 2]) << 8 | dol[offset + 3];
    };
    for (unsigned section = 0; section < 18; ++section) {
        const uint32_t offset = word(section * 4), address = word((18 + section) * 4), size = word((36 + section) * 4);
        if (!size) {
            continue;
        }
        if (uint64_t(offset) + size > dol.size() || !ctx.mmu.get_ptr(address) || !ctx.mmu.get_ptr(address + size - 1)) {
            return 8;
        }
        std::memcpy(ctx.mmu.get_ptr(address), dol.data() + offset, size);
    }
    std::ifstream input(argv[2]);
    uint32_t entry, cr, store, target;
    if (!(input >> entry >> ctx.lr >> ctx.ctr >> ctx.xer >> ctx.msr >> ctx.fpscr >> cr >> store >> target)) {
        return 8;
    }
    for (auto& value : ctx.gpr) { input >> value; }
    for (auto& value : ctx.gqr) { input >> value; }
    if (!input) {
        return 8;
    }
    auto number = [&]() {
        std::string value;
        if (!(input >> value)) {
            throw std::runtime_error("Missing floating fixture");
        }
        char* end = nullptr;
        const double result = std::strtod(value.c_str(), &end);
        if (!end || *end) {
            throw std::runtime_error("Invalid floating fixture");
        }
        return result;
    };
    for (unsigned i = 0; i < 32; ++i) {
        ctx.fpr[i] = number(); ctx.ps1[i] = number();
    }
    const double observed0 = number(), observed1 = number();
    for (unsigned i = 0; i < 8; ++i) {
        const unsigned bits = (cr >> (28 - 4 * i)) & 15;
        ctx.cr[i].lt = bits & 8; ctx.cr[i].gt = bits & 4;
        ctx.cr[i].eq = bits & 2; ctx.cr[i].so = bits & 1;
    }
    unsigned ranges;
    if (!(input >> ranges) || ranges != 7) {
        return 8;
    }
    for (unsigned range = 0; range < ranges; ++range) {
        uint32_t address;
        std::string data;
        input >> address >> data;
        if (!input || data.empty() || data.size() % 2 || data.size() > 32768
            || !ctx.mmu.get_ptr(address) || !ctx.mmu.get_ptr(address + data.size() / 2 - 1)) {
            return 8;
        }
        for (size_t i = 0; i < data.size(); i += 2) {
            ctx.mmu.get_ptr(address)[i / 2] = uint8_t(std::stoul(data.substr(i, 2), nullptr, 16));
        }
    }
    ctx.pc = entry;
    const uint32_t caller = ctx.lr;
    if (entry == 0x8020AFD0) {
        func_8020AFD0(ctx);
    } else if (entry == 0x8020B460) {
        func_8020B460(ctx);
    } else {
        return 8;
    }
    std::cout << "IDCT_REPLAY entry=" << std::hex << entry << " pc=" << ctx.pc << " caller=" << caller;
    std::cout << " store=" << store << " target=" << target << " bytes=";
    std::cout << std::setw(2) << std::setfill('0') << unsigned(ctx.mmu.read8(target));
    std::cout << std::setw(2) << unsigned(ctx.mmu.read8(target + 1));
    std::cout << " observed=" << std::hexfloat << observed0 << "," << observed1 << "\n";
    return ctx.pc == caller ? 0 : 2;
}
