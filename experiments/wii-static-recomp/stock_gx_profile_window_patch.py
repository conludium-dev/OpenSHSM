"""Separate GX profiling intervals from host statistics and gate diagnostic readback."""


def once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('GX profile integration site differs')
    return source.replace(before, after)


def gx(source):
    source = once(source, '    auto t0 = std::chrono::steady_clock::now();', '''    auto t0 = std::chrono::steady_clock::now();
    static auto profile_last = t0;
    static uint64_t profile_parse_us = 0;
    static uint64_t profile_render_us = 0;''')
    source = once(source, '''    g_stat_parse_us +=
        std::chrono::duration_cast<std::chrono::microseconds>(t1 - t0).count();''', '''    const uint64_t parse_us =
        std::chrono::duration_cast<std::chrono::microseconds>(t1 - t0).count();
    g_stat_parse_us += parse_us;
    profile_parse_us += parse_us;''')
    start = source.index('    // [GXPROF]: once a second,')
    end = source.index('\n    if (g_window) {', start)
    block = source[start:end]
    block = block[block.index('    {\n'):]
    block = once(block, '        static auto last = std::chrono::steady_clock::now();\n', '')
    block = block.replace('now - last', 'now - profile_last')
    block = once(block, '            last = now;', '''            const auto interval_us = std::chrono::duration_cast<std::chrono::microseconds>(now - profile_last).count();
            profile_last = now;''')
    block = once(block, 'std::cout << "[GXPROF] parse+decode_ms=" << g_stat_parse_us / 1000', '''std::cout << std::dec << "[GXPROF] parse+decode_ms=" << (profile_parse_us + g_prof_decode_us_accum) / 1000''')
    block = once(block, '                      << " draws_snap="', '''                      << " interval_us=" << interval_us
                      << " parse_us=" << profile_parse_us
                      << " decode_us=" << g_prof_decode_us_accum
                      << " render_us=" << profile_render_us
                      << " draws_snap="''')
    block = once(block, '            g_prof_decode_us_accum = 0;', '''            profile_parse_us = 0;
            profile_render_us = 0;
            g_prof_decode_us_accum = 0;''')
    source = source[:start] + source[end:]
    source = once(source, '''            g_stat_render_us +=
                std::chrono::duration_cast<std::chrono::microseconds>(r1 - r0)
                    .count();''', '''            const uint64_t render_us =
                std::chrono::duration_cast<std::chrono::microseconds>(r1 - r0).count();
            g_stat_render_us += render_us;
            profile_render_us += render_us;''')
    marker = '\n}\n\nnamespace nwii::runtime {\n\nstatic inline void wgp_push'
    return once(source, marker, '\n' + block + marker)


def host(source):
    before = '''          std::vector<unsigned char> p(640 * 480 * 4);
          glBindFramebuffer(GL_READ_FRAMEBUFFER, efb_fbo);
          glReadPixels(0, 48, 640, 480, GL_RGBA, GL_UNSIGNED_BYTE, p.data());
          glBindFramebuffer(GL_READ_FRAMEBUFFER, 0);
          size_t nonblack = 0;
          for (size_t i = 0; i < p.size(); i += 4)
            if (p[i] | p[i + 1] | p[i + 2])
              ++nonblack;'''
    after = '''          static const bool efb_stats = std::getenv("NWII_EFB_STATS") != nullptr;
          size_t nonblack = 0;
          glBindFramebuffer(GL_READ_FRAMEBUFFER, efb_fbo);
          if (efb_stats) {
              std::vector<unsigned char> p(640 * 480 * 4);
              glReadPixels(0, 48, 640, 480, GL_RGBA, GL_UNSIGNED_BYTE, p.data());
              for (size_t i = 0; i < p.size(); i += 4) {
                  if (p[i] | p[i + 1] | p[i + 2]) {
                      ++nonblack;
                  }
              }
          }
          glBindFramebuffer(GL_READ_FRAMEBUFFER, 0);'''
    source = once(source, before, after)
    return once(source, '                    << " efb_nonblack=" << nonblack << "/307200"', '''                    << " efb_readback=" << efb_stats
                    << " efb_nonblack=" << (efb_stats ? std::to_string(nonblack) + "/307200" : "disabled")''')
