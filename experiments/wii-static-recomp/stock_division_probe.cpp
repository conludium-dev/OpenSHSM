#include "processor_adapter.h"
#include <charconv>
#include <iostream>
#include <sstream>
#include <string>
#include <iomanip>

extern "C" void func_801A68D4(nwii::runtime::CPUContext& ctx);
extern "C" void func_80197270(nwii::runtime::CPUContext& ctx);
extern "C" void func_8019734C(nwii::runtime::CPUContext& ctx);

int main(int argc, char** argv) {
    const bool decimal = argc == 2 && std::string(argv[1]) == "--decimal";
    const bool multiply = argc == 2 && std::string(argv[1]) == "--multiply";
    const bool replay = argc == 2 && std::string(argv[1]) == "--replay-multiply";
    if (argc != 1 && !decimal && !multiply && !replay) {
        return 8;
    }
    nwii::runtime::ProcessorContext ctx;
    std::string line;
    while (std::getline(std::cin, line)) {
        std::istringstream input(line);
        if (replay) {
            for (auto& value : ctx.gpr) {
                if (!(input >> value)) {
                    return 8;
                }
            }
            uint32_t cr = 0;
            if (!(input >> ctx.ctr >> ctx.xer >> ctx.msr >> cr)) {
                return 8;
            }
            for (unsigned i = 0; i < 8; ++i) {
                const unsigned field = (cr >> (28 - i * 4)) & 15;
                ctx.cr[i].lt = (field & 8) != 0;
                ctx.cr[i].gt = (field & 4) != 0;
                ctx.cr[i].eq = (field & 2) != 0;
                ctx.cr[i].so = (field & 1) != 0;
            }
            for (unsigned reg = 3; reg <= 5; ++reg) {
                std::string memory;
                if (!(input >> memory) || memory.size() != 128
                    || !ctx.mmu.get_ptr(ctx.gpr[reg]) || ctx.gpr[reg] > 0xFFFFFFC0
                    || !ctx.mmu.get_ptr(ctx.gpr[reg] + 63)) {
                    return 8;
                }
                for (unsigned i = 0; i < 64; ++i) {
                    unsigned value = 0;
                    auto parsed = std::from_chars(memory.data() + i * 2, memory.data() + i * 2 + 2, value, 16);
                    if (parsed.ec != std::errc() || parsed.ptr != memory.data() + i * 2 + 2) {
                        return 8;
                    }
                    ctx.mmu.write8(ctx.gpr[reg] + i, value);
                }
            }
            std::string extra;
            if (input >> extra) {
                return 8;
            }
            ctx.pc = 0x8019734C;
            ctx.lr = 0x807F0000;
            func_8019734C(ctx);
            std::cout << std::hex << std::setfill('0');
            for (unsigned i = 0; i < 64; ++i) {
                std::cout << std::setw(2) << unsigned(ctx.mmu.read8(ctx.gpr[3] + i));
            }
            std::cout << std::dec << ' ';
            cr = 0;
            for (const auto& field : ctx.cr) {
                cr = (cr << 4) | (unsigned(field.lt) << 3) | (unsigned(field.gt) << 2)
                    | (unsigned(field.eq) << 1) | unsigned(field.so);
            }
            for (uint32_t value : ctx.gpr) {
                std::cout << value << ' ';
            }
            std::cout << ctx.pc << ' ' << ctx.lr << ' ' << ctx.ctr << ' ' << ctx.xer << ' ' << cr << '\n';
            continue;
        }
        std::string left;
        std::string right;
        std::string extra;
        if (!(input >> left >> right) || input >> extra) {
            return 8;
        }
        uint64_t numerator = 0;
        uint64_t denominator = 0;
        auto a = std::from_chars(left.data(), left.data() + left.size(), numerator);
        auto b = std::from_chars(right.data(), right.data() + right.size(), denominator);
        if (a.ec != std::errc() || a.ptr != left.data() + left.size()
            || b.ec != std::errc() || b.ptr != right.data() + right.size() || denominator == 0) {
            return 8;
        }
        for (unsigned i = 0; i < 32; ++i) {
            ctx.gpr[i] = 0x11110000 + i;
        }
        ctx.gpr[1] = 0x80020000;
        ctx.gpr[3] = numerator >> 32;
        ctx.gpr[4] = uint32_t(numerator);
        ctx.gpr[5] = denominator >> 32;
        ctx.gpr[6] = uint32_t(denominator);
        ctx.lr = 0x807F0000;
        ctx.pc = 0x801A68D4;
        ctx.ctr = 0x12345678;
        ctx.xer = 0;
        ctx.msr = 0;
        for (auto& cr : ctx.cr) {
            cr = {};
        }
        if (decimal || multiply) {
            ctx.gpr[3] = 0x80009000;
            ctx.gpr[4] = 0x11110004;
            ctx.gpr[5] = numerator >> 32;
            ctx.gpr[6] = uint32_t(numerator);
            ctx.pc = 0x80197270;
            for (unsigned i = 0; i < 64; ++i) {
                ctx.mmu.write8(0x80009000 + i, 0xA5);
            }
            for (unsigned i = 0; i < 112; ++i) {
                ctx.mmu.write8(0x80020000 - 96 + i, 0xCC);
            }
            if (multiply) {
                for (unsigned operand = 0; operand < 2; ++operand) {
                    const uint32_t address = 0x80009200 + operand * 0x200;
                    const std::string digits = std::to_string(operand ? denominator : numerator);
                    for (unsigned i = 0; i < 64; ++i) {
                        ctx.mmu.write8(address + i, 0xA5);
                    }
                    ctx.mmu.write8(address, 0);
                    ctx.mmu.write16(address + 2, digits.size() - 1);
                    ctx.mmu.write8(address + 4, digits.size());
                    for (unsigned i = 0; i < digits.size(); ++i) {
                        ctx.mmu.write8(address + 5 + i, digits[i] - '0');
                    }
                }
                ctx.gpr[4] = 0x80009200;
                ctx.gpr[5] = 0x80009400;
                ctx.gpr[6] = uint32_t(denominator);
                ctx.pc = 0x8019734C;
                func_8019734C(ctx);
            } else {
                func_80197270(ctx);
            }
            std::cout << std::hex << std::setfill('0');
            for (unsigned i = 0; i < 64; ++i) {
                std::cout << std::setw(2) << unsigned(ctx.mmu.read8(0x80009000 + i));
            }
            std::cout << std::dec << ' ';
        } else {
            func_801A68D4(ctx);
        }
        uint32_t cr = 0;
        for (const auto& field : ctx.cr) {
            cr = (cr << 4) | (unsigned(field.lt) << 3) | (unsigned(field.gt) << 2)
                | (unsigned(field.eq) << 1) | unsigned(field.so);
        }
        for (uint32_t value : ctx.gpr) {
            std::cout << value << ' ';
        }
        std::cout << ctx.pc << ' ' << ctx.lr << ' ' << ctx.ctr << ' ' << ctx.xer << ' ' << cr << '\n';
    }
}
