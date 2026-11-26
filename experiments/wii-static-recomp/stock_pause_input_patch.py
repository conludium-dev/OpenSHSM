"""Route PC pause controls to the existing Wii input sources."""


def replace_once(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old, new, 1)


def keyboard(source):
    source = replace_once(source,
        '    if (keys[SDL_SCANCODE_RETURN]) motes[0].buttons |= 0x0010; \n',
        '    if (keys[SDL_SCANCODE_RETURN] || keys[SDL_SCANCODE_ESCAPE]) motes[0].buttons |= 0x0200; \n'
        '    if (keys[SDL_SCANCODE_F]) motes[0].buttons |= 0x0010; \n')
    return source


def gamepad(source):
    source = replace_once(source,
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_START)) motes[i].buttons |= 0x0010; \n',
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_START)) motes[i].buttons |= 0x0200; \n'
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_RIGHTSHOULDER)) motes[i].buttons |= 0x0010; \n')
    return source


def manager_header(source):
    return source


def manager(source):
    return replace_once(source,
        '        if (queue.size() == 16) {\n'
        '            queue.pop_front();\n'
        '            ++dropped_snapshots[channel];\n'
        '        }\n',
        '        if (queue.size() == 16) {\n'
        '            const uint32_t pause = queue.front().mote.err == 0'
        ' ? queue.front().mote.buttons & 0x0200 : 0;\n'
        '            queue.pop_front();\n'
        '            if (pause != 0 && queue.front().mote.err == 0) {\n'
        '                queue.front().mote.buttons |= pause;\n'
        '            }\n'
        '            ++dropped_snapshots[channel];\n'
        '        }\n')
