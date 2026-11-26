"""Avoid repeated environment scans and source copies in vertex transformation."""


def renderer(text):
    before = '''  if (std::getenv("NWII_FLATZ")) {
    bv.z = 0.0f;
  }'''
    after = '''    static const bool flat_z = std::getenv("NWII_FLATZ") != nullptr;
    if (flat_z) {
        bv.z = 0.0f;
    }'''
    if text.count(before) != 1:
        raise ValueError('Unexpected vertex diagnostic flag source')
    text = text.replace(before, after, 1)
    before = '''        auto source = cmd.raw->sources[index];
        if (row >= 5 && row <= 12 && !source.has_uv[row - 5]) {
            source.uv[row - 5] = {0.0f, 0.0f};
            source.has_uv[row - 5] = true;
        }
        const auto coordinate = openshsm::experiment::generate_draw_regular_texcoord(
            source, g_state, s_post_matrices, channel);'''
    after = '''        const auto& original_source = cmd.raw->sources[index];
        openshsm::experiment::GxTexVector coordinate;
        if (row >= 5 && row <= 12 && !original_source.has_uv[row - 5]) {
            auto source = original_source;
            source.uv[row - 5] = {0.0f, 0.0f};
            source.has_uv[row - 5] = true;
            coordinate = openshsm::experiment::generate_draw_regular_texcoord(
                source, g_state, s_post_matrices, channel);
        } else {
            coordinate = openshsm::experiment::generate_draw_regular_texcoord(
                original_source, g_state, s_post_matrices, channel);
        }'''
    if text.count(before) != 1:
        raise ValueError('Unexpected vertex texgen source')
    return text.replace(before, after, 1)
