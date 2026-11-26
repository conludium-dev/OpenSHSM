"""Expose accepted linked-FIFO writes through existing private capture hooks."""


def adapt(text):
    marker = '        s_parse_buf.insert(s_parse_buf.end(), packet, packet + 32);'
    assert text.count(marker) == 1
    text = text.replace(marker, '        const uint32_t observed_prior_bytes = uint32_t(s_parse_buf.size());\n' + marker)
    marker = '        nwii::runtime::gx::FifoParser::Parse(s_parse_buf, decoded);'
    assert text.count(marker) == 1
    text = text.replace(marker, marker + '''
        if (const char* path = std::getenv("NWII_CPSTREAM")) {
            static FILE* capture = fopen(path, "wb");
            static unsigned count = 0;
            if (capture && count < 524288) {
                for (uint32_t value : {address, observed_prior_bytes, uint32_t(s_parse_buf.size())}) {
                    uint8_t bytes[4] = {uint8_t(value >> 24), uint8_t(value >> 16), uint8_t(value >> 8), uint8_t(value)};
                    fwrite(bytes, 1, 4, capture);
                }
                fwrite(packet, 1, 32, capture);
                fflush(capture);
                ++count;
            }
        }
''')
    start = text.index('static inline void wgp_push(uint8_t b) {')
    end = text.index('\n}', start) + 2
    original = text[start:end]
    assert original.count('    g_hw_fifo.push_back(b);') == 1
    observer = original.replace('wgp_push(uint8_t b)', 'wgp_observe(uint8_t b)')
    observer = observer.replace('    g_hw_fifo.push_back(b);', '')
    observer = observer.replace('n < 4000000', 'n < 16777216')
    observer = observer.replace('            fflush(f);\n', '            if ((n & 31) == 31) { fflush(f); }\n')
    observer = observer.replace('            last_pc = pc;', '            fflush(sf);\n            last_pc = pc;')
    observer += '''

static inline void wgp_push(uint8_t b) {
    wgp_observe(b);
    g_hw_fifo.push_back(b);
}'''
    text = text[:start] + observer + text[end:]
    marker = '    s_gather[s_gather_count++] = b;'
    assert text.count(marker) == 1
    text = text.replace(marker, '    wgp_observe(b);\n' + marker)
    marker = '    s_gather_count = 0;\n    nwii::runtime::hw::cp_gather_bursted(base, end);'
    assert text.count(marker) == 1
    text = text.replace(marker, '''    if (const char* path = std::getenv("NWII_WGBURSTS")) {
        static FILE* capture = fopen(path, "wb");
        static unsigned count = 0;
        if (capture && count < 524288) {
            uint8_t address[4] = {uint8_t(physical >> 24), uint8_t(physical >> 16), uint8_t(physical >> 8), uint8_t(physical)};
            fwrite(address, 1, 4, capture);
            fwrite(s_gather, 1, 32, capture);
            fflush(capture);
            ++count;
        }
    }
''' + marker)
    return text
