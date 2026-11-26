#include "stock_thp_snapshot.h"
#define main unused_frame_replay_main
#include "stock_thp_frame_replay.cpp"
#undef main

int main(int argc, char** argv) {
    if (argc != 2) {
        return 8;
    }
    auto a = std::make_unique<nwii::runtime::ProcessorContext>();
    auto b = std::make_unique<nwii::runtime::ProcessorContext>();
    a->pc = 0x80209D80;
    a->lr = 0x8009C5E4;
    a->msr = 0x9032;
    a->hid2 = 0xA0000000;
    a->inst_count = 0x123456789ABCu;
    a->fpr[0] = std::bit_cast<double>(0x7FF8000012345678ull);
    a->ps1[0] = -0.0;
    a->gpr[3] = 0x91000000;
    a->cr[1].lt = true;
    a->dma_u = 0x13579000;
    a->mmu.mem2[123] = 0xA5;
    const auto before1 = a->mmu.mem1, before2 = a->mmu.mem2, before_cache = a->mmu.locked_cache;
    stock_thp_snapshot::observe(*a);
    stock_thp_snapshot::observe(*a);
    load(*b, argv[1]);
    if (a->mmu.mem1 != before1 || a->mmu.mem2 != before2 || a->mmu.locked_cache != before_cache
        || a->gpr != b->gpr || a->gqr != b->gqr || a->sprg != b->sprg || a->msr != b->msr
        || a->pc != b->pc || a->lr != b->lr || a->hid2 != b->hid2 || a->dma_u != b->dma_u
        || a->inst_count != b->inst_count || !b->cr[1].lt
        || std::memcmp(a->fpr.data(), b->fpr.data(), sizeof(a->fpr)) != 0
        || std::memcmp(a->ps1.data(), b->ps1.data(), sizeof(a->ps1)) != 0
        || b->mmu.mem1 != before1 || b->mmu.mem2 != before2 || b->mmu.locked_cache != before_cache) {
        return 9;
    }
    std::cout << "THP_SNAPSHOT_FORMAT_NONMUTATION_PASS\n";
}
