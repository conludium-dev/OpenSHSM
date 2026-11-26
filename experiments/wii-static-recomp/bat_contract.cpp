#include "loader-bat-seed.h"
#include <cassert>
#include <iostream>

int main() {
    using namespace nwii::runtime;
    SeededBatContext context;
    context.msr = 0x2030;
    context.hid0 = 0x4000;
    context.dbat[3] = {0xa0000002, 0x00600002};
    context.dbat[6] = {0xb0000002, 0x00600022};
    auto bytes = context.mmu.get_ptr(0x618000);
    const std::array<uint8_t, 4> seed{0x11, 0x22, 0x33, 0x44};
    std::copy(seed.begin(), seed.end(), bytes);
    bat_memory_write32(context, 0xa0018000, 0x55667788);
    const auto first = bat_memory_read32(context, 0xa0018000);
    const auto second = bat_memory_read32(context, 0xb0018000);
    bat_memory_cache_operation(context, 0xa0018000, 54);
    const auto third = bat_memory_read32(context, 0xb0018000);
    bat_memory_write32(context, 0xb0018000, 0x99aabbcc);
    const auto fourth = bat_memory_read32(context, 0xa0018000);
    bat_memory_cache_operation(context, 0xa0018000, 470);
    const auto fifth = bat_memory_read32(context, 0xa0018000);
    assert((std::array<uint32_t, 5>{first, second, third, fourth, fifth} ==
            std::array<uint32_t, 5>{0x55667788, 0x11223344, 0x55667788, 0x55667788, 0x99aabbcc}));
    std::cout << "CACHE_SAMPLES " << first << ' ' << second << ' ' << third << ' ' << fourth << ' ' << fifth << '\n';
    bat_memory_write64(context, 0xa001801c, 0x123456789abcdef0ull);
    assert(bat_memory_read64(context, 0xa001801c) == 0x123456789abcdef0ull);
    bat_memory_write64(context, 0x90001000, 0xabcdef0123456789ull);
    assert(bat_memory_read64(context, 0x90001000) == 0xabcdef0123456789ull);
    assert(bat_memory_read64(context, 0xd0001000) == 0);
    bat_memory_cache_operation(context, 0x90001000, 54);
    assert(bat_memory_read64(context, 0xd0001000) == 0xabcdef0123456789ull);
    bat_memory_write_f32(context, 0x90001020, -1.25f);
    assert(bat_memory_read_f32(context, 0x90001020) == -1.25f);
    bat_memory_write_f64(context, 0x90001028, 2.5);
    assert(bat_memory_read_f64(context, 0x90001028) == 2.5);
    context.instructionImages.emplace_back(0x80600000, std::vector<uint8_t>(0x60000));
    unsigned refusals = 0;
    auto refused = [&](auto action) {
        const auto ibat = context.ibat;
        const auto dbat = context.dbat;
        const auto hid4 = context.hid4;
        bool caught = false;
        try {
            action();
        } catch (const std::runtime_error&) {
            caught = true;
        }
        assert(caught && context.hid4 == hid4);
        for (unsigned index = 0; index < 8; ++index) {
            assert(context.ibat[index].upper == ibat[index].upper && context.ibat[index].lower == ibat[index].lower);
            assert(context.dbat[index].upper == dbat[index].upper && context.dbat[index].lower == dbat[index].lower);
        }
        ++refusals;
    };
    refused([&] { experiment_write_hid4(context, 0); });
    context.msr |= 0x4000;
    refused([&] { experiment_write_hid4(context, 0x83900000); });
    refused([&] { experiment_read_bat(context, false, 0, false); });
    context.msr = 0xa030;
    refused([&] { experiment_write_hid4(context, 0x83900000); });
    context.msr = 0x2030;
    refused([&] { experiment_write_bat(context, false, 8, false, 0); });
    refused([&] { bat_memory_range(context, 0xffffffff, 8); });
    refused([&] { bat_memory_range(context, 0x80000000, 0); });
    refused([&] { bat_memory_read32(context, 0xcc000000); });
    refused([&] { bat_memory_read32(context, 0x70000000); });
    refused([&] { bat_memory_write32(context, 0xa0018000, 0); });
    context.ibat[1] = {0x80620002, 0x00620002};
    refused([&] { experiment_write_bat(context, true, 1, true, 0x00700002); });
    bat_validate_images(context, context.ibat, context.hid4);
    std::cout << "BAT_CONTRACT shared-cache/MEM1-MEM2/typed-memory PASS guards=" << refusals << '\n';
}
