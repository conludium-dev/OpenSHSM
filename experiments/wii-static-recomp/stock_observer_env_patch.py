"""Latch immutable per-process diagnostic flags; never bypass guest execution checks."""
def idct(text):
    marker = '    if (!std::getenv("NWII_THPDUMP")) {\n        return;\n    }'
    assert text.count(marker) == 1
    return text.replace(marker, '    static const bool enabled = std::getenv("NWII_THPDUMP") != nullptr;\n'
        '    if (!enabled) {\n        return;\n    }')

def ios(text):
    marker = '  if (std::getenv("NWII_SAMPLE")) {'
    start = text.index('bool process_pending_callbacks(CPUContext &ctx) {')
    position = text.index(marker, start)
    assert position - start < 100
    replacement = '  static const bool sample_enabled = std::getenv("NWII_SAMPLE") != nullptr;\n'
    replacement += '  if (sample_enabled) {'
    return text[:position] + replacement + text[position + len(marker):]
