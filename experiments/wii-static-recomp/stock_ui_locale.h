#pragma once
#include <SDL.h>

namespace openshsm::experiment {

inline bool use_russian_ui() {
    static const bool russian = [] {
        const char* override_value = SDL_getenv("OPENSHSM_LANGUAGE");
        if (override_value && *override_value) {
            if (SDL_strncasecmp(override_value, "ru", 2) == 0) {
                return true;
            }
            if (SDL_strncasecmp(override_value, "en", 2) == 0) {
                return false;
            }
        }
        SDL_Locale* locales = SDL_GetPreferredLocales();
        const bool preferred = locales && locales[0].language &&
            SDL_strncasecmp(locales[0].language, "ru", 2) == 0;
        SDL_free(locales);
        return preferred;
    }();
    return russian;
}

inline const char* ui_text(const char* english, const char* russian) {
    return use_russian_ui() ? russian : english;
}

}
