#pragma once
#include <cstddef>
#include <cstdint>

struct StockBoundsRange {
    uint32_t start;
    uint32_t end;
    uint32_t original_index;
};

inline uint32_t stock_bounds_index(const StockBoundsRange* ranges, size_t count, uint32_t target) {
    size_t first = 0;
    size_t last = count;
    while (first < last) {
        size_t middle = first + (last - first) / 2;
        if (ranges[middle].start <= target) {
            first = middle + 1;
        } else {
            last = middle;
        }
    }
    if (first != 0 && target < ranges[first - 1].end) {
        return ranges[first - 1].original_index;
    }
    return UINT32_MAX;
}
