"""Reuse vertex sizes only within consecutive draw commands in one parser call."""


def parser(source):
    before = '''    const size_t fifo_size = fifo.size();
    while (offset < fifo_size) {
        uint8_t cmd = fifo[offset];'''
    after = '''    const size_t fifo_size = fifo.size();
    size_t vertex_sizes[8]{};
    uint8_t vertex_sizes_valid = 0;
    while (offset < fifo_size) {
        uint8_t cmd = fifo[offset];
        if (cmd < 0x80 || cmd > 0xBF) {
            vertex_sizes_valid = 0;
        }'''
    if source.count(before) != 1:
        raise ValueError('GX vertex-size cache patch site differs')
    source = source.replace(before, after)
    before = '            size_t vsize = VertexSize(vat);'
    after = '''            const uint8_t vat_bit = uint8_t(1u << vat_idx);
            if (!(vertex_sizes_valid & vat_bit)) {
                vertex_sizes[vat_idx] = VertexSize(vat);
                vertex_sizes_valid |= vat_bit;
            }
            size_t vsize = vertex_sizes[vat_idx];'''
    if source.count(before) != 1:
        raise ValueError('GX vertex-size cache patch site differs')
    return source.replace(before, after)
