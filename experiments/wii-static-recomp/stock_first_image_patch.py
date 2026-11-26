"""PC window visibility only; preserve every original startup/guest operation."""
PATCHES = [
    ('uint32_t window_flags = SDL_WINDOW_SHOWN |', 'uint32_t window_flags = SDL_WINDOW_HIDDEN |'),
    ('    while (!quit && ctx->is_running) {',
     '    openshsm::experiment::FirstImageGate first_image;\n    while (!quit && ctx->is_running) {'),
    ('        if (trace_startup) { startup_trace("blit end"); }',
     '''        if (trace_startup) { startup_trace("blit end"); }
        if (!first_image.visible()) {
            std::vector<uint8_t> initial_pixels(640 * 480 * 4);
            glReadPixels(0, 0, 640, 480, GL_RGBA, GL_UNSIGNED_BYTE, initial_pixels.data());
            first_image.observe(initial_pixels.data(), initial_pixels.size());
        }'''),
    ('        SDL_GL_SwapWindow(window);',
     '''        SDL_GL_SwapWindow(window);
        if (first_image.visible() && !(SDL_GetWindowFlags(window) & SDL_WINDOW_SHOWN)) {
            SDL_ShowWindow(window);
        }''')
]


def adapt(text):
    original = text
    for before, after in PATCHES:
        assert text.count(before) == 1
        text = text.replace(before, after, 1)
    text = '#include "stock_first_image.h"\n' + text
    assert restore(text) == original
    return text


def restore(text):
    assert text.startswith('#include "stock_first_image.h"\n')
    text = text.removeprefix('#include "stock_first_image.h"\n')
    for before, after in reversed(PATCHES):
        assert text.count(after) == 1
        text = text.replace(after, before, 1)
    return text
