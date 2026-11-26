"""Convert Wii ADMA big-endian right/left frames to SDL host-endian left/right frames."""


def adapt(source):
    before = '''    for (unsigned i = 0; i < 16; ++i) {
        samples[i] = int16_t(g_mmu->read16(va + i * 2));
    }'''
    if source.count(before) != 1:
        raise ValueError('ADMA PCM decoding site differs')
    return '#include "stock_adma_pcm.h"\n' + source.replace(before,
        '    openshsm::experiment::read_adma_stereo(*g_mmu, va, samples);', 1)
