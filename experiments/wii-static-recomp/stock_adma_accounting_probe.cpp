#include <stock_adma_output.h>
#include <array>
#include <cassert>
#include <cstdio>
#include <iostream>
#include <vector>

int main(int argc, char** argv) {
    assert(argc == 2);
    using openshsm::experiment::AdmaOutput;
    std::array<int16_t, 16> samples{};
    for (unsigned i = 0; i < samples.size(); ++i) {
        samples[i] = int16_t(int(i) * 901 - 7000);
    }
    AdmaOutput capped;
    std::vector<int16_t> full(63990, 77);
    capped.append(samples.data(), 8, 32000, full);
    assert(full.size() == 63990);
    full.resize(63984);
    capped.append(samples.data(), 8, 32000, full);
    assert(full.size() == 64000);
    capped.append(samples.data(), 8, 32000, full);
    capped.finish(full);
#ifdef COUNTED
    assert(capped.accepted() == 8 && capped.dropped() == 16);
    assert(capped.flush_accepted() == 0 && capped.flush_dropped() == 0);
#endif
    AdmaOutput switched;
    std::vector<int16_t> pcm;
    for (unsigned i = 0; i < 150; ++i) {
        switched.append(samples.data(), 8, 48000, pcm);
    }
    switched.append(samples.data(), 8, 32000, pcm);
    assert(pcm.size() == 808 * 2);
    switched.append(samples.data(), 8, 48000, pcm);
    const auto before = pcm.size();
    switched.finish(pcm);
    assert(pcm.size() >= before);
#ifdef COUNTED
    assert(switched.accepted() == pcm.size() / 2 && switched.dropped() == 0);
    assert(switched.flush_accepted() > 0 && switched.flush_dropped() == 0);
#endif
    AdmaOutput flush_capped;
    std::vector<int16_t> capped_pcm;
    for (unsigned i = 0; i < 150; ++i) {
        flush_capped.append(samples.data(), 8, 48000, capped_pcm);
    }
    capped_pcm.resize(64000, 123);
    flush_capped.finish(capped_pcm);
#ifdef COUNTED
    assert(flush_capped.flush_dropped() > 0);
#endif
    auto* file = std::fopen(argv[1], "wb");
    assert(file && std::fwrite(pcm.data(), sizeof(int16_t), pcm.size(), file) == pcm.size());
    assert(std::fclose(file) == 0);
    std::cout << "ADMA_ACCOUNTING_CAP_SWITCH_PCM_PASS frames=" << pcm.size() / 2 << '\n';
}
