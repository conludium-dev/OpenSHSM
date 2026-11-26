#pragma once
#include <cstddef>
#include <cstdint>

namespace openshsm::experiment {

class FirstImageGate {
public:
    bool visible() const {
        return revealed;
    }

    bool observe(const uint8_t* rgba, std::size_t bytes) {
        if (revealed) {
            return true;
        }
        if (!rgba || bytes != 640 * 480 * 4) {
            return false;
        }
        constexpr std::size_t reference = (24 * 640 + 32) * 4;
        for (std::size_t y = 24; y < 456; ++y) {
            for (std::size_t x = 32; x < 608; ++x) {
                const std::size_t i = (y * 640 + x) * 4;
                if (rgba[i] != rgba[reference] || rgba[i + 1] != rgba[reference + 1] || rgba[i + 2] != rgba[reference + 2]) {
                    revealed = true;
                    return true;
                }
            }
        }
        return revealed;
    }

private:
    bool revealed = false;
};

}
