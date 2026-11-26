#include "runtime/cpu_context.h"
#include <bit>
#include <memory>
#include <stdexcept>

using nwii::runtime::CPUContext;
void func_800F3E60(CPUContext&);

namespace nwii::runtime {
bool g_trace_calls = true;
uint32_t g_watch_addr = 0;
thread_local uint32_t probeCallbacks = 0;
void trace_call(uint32_t, CPUContext&) { ++probeCallbacks; }
void interpret_step(CPUContext&) { throw std::runtime_error("Interpreter fallback forbidden in this static probe"); }
void watch_hit(uint32_t, uint32_t, int) { throw std::runtime_error("Unexpected watch access"); }
uint32_t HW_Reg_Read32(uint32_t) { throw std::runtime_error("Unexpected hardware read"); }
void HW_Reg_Write32(uint32_t, uint32_t) { throw std::runtime_error("Unexpected hardware write"); }
void GX_WGPIPE_Write32(uint32_t) { throw std::runtime_error("Unexpected GX write"); }
}

extern "C" void* shsm_probe_create() {
    return new CPUContext;
}

extern "C" void shsm_probe_destroy(void* opaque) {
    delete static_cast<CPUContext*>(opaque);
}

extern "C" int shsm_probe_step(void* opaque, uint32_t value, uint32_t direction,
    uint32_t* result, uint32_t* abi, uint32_t* callbacks) {
    if (!opaque || !result || !abi || !callbacks) {
        return 2;
    }
    auto& context = *static_cast<CPUContext*>(opaque);
    constexpr uint32_t table = 0x80477328;
    constexpr uint32_t stack = 0x80100000;
    constexpr uint32_t returnAddress = 0xf0001000;
    context.gpr.fill(0);
    for (uint32_t index = 14; index < 32; ++index) {
        context.gpr[index] = 0x12340000 + index * 0x100;
    }
    const auto before = context.gpr;
    for (uint32_t index = 0; index < 17; ++index) {
        context.mmu.write32(table + index * 4, index == 16 ? value : 0xabcdef01);
    }
    context.gpr[1] = stack;
    context.gpr[4] = direction;
    context.lr = returnAddress;
    context.pc = 0x800f3e60;
    nwii::runtime::probeCallbacks = 0;
    try {
        func_800F3E60(context);
    } catch (...) {
        return 3;
    }
    *result = context.mmu.read32(table + 16 * 4);
    *abi = context.gpr[1] == stack && context.lr == returnAddress && context.pc == returnAddress;
    for (uint32_t index = 14; index < 32; ++index) {
        *abi &= context.gpr[index] == before[index];
    }
    for (uint32_t index = 0; index < 16; ++index) {
        *abi &= context.mmu.read32(table + index * 4) == 0xabcdef01;
    }
    *callbacks = nwii::runtime::probeCallbacks;
    return 0;
}
