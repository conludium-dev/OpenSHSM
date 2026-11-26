#include "Common/FloatUtils.h"
#include <bit>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <limits>

int main() {
    unsigned long long raw = 0;
    uint64_t count = 0;
    uint64_t reciprocal_mismatches = 0;
    uint64_t square_root_mismatches = 0;
    while (std::scanf("%llx", &raw) == 1) {
        const uint64_t bits = static_cast<uint64_t>(raw);
        const double value = std::bit_cast<double>(bits);
        const double reciprocal = Common::ApproximateReciprocal(value);
        const double square_root = Common::ApproximateReciprocalSquareRoot(value);
        const double host_reciprocal = 1.0 / value;
        const double host_square_root = 1.0 / std::sqrt(value);
        if (std::isfinite(value) && value != 0.0) {
            reciprocal_mismatches += std::bit_cast<uint64_t>(reciprocal) !=
                std::bit_cast<uint64_t>(host_reciprocal);
        }
        if (std::isfinite(value) && value > 0.0) {
            square_root_mismatches += std::bit_cast<uint64_t>(square_root) !=
                std::bit_cast<uint64_t>(host_square_root);
        }
        std::printf("%016llx %016llx %016llx\n", raw,
            static_cast<unsigned long long>(std::bit_cast<uint64_t>(reciprocal)),
            static_cast<unsigned long long>(std::bit_cast<uint64_t>(square_root)));
        ++count;
    }
    if (!std::feof(stdin) || std::ferror(stdin) || std::ferror(stdout)) {
        return 2;
    }
    std::fprintf(stderr, "%llu %llu %llu\n",
        static_cast<unsigned long long>(count),
        static_cast<unsigned long long>(reciprocal_mismatches),
        static_cast<unsigned long long>(square_root_mismatches));
    return count && reciprocal_mismatches && square_root_mismatches ? 0 : 3;
}
