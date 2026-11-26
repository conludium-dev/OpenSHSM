"""Observe original FMOD Event::start returns through the existing ADMA host report."""
import struct


def guest(text, dol):
    address = 0x80392400
    layout = struct.unpack('>64I', dol[:256])
    section = next(i for i in range(18) if layout[18 + i] <= address
        and address + 4 <= layout[18 + i] + layout[36 + i])
    word = struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0]
    marker = 'loc_80392400: ;\n'
    if word != 0x4e800020 or text.count(marker) != 1 or \
            '// 0x80392400: 4E800020' not in text or 'stock_fmod_event_accounting.h' in text:
        raise ValueError('Original FMOD start return site differs')
    return '#include "stock_fmod_event_accounting.h"\n' + text.replace(marker,
        marker + '    nwii::runtime::hw::dsp_record_fmod_event_result(ctx.gpr[3]);\n', 1)


def dsp(text):
    marker = 'void dsp_audio_report() {'
    if text.count(marker) != 1 or 'void dsp_record_fmod_event_result(' in text:
        raise ValueError('FMOD result accounting integration site differs')
    helper = '''void dsp_record_fmod_event_result(uint32_t status) {
    auto& observer = openshsm::experiment::dsp_supply_observer;
    if (!observer.is_enabled()) {
        return;
    }
    std::lock_guard<std::mutex> lock(adma_mutex);
    observer.fmod_event_result(status);
}

'''
    return text.replace(marker, helper + marker, 1)
