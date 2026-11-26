"""Transform each source vertex once within its existing primitive command."""


def adapt(text):
    replacements = [
        ('static void EmitVertex(const GXCommand &cmd, size_t index) {',
         'static BatchVertex TransformVertex(const GXCommand &cmd, size_t index) {'),
        ('  s_batch.push_back(bv);', '  return bv;'),
        ('  const size_t n = v.size();\n\n  switch (cmd.prim_type) {',
         '''  const size_t n = v.size();
    if (cmd.prim_type != 0x80 && cmd.prim_type != 0x90 && cmd.prim_type != 0x98 && cmd.prim_type != 0xA0) {
        return;
    }
    static std::vector<BatchVertex> transformed;
    transformed.resize(n);
    for (size_t index = 0; index < n; ++index) {
        transformed[index] = TransformVertex(cmd, index);
    }
    const auto EmitVertex = [&](const GXCommand&, size_t index) {
        s_batch.push_back(transformed[index]);
    };

  switch (cmd.prim_type) {'''),
    ]
    for before, after in replacements:
        if text.count(before) != 1:
            raise ValueError('Unexpected vertex emission source')
        text = text.replace(before, after)
    return text
