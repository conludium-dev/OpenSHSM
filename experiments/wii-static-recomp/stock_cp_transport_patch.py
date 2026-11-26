"""Publish real gather bursts and acknowledge CP reads only after existing decoder execution."""

def adapt_pi_transport(text):
    for name in ('base', 'end', 'wptr'):
        old = f'pi_fifo_{name} = val;'
        assert text.count(old) == 1
        text = text.replace(old, f'pi_fifo_{name} = val & 0x1FFFFFE0;')
    return text

def adapt_cp_transport(text):
    text = text.replace('#include <iostream>', '#include <iostream>\n#include <mutex>\n#include <stdexcept>')
    text = text.replace('static uint16_t g_cp_cr = 0;', 'static std::recursive_mutex g_cp_mutex;\nstatic uint16_t g_cp_cr = 0;', 1)
    old = '        reg32 = (reg32 & 0xFFFF) | ((val & 0xFFFF) << 16);\n    }\n}'
    assert text.count(old) == 1
    text = text.replace(old, '        reg32 = (reg32 & 0xFFFF) | ((val & 0xFFFF) << 16);\n    }\n    reg32 &= 0x1FFFFFE0;\n}', 1)
    start = text.index('static void process_cp_fifo() {')
    end = text.index('static uint16_t read_cp_status()', start)
    text = text[:start] + '''static void process_cp_fifo() {
    update_cp_breakpoint();
}

uint32_t cp_fifo_base_reg() {
    std::lock_guard<std::recursive_mutex> lock(g_cp_mutex);
    return g_cp_fifo_base;
}

void cp_gather_bursted(uint32_t pi_base, uint32_t pi_end) {
    std::lock_guard<std::recursive_mutex> lock(g_cp_mutex);
    if (!(g_cp_cr & 0x10)) {
        return;
    }
    const uint32_t base = g_cp_fifo_base & 0x1FFFFFFF;
    const uint32_t end = g_cp_fifo_end & 0x1FFFFFFF;
    const uint32_t wp = g_cp_fifo_wp & 0x1FFFFFFF;
    if (base != (pi_base & 0x1FFFFFFF) || end != (pi_end & 0x1FFFFFFF)
        || end < base || wp < base || wp > end || (wp & 31)) {
        throw std::runtime_error("CP/PI linked FIFO configuration mismatch");
    }
    if (g_cp_fifo_rw_dist > end - base) {
        throw std::runtime_error("CP FIFO overflow on actual gather burst");
    }
    g_cp_fifo_wp = wp == end ? base : wp + 32;
    g_cp_fifo_rw_dist += 32;
    if (g_cp_cr & 1) {
        pi_fifo_set_wptr(g_cp_fifo_wp);
    }
    update_cp_breakpoint();
}

bool cp_fifo_fetch(uint8_t bytes[32], uint32_t& address) {
    std::lock_guard<std::recursive_mutex> lock(g_cp_mutex);
    update_cp_breakpoint();
    if (!g_ctx_ptr || !(g_cp_cr & 1) || g_cp_fifo_rw_dist < 32 || (g_cp_sr & 0x10)) {
        return false;
    }
    address = g_cp_fifo_rp & 0x1FFFFFFF;
    const uint32_t base = g_cp_fifo_base & 0x1FFFFFFF;
    const uint32_t end = g_cp_fifo_end & 0x1FFFFFFF;
    if (address < base || address > end || (address & 31)
        || !g_ctx_ptr->mmu.get_ptr(address) || !g_ctx_ptr->mmu.get_ptr(address + 31)) {
        throw std::runtime_error("Invalid CP FIFO read range");
    }
    for (unsigned i = 0; i < 32; ++i) {
        bytes[i] = g_ctx_ptr->mmu.read8(address + i);
    }
    return true;
}

void cp_fifo_decoded(uint32_t address) {
    std::lock_guard<std::recursive_mutex> lock(g_cp_mutex);
    if ((g_cp_fifo_rp & 0x1FFFFFFF) != address || g_cp_fifo_rw_dist < 32) {
        throw std::runtime_error("CP FIFO changed during decoder transaction");
    }
    const uint32_t base = g_cp_fifo_base & 0x1FFFFFFF;
    const uint32_t end = g_cp_fifo_end & 0x1FFFFFFF;
    g_cp_fifo_rp = address == end ? base : address + 32;
    g_cp_fifo_rw_dist -= 32;
    update_cp_breakpoint();
}

''' + text[end:]
    text = text.replace('[](uint32_t addr) -> uint32_t {', '[](uint32_t addr) -> uint32_t {\n            std::lock_guard<std::recursive_mutex> lock(g_cp_mutex);', 1)
    text = text.replace('[](uint32_t addr, uint32_t val) {', '[](uint32_t addr, uint32_t val) {\n            std::lock_guard<std::recursive_mutex> lock(g_cp_mutex);', 1)
    return text

def adapt_gx_transport(text):
    marker = 'void ProcessGXFifo() {'
    declarations = '''namespace nwii::runtime::hw {
void cp_gather_bursted(uint32_t, uint32_t);
bool cp_fifo_fetch(uint8_t[32], uint32_t&);
void cp_fifo_decoded(uint32_t);
}

'''
    assert text.count(marker) == 1
    text = text.replace(marker, declarations + marker)
    old = '    if (s_parse_buf.empty()) return;'
    assert text.count(old) == 1
    text = text.replace(old, '    if (s_parse_buf.empty() && !nwii::runtime::g_ctx_ptr) return;')
    old = '''    nwii::runtime::gx::FifoParser::Parse(s_parse_buf, commands);
    g_cp_decode_bytes.store(s_parse_buf.size());'''
    new = '''    nwii::runtime::gx::FifoParser::Parse(s_parse_buf, commands);
    g_cp_decode_bytes.store(s_parse_buf.size());
    uint8_t packet[32];
    uint32_t address = 0;
    unsigned bursts = 0;
    while (bursts++ < 4096 && nwii::runtime::hw::cp_fifo_fetch(packet, address)) {
        s_parse_buf.insert(s_parse_buf.end(), packet, packet + 32);
        g_cp_decode_bytes.store(s_parse_buf.size());
        std::vector<nwii::runtime::gx::GXCommand> decoded;
        nwii::runtime::gx::FifoParser::Parse(s_parse_buf, decoded);
        commands.insert(commands.end(), std::make_move_iterator(decoded.begin()),
                        std::make_move_iterator(decoded.end()));
        g_cp_decode_bytes.store(s_parse_buf.size());
        nwii::runtime::hw::cp_fifo_decoded(address);
    }'''
    assert text.count(old) == 1
    text = text.replace(old, new)
    start = text.index('static bool wgp_redirect(uint8_t b) {')
    end = text.index('\nvoid GX_WGPIPE_Write8', start)
    text = text[:start] + '''static uint8_t s_gather[32] = {};
static unsigned s_gather_count = 0;

static bool wgp_redirect(uint8_t b) {
    uint32_t base, end, wptr;
    nwii::runtime::hw::pi_fifo_get(base, end, wptr);
    if (base == 0) {
        return false;
    }
    if (!nwii::runtime::g_mmu || s_gather_count >= 32) {
        throw std::runtime_error("Unavailable write-gather RAM or uncommitted burst");
    }
    s_gather[s_gather_count++] = b;
    if (s_gather_count < 32) {
        return true;
    }
    const uint32_t physical = wptr & 0x1FFFFFFF;
    if ((physical & 31) || physical < (base & 0x1FFFFFFF) || physical > (end & 0x1FFFFFFF)
        || !nwii::runtime::g_mmu->get_ptr(physical) || !nwii::runtime::g_mmu->get_ptr(physical + 31)) {
        throw std::runtime_error("Invalid PI gather-burst destination");
    }
    for (unsigned i = 0; i < 32; ++i) {
        nwii::runtime::g_mmu->write8(physical + i, s_gather[i]);
    }
    nwii::runtime::hw::pi_fifo_set_wptr(physical == (end & 0x1FFFFFFF) ? base : wptr + 32);
    s_gather_count = 0;
    nwii::runtime::hw::cp_gather_bursted(base, end);
    return true;
}
''' + text[end:]
    text = text.replace('throw std::runtime_error("Invalid PI gather-burst destination");',
        'fprintf(stderr, "[CPTRANSPORT] invalid PI base=%08x end=%08x wp=%08x count=%u\\n", base, end, wptr, s_gather_count);\n        fflush(stderr);\n        throw std::runtime_error("Invalid PI gather-burst destination");')
    return text.replace('#include <atomic>', '#include <atomic>\n#include <stdexcept>\n#include <cstdio>', 1)
