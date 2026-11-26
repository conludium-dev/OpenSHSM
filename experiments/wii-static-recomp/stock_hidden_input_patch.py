"""Add opt-in, timed Wii-button input to the existing hidden GL diagnostic."""


def adapt(source):
    before = '#include <SDL.h>\n'
    assert source.count(before) == 1
    source = source.replace(before, before + '#include <cstdlib>\n', 1)

    before = '    pads[0].err = 0; \n'
    assert source.count(before) == 1
    after = '''    const char *hidden = SDL_getenv("OPENSHSM_HIDDEN_GL");
    const char *schedule = SDL_getenv("OPENSHSM_HIDDEN_INPUT_SCHEDULE");
    if (hidden && hidden[0] == '1' && schedule) {
        const Uint32 ticks = SDL_GetTicks();
        while (*schedule) {
            char *end = nullptr;
            const unsigned long start = std::strtoul(schedule, &end, 10);
            if (end == schedule || *end != ':') {
                break;
            }
            schedule = end + 1;
            const unsigned long duration = std::strtoul(schedule, &end, 10);
            if (end == schedule || *end != ':') {
                break;
            }
            schedule = end + 1;
            const unsigned long mask = std::strtoul(schedule, &end, 16);
            if (end == schedule || (*end != ';' && *end != '\\0')) {
                break;
            }
            if (start <= ticks && ticks - start < duration && mask <= 0xffff) {
                motes[0].buttons |= static_cast<uint32_t>(mask);
            }
            schedule = *end ? end + 1 : end;
        }
    }
'''
    return source.replace(before, after + before, 1)
