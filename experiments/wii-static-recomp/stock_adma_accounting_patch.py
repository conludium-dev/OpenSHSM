"""Mechanically extend the existing converter; scheduling, samples and cap policy stay unchanged."""
def counted_output(text):
    changes = [
        ('    static void insert(', '    void insert('),
        ('            output.insert(output.end(), samples, samples + count);',
            '            output.insert(output.end(), samples, samples + count);\n'
            '            accepted_frames += count / 2;\n        } else {\n'
            '            dropped_frames += count / 2;'),
        ('    SDL_AudioStream* stream = nullptr;',
            '    uint64_t accepted_frames = 0, dropped_frames = 0;\n'
            '    uint64_t flush_accepted_frames = 0, flush_dropped_frames = 0;\n    SDL_AudioStream* stream = nullptr;'),
        ('public:\n', 'public:\n    uint64_t accepted() const { return accepted_frames; }\n'
            '    uint64_t dropped() const { return dropped_frames; }\n'
            '    uint64_t flush_accepted() const { return flush_accepted_frames; }\n'
            '    uint64_t flush_dropped() const { return flush_dropped_frames; }\n'),
        ('    void finish(std::vector<int16_t>& output) {',
            '    void finish(std::vector<int16_t>& output) {\n'
            '        const auto accepted_before = accepted_frames, dropped_before = dropped_frames;'),
        ('        current_rate = 0;',
            '        current_rate = 0;\n'
            '        flush_accepted_frames += accepted_frames - accepted_before;\n'
            '        flush_dropped_frames += dropped_frames - dropped_before;')]
    for before, after in changes:
        assert text.count(before) == 1, before
        text = text.replace(before, after)
    return text

def counted_dsp(text):
    changes = [
        ('#include "stock_dsp_supply.h"', '#include "stock_adma_accounting.h"'),
        ('        const auto before = adma_ring.size() / 2;\n', ''),
        ('        const auto after = adma_ring.size() / 2;\n'
            '        openshsm::experiment::dsp_supply_observer.produced(after - before, before,\n'
            '            after, late, s_adma_period, true);',
            '        openshsm::experiment::dsp_supply_observer.generated(adma_output.accepted(),\n'
            '            adma_output.dropped(), adma_ring.size() / 2, ai_dma_sample_rate(),\n'
            '            ctx.read_timebase(), ctx.tb_freq, adma_output.flush_accepted(), adma_output.flush_dropped());')]
    for before, after in changes:
        assert text.count(before) == 1, before
        text = text.replace(before, after)
    marker = '                    adma_output.finish(adma_ring);'
    # Indentation differs at reset and stop; preserve both existing paths.
    assert text.count('adma_output.finish(adma_ring);') == 2
    text = text.replace('adma_output.finish(adma_ring);',
        'adma_output.finish(adma_ring);\n'
        '                    openshsm::experiment::dsp_supply_observer.synchronize(adma_output.accepted(),\n'
        '                        adma_output.dropped(), adma_ring.size() / 2,\n'
        '                        adma_output.flush_accepted(), adma_output.flush_dropped());')
    return text
