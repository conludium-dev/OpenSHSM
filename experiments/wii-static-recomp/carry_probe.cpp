#include "carry_adapter.h"
#define main unused_frontend_main
#include "memory_frontend_probe.cpp"
#undef main

int main() {
    using namespace nwii::runtime;
    CPUContext context;
    uint32_t opcode, value, xer;
    while (std::cin >> opcode >> value >> xer) {
        const unsigned operation = opcode >> 26;
        if (operation != 8 && operation != 12 && operation != 13) {
            return 2;
        }
        const unsigned destination = (opcode >> 21) & 31;
        const unsigned source = (opcode >> 16) & 31;
        int32_t immediate = opcode & 65535;
        if (immediate & 32768) {
            immediate -= 65536;
        }
        for (unsigned index = 0; index < 32; ++index) {
            context.gpr[index] = 0x12340000 + index * 0x100;
        }
        context.gpr[source] = value;
        const auto registers = context.gpr;
        context.xer = xer;
        for (auto& field : context.cr) {
            field.lt = true;
            field.gt = false;
            field.eq = true;
            field.so = false;
        }
        if (operation == 8) {
            experiment_subfic(context, destination, source, immediate);
        } else {
            experiment_addic(context, destination, source, immediate, operation == 13);
        }
        bool preserved = true;
        for (unsigned index = 0; index < 32; ++index) {
            if (index != destination) {
                preserved &= context.gpr[index] == registers[index];
            }
        }
        uint32_t cr = 0;
        for (const auto& field : context.cr) {
            cr = (cr << 4) | ((field.lt ? 8 : 0) | (field.gt ? 4 : 0) | (field.eq ? 2 : 0) | (field.so ? 1 : 0));
        }
        std::cout << context.gpr[destination] << ' ' << context.xer << ' ' << cr << ' ' << preserved << '\n';
    }
}
