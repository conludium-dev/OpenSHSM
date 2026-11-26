#include <input/input_manager.h>
#include <input/sources/mouse_keyboard_source.h>
#include <SDL.h>
#include <iostream>
#include <memory>

int main() {
    if (SDL_Init(SDL_INIT_EVENTS) != 0) {
        return 1;
    }
    auto& input = nwii::runtime::input::InputManager::get();
    input.update();
    if (input.get_wiimote_state(0).err != -1) {
        return 2;
    }
    input.add_source(std::make_unique<nwii::runtime::input::MouseKeyboardSource>());
    input.update();
    if (input.get_wiimote_state(0).err != 0 || input.get_gcpad_state(0).err != 0) {
        return 3;
    }
    for (int channel = 1; channel < 4; ++channel) {
        if (input.get_wiimote_state(channel).err != -1) {
            return 4;
        }
    }
    SDL_Quit();
    std::cout << "LINKED_HOST_INPUT_PROVIDER_PRESENT 0/-1 channels verified\n";
    return 0;
}
