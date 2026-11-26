#include "stock_axwii_commands.h"
#include "axwii-command-reference.h"
#include "Core/HW/DSPHLE/UCodes/AXStructs.h"
#include <cstddef>
#include <fstream>
#include <iostream>

static std::vector<SpyCall> normalized(const std::vector<openshsm::experiment::AxWiiCommand>& commands) {
    std::vector<SpyCall> result;
    for (const auto& cmd : commands) {
        const auto& a = cmd.arguments;
        const auto pointer = [&](unsigned offset) { return uint32_t(a[offset]) << 16 | a[offset + 1]; };
        switch (cmd.opcode) {
        case 0: case 1: case 2: case 3: case 4:
            result.push_back({cmd.opcode, {pointer(0)}});
            break;
        case 5: case 6: case 7:
            result.push_back({cmd.opcode, {a[0], pointer(1), pointer(3)}});
            break;
        case 8: case 9:
            result.push_back({cmd.opcode, {a[0], pointer(1), pointer(3), pointer(5), pointer(7), pointer(9), pointer(11)}});
            break;
        case 10:
            result.push_back({10, {a[0], a[1], pointer(2), 3}});
            break;
        case 11: case 12:
            result.push_back({cmd.opcode, {a[0], pointer(1), pointer(3)}});
            break;
        case 13:
            result.push_back({13, {pointer(0), pointer(2), pointer(4), pointer(6)}});
            break;
        case 14:
            break;
        }
    }
    return result;
}

int main(int argc, char** argv) {
    unsigned cases = 0;
    for (int index = 1; index < argc; ++index) {
        std::ifstream stream(argv[index], std::ios::binary);
        std::vector<uint8_t> data(std::istreambuf_iterator<char>(stream), {});
        const auto commands = openshsm::experiment::decode_axwii_commands(data, 0x4cc52064);
        AXWiiUCode reference;
        for (size_t word = 0; word < data.size() / 2; ++word) {
            reference.m_cmdlist.push_back(uint16_t(uint16_t(data[word * 2]) << 8 | data[word * 2 + 1]));
        }
        reference.HandleCommandList();
        if (reference.calls != normalized(commands)) {
            return 2;
        }
        ++cases;
    }
    unsigned refused = 0;
    for (const std::vector<uint8_t>& invalid : {std::vector<uint8_t>{}, {0}, {0, 0}, {0, 15},
            {0, 1, 0, 0, 0, 0}, {0, 14, 0}}) {
        try {
            openshsm::experiment::decode_axwii_commands(invalid, 0x4cc52064);
        } catch (const std::runtime_error&) {
            ++refused;
        }
    }
    try {
        openshsm::experiment::decode_axwii_commands(std::vector<uint8_t>{0, 14}, 0xfa450138);
    } catch (const std::runtime_error&) {
        ++refused;
    }
    if (refused != 7) {
        return 3;
    }
    using DSP::HLE::AXPBWii;
    std::cout << "AXWII_COMMAND_SCHEMA_COMPONENT_PASS " << cases << " lists;7 malformed/variant refusals\n";
    std::cout << "PB_LAYOUT " << sizeof(AXPBWii) << ' ' << offsetof(AXPBWii, updates) << ' '
        << sizeof(DSP::HLE::PBUpdatesWii) << ' ' << offsetof(AXPBWii, running) << ' '
        << offsetof(AXPBWii, audio_addr) << ' ' << offsetof(AXPBWii, adpcm) << ' '
        << offsetof(AXPBWii, src) << ' ' << offsetof(AXPBWii, vol_env) << '\n';
}
