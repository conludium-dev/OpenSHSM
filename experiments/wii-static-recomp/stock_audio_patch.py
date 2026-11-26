"""Host audio register adapter; masks checked against Dolphin AI and own Wii initialization."""


def adapt_audio(text):
    start = text.index('void register_ai(')
    assert text.count('void register_ai(') == 1
    return text[:start] + '''static uint64_t ai_fraction = 0;

static void update_audio_counter() {
    if (!(ai_cr & 0x01)) {
        return;
    }
    uint64_t current = nwii::runtime::get_os_time();
    uint32_t rate = (ai_cr & 0x02) ? 48000 : 32000;
    uint64_t scaled = (current - ai_start_time) * rate + ai_fraction;
    uint32_t samples = static_cast<uint32_t>(scaled / 1000000);
    ai_fraction = scaled % 1000000;
    ai_start_time = current;
    if (samples == 0) {
        return;
    }
    uint32_t first = ai_scnt + 1;
    ai_scnt += samples;
    if (ai_it - first <= ai_scnt - first) {
        ai_cr |= 0x08;
    }
    if ((ai_cr & 0x0C) == 0x0C) {
        trigger_pi_interrupt(0x20);
    }
}

void register_ai(MMIODispatcher& dispatcher) {
    dispatcher.register_region(0xCC006C00, 0xCC006CFF,
        [](uint32_t addr) -> uint32_t {
            update_audio_counter();
            switch (addr) {
            case 0xCC006C00: return ai_cr;
            case 0xCC006C04: return ai_vr;
            case 0xCC006C08: return ai_scnt;
            case 0xCC006C0C: return ai_it;
            default: return 0;
            }
        },
        [](uint32_t addr, uint32_t val) {
            update_audio_counter();
            if (addr == 0xCC006C00) {
                if (val & 0x08) {
                    ai_cr &= ~0x08;
                }
                if (val & 0x20) {
                    ai_scnt = 0;
                }
                ai_cr = (ai_cr & 0x08) | (val & ~0x28);
                ai_start_time = nwii::runtime::get_os_time();
                ai_fraction = 0;
                if ((ai_cr & 0x0C) == 0x0C) {
                    trigger_pi_interrupt(0x20);
                } else {
                    clear_pi_interrupt(0x20);
                }
            } else if (addr == 0xCC006C04) {
                ai_vr = val;
            } else if (addr == 0xCC006C08) {
                ai_scnt = val;
                ai_start_time = nwii::runtime::get_os_time();
                ai_fraction = 0;
            } else if (addr == 0xCC006C0C) {
                ai_it = val;
            }
        }
    );
    for (uint32_t base : {0xCD006C00u, 0x0D006C00u}) {
        dispatcher.register_region(base, base + 0xFF,
            [&dispatcher](uint32_t addr) {
                return dispatcher.read32(0xCC006C00 | (addr & 0xFF));
            },
            [&dispatcher](uint32_t addr, uint32_t val) {
                dispatcher.write32(0xCC006C00 | (addr & 0xFF), val);
            }
        );
    }
}

void ai_update() {
    update_audio_counter();
}
}
'''
