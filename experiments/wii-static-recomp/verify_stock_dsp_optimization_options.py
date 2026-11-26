"""Check DSP-only flag selection and refusal of unsafe experiment object reuse."""
from pathlib import Path
import json
import tempfile

from build_stock_owner_windows import RUNTIME_O2_MEMBERS, runtime_compile_flags, validate_dsp_resume, windows_main_source


def main():
    assert 'hw_dsp.cpp' not in RUNTIME_O2_MEMBERS
    assert runtime_compile_flags('hw_dsp.cpp') == ['-g', '-std=gnu++20']
    assert runtime_compile_flags('hw_dsp.cpp', True) == [
        '-g', '-std=gnu++20', '-O2', '-fno-strict-aliasing', '-fwrapv', '-ffp-contract=off']
    for name in ['gx.cpp', 'ios.cpp', 'hw_ai.cpp', 'event_scheduler.cpp']:
        assert runtime_compile_flags(name) == runtime_compile_flags(name, True)
    with tempfile.TemporaryDirectory(prefix='openshsm-dsp-options-') as temporary:
        root = Path(temporary)
        validate_dsp_resume(root, False, True)
        validate_dsp_resume(root, True, False)
        try:
            validate_dsp_resume(root, True, True)
        except ValueError:
            pass
        else:
            raise AssertionError('Optimized experiment reused old objects')
        report = root / 'build-result.json'
        report.write_text(json.dumps({'dependencies': {'runtimeO2Members': ['hw_dsp.cpp']}}))
        try:
            validate_dsp_resume(root, True, False)
        except ValueError:
            pass
        else:
            raise AssertionError('Baseline reused optimized DSP object')
        report.write_text(json.dumps({'dependencies': {'runtimeO2Members': ['gx.cpp']}}))
        validate_dsp_resume(root, True, False)
    sample = 'SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 2);\n' + \
        '      std::cout << "[GL] " << (const char *)glGetString(GL_RENDERER)'
    adapted = windows_main_source(sample)
    assert 'SDL_GL_CONTEXT_MINOR_VERSION, 3)' in adapted
    assert '!glGenSamplers || !glBindSampler' in adapted
    print('DSP_O2_FLAGS_AND_REUSE_GUARDS_PASS;WINDOWS_GL33_GUARD_RETAINED')


if __name__ == '__main__':
    main()
