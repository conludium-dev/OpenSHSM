"""Add missing CP breakpoint registers/condition to the existing FIFO backend."""


def adapt_cp(text):
    replacements = [
        ('static uint32_t g_cp_fifo_rp = 0;', '''static uint32_t g_cp_fifo_rp = 0;
static uint32_t g_cp_fifo_bp = 0;

static void update_cp_breakpoint() {
    bool hit = (g_cp_cr & 0x02) &&
        ((g_cp_fifo_rp & 0x1FFFFFFF) == (g_cp_fifo_bp & 0x1FFFFFFF));
    g_cp_sr = (g_cp_sr & ~0x10) | (hit ? 0x10 : 0);
    if (hit && (g_cp_cr & 0x21) == 0x21) {
        trigger_pi_interrupt(0x800);
    } else {
        clear_pi_interrupt(0x800);
    }
}'''),
        ('    while (rp != wp && count++ < 100000) {', '''    while (rp != wp && count++ < 100000) {
        if ((g_cp_cr & 0x02) && (rp == (g_cp_fifo_bp & 0x03FFFFFF))) {
            break;
        }'''),
        ('    g_cp_fifo_rp = rp;', '    g_cp_fifo_rp = rp;\n    update_cp_breakpoint();'),
        ('                case 0xCC00003A: return g_cp_fifo_rp >> 16;', '''                case 0xCC00003A: return g_cp_fifo_rp >> 16;
                case 0xCC00003C: return g_cp_fifo_bp & 0xFFFF;
                case 0xCC00003E: return g_cp_fifo_bp >> 16;'''),
        ('            else if (addr >= 0xCC000038 && addr <= 0xCC00003A) { write_reg32(addr, val, g_cp_fifo_rp); }', '''            else if (addr >= 0xCC000038 && addr <= 0xCC00003A) { write_reg32(addr, val, g_cp_fifo_rp); }
            else if (addr >= 0xCC00003C && addr <= 0xCC00003E) { write_reg32(addr, val, g_cp_fifo_bp); }
            update_cp_breakpoint();'''),
    ]
    for old, new in replacements:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    return text
