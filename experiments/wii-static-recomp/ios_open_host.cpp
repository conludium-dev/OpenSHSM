#include "runtime/cpu_context.h"
#include <algorithm>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <vector>

using namespace nwii::runtime;
void func_80242550(CPUContext&);
#ifdef SHSM_ORIGINAL_FREE
void func_802438B0(CPUContext&);
#endif
static uint32_t allocation;
static std::vector<uint32_t> events;

#ifdef SHSM_ORIGINAL_ALLOCATOR
void func_80243570(CPUContext&);
#ifndef SHSM_ORIGINAL_IRQ_SERVICES
void func_802174E0(CPUContext& context) {
    events.insert(events.end(), {3, 0, 0, 0});
    context.gpr[3] = 0;
    context.pc = context.lr;
}
void func_80217520(CPUContext& context) {
    events.insert(events.end(), {4, context.gpr[3], 0, 0});
    context.pc = context.lr;
}
#endif
#else
void func_802438A0(CPUContext& context) {
    events.insert(events.end(), {0, context.gpr[3], context.gpr[4], context.gpr[5]});
    context.gpr[3] = allocation;
    context.pc = context.lr;
}
#endif

void func_80212FD0(CPUContext& context) {
    events.insert(events.end(), {1, context.gpr[3], context.gpr[4], 0});
    context.pc = context.lr;
}

#ifndef SHSM_ORIGINAL_TRANSPORT
void func_802421F0(CPUContext& context) {
    events.insert(events.end(), {2, context.gpr[3], context.gpr[4], 0});
    context.gpr[3] = uint32_t(-6);
    context.pc = context.lr;
}
#else
void func_802421F0(CPUContext&);
#endif

namespace nwii::runtime {
bool g_trace_calls = false;
uint32_t g_watch_addr = 0;
void trace_call(uint32_t, CPUContext&) { throw std::runtime_error("Unexpected trace"); }
void interpret_step(CPUContext&) { throw std::runtime_error("Interpreter unavailable"); }
bool process_pending_callbacks(CPUContext& context) {
#ifdef SHSM_EMPTY_IRQ_FIXTURE
    std::lock_guard<std::mutex> lock(context.cb_mutex);
    if (context.in_callback || context.callback_depth || !context.backup_stack.empty()
        || context.dispatch_saved_ctx || context.ext_resched_pending || context.exception_pc
        || context.vblank_pending.load() || context.dec_irq_pending || context.pending_cb_count.load()
        || !context.pending_callbacks.empty()) {
        throw std::runtime_error("Unverified pending interrupt in empty-event fixture");
    }
#endif
    return false;
}
void watch_hit(uint32_t, uint32_t, int) { throw std::runtime_error("Unexpected watch"); }
#ifdef SHSM_ORIGINAL_IPC_REGISTERS
uint32_t experiment_thread_ipc_read(uint32_t);
void experiment_thread_ipc_write(uint32_t, uint32_t);
#ifdef SHSM_THREAD_IPC_IRQ
void experiment_thread_ipc_clear(uint32_t);
#endif
#endif
uint32_t HW_Reg_Read32(uint32_t address) {
#ifdef SHSM_EXTERNAL_IRQ_TEST
    extern uint32_t experiment_external_pi_read(uint32_t);
    return experiment_external_pi_read(address);
#elif defined(SHSM_ORIGINAL_IPC_REGISTERS)
    return experiment_thread_ipc_read(address);
#else
    throw std::runtime_error("MMIO unavailable");
#endif
}
void HW_Reg_Write32(uint32_t address, uint32_t value) {
#ifdef SHSM_ORIGINAL_IPC_REGISTERS
    if (address == 0x0d000000 || address == 0x0d000004) {
        experiment_thread_ipc_write(address, value);
        return;
    }
#endif
#if defined(SHSM_REPLY_HANDLER) || defined(SHSM_HANDLER_COMPLETION)
    if (address != 0x0d000030 || value != 0x40000000) {
        throw std::runtime_error("Reply MMIO outside scoped clear fixture");
    }
#ifdef SHSM_THREAD_IPC_IRQ
    experiment_thread_ipc_clear(value);
#endif
    events.insert(events.end(), {16, address, value, 0});
#else
    throw std::runtime_error("MMIO unavailable");
#endif
}
void GX_WGPIPE_Write32(uint32_t) { throw std::runtime_error("GX unavailable"); }
}

int main() {
    CPUContext context;
    unsigned length, region, fail, mode, xer;
    while (std::cin >> length >> region >> fail >> mode >> xer) {
        if (length > 65 || region > 1 || fail > 1) {
            return 2;
        }
        const uint32_t packet = region ? 0x93e01000 : 0x806a0000;
        const uint32_t path = region ? 0x93e02000 : 0x806a1000;
        allocation = fail ? 0 : packet;
        std::fill(context.mmu.get_ptr(packet), context.mmu.get_ptr(packet) + 64, 0xa5);
        std::fill(context.mmu.get_ptr(path), context.mmu.get_ptr(path) + 96, 0);
        std::fill(context.mmu.get_ptr(path), context.mmu.get_ptr(path) + length, 'A');
        std::fill(context.mmu.get_ptr(0x806fffc0), context.mmu.get_ptr(0x806fffc0) + 96, 0);
        context.mmu.write32(0x80528b74, 3);
#ifdef SHSM_ORIGINAL_ALLOCATOR
        std::fill(context.mmu.get_ptr(packet), context.mmu.get_ptr(packet) + 4096, 0xa5);
        std::fill(context.mmu.get_ptr(0x804b2b40), context.mmu.get_ptr(0x804b2b40) + 128, 0);
        context.gpr[1] = 0x80700000;
        context.gpr[3] = packet;
        context.gpr[4] = fail ? 64 : 4096;
        context.pc = 0x80243570;
        context.lr = 0x807f0000;
        context.xer = 0;
        context.cr.fill({});
        func_80243570(context);
        if (context.pc != 0x807f0000 || context.gpr[3] != 0) {
            return 4;
        }
        context.mmu.write32(0x80528b74, context.gpr[3]);
        std::fill(context.mmu.get_ptr(0x806fff80), context.mmu.get_ptr(0x806fff80) + 160, 0);
#endif
        for (unsigned i = 0; i < 32; ++i) {
            context.gpr[i] = 0x12340000 + i;
        }
        context.gpr[1] = 0x80700000;
        context.gpr[3] = path;
        context.gpr[4] = mode;
        context.gpr[13] = 0x8052e720;
        context.cr.fill({});
        context.xer = xer;
        context.lr = 0x807f0000;
        context.ctr = 0;
        context.pc = 0x80242550;
        events.clear();
        func_80242550(context);
        if (context.pc != 0x807f0000) {
            return 3;
        }
#ifdef SHSM_ORIGINAL_FREE
        for (unsigned cycle = 0; cycle < 2; ++cycle) {
            if (cycle) {
                context.gpr[3] = path;
                context.gpr[4] = mode;
                context.pc = 0x80242550;
                context.lr = 0x807f0000;
                func_80242550(context);
            }
            if (context.pc != 0x807f0000 || context.gpr[3] != (fail ? uint32_t(-22) : uint32_t(-6))) {
                return 5;
            }
            const auto pointer = fail ? 0 : events[events.size() - 3];
            events.insert(events.end(), {6, context.gpr[3], cycle, 0});
            if (!fail) {
                if (pointer != packet + 32) {
                    return 6;
                }
                events.insert(events.end(), {5, pointer, 0, 0});
                context.gpr[3] = 0;
                context.gpr[4] = pointer;
                context.pc = 0x802438b0;
                context.lr = 0x807f0000;
                func_802438B0(context);
                if (context.pc != 0x807f0000 || context.gpr[3] != 0 || context.mmu.read32(0x804b2b44) != 0 ||
                    context.mmu.read32(0x804b2b4c) != packet || context.mmu.read32(packet + 4) != 4080) {
                    return 7;
                }
            }
        }
#endif
        uint32_t cr = 0;
        for (const auto& field : context.cr) {
            cr = (cr << 4) | (field.lt << 3) | (field.gt << 2) | (field.eq << 1) | field.so;
        }
        std::cout << context.pc << ' ' << context.lr << ' ' << context.ctr << ' ' << context.xer << ' ' << cr;
        for (auto value : context.gpr) {
            std::cout << ' ' << value;
        }
        std::cout << ' ' << events.size();
        for (auto value : events) {
            std::cout << ' ' << value;
        }
        std::cout << ' ' << std::hex << std::setfill('0');
        for (unsigned i = 0; i < 64; ++i) {
            std::cout << std::setw(2) << unsigned(context.mmu.get_ptr(packet)[i]);
        }
        std::cout << ' ';
        for (unsigned i = 0; i < 96; ++i) {
            std::cout << std::setw(2) << unsigned(context.mmu.get_ptr(0x806fffc0)[i]);
        }
#ifdef SHSM_ORIGINAL_ALLOCATOR
        std::cout << ' ';
        for (unsigned i = 0; i < 4096; ++i) {
            std::cout << std::setw(2) << unsigned(context.mmu.get_ptr(packet)[i]);
        }
        std::cout << ' ';
        for (unsigned i = 0; i < 128; ++i) {
            std::cout << std::setw(2) << unsigned(context.mmu.get_ptr(0x804b2b40)[i]);
        }
#endif
        std::cout << std::dec << '\n';
    }
    return 0;
}
