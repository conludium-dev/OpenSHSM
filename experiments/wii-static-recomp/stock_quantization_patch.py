"""Correct signed six-bit GQR scales in a private copy of the existing CPU helper."""

def adapt_quantization(text):
    for direction in ('ld', 'st'):
        exponent = '-((int)ld_scale)' if direction == 'ld' else '(int)st_scale'
        old = f'    float scale = std::pow(2.0f, {exponent});'
        assert text.count(old) == 1
        sign = '-' if direction == 'ld' else ''
        text = text.replace(old, f'''    const int signed_scale = int({direction}_scale ^ 32u) - 32;
    float scale = std::ldexp(1.0f, {sign}signed_scale);''')
    marker = '    auto store_element = [&](uint32_t a, double val) {'
    assert text.count(marker) == 1
    text = text.replace(marker, '''    auto quantize = [&](double value, float low, float high) {
        const float scaled = float(value) * scale;
        if (std::isnan(scaled)) {
            throw std::runtime_error("PSQ integer NaN is not verified");
        }
        return std::fmin(high, std::fmax(low, scaled));
    };
''' + marker)
    for cast, low, high in [('uint8_t', '0.0f', '255.0f'), ('uint16_t', '0.0f', '65535.0f'),
        ('int8_t', '-128.0f', '127.0f'), ('int16_t', '-32768.0f', '32767.0f')]:
        old = f'({cast})(val * scale)'
        assert text.count(old) == 1
        text = text.replace(old, f'({cast})quantize(val, {low}, {high})')
    return '#include <stdexcept>\n' + text
