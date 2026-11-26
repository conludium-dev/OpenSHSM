#include "stock_dispatch_lookup.h"

extern "C" size_t stock_dispatch_select_index(const StockDispatchRoute* routes, size_t count, uint32_t target) {
    size_t first = 0;
    size_t remaining = count;
    if (remaining == 0) {
        return count;
    }
    while (remaining > 1) {
        const size_t half = remaining / 2;
        const size_t middle = first + half - 1;
        const bool right = routes[middle].address < target;
        first = right ? first + half : first;
        remaining -= half;
    }
    first += routes[first].address < target;
    return first < count && routes[first].address == target ? first : count;
}
