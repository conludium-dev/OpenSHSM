"""Replace only the existing synthetic console-configuration producer."""


def adapt(text):
    start = text.index('static std::vector<uint8_t> make_sysconf() {')
    end = text.index('static std::vector<uint8_t> make_setting_txt()', start)
    original = text[start:end]
    assert 'uint8_t key[] = "IPL.AR";' in original
    assert "sc[3]='1'; sc[4]='5';" in original
    return '#include "stock_sysconf.h"\n' + text[:start] + '''static std::vector<uint8_t> make_sysconf() {
    return openshsm::experiment::wii_sysconf_aspect(true);
}

''' + text[end:]
