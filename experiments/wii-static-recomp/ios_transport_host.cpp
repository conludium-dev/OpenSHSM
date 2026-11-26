#include "functions.h"
#define main experiment_previous_ios_main
#include "ios_open_host.cpp"
#undef main
#ifdef SHSM_KERNEL_COMPLETION
#include "ipc_open_packet.h"
#include "runtime/event_scheduler.h"
static bool replyReady;
#endif

struct TransportBoundary {};
#if defined(SHSM_REPLY_HANDLER) || defined(SHSM_HANDLER_COMPLETION)
static uint32_t fixtureReplyPointer;
static uint32_t fixtureControl;
#ifdef SHSM_HANDLER_COMPLETION
static bool handlerActive;
static bool wakeupReady;
static uint32_t expectedQueue;
#endif
void func_80212FA0(CPUContext& c) {
    events.insert(events.end(), {20, c.gpr[3], c.gpr[4], 0});
    c.pc = c.lr;
}
#ifndef SHSM_WAKEUP_COMPLETION
void func_8021B5D0(CPUContext& c) {
    events.insert(events.end(), {21, c.gpr[3], 0, 0});
#ifdef SHSM_HANDLER_COMPLETION
    if (!handlerActive || c.gpr[3] != expectedQueue) {
        throw std::runtime_error("Unexpected reply wakeup queue");
    }
#ifndef SHSM_DROP_WAKEUP_MUTANT
    wakeupReady = true;
#endif
#endif
    c.pc = c.lr;
}
#else
void func_8021A790(CPUContext& c) {
    events.insert(events.end(), {30, c.gpr[3], 0, 0});
    c.pc = c.lr;
}
extern "C" void experiment_drop_wakeup(CPUContext& c) { c.pc = c.lr; }
namespace nwii::runtime {
uint16_t HW_Reg_Read16(uint32_t) { throw std::runtime_error("Wakeup MMIO unavailable"); }
void HW_Reg_Write16(uint32_t, uint16_t) { throw std::runtime_error("Wakeup MMIO unavailable"); }
void GX_WGPIPE_Write16(uint16_t) { throw std::runtime_error("Wakeup GX unavailable"); }
}
#endif
void func_80243C00(CPUContext& c) {
    events.insert(events.end(), {22, c.gpr[3], c.gpr[4], 0});
    c.pc = c.lr;
}
void func_80213A70(CPUContext&) { throw std::runtime_error("Async context unavailable"); }
void func_80213830(CPUContext&) { throw std::runtime_error("Async context unavailable"); }
namespace nwii::runtime {
void note_null_call(uint32_t, uint32_t) { throw std::runtime_error("Async callback unavailable"); }
}
#endif
void func_8021A440(CPUContext& c) {
    events.insert(events.end(), {10, c.gpr[3], 0, 0});
    c.pc = c.lr;
}
void func_80243B60(CPUContext& c) {
    events.insert(events.end(), {11, c.gpr[3], c.gpr[4], 0});
    c.pc = c.lr;
}
void func_80241C30(CPUContext& c) {
    events.insert(events.end(), {12, c.gpr[3], c.gpr[4], 0});
#ifdef SHSM_KERNEL_COMPLETION
    if (c.gpr[3] == 0) {
        const auto physical = c.gpr[4];
        EventScheduler::get().schedule_after(1, [physical](CPUContext& context, uint64_t) {
            const auto result = experiment_ipc_open_packet(context, physical);
            events.insert(events.end(), {14, uint32_t(result), physical, 0});
#ifdef SHSM_HANDLER_COMPLETION
            const auto gpr = context.gpr;
            const auto cr = context.cr;
            const auto lr = context.lr;
            const auto ctr = context.ctr;
            const auto xer = context.xer;
            const auto pc = context.pc;
            fixtureReplyPointer = physical;
            fixtureControl = 0x30;
            expectedQueue = physical + 0x80000000u + 0x2c;
            handlerActive = true;
            context.gpr[3] = 0;
            context.gpr[4] = 0;
            context.pc = 0x80241ca0;
            context.lr = 0x807f0200;
            func_80241CA0(context);
            if (context.pc != 0x807f0200) {
                throw std::runtime_error("Reply handler failed to return");
            }
            handlerActive = false;
            context.gpr = gpr;
            context.cr = cr;
            context.lr = lr;
            context.ctr = ctr;
            context.xer = xer;
            context.pc = pc;
#endif
            replyReady = true;
        });
    }
#endif
    c.pc = c.lr;
}
void func_80241C20(CPUContext& c) {
    events.insert(events.end(), {13, c.gpr[3], 0, 0});
    c.gpr[3] = 0x30;
#ifdef SHSM_REPLY_HANDLER
    c.gpr[3] = events[events.size() - 3] == 2 ? fixtureReplyPointer : fixtureControl;
#endif
#ifdef SHSM_HANDLER_COMPLETION
    if (handlerActive) {
        c.gpr[3] = events[events.size() - 3] == 2 ? fixtureReplyPointer : fixtureControl;
    }
#endif
    c.pc = c.lr;
}
void func_8021B4E0(CPUContext& c) {
#ifdef SHSM_KERNEL_COMPLETION
#ifdef SHSM_WAKEUP_COMPLETION
    c.mmu.write32(c.gpr[3], 0x80680000);
    c.mmu.write32(c.gpr[3] + 4, 0x80680000);
    c.mmu.write16(0x806802c8, 4);
    c.mmu.write32(0x806802cc, 0);
    c.mmu.write32(0x806802d0, 7);
    c.mmu.write32(0x806802dc, c.gpr[3]);
#endif
#ifdef SHSM_DROP_REPLY_MUTANT
    EventScheduler::get().reset();
#endif
    EventScheduler::get().advance(c, 1);
#ifdef SHSM_WAKEUP_COMPLETION
    wakeupReady = c.mmu.read16(0x806802c8) == 1 && c.mmu.read32(c.gpr[3]) == 0 &&
                  c.mmu.read32(c.gpr[3] + 4) == 0 && c.mmu.read32(0x806802dc) == 0x804929a8 &&
                  c.mmu.read32(0x804929a8) == 0x80680000 && c.mmu.read32(0x804929ac) == 0x80680000 &&
                  c.mmu.read32(0x8052ab08) == 0x01000000 && c.mmu.read32(0x8052ab04) == 1;
#endif
    if (replyReady
#ifdef SHSM_HANDLER_COMPLETION
        && wakeupReady
#endif
    ) {
        c.pc = c.lr;
        return;
    }
#endif
    throw TransportBoundary{};
}
void func_802438B0(CPUContext& c) {
#ifdef SHSM_KERNEL_COMPLETION
    events.insert(events.end(), {15, c.gpr[3], c.gpr[4], 0});
    c.pc = c.lr;
#else
    throw TransportBoundary{};
#endif
}

int main() {
    CPUContext c;
#ifdef SHSM_KERNEL_COMPLETION
    IOSKernel::get().init();
#endif
    unsigned present, pending, ack, async, xer;
    while (std::cin >> present >> pending >> ack >> async >> xer) {
        std::fill(c.mmu.get_ptr(0x806a0020), c.mmu.get_ptr(0x806a0020) + 64, 0);
        std::fill(c.mmu.get_ptr(0x804b2a80), c.mmu.get_ptr(0x804b2a80) + 80, 0);
        std::fill(c.mmu.get_ptr(0x806fffc0), c.mmu.get_ptr(0x806fffc0) + 96, 0);
        c.mmu.write32(0x804b2a84, pending);
        c.mmu.write32(0x80528b70, ack);
        c.mmu.write32(0x80528b74, 0);
        c.mmu.write32(0x806a0020, 1);
        c.mmu.write32(0x806a0024, uint32_t(-6));
#ifdef SHSM_WAKEUP_COMPLETION
        for (auto span : {std::pair{0x80680000u, 1024u}, {0x80492970u, 256u}, {0x8052ab04u, 8u}, {0x806ffce0u, 832u}}) {
            std::fill(c.mmu.get_ptr(span.first), c.mmu.get_ptr(span.first) + span.second, 0);
        }
#endif
#ifdef SHSM_HANDLER_COMPLETION
        handlerActive = false;
        wakeupReady = false;
        std::fill(c.mmu.get_ptr(0x806ffd00), c.mmu.get_ptr(0x806ffd00) + 800, 0);
#endif
#ifdef SHSM_REPLY_HANDLER
        fixtureReplyPointer = present ? 0x6a0020 : 0;
        fixtureControl = ack;
        c.mmu.write32(0x806a0020, 8);
        c.mmu.write32(0x806a0024, pending);
        c.mmu.write32(0x806a0028, 1);
        std::fill(c.mmu.get_ptr(0x806ffd00), c.mmu.get_ptr(0x806ffd00) + 800, 0);
#endif
#ifdef SHSM_KERNEL_COMPLETION
        EventScheduler::get().reset();
        replyReady = false;
        c.mmu.write32(0x806a0024, 0);
        c.mmu.write32(0x806a002c, 0x6a1000);
        c.mmu.write32(0x806a0030, 1);
        std::fill(c.mmu.get_ptr(0x6a1000), c.mmu.get_ptr(0x6a1000) + 64, 0);
        const std::string device = "/dev/openshsm_missing";
        std::copy(device.begin(), device.end(), c.mmu.get_ptr(0x6a1000));
#endif
        for (unsigned i = 0; i < 32; ++i) {
            c.gpr[i] = 0x12340000 + i;
        }
        c.gpr[1] = 0x80700000;
        c.gpr[3] = present ? 0x806a0020 : 0;
        c.gpr[4] = async;
        c.gpr[13] = 0x8052e720;
        c.pc = 0x802421f0;
        c.lr = 0x807f0000;
        c.ctr = 0;
        c.xer = xer;
        c.cr.fill({});
        events.clear();
        bool boundary = false;
        try {
#ifdef SHSM_REPLY_HANDLER
            c.pc = 0x80241ca0;
            func_80241CA0(c);
#else
            func_802421F0(c);
#endif
        } catch (const TransportBoundary&) {
            boundary = true;
        }
        uint32_t cr = 0;
        for (const auto& f : c.cr) {
            cr = (cr << 4) | (f.lt << 3) | (f.gt << 2) | (f.eq << 1) | f.so;
        }
        std::cout << boundary << ' ' << c.pc << ' ' << c.lr << ' ' << c.ctr << ' ' << c.xer << ' ' << cr;
        for (auto value : c.gpr) {
            std::cout << ' ' << value;
        }
        std::cout << ' ' << events.size();
        for (auto value : events) {
            std::cout << ' ' << value;
        }
        std::cout << ' ' << std::hex << std::setfill('0');
        for (auto span : {std::pair{0x806a0020u, 64u}, {0x804b2a80u, 80u}, {0x806fffc0u, 96u}, {0x80528b70u, 4u}}) {
            for (unsigned i = 0; i < span.second; ++i) {
                std::cout << std::setw(2) << unsigned(c.mmu.get_ptr(span.first)[i]);
            }
        }
        std::cout << std::dec << '\n';
#if defined(SHSM_REPLY_HANDLER) || defined(SHSM_HANDLER_COMPLETION)
        std::cout << "HANDLER_STACK " << std::hex << std::setfill('0');
#ifdef SHSM_WAKEUP_COMPLETION
        for (unsigned i = 0; i < 832; ++i) {
            std::cout << std::setw(2) << unsigned(c.mmu.get_ptr(0x806ffce0)[i]);
        }
#else
        for (unsigned i = 0; i < 800; ++i) {
            std::cout << std::setw(2) << unsigned(c.mmu.get_ptr(0x806ffd00)[i]);
        }
#endif
        std::cout << std::dec << '\n';
#endif
#ifdef SHSM_WAKEUP_COMPLETION
        std::cout << "WAKEUP_MEMORY " << std::hex << std::setfill('0');
        for (auto span : {std::pair{0x80680000u, 1024u}, {0x80492970u, 256u}, {0x8052ab04u, 8u}}) {
            for (unsigned i = 0; i < span.second; ++i) {
                std::cout << std::setw(2) << unsigned(c.mmu.get_ptr(span.first)[i]);
            }
        }
        std::cout << std::dec << '\n';
#endif
    }
}
