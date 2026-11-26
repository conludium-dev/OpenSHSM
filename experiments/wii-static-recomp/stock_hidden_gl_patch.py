"""Keep the existing GL game path invisible and silent for private diagnostics."""


def adapt(text):
    before = '  bool headless = headless_env && headless_env[0] == \'1\';\n'
    after = before + (
        '  const char *hidden_gl_env = std::getenv("OPENSHSM_HIDDEN_GL");\n'
        '  bool hidden_gl = hidden_gl_env && hidden_gl_env[0] == \'1\';\n')
    assert text.count(before) == 1
    text = text.replace(before, after, 1)

    before = '    audio_dev = SDL_OpenAudioDevice(NULL, 0, &want, &have, 0);\n'
    after = '    if (!hidden_gl) {\n' + before + '    }\n'
    assert text.count(before) == 1
    text = text.replace(before, after, 1)

    before = '        if (first_image.visible() && !(SDL_GetWindowFlags(window) & SDL_WINDOW_SHOWN)) {\n'
    after = '        if (!hidden_gl && first_image.visible() && !(SDL_GetWindowFlags(window) & SDL_WINDOW_SHOWN)) {\n'
    assert text.count(before) == 1
    text = text.replace(before, after, 1)

    before = '          if ((++shot_frame % 300) == 0) {\n'
    after = '          if ((++shot_frame % (hidden_gl ? 120 : 300)) == 0) {\n'
    assert text.count(before) == 1
    text = text.replace(before, after, 1)
    return text
