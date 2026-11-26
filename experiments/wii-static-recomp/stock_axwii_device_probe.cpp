#include <processor_adapter.h>
#include "hw_dsp.cpp"
#include <fstream>
#include <memory>

int main(int argc, char** argv) {
    if (argc != 2 && argc != 3) {
        return 1;
    }
    const std::string mode = argc == 3 ? argv[2] : "normal";
    const bool polyphase = mode == "polyphase0" || mode == "polyphase1" || mode == "polyphase2" || mode == "polyphase3";
    const bool remote = mode == "remote";
    if (mode != "normal" && mode != "disabled" && mode != "firmware" && mode != "coefficients" && mode != "address" && !polyphase && !remote) {
        return 1;
    }
    using namespace nwii::runtime;
    auto owned = std::make_unique<ProcessorContext>();
    auto& ctx = *owned;
    ctx.is_running = true;
    g_mmu = &ctx.mmu;
    g_ctx_ptr = &ctx;
    ctx.tb_freq = 60750000;
    setenv("OPENSHSM_AXWII_MIXER", mode == "disabled" ? "0" : "1", 1);
    auto& scheduler = EventScheduler::get();
    scheduler.reset();
    auto& mmio = MMIODispatcher::get();
    mmio.clear();
    hw::register_dsp(mmio);
    mmio.write16(0xcc00500a, 0x0100);
    const auto mail = [&](uint32_t value) {
        mmio.write16(0xcc005000, uint16_t(value >> 16));
        mmio.write16(0xcc005002, uint16_t(value));
    };
    const auto read = [&]() {
        return uint32_t(mmio.read16(0xcc005004)) << 16 | mmio.read16(0xcc005006);
    };
    std::array<uint8_t, 8192> firmware{};
    std::ifstream input(argv[1], std::ios::binary);
    input.read(reinterpret_cast<char*>(firmware.data()), firmware.size());
    if (!input || input.peek() != EOF) {
        return 2;
    }
    if (mode == "firmware") {
        firmware[0] ^= 1;
    }
    constexpr uint32_t firmware_address = 0x80004000;
    for (unsigned index = 0; index < firmware.size(); ++index) {
        ctx.mmu.write8(firmware_address + index, firmware[index]);
    }
    (void)read();
    unsigned boot_words = 0;
    uint64_t ticks = 0;
    for (uint32_t word : {0x80f3a001u, firmware_address, 0x80f3c002u, 0u,
            0x80f3a002u, 8192u, 0x80f3b002u, 0u, 0x80f3d001u, 0u}) {
        mail(word);
        ++boot_words;
        if (mode != "disabled") {
            ticks += ctx.tb_freq / 1000 + 1;
            scheduler.advance(ctx, ticks);
            if (boot_words < 10 && (mmio.read16(0xcc005004) & 0x8000)) {
                return 12;
            }
        }
    }
    ticks += ctx.tb_freq / 1000 + 1;
    scheduler.advance(ctx, ticks);
    for (unsigned index = 0; index < (mode == "disabled" ? 10u : 1u); ++index) {
        if (read() != 0xdcd10000) {
            return 3;
        }
    }
    if (mmio.read16(0xcc005004) & 0x8000) {
        return 13;
    }
    constexpr uint32_t list = 0x80560000, init = 0x80570000, lr_input = 0x80571000;
    constexpr uint32_t pb_address = 0x80572000, lr_output = 0x80574000, surround = 0x80575000;
    constexpr uint32_t sample_address = 0x089c8038;
    openshsm::experiment::AxWiiParameterBlock pb;
    pb.words[0] = uint16_t((pb_address + 320) >> 16);
    pb.words[1] = uint16_t(pb_address + 320);
    pb.words[8] = 1;
    pb.words[4] = 2;
    pb.words[60] = 1;
    pb.words[61] = 0xa;
    for (unsigned index : {62u, 64u, 66u}) {
        const uint32_t address = index == 64 ? sample_address + 4095 : sample_address;
        pb.words[index] = uint16_t(address >> 16);
        pb.words[index + 1] = uint16_t(address);
    }
    pb.words[84] = 2048;
    pb.words[58] = pb.words[10] = pb.words[12] = 32768;
    pb.words[7] = 5;
    if (mode == "coefficients") {
        pb.words[4] = 0;
        pb.words[5] = 4;
    } else if (polyphase) {
        pb.words[4] = 0;
        pb.words[5] = unsigned(mode.back() - '0');
        pb.words[88] = 1;
    } else if (remote) {
        pb.words[112] = 1;
        pb.words[113] = 1;
        pb.words[114] = 32768;
    }
    const auto wire = openshsm::experiment::encode_axwii_pb(pb, 0x4cc52064);
    for (unsigned index = 0; index < wire.size(); ++index) {
        ctx.mmu.write8(pb_address + index, wire[index]);
    }
    for (unsigned index = 0; index < 256; ++index) {
        ctx.mmu.write16(sample_address * 2 + index * 2, uint16_t(1000 + index));
    }
    std::vector<uint16_t> program;
    const auto pointer = [&](uint32_t value) { program.push_back(uint16_t(value >> 16)); program.push_back(uint16_t(value)); };
    program.push_back(0); pointer(init);
    program.push_back(1); pointer(lr_input);
    program.push_back(4); pointer(pb_address);
    program.insert(program.end(), {10, 32768, 10, 0x8043, 0xc6c0, 13});
    for (unsigned index = 0; index < 4; ++index) { pointer(0x80576000 + index * 64); }
    program.insert(program.end(), {11, 32768}); pointer(surround); pointer(lr_output);
    program.push_back(14);
    for (unsigned index = 0; index < program.size(); ++index) {
        ctx.mmu.write16(list + index * 2, program[index]);
    }
    if (mode != "normal" && !polyphase && !remote) {
        for (unsigned index = 0; index < 192; ++index) {
            ctx.mmu.write16(lr_output + index * 2, 0x1234);
        }
        mail(0xbabe0080);
        mail(mode == "address" ? 0xfffffffcu : list);
        ticks += ctx.tb_freq / 1000 + 1;
        scheduler.advance(ctx, ticks);
        if (mode == "disabled") {
            if (!ctx.is_running || read() != 0xdcd10002) {
                return 8;
            }
        } else if (ctx.is_running || (mmio.read16(0xcc005004) & 0x8000)) {
            return 9;
        }
        for (unsigned index = 0; index < 192; ++index) {
            if (ctx.mmu.read16(lr_output + index * 2) != 0x1234) {
                return 10;
            }
        }
        if (ctx.mmu.read32(pb_address + 122) != sample_address) {
            return 11;
        }
        scheduler.reset();
        g_mmu = nullptr;
        g_ctx_ptr = nullptr;
        std::cout << "CURRENT_AXWII_DEVICE_GUARD_PASS " << mode << ";PCM/PB unchanged;no false SYNC\n";
        return 0;
    }
    for (unsigned frame = 0; frame < 2; ++frame) {
        mail(0xbabe0080);
        mail(list);
        if (!ctx.is_running || read() != 0xdcd10004) {
            return 4;
        }
        ticks += ctx.tb_freq / 1000 + 1;
        scheduler.advance(ctx, ticks);
        if (read() != 0xdcd10002) {
            return 5;
        }
        mail(frame == 0 ? 0xcdd10003u : 0xcdd10000u);
        ticks += ctx.tb_freq / 1000 + 1;
        scheduler.advance(ctx, ticks);
        if (frame == 0) {
            if (mmio.read16(0xcc005004) & 0x8000) {
                return 14;
            }
        } else if (read() != 0xdcd10001 || (mmio.read16(0xcc005004) & 0x8000)) {
            return 15;
        }
        const auto current = ctx.mmu.read32(pb_address + 122);
        if (current != sample_address + (frame + 1) * 96) {
            return 6;
        }
        float current_volume = frame == 0 ? 0.0f : 32768.0f;
        for (unsigned index = 0; index < 96; ++index) {
            int32_t sample = int32_t(1000 + frame * 96 + index);
            if (polyphase) {
                int64_t total = 0;
                for (unsigned tap = 0; tap < 4; ++tap) {
                    const int position = int(frame * 96 + index) + int(tap) - 3;
                    const int32_t value = position < 0 ? 0 : 1000 + position;
                    total += int64_t(value) * openshsm::experiment::axwii_free_coefficients[pb.words[5] * 512 + tap];
                }
                sample = int32_t(std::clamp(total >> 15, int64_t(-32768), int64_t(32767)));
            }
            current_volume += frame == 0 ? 32768.0f / 96 : 0;
            const uint16_t ramp = uint16_t(current_volume);
            const int16_t expected = int16_t((sample * ramp) >> 15);
            if (int16_t(ctx.mmu.read16(lr_output + index * 4)) != expected ||
                int16_t(ctx.mmu.read16(lr_output + index * 4 + 2)) != expected) {
                std::cerr << "PCM mismatch frame=" << frame << " sample=" << index
                          << " expected=" << expected << " right=" << int16_t(ctx.mmu.read16(lr_output + index * 4))
                          << " left=" << int16_t(ctx.mmu.read16(lr_output + index * 4 + 2)) << "\n";
                return 7;
            }
        }
    }
    if (remote) {
        bool nonzero = false;
        for (unsigned index = 0; index < 18; ++index) {
            nonzero |= ctx.mmu.read16(0x80576000 + index * 2) != 0;
        }
        if (!nonzero) {
            return 16;
        }
    }
    scheduler.reset();
    g_mmu = nullptr;
    g_ctx_ptr = nullptr;
    std::cout << "CURRENT_AXWII_DEVICE_MMIO_PCM_PASS 2 frames;MEM2;PB writeback;SYNC4,YIELD2;single boot INIT;CONTINUE no ACK;RESUME1\n";
    std::cout << "COEFFICIENT_MODE " << mode << "\n";
}
