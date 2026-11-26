"""Make per-draw diagnostic clock reads opt-in without changing GX commands."""


def parser(source):
    before = '            auto sn0 = std::chrono::steady_clock::now();'
    after = '''            static const bool snapshot_timing = std::getenv("NWII_GX_SNAPSHOT_TIMING") != nullptr;
            std::chrono::steady_clock::time_point sn0{};
            if (snapshot_timing) {
                sn0 = std::chrono::steady_clock::now();
            }'''
    if source.count(before) != 1:
        raise ValueError('GX snapshot timing start differs')
    source = source.replace(before, after)
    before = '''            g_prof_snap_us += std::chrono::duration_cast<std::chrono::microseconds>(
                std::chrono::steady_clock::now() - sn0).count();'''
    after = '''            if (snapshot_timing) {
                g_prof_snap_us += std::chrono::duration_cast<std::chrono::microseconds>(
                    std::chrono::steady_clock::now() - sn0).count();
            }'''
    if source.count(before) != 1:
        raise ValueError('GX snapshot timing end differs')
    return source.replace(before, after)


def gx(source):
    before = '                      << " snap_ms=" << fp::g_prof_snap_us / 1000\n'
    after = before + '                      << " snap_timing=" << (std::getenv("NWII_GX_SNAPSHOT_TIMING") != nullptr)\n'
    if source.count(before) != 1:
        raise ValueError('GX snapshot timing report differs')
    return source.replace(before, after)
