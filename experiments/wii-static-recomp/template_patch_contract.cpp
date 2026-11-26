#include "template_patch.h"
#include "loader-bat-seed.h"
#include <iostream>

int main() {
    using namespace nwii::runtime;
    std::string hex;
    if (!(std::cin >> hex) || hex.size() != 304) {
        return 8;
    }
    std::vector<uint8_t> original(152);
    for (unsigned index = 0; index < 152; ++index) {
        original[index] = std::stoul(hex.substr(index * 2, 2), nullptr, 16);
    }
    SeededBatContext context;
    context.msr = 0x2030;
    context.hid0 = 0xc200;
    context.fpscr = 4;
    auto pointer = context.mmu.get_ptr(0x80211ba0);
    std::copy(original.begin(), original.end(), pointer);
    context.instructionImages.emplace_back(0x80211ba0, original);
    for (unsigned index = 0; index < 16; ++index) {
        experiment_template_patch(context, 0x80211c08, 0x38600000 | index, 0x802119a8);
        if (bat_memory_read32(context, 0x80211c08) != (0x38600000 | index)) {
            return 9;
        }
    }
    if (!std::equal(original.begin(), original.end(), pointer)) {
        return 10;
    }
    bat_memory_cache_operation(context, 0x80211c08, 54);
    if (pointer[107] != 15 || context.instructionImages[0].second != original) {
        return 11;
    }
    unsigned guards = 0;
    auto refused = [&](uint32_t address, uint32_t value, uint32_t instruction) {
        const auto lines = context.dataLines;
        const auto replacement = context.replacement;
        const auto gpr = context.gpr;
        const auto fpr = context.fpr;
        const auto ps1 = context.ps1;
        const auto fpscr = context.fpscr;
        const auto images = context.instructionImages;
        const std::vector<uint8_t> before(pointer, pointer + 152);
        bool caught = false;
        try {
            experiment_template_patch(context, address, value, instruction);
        } catch (const std::runtime_error&) {
            caught = true;
        }
        if (!caught || context.gpr != gpr || context.fpr != fpr || context.ps1 != ps1 || context.fpscr != fpscr ||
            context.instructionImages != images || context.replacement != replacement || !std::equal(before.begin(), before.end(), pointer)) {
            throw std::runtime_error("Template refusal mutated state/backing");
        }
        for (unsigned set = 0; set < 128; ++set) {
            for (unsigned way = 0; way < 8; ++way) {
                const auto& prior = lines[set][way];
                const auto& next = context.dataLines[set][way];
                if (prior.bytes != next.bytes || prior.address != next.address || prior.valid != next.valid || prior.dirty != next.dirty) {
                    throw std::runtime_error("Template refusal mutated cache");
                }
            }
        }
        ++guards;
    };
    refused(0x80211c0c, 0x38600000, 0x802119a8);
    refused(0x80211c08, 0x38600010, 0x802119a8);
    refused(0x80211c08, 0x60000000, 0x802119a8);
    refused(0x80211c08, 0x38600000, 0x802119ac);
    context.msr = 0x2031;
    refused(0x80211c08, 0x38600000, 0x802119a8);
    context.msr = 0x2030;
    context.hid0 = 0x8200;
    refused(0x80211c08, 0x38600000, 0x802119a8);
    context.hid0 = 0xc200;
    context.dataLines = {};
    pointer[0] ^= 1;
    refused(0x80211c08, 0x38600000, 0x802119a8);
    pointer[0] ^= 1;
    pointer[107] = 16;
    refused(0x80211c08, 0x38600000, 0x802119a8);
    pointer[107] = 15;
    context.instructionImages.clear();
    refused(0x80211c08, 0x38600000, 0x802119a8);
    context.instructionImages.emplace_back(0x80211ba0, original);
    context.instructionImages[0].second[104] ^= 1;
    refused(0x80211c08, 0x38600000, 0x802119a8);
    unsigned entries = 0;
    for (uint32_t address = 0x80211ba0; address < 0x80211c38; address += 4) {
        bool caught = false;
        try {
            experiment_template_execution_guard(context, address);
        } catch (const std::runtime_error&) {
            caught = true;
        }
        if (!caught) {
            return 12;
        }
        ++entries;
    }
    experiment_template_execution_guard(context, 0x80211b9c);
    experiment_template_execution_guard(context, 0x80211c38);
    std::cout << "TEMPLATE_CONTRACT writes=16 guards=" << guards << " entries=" << entries << '\n';
}
