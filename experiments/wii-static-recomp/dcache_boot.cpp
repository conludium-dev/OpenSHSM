#include "dcache_adapter.h"
#define ProcessorContext MemoryContext
#define trace_call original_trace_call
#define main original_boot_main
#include "mass_boot.cpp"
#undef main
#undef trace_call
#undef ProcessorContext

namespace nwii::runtime {
void trace_call(uint32_t address, CPUContext& context) {
    std::cout << "FP_STATE " << address << ' ' << context.fpscr;
    for (const auto& field : context.cr) {
        std::cout << ' ' << ((field.lt ? 8 : 0) | (field.gt ? 4 : 0) | (field.eq ? 2 : 0) | (field.so ? 1 : 0));
    }
    for (double value : context.fpr) {
        std::cout << ' ' << std::bit_cast<uint64_t>(value);
    }
    for (double value : context.ps1) {
        std::cout << ' ' << std::bit_cast<uint64_t>(value);
    }
    std::cout << ' ' << context.ctr << ' ' << context.xer << '\n';
    if (context.gpr[1] >= 16 && context.mmu.get_ptr(context.gpr[1] - 16)) {
        std::cout << "CPU_STACK " << address;
        for (unsigned index = 0; index < 64; ++index) {
            const uint32_t virtualAddress = context.gpr[1] - 16 + index;
            const uint32_t physical = virtualAddress & 0x3fffffffu;
            uint8_t value = *context.mmu.get_ptr(physical);
            if (memory_cached(context, virtualAddress)) {
                for (const auto& line : memory_context(context).dataLines[(physical >> 5) & 127]) {
                    if (line.valid && line.address == (physical & ~31u)) {
                        value = line.bytes[physical & 31];
                        break;
                    }
                }
            }
            std::cout << ' ' << unsigned(value);
        }
        std::cout << '\n';
    }
    original_trace_call(address, context);
}
}

int main(int argc, char** argv) {
    return original_boot_main(argc, argv);
}
