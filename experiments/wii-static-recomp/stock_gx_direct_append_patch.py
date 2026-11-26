"""Append decoded CP packets to the existing GX command vector."""


def adapt(source: str) -> str:
    before = """        std::vector<nwii::runtime::gx::GXCommand> decoded;
        nwii::runtime::gx::FifoParser::Parse(s_parse_buf, decoded);
        commands.insert(commands.end(), std::make_move_iterator(decoded.begin()),
                        std::make_move_iterator(decoded.end()));"""
    after = """        nwii::runtime::gx::FifoParser::Parse(s_parse_buf, commands);"""
    assert source.count(before) == 1
    return source.replace(before, after, 1)
