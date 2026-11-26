#pragma once
#include <SDL.h>

namespace openshsm::experiment {

inline void register_pc_controller_mappings() {
#if defined(__APPLE__)
    static bool registered = false;
    if (!registered) {
        registered = SDL_GameControllerAddMapping(
            "03000000c82d00001b30000001000000,8BitDo Ultimate 2C Wireless,"
            "a:b0,b:b1,back:b10,dpdown:h0.4,dpleft:h0.8,dpright:h0.2,dpup:h0.1,guide:b12,"
            "leftshoulder:b6,leftstick:b13,lefttrigger:a5,leftx:a0,lefty:a1,"
            "rightshoulder:b7,rightstick:b14,righttrigger:a4,rightx:a2,righty:a3,start:b11,x:b3,y:b4,") >= 0;
    }
#endif
}

inline bool fallback_pc_controller_backend() {
#if defined(__APPLE__)
    if (SDL_NumJoysticks() == 0 && SDL_getenv("SDL_JOYSTICK_MFI") == nullptr) {
        SDL_QuitSubSystem(SDL_INIT_GAMECONTROLLER);
        SDL_SetHint("SDL_JOYSTICK_MFI", "0");
        if (SDL_InitSubSystem(SDL_INIT_GAMECONTROLLER) != 0) {
            SDL_Log("OpenSHSM HID controller fallback failed: %s", SDL_GetError());
            return false;
        }
        SDL_Log("OpenSHSM HID controller fallback: %d device(s)", SDL_NumJoysticks());
    }
#endif
    return true;
}

}
