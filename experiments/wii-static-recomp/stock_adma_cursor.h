#pragma once
#include <cstdint>
#include <limits>
#include <stdexcept>

namespace openshsm::experiment {

struct AdmaChunk {
    uint32_t address;
    bool interrupt;
};

class AdmaCursor {
public:
    void latch(uint32_t programmed_address, uint16_t programmed_blocks) {
        current_address = programmed_address & 0x1FFFFFE0;
        remaining_blocks = programmed_blocks & 0x7FFF;
    }

    AdmaChunk transfer(uint32_t programmed_address, uint16_t programmed_blocks) {
        const uint32_t address = current_address;
        if (remaining_blocks != 0) {
            --remaining_blocks;
            current_address += 32;
        }
        const bool interrupt = remaining_blocks == 0;
        if (interrupt) {
            latch(programmed_address, programmed_blocks);
        }
        return {address, interrupt};
    }

    uint16_t blocks_left_register() const {
        return remaining_blocks ? remaining_blocks - 1 : 0;
    }

private:
    uint32_t current_address = 0;
    uint16_t remaining_blocks = 0;
};

class AdmaTickPhase {
public:
    uint64_t next(uint64_t tb_frequency, uint32_t sample_rate) {
        if ((sample_rate != 32000 && sample_rate != 48000) || tb_frequency < sample_rate / 8 ||
            tb_frequency > (std::numeric_limits<uint64_t>::max() - 48000) / 8) {
            throw std::runtime_error("Unsupported ADMA clock/rate");
        }
        if (sample_rate != previous_rate) {
            fraction = 0;
            previous_rate = sample_rate;
        }
        const uint64_t numerator = tb_frequency * 8 + fraction;
        fraction = numerator % sample_rate;
        return numerator / sample_rate;
    }

private:
    uint64_t fraction = 0;
    uint32_t previous_rate = 0;
};

}
