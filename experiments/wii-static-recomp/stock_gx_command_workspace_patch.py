"""Reuse command-vector storage while releasing commands at every scope exit."""


def gx(source):
    marker = 'void ProcessGXFifo() {'
    helper = '''template<class T> struct StockGxClearOnExit {
    std::vector<T>& value;
    ~StockGxClearOnExit() {
        value.clear();
    }
};

'''
    if source.count(marker) != 1:
        raise ValueError('GX command workspace entry differs')
    source = source.replace(marker, helper + marker)
    for name in ('commands', 'frame'):
        before = f'    std::vector<nwii::runtime::gx::GXCommand> {name};'
        after = f'''    static std::vector<nwii::runtime::gx::GXCommand> {name};
    StockGxClearOnExit clear_{name}{{{name}}};'''
        if source.count(before) != 1:
            raise ValueError(f'GX {name} workspace differs')
        source = source.replace(before, after)
    return source
