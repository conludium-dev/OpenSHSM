#pragma once
#include <SDL.h>
#include <cstdint>
#include <stdexcept>
#include <vector>

namespace openshsm::experiment {

class AdmaOutput {
public:
    ~AdmaOutput() {
        SDL_FreeAudioStream(stream);
    }

    void append(const int16_t* samples, unsigned frames, unsigned rate, std::vector<int16_t>& output) {
        if (rate != 32000 && rate != 48000) {
            throw std::runtime_error("Unsupported ADMA sample rate");
        }
        if (rate != current_rate) {
            finish(output);
            current_rate = rate;
            if (rate == 48000) {
                stream = SDL_NewAudioStream(AUDIO_S16SYS, 2, 48000, AUDIO_S16SYS, 2, 32000);
                if (!stream) {
                    throw std::runtime_error(SDL_GetError());
                }
            }
        }
        if (rate == 32000) {
            insert(samples, frames * 2, output);
        } else {
            if (SDL_AudioStreamPut(stream, samples, int(frames * 4)) != 0) {
                throw std::runtime_error(SDL_GetError());
            }
            drain(output);
        }
    }

    void finish(std::vector<int16_t>& output) {
        if (stream) {
            if (SDL_AudioStreamFlush(stream) != 0) {
                throw std::runtime_error(SDL_GetError());
            }
            drain(output);
            SDL_FreeAudioStream(stream);
            stream = nullptr;
        }
        current_rate = 0;
    }

private:
    static void insert(const int16_t* samples, unsigned count, std::vector<int16_t>& output) {
        if (output.size() + count <= 64000) {
            output.insert(output.end(), samples, samples + count);
        }
    }

    void drain(std::vector<int16_t>& output) {
        for (;;) {
            int16_t samples[512];
            const int bytes = SDL_AudioStreamGet(stream, samples, sizeof(samples));
            if (bytes < 0 || bytes % 4 != 0) {
                throw std::runtime_error("Invalid ADMA converted PCM");
            }
            if (bytes == 0) {
                return;
            }
            insert(samples, unsigned(bytes / 2), output);
        }
    }

    SDL_AudioStream* stream = nullptr;
    unsigned current_rate = 0;
};

}
