"""Keep Wii MEM1 and MEM2 display-list addresses distinct and bounded."""


def parser(text):
    before = '''    uint32_t phys = addr & 0x1FFFFFFF;
    if (!nwii::runtime::g_mmu || size == 0 || size > 0x400000 ||
        phys + size > 0x01800000 || depth >= 4)
        return;'''
    after = '''    uint32_t phys = openshsm::experiment::gx_display_list_physical(addr);
    if (!nwii::runtime::g_mmu || size > 0x400000 || depth >= 4 ||
        !openshsm::experiment::gx_display_list_range(addr, size)) {
        return;
    }'''
    assert text.count(before) == 1
    return '#include "stock_gx_display_list_memory.h"\n' + text.replace(before, after, 1)


def snapshots(text):
    before = '    if (!nwii::runtime::g_mmu || size == 0 || size > (8u << 20)) return;'
    after = '''    if (!nwii::runtime::g_mmu || size > (8u << 20) ||
        !openshsm::experiment::gx_display_list_range(addr, size)) {
        return;
    }'''
    assert text.count(before) == 1
    text = text.replace(before, after, 1)
    before = '(addr & 0x03FFFFFF)'
    assert text.count(before) == 3
    text = text.replace(before, 'openshsm::experiment::gx_display_list_physical(addr)')
    return '#include "stock_gx_display_list_memory.h"\n' + text
