"""CP idle registers follow existing FIFO/decoder work, not guessed guest readiness."""

def adapt_cp_idle(text):
    old = 'void GX_WGPIPE_Write8(uint8_t val);'
    assert text.count(old) == 1
    text = text.replace(old, old + '\nuint16_t GX_CPIdleBits();')
    old = 'static int cp_debug_count = 0;'
    new = '''static uint16_t read_cp_status() {
    const uint16_t host_idle = nwii::runtime::GX_CPIdleBits();
    const bool empty = g_cp_fifo_rw_dist == 0;
    const bool read_idle = (empty || g_cp_fifo_rp == g_cp_fifo_wp) && (host_idle & 0x04);
    const bool command_idle = (empty || (g_cp_sr & 0x10) || !(g_cp_cr & 1)) && (host_idle & 0x08);
    return (g_cp_sr & ~0x0C) | (read_idle ? 0x04 : 0) | (command_idle ? 0x08 : 0);
}

static int cp_debug_count = 0;'''
    assert text.count(old) == 1
    text = text.replace(old, new)
    old = 'case 0xCC000000: return g_cp_sr;'
    assert text.count(old) == 1
    return text.replace(old, 'case 0xCC000000: return read_cp_status();')

def adapt_gx_idle(text):
    changes = [
        ('#include <mutex>', '#include <mutex>\n#include <atomic>'),
        ('std::vector<uint8_t> g_hw_fifo;', '''std::vector<uint8_t> g_hw_fifo;
static std::atomic<size_t> g_cp_decode_bytes{0};

namespace nwii::runtime {
uint16_t GX_CPIdleBits() {
    std::lock_guard<std::mutex> lock(g_fifo_mutex);
    const bool unread_empty = g_hw_fifo.empty();
    const bool decoder_empty = g_cp_decode_bytes.load() == 0;
    return (unread_empty ? 0x04 : 0) | (unread_empty && decoder_empty ? 0x08 : 0);
}
}'''),
        ('            g_hw_fifo.clear();', '            g_cp_decode_bytes.store(s_parse_buf.size());\n            g_hw_fifo.clear();'),
        ('    nwii::runtime::gx::FifoParser::Parse(s_parse_buf, commands);', '    nwii::runtime::gx::FifoParser::Parse(s_parse_buf, commands);\n    g_cp_decode_bytes.store(s_parse_buf.size());'),
        ('    if (s_parse_buf.size() > (4u << 20))\n        s_parse_buf.clear();', '''    if (s_parse_buf.size() > (4u << 20)) {
        s_parse_buf.clear();
        g_cp_decode_bytes.store(0);
    }'''),
    ]
    for old, new in changes:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    return text
