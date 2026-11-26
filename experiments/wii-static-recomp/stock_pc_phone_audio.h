#pragma once
#include <runtime/config.h>

namespace openshsm::experiment {

template <typename Context> void pc_phone_audio_option(Context& ctx) {
    if (nwii::runtime::Config::get().input_mode == 6
        && ctx.gpr[4] == 0x80477328 && ctx.gpr[0] == 17 * 4) {
        ctx.gpr[3] = 1;
    }
}

}

