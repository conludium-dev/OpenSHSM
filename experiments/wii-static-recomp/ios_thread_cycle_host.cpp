#define SHSM_EXTERNAL_SELECTOR_MAIN
#define SHSM_ORIGINAL_SET_CONTEXT
#define SHSM_CONTEXT_TRANSFER
#include "ios_select_thread_host.cpp"
#ifdef SHSM_THREAD_KERNEL_REPLY
#include "ipc_open_packet.h"
#include "runtime/event_scheduler.h"
#endif
#ifdef SHSM_THREAD_IPC_CONTROL
#include "ipc_reset_backend.cpp"
#endif
#ifdef SHSM_THREAD_EXTERNAL_IRQ
void func_8021C000(CPUContext& c) {
    c.gpr[3] = 1;
    c.gpr[4] = 0x23456789;
    events.insert(events.end(), {42, c.gpr[3], c.gpr[4], 0});
    c.pc = c.lr;
}
#endif

static const std::pair<uint32_t, uint32_t> spans[] = {
    {0x80680000, 1024}, {0x80690000, 1024},
#ifdef SHSM_THREAD_REPLY_HANDLER
#ifdef SHSM_THREAD_OPEN
    {0x806a0000, 4096},
#else
    {0x806a0020, 64},
#endif
#else
    {0x806a004c, 8},
#endif
    {0x80492970, 256}, {0x8052ab00, 12}, {0x800000c0, 28}, {0x800000e4, 4}, {0x806fff80, 160},
#ifdef SHSM_THREAD_REPLY_HANDLER
    {0x806fec80, 928},
#else
    {0x806fef80, 160},
#endif
#ifdef SHSM_THREAD_TRANSPORT
    {0x804b2a80, 80}, {0x80528b70, 8}
#endif
#ifdef SHSM_THREAD_OPEN
    , {0x804b2b40, 128}
#endif
#ifdef SHSM_THREAD_IPC_ACK
    , {0x8052afd8, 8}
#endif
#ifdef SHSM_THREAD_IPC_CONTROL
    , {0x806a1200,
#ifdef SHSM_THREAD_IPC_IRQ
       32}
#else
       24}
#endif
#endif
#ifdef SHSM_THREAD_EXTERNAL_IRQ
    , {0x80003040, 128}, {0x8042cf98, 48}, {0x8052aac8, 20}
#endif
#ifdef SHSM_THREAD_EXCEPTION_VECTOR
    , {0x80000500, 152}, {0x80003000, 64}
#endif
#ifdef SHSM_THREAD_VECTOR_RETURN
    , {0x806a1300, 8}
#endif
};

static void dump(CPUContext& c);
static void dispatch(CPUContext& c, uint32_t endpoint);

#ifdef SHSM_THREAD_KERNEL_REPLY
static bool threadReplyDelivered;
#ifdef SHSM_THREAD_IPC_IRQ
static bool threadReplyQueued;
static void deliver_visible_reply(CPUContext& context, uint64_t);
#endif
#ifdef SHSM_THREAD_IPC_INTERRUPT
#ifdef SHSM_THREAD_IPC_CONTROL
static uint32_t& threadIpcControl = hw::ipc_ppc_ctrl;
#else
static uint32_t threadIpcControl = 0x30;
#endif
static constexpr uint32_t ackControlAfter =
#ifdef SHSM_THREAD_IPC_IRQ
    0x34;
#elif defined(SHSM_THREAD_IPC_CONTROL)
    0x30;
#else
    0x22;
#endif
static constexpr uint32_t replyControlAfter =
#ifdef SHSM_THREAD_IPC_CONTROL
    0x38;
#else
    0x18;
#endif
#endif
static void deliver_thread_reply(CPUContext& context, uint64_t) {
#ifdef SHSM_THREAD_IPC_IRQ
    const auto preparedResult = experiment_ipc_open_packet(context, 0x006a0020);
    events.insert(events.end(), {14, uint32_t(preparedResult), 0x006a0020, 0});
    threadReplyQueued = true;
#endif
#ifdef SHSM_THREAD_IPC_ACK
    std::array<uint8_t, 4096> heapBeforeAck;
    std::copy_n(context.mmu.get_ptr(0x806a0000), heapBeforeAck.size(), heapBeforeAck.begin());
    std::array<uint8_t, 128> tableBeforeAck;
    std::copy_n(context.mmu.get_ptr(0x804b2b40), tableBeforeAck.size(), tableBeforeAck.begin());
#ifdef SHSM_THREAD_IPC_CONTROL
    if (hw::ipc_ppc_msg != 0x006a0020 || threadIpcControl != 0x31) {
        throw std::runtime_error("ACK has no outstanding original request");
    }
    threadIpcControl = (threadIpcControl & ~1u) | 2u;
#ifdef SHSM_THREAD_IPC_IRQ
    hw::experiment_ipc_irq_update();
#endif
#else
    threadIpcControl = 0x22;
#endif
    context.pc = 0x80241f00;
    func_80241F00(context);
    if (context.pc != 0x807f6000 || context.mmu.read32(0x80528b70) != 1
        || context.mmu.read16(0x806902c8) != 4 || context.mmu.read32(0x806a0020) !=
#ifdef SHSM_THREAD_IPC_IRQ
        8
#else
        1
#endif
        || !std::equal(heapBeforeAck.begin(), heapBeforeAck.end(), context.mmu.get_ptr(0x806a0000))
        || !std::equal(tableBeforeAck.begin(), tableBeforeAck.end(), context.mmu.get_ptr(0x804b2b40))
        || threadIpcControl != ackControlAfter) {
        throw std::runtime_error("ACK boundary pc=" + std::to_string(context.pc)
            + " mailbox=" + std::to_string(context.mmu.read32(0x80528b70))
            + " state=" + std::to_string(context.mmu.read16(0x806902c8))
            + " command=" + std::to_string(context.mmu.read32(0x806a0020))
            + " descriptor4=" + std::to_string(context.mmu.read32(0x804b2b44))
            + " control=" + std::to_string(threadIpcControl));
    }
    dump(context);
#ifdef SHSM_THREAD_IPC_IRQ
#ifndef SHSM_DROP_AFTER_ACK
    EventScheduler::get().schedule_after(1, deliver_visible_reply);
#endif
    return;
#endif
#ifdef SHSM_DROP_AFTER_ACK
    return;
#endif
    context.gpr[3] = 0;
    context.gpr[4] = 0x806b0000;
#endif
    const int32_t result = experiment_ipc_open_packet(context, 0x006a0020);
    events.insert(events.end(), {14, uint32_t(result), 0x006a0020, 0});
#ifdef SHSM_THREAD_IPC_INTERRUPT
#ifdef SHSM_THREAD_IPC_CONTROL
    hw::ipc_arm_msg = hw::ipc_ppc_msg;
    threadIpcControl |= 4u;
#else
    threadIpcControl = 0x14;
#endif
    context.pc = 0x80241f00;
    func_80241F00(context);
    if (context.pc != 0x807f6000 || threadIpcControl != replyControlAfter) {
        throw std::runtime_error("Original IPC wrapper did not finish reply-only fixture");
    }
#else
    func_80241CA0(context);
#endif
    threadReplyDelivered = true;
}
#ifdef SHSM_THREAD_IPC_IRQ
static void deliver_visible_reply(CPUContext& context, uint64_t) {
    const auto irq = hw::experiment_ipc_irq_snapshot();
    if (threadReplyQueued || threadIpcControl != 0x34 || irq.ppcFlags != 0x40000000 || irq.piCause != 0x14000) {
        throw std::runtime_error("Reply dispatch without latched visible IRQ");
    }
    events.insert(events.end(), {24, irq.piCause, irq.ppcFlags, threadIpcControl});
#ifdef SHSM_THREAD_EXTERNAL_IRQ
    const uint32_t base = 0x80680000;
#ifdef SHSM_THREAD_EXCEPTION_VECTOR
    context.mmu.write32(0x800000d4, base);
    context.mmu.write32(0x800000c0, base & 0x3fffffff);
    context.srr0 = 0x807f4000;
    context.srr1 = context.msr | 2u;
    context.msr &= ~0x8032u;
    context.pc = 0x80211ba0;
    func_80211BA0(context);
    if (context.pc != 0x80217c60 || context.gpr[3] != 4 || context.gpr[4] != base) {
        throw std::runtime_error("Original vector did not route external exception");
    }
#else
    for (unsigned i = 3; i <= 5; ++i) {
        context.mmu.write32(base + i * 4, context.gpr[i]);
    }
    uint32_t cr = 0;
    for (const auto& field : context.cr) {
        cr = (cr << 4) | (field.lt << 3) | (field.gt << 2) | (field.eq << 1) | field.so;
    }
    for (auto [offset, value] : {std::pair{0x80u, cr}, {0x84u, context.lr}, {0x88u, context.ctr},
                                  {0x8cu, context.xer}, {0x198u, 0x807f4000u}, {0x19cu, context.msr}}) {
        context.mmu.write32(base + offset, value);
    }
    context.mmu.write16(base + 0x1a2, 2);
    context.mmu.write32(0x800000d4, base);
    context.mmu.write32(0x800000c0, base & 0x3fffffff);
    context.gpr[3] = 4;
    context.gpr[4] = base;
    context.pc = 0x80217c60;
#endif
    func_80217C60(context);
    if (context.pc != 0x80241f00 || context.gpr[3] != 27 || context.gpr[4] != base
        || context.lr != 0x80217c24 || context.mmu.read32(0x8052ab00) != 1) {
        throw std::runtime_error("Original dispatcher did not select IPC handler");
    }
    events.insert(events.end(), {40, 27, base, 1});
#else
    context.gpr[3] = 0;
    context.gpr[4] = 0x806b0000;
    context.lr = 0x807f6000;
    context.pc = 0x80241f00;
#endif
    func_80241F00(context);
#ifdef SHSM_THREAD_EXTERNAL_IRQ
    if (context.pc != 0x80217c24 || threadIpcControl != 0x38
        || context.mmu.read32(0x8052ab00) != 1 || context.mmu.read16(0x806902c8) != 1) {
        throw std::runtime_error("Original IPC handler switched before dispatcher enable");
    }
    dump(context);
    func_80217C60(context);
    dispatch(context, 0x8021a890);
    if (context.mmu.read32(0x8052ab00) != 0 || context.mmu.read32(0x800000e4) != 0x80690000) {
        throw std::runtime_error("Original dispatcher did not resume waiting A");
    }
#else
    if (context.pc != 0x807f6000 || threadIpcControl != 0x38) {
        throw std::runtime_error("Visible reply did not finish original wrapper");
    }
#endif
    threadReplyDelivered = true;
}
#endif
#endif

#ifdef SHSM_THREAD_REPLY_HANDLER
static uint32_t thread_register_read(uint32_t index) {
    if (index != 1 && index != 2) {
        throw std::runtime_error("Reply register outside fixture");
    }
    events.insert(events.end(), {13, index, 0, 0});
    return index == 2 ?
#ifdef SHSM_THREAD_IPC_CONTROL
        hw::ipc_arm_msg :
#else
        0x006a0020 :
#endif
#ifdef SHSM_THREAD_IPC_INTERRUPT
        threadIpcControl;
#else
        0x30;
#endif
}
static void thread_register_write(uint32_t index, uint32_t value) {
#ifdef SHSM_THREAD_TRANSPORT
    if (index == 0) {
        if (value != 0x006a0020) {
            throw std::runtime_error("Transport request outside fixture");
        }
        events.insert(events.end(), {12, index, value, 0});
#ifdef SHSM_THREAD_IPC_CONTROL
        hw::ipc_ppc_msg = value;
#else
        EventScheduler::get().schedule_after(1, deliver_thread_reply);
#endif
        return;
    }
#endif
#ifdef SHSM_THREAD_IPC_CONTROL
    if (index != 1 || (value != 0x31 && value != 0x32 && value != 0x34 && value != 0x38)) {
        throw std::runtime_error("Control write outside original lifecycle");
    }
    if (value == 0x31) {
        if (threadIpcControl != 0x30 || hw::ipc_ppc_msg != 0x006a0020) {
            throw std::runtime_error("Send control lacks prepared original packet");
        }
        threadIpcControl = value;
        EventScheduler::get().schedule_after(1, deliver_thread_reply);
    } else {
#ifdef SHSM_THREAD_IPC_IRQ
        hw::experiment_ipc_control_latched_irq(value);
#else
        hw::experiment_ipc_control_no_request(value);
#endif
    }
    events.insert(events.end(), {12, index, value, 0});
    return;
#endif
    if (index != 1 || (value != 0x34 && value != 0x38
#ifdef SHSM_THREAD_TRANSPORT
                         && value != 0x31
#endif
    )) {
#ifdef SHSM_THREAD_IPC_INTERRUPT
        if (index == 1 && (value == 0x14 || value == 0x18
#ifdef SHSM_THREAD_IPC_ACK
                             || value == 0x22
#endif
        )) {
            threadIpcControl = value;
        } else {
            throw std::runtime_error("Reply acknowledgement outside fixture");
        }
#else
        throw std::runtime_error("Reply acknowledgement outside fixture");
#endif
    }
    events.insert(events.end(), {12, index, value, 0});
}
#ifndef SHSM_ORIGINAL_IPC_REGISTERS
void func_80241C20(CPUContext& c) {
    c.gpr[3] = thread_register_read(c.gpr[3]);
    c.pc = c.lr;
}
void func_80241C30(CPUContext& c) {
    thread_register_write(c.gpr[3], c.gpr[4]);
    c.pc = c.lr;
}
#else
namespace nwii::runtime {
#ifdef SHSM_THREAD_IPC_IRQ
void experiment_thread_ipc_clear(uint32_t value) {
    hw::experiment_ipc_irq_clear(value);
    if (threadReplyQueued) {
        hw::ipc_arm_msg = hw::ipc_ppc_msg;
        threadIpcControl |= 4u;
        threadReplyQueued = false;
    }
    EventScheduler::get().schedule_after(1, [](CPUContext&, uint64_t) { hw::experiment_ipc_irq_update(); });
}
#endif
uint32_t experiment_thread_ipc_read(uint32_t address) {
#ifdef SHSM_THREAD_EXTERNAL_IRQ
    if (address == 0x0c003000 || address == 0x0c003004) {
        const auto value = MMIODispatcher::get().read32(address | 0xc0000000);
        events.insert(events.end(), {41, address, value, 0});
        return value;
    }
#endif
    if (address != 0x0d000004 && address != 0x0d000008) {
        throw std::runtime_error("Original IPC read address outside fixture");
    }
    return thread_register_read((address - 0x0d000000) / 4);
}
void experiment_thread_ipc_write(uint32_t address, uint32_t value) {
    if (address != 0x0d000000 && address != 0x0d000004) {
        throw std::runtime_error("Original IPC write address outside fixture");
    }
    thread_register_write((address - 0x0d000000) / 4, value);
}
}
#endif
void func_80212FA0(CPUContext& c) {
    if (c.gpr[3] != 0x806a0020 || c.gpr[4] != 32) {
        throw std::runtime_error("Reply cache invalidation outside fixture");
    }
    events.insert(events.end(), {20, c.gpr[3], c.gpr[4], 0});
    c.pc = c.lr;
}
void func_80243C00(CPUContext& c) {
    events.insert(events.end(), {22, c.gpr[3], c.gpr[4], 0});
    c.pc = c.lr;
}
#ifdef SHSM_THREAD_IPC_INTERRUPT
void func_80243BF0(CPUContext& c) {
#ifdef SHSM_THREAD_IPC_ACK
    events.insert(events.end(), {23, c.gpr[3], c.gpr[4], 0});
    c.pc = c.lr;
#else
    throw std::runtime_error("IPC ACK branch outside reply-only fixture");
#endif
}
#endif
#ifndef SHSM_THREAD_OPEN
void func_802438B0(CPUContext& c) {
#ifdef SHSM_THREAD_TRANSPORT
    if (c.gpr[3] != 0 || c.gpr[4] != 0x806a0020) {
        throw std::runtime_error("Transport free outside fixture");
    }
    events.insert(events.end(), {15, c.gpr[3], c.gpr[4], 0});
    c.pc = c.lr;
#else
    throw std::runtime_error("Async free outside fixture");
#endif
}
#endif
#ifdef SHSM_THREAD_TRANSPORT
void func_80243B60(CPUContext& c) {
    events.insert(events.end(), {11, c.gpr[3], c.gpr[4], 0});
    c.pc = c.lr;
}
#endif
#endif

static void dispatch(CPUContext& c, uint32_t endpoint) {
    for (unsigned step = 0; step < 16 && c.pc != endpoint; ++step) {
        switch (c.pc) {
            case 0x8021a1a0:
                func_8021A1A0(c);
                func_8021A790(c);
                break;
            case 0x8021a890:
                if (c.gpr[3] != 1) {
                    throw std::runtime_error("Thread resume result unavailable");
                }
                func_8021A790(c);
                break;
            case 0x8021b5b0:
                func_8021B4E0(c);
                break;
#ifdef SHSM_THREAD_TRANSPORT
            case 0x802423dc:
                func_802421F0(c);
                break;
#endif
#ifdef SHSM_THREAD_OPEN
            case 0x8024264c:
                func_80242550(c);
                break;
#endif
            default:
                throw std::runtime_error("Unexpected thread-cycle PC");
        }
    }
    if (c.pc != endpoint) {
        throw std::runtime_error("Thread cycle did not reach endpoint");
    }
}

static void dump(CPUContext& c) {
#ifdef SHSM_THREAD_IPC_CONTROL
    const auto ipc = hw::experiment_ipc_snapshot();
    unsigned offset = 0;
    for (uint32_t value : {ipc.ppcMessage, ipc.armMessage, ipc.ppcControl, ipc.armControl, ipc.ppcMask, uint32_t(ipc.delay)}) {
        c.mmu.write32(0x806a1200 + offset, value);
        offset += 4;
    }
#ifdef SHSM_THREAD_IPC_IRQ
    const auto irq = hw::experiment_ipc_irq_snapshot();
    c.mmu.write32(0x806a1218, irq.ppcFlags);
    c.mmu.write32(0x806a121c, irq.piCause);
#endif
#endif
    uint32_t cr = 0;
    for (const auto& f : c.cr) {
        cr = (cr << 4) | (f.lt << 3) | (f.gt << 2) | (f.eq << 1) | f.so;
    }
    std::cout << c.pc << ' ' << c.lr << ' ' << c.ctr << ' ' << c.xer << ' ' << cr << ' ' << c.msr;
    for (auto value : c.gpr) {
        std::cout << ' ' << value;
    }
    std::cout << ' ' << c.srr0 << ' ' << c.srr1;
    for (unsigned i = 1; i < 8; ++i) {
        std::cout << ' ' << c.gqr[i];
    }
#ifdef SHSM_THREAD_EXCEPTION_VECTOR
    for (auto value : c.sprg) {
        std::cout << ' ' << value;
    }
#endif
    std::cout << ' ' << events.size();
    for (auto value : events) {
        std::cout << ' ' << value;
    }
    std::cout << ' ' << std::hex << std::setfill('0');
    for (auto [address, size] : spans) {
        for (unsigned i = 0; i < size; ++i) {
            std::cout << std::setw(2) << unsigned(c.mmu.get_ptr(address)[i]);
        }
    }
    std::cout << std::dec << '\n';
}

int main() {
    CPUContext c;
#ifdef SHSM_THREAD_EXTERNAL_IRQ
    hw::register_pi(MMIODispatcher::get());
#endif
#ifdef SHSM_THREAD_KERNEL_REPLY
    IOSKernel::get().init();
#endif
#ifdef SHSM_EMPTY_IRQ_FIXTURE
    bool refused = false;
    c.pending_cb_count.store(1);
    try {
        process_pending_callbacks(c);
    } catch (const std::runtime_error&) {
        refused = true;
    }
    c.pending_cb_count.store(0);
    if (!refused) {
        throw std::runtime_error("Pending IRQ was accepted by empty-event fixture");
    }
#endif
    unsigned aPriority, bPriority, owner, msr, xer, flags;
    bool heapCreated = false;
    unsigned completedCycles = 0;
    while (std::cin >> aPriority >> bPriority >> owner >> msr >> xer >> flags) {
        for (auto [address, size] : spans) {
#ifdef SHSM_THREAD_HEAP_REUSE
            if (heapCreated && (address == 0x806a0000 || address == 0x804b2b40)) {
                continue;
            }
#endif
            std::fill(c.mmu.get_ptr(address), c.mmu.get_ptr(address) + size, 0);
        }
#ifdef SHSM_THREAD_EXTERNAL_IRQ
        for (unsigned i = 0; i < 12; ++i) {
            uint32_t value;
            if (!(std::cin >> value)) {
                return 2;
            }
            c.mmu.write32(0x8042cf98 + i * 4, value);
        }
        c.mmu.write32(0x8052aad8, 0x80003040);
        c.mmu.write32(0x800030ac, 0x80241f00);
        hw::pi_intmr = 0x4000;
#endif
#ifdef SHSM_THREAD_EXCEPTION_VECTOR
        for (unsigned i = 0; i < 38; ++i) {
            uint32_t value;
            if (!(std::cin >> value)) {
                return 2;
            }
            c.mmu.write32(0x80000500 + i * 4, value);
        }
        if (c.mmu.read32(0x80000568) != 0x38600000) {
            throw std::runtime_error("Original vector ID template changed");
        }
        c.mmu.write32(0x80000568, 0x38600004);
        c.mmu.write32(0x80003010, 0x80217c60);
        c.sprg.fill(0);
#endif
#ifdef SHSM_THREAD_OPEN
        if (!heapCreated) {
            c.gpr[1] = 0x80700000;
            c.gpr[3] = 0x806a0000;
            c.gpr[4] =
#ifdef SHSM_THREAD_ALLOCATION_FAILURE
                64;
#else
                4096;
#endif
            c.gpr[13] = 0x8052e720;
            c.pc = 0x80243570;
            c.lr = 0x807f9000;
            c.xer = 0;
            c.msr = 0;
            c.cr.fill({});
            func_80243570(c);
            if (c.pc != 0x807f9000 || c.gpr[3] != 0) {
                throw std::runtime_error("Original heap creation did not return heap0");
            }
#ifdef SHSM_THREAD_HEAP_REUSE
            heapCreated = true;
#endif
        }
        std::fill(c.mmu.get_ptr(0x806fff80), c.mmu.get_ptr(0x80700020), 0);
#endif
#ifdef SHSM_THREAD_TRANSPORT
        std::fill(c.mmu.get_ptr(0x804b2a80), c.mmu.get_ptr(0x804b2ad0), 0);
        c.mmu.write32(0x80528b70, 1);
        c.mmu.write32(0x80528b74, 0);
        EventScheduler::get().reset();
#endif
#ifdef SHSM_THREAD_KERNEL_REPLY
        std::fill(c.mmu.get_ptr(0x806a1000), c.mmu.get_ptr(0x806a1000) + 64, 0);
        const std::string path = "/dev/openshsm_missing";
        std::copy(path.begin(), path.end(), c.mmu.get_ptr(0x806a1000));
#ifndef SHSM_THREAD_OPEN
        c.mmu.write32(0x806a0020, 1);
        c.mmu.write32(0x806a002c, 0x006a1000);
        c.mmu.write32(0x806a0030, 1);
#endif
#endif
        for (unsigned i = 0; i < 32; ++i) {
            c.gpr[i] = 0x12340000 + i;
            c.mmu.write32(0x80680000 + i * 4, 0x56780000 + i);
        }
        for (auto [offset, value] : {std::pair{4u, 0x806ff000u}, {12u, 1u}, {52u, 0x8052e720u},
                                    {0x80u, 0x87654321u}, {0x84u, 0x807f5000u}, {0x88u, 0x13570000u},
                                    {0x8cu, xer}, {0x198u, 0x807f4000u}, {0x19cu, msr},
                                    {0x2d0u, bPriority}, {0x2dcu, 0x80492970 + bPriority * 8}}) {
            c.mmu.write32(0x80680000 + offset, value);
        }
        for (unsigned i = 1; i < 8; ++i) {
            c.mmu.write32(0x806801a4 + i * 4, i);
        }
        c.mmu.write16(0x806801a2, flags);
        c.mmu.write16(0x806802c8, 1);
        c.mmu.write16(0x806902c8, 2);
        c.mmu.write32(0x806902d0, aPriority);
        c.mmu.write32(0x80492970 + bPriority * 8, 0x80680000);
        c.mmu.write32(0x80492974 + bPriority * 8, 0x80680000);
        c.mmu.write32(0x8052ab08, 1u << (31 - bPriority));
        c.mmu.write32(0x80528a30, 0x8021a1a0);
        c.mmu.write32(0x800000d4, 0x80690000);
        c.mmu.write32(0x800000e4, 0x80690000);
        c.mmu.write32(0x800000d8, owner == 1 ? 0x80690000 : owner == 2 ? 0x80680000 : 0);
        c.gpr[1] = 0x80700000;
        c.gpr[3] = 0x806a004c;
        c.gpr[13] = 0x8052e720;
        c.lr = 0x807f0000;
        c.pc = 0x8021b4e0;
        c.ctr = 0;
        c.xer = xer;
        c.msr = msr;
        c.srr0 = 0;
        c.srr1 = 0;
        c.gqr.fill(0);
        c.cr.fill({});
        events.clear();
#ifdef SHSM_THREAD_IPC_INTERRUPT
        threadIpcControl = 0x30;
#endif
#ifdef SHSM_THREAD_IPC_CONTROL
        hw::ipc_ppc_msg = 0;
        hw::ipc_arm_msg = 0;
        hw::ipc_arm_ctrl = 0;
        g_ipc_interrupt_delay = 0;
#endif
#ifdef SHSM_THREAD_IPC_IRQ
        hw::experimentPpcFlags = 0;
        hw::pi_intsr = 0x10000;
        threadReplyQueued = false;
#endif
#ifdef SHSM_THREAD_TRANSPORT
#ifdef SHSM_THREAD_OPEN
        c.gpr[3] = 0x806a1000;
        c.gpr[4] = 1;
        c.pc = 0x80242550;
        threadReplyDelivered = false;
        func_80242550(c);
#ifdef SHSM_THREAD_ALLOCATION_FAILURE
        EventScheduler::get().advance(c, 1);
        if (c.pc != 0x807f0000 || c.gpr[3] != uint32_t(-22) || threadReplyDelivered || !events.empty()
            || c.mmu.read32(0x804b2b44) != 0 || c.mmu.read32(0x804b2b4c) != 0x806a0000
            || c.mmu.read32(0x806a0004) != 48 || c.mmu.read32(0x804b2a84) != 0
            || c.mmu.read32(0x80528b70) != 1) {
            throw std::runtime_error("Failed allocation changed request lifecycle");
        }
        dump(c);
        continue;
#endif
#else
        c.gpr[3] = 0x806a0020;
        c.gpr[4] = 0;
        c.pc = 0x802421f0;
        threadReplyDelivered = false;
        func_802421F0(c);
#endif
#else
        func_8021B4E0(c);
#endif
        dispatch(c, 0x807f4000);
        dump(c);
        c.gpr[3] = 0x806a004c;
        c.lr = 0x807f6000;
        c.pc = 0x8021b5d0;
#ifdef SHSM_DEFERRED_WAKEUP
        c.mmu.write32(0x800000d4, 0x806b0000);
        c.msr &= ~0x8000u;
#endif
#ifdef SHSM_THREAD_REPLY_HANDLER
#ifndef SHSM_THREAD_KERNEL_REPLY
        c.mmu.write32(0x806a0020, 8);
        c.mmu.write32(0x806a0024, uint32_t(-6));
        c.mmu.write32(0x806a0028, 1);
#endif
        c.gpr[3] = 0;
        c.gpr[4] = 0x806b0000;
        c.pc = 0x80241ca0;
#ifdef SHSM_THREAD_KERNEL_REPLY
#ifndef SHSM_THREAD_TRANSPORT
        threadReplyDelivered = false;
        EventScheduler::get().reset();
        EventScheduler::get().schedule_after(1, deliver_thread_reply);
#endif
#ifdef SHSM_DROP_THREAD_REPLY
        bool dropNow = true;
#ifdef SHSM_DROP_AFTER_REUSE
        dropNow = completedCycles != 0;
#endif
        if (dropNow) {
#ifndef SHSM_DROP_AFTER_ACK
            EventScheduler::get().reset();
#endif
        }
#endif
        EventScheduler::get().advance(c, 1);
#ifdef SHSM_THREAD_IPC_IRQ
        EventScheduler::get().advance(c, 2);
        EventScheduler::get().advance(c, 3);
#endif
#ifdef SHSM_DROP_THREAD_REPLY
        if (dropNow) {
            if (!threadReplyDelivered && c.mmu.read16(0x806902c8) == 4
            && c.mmu.read32(0x806a004c) == 0x80690000 && c.mmu.read32(0x806a0020) ==
#if defined(SHSM_THREAD_IPC_IRQ) && defined(SHSM_DROP_AFTER_ACK)
                8 && c.mmu.read32(0x806a0024) == uint32_t(-6)
#else
                1 && c.mmu.read32(0x806a0024) == (completedCycles ? uint32_t(-6) : 0)
#endif
            ) {
#ifdef SHSM_DROP_AFTER_ACK
                if (c.mmu.read32(0x80528b70) != 1 || threadIpcControl != ackControlAfter) {
                    throw std::runtime_error("ACK-only mutant did not acknowledge original send");
                }
#ifdef SHSM_THREAD_IPC_IRQ
                const auto irq = hw::experiment_ipc_irq_snapshot();
                if (irq.ppcFlags != 0x40000000 || irq.piCause != 0x14000 || threadReplyQueued) {
                    throw std::runtime_error("Prepared-header mutant lacks visible latched reply IRQ");
                }
#endif
                std::cout << "THREAD_ACK_WITHOUT_REPLY_DETECTED\n";
#endif
                std::cout << "THREAD_TRANSPORT_LOST_REPLY_DETECTED\n";
                return 9;
            }
            throw std::runtime_error("Lost-reply mutant did not leave the original thread waiting");
        }
#endif
        if (!threadReplyDelivered || c.mmu.read32(0x806a0024) != uint32_t(-6)) {
            throw std::runtime_error("Kernel reply did not complete");
        }
#else
        func_80241CA0(c);
#endif
#else
        func_8021B5D0(c);
#endif
#ifdef SHSM_DEFERRED_WAKEUP
#ifndef SHSM_THREAD_EXTERNAL_IRQ
        dispatch(c, 0x807f6000);
        dump(c);
        c.gpr[3] = 0x80680000;
        c.pc = 0x80213830;
        c.lr = 0x807f7000;
        func_80213830(c);
        if (c.pc != 0x807f7000) {
            throw std::runtime_error("Interrupted context restoration did not return");
        }
        c.pc = 0x8021a9c0;
        c.lr = 0x807f8000;
        func_8021A9C0(c);
#endif
#endif
        dispatch(c, 0x807f0000);
#ifdef SHSM_THREAD_TRANSPORT
        if (c.gpr[3] != uint32_t(-6)) {
            throw std::runtime_error("Transport did not return computed kernel result");
        }
#ifdef SHSM_THREAD_OPEN
        if (c.mmu.read32(0x804b2b44) != 0 || c.mmu.read32(0x804b2b4c) != 0x806a0000
            || c.mmu.read32(0x806a0004) != 4080) {
            throw std::runtime_error("Original free did not coalesce the request heap");
        }
#endif
#endif
        dump(c);
        ++completedCycles;
#ifdef SHSM_THREAD_VECTOR_RETURN
        c.gpr[3] = 0x806a1300;
        c.pc = 0x8021a440;
        c.lr = 0x807f9000;
        func_8021A440(c);
        if (c.pc != 0x807f9000) {
            throw std::runtime_error("Original return waitqueue initialization failed");
        }
        c.gpr[3] = 0x806a1300;
        c.pc = 0x8021b4e0;
        c.lr = 0x807fa000;
        func_8021B4E0(c);
        dispatch(c, 0x807f4000);
        if (c.mmu.read32(0x800000e4) != 0x80680000 || c.mmu.read32(0x800000d4) != 0x80680000
            || c.mmu.read16(0x806902c8) != 4 || c.mmu.read16(0x806802c8) != 2
            || c.mmu.read32(0x806a1300) != 0x80690000 || (c.mmu.read16(0x806801a2) & 2)) {
            throw std::runtime_error("Original selector did not restore interrupted B");
        }
        dump(c);
#endif
    }
}
