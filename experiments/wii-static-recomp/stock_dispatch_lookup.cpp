#include "stock_dispatch_lookup.h"

extern "C" size_t stock_dispatch_index(const StockDispatchRoute* routes, size_t count, uint32_t target) {
    size_t first = 0;
    size_t last = count;
    while (first < last) {
        const size_t middle = first + (last - first) / 2;
        if (routes[middle].address < target) {
            first = middle + 1;
        } else {
            last = middle;
        }
    }
    if (first < count && routes[first].address == target) {
        return first;
    }
    return count;
}
