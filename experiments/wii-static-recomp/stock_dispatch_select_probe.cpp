#include "stock_dispatch_lookup.h"
#include <algorithm>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <vector>
extern "C" size_t stock_dispatch_select_index(const StockDispatchRoute*, size_t, uint32_t);
static volatile size_t sink = 0;

int main(int argc, char** argv) {
    assert(argc == 3);
    FILE* input = std::fopen(argv[1], "rb");
    assert(input);
    std::vector<StockDispatchRoute> routes;
    uint32_t address;
    while (std::fread(&address, sizeof(address), 1, input) == 1) {
        routes.push_back({address, nullptr});
    }
    std::fclose(input);
    assert(!routes.empty());
    size_t verified = 0;
    auto check = [&](const auto& table, uint32_t target) {
        const auto expected_iterator = std::lower_bound(table.begin(), table.end(), target,
            [](const auto& route, uint32_t key) { return route.address < key; });
        const size_t expected = expected_iterator != table.end() && expected_iterator->address == target
            ? size_t(expected_iterator - table.begin()) : table.size();
        assert(stock_dispatch_index(table.data(), table.size(), target) == expected);
        assert(stock_dispatch_select_index(table.data(), table.size(), target) == expected);
        ++verified;
    };
    std::vector<uint32_t> boundaries{0};
    for (const auto& route : routes) {
        boundaries.push_back(route.address);
        if (route.address != UINT32_MAX) {
            boundaries.push_back(route.address + 1);
        }
    }
    boundaries.push_back(UINT32_MAX);
    std::sort(boundaries.begin(), boundaries.end());
    boundaries.erase(std::unique(boundaries.begin(), boundaries.end()), boundaries.end());
    for (size_t i = 0; i < boundaries.size(); ++i) {
        check(routes, boundaries[i]);
        if (i + 1 < boundaries.size()) {
            check(routes, boundaries[i + 1] - 1);
            check(routes, boundaries[i] + (boundaries[i + 1] - boundaries[i]) / 2);
        }
    }
    const std::vector<StockDispatchRoute> duplicates{{0, nullptr}, {0, nullptr}, {7, nullptr},
        {7, nullptr}, {UINT32_MAX, nullptr}};
    const std::vector<StockDispatchRoute> empty;
    for (uint32_t target : {0u, 1u, 6u, 7u, 8u, UINT32_MAX}) {
        check(duplicates, target);
        check(empty, target);
    }
    for (unsigned count = 1; count <= 65; ++count) {
        std::vector<StockDispatchRoute> synthetic;
        for (unsigned index = 0; index < count; ++index) {
            synthetic.push_back({index / 3 * 7, nullptr});
        }
        for (uint32_t target = 0; target < 170; ++target) {
            check(synthetic, target);
        }
        check(synthetic, UINT32_MAX);
    }
    std::printf("SELECT_ROUTE_PARTITIONS_EQUAL %zu\n", verified);
    std::vector<uint32_t> queries;
    uint32_t random = 0x5348534D;
    for (unsigned i = 0; i < 262144; ++i) {
        random ^= random << 13;
        random ^= random >> 17;
        random ^= random << 5;
        queries.push_back(routes[random % routes.size()].address + (i % 5 == 0 ? 1 : 0));
    }
    for (unsigned pattern = 0; pattern < 2; ++pattern) {
        if (pattern == 1) {
            input = std::fopen(argv[2], "rb");
            assert(input);
            std::vector<uint32_t> sampled;
            while (std::fread(&address, sizeof(address), 1, input) == 1) {
                sampled.push_back(address);
                check(routes, address);
            }
            std::fclose(input);
            assert(!sampled.empty());
            for (size_t i = 0; i < queries.size(); ++i) {
                queries[i] = sampled[i % sampled.size()];
            }
        }
        for (unsigned run = 0; run < 5; ++run) {
            for (unsigned order = 0; order < 2; ++order) {
                const bool candidate = bool((order + run) % 2);
                auto function = candidate ? stock_dispatch_select_index : stock_dispatch_index;
                size_t total = 0;
                const auto start = std::chrono::steady_clock::now();
                for (uint32_t target : queries) {
                    total += function(routes.data(), routes.size(), target);
                }
                const auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(
                    std::chrono::steady_clock::now() - start).count();
                sink = total;
                std::printf("BATCH pattern=%u run=%u candidate=%u ns=%lld queries=%zu checksum=%zu\n",
                    pattern, run, candidate, (long long)elapsed, queries.size(), total);
            }
        }
    }
}
