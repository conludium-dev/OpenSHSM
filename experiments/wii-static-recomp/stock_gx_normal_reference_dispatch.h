template<class T> void dispatch(unsigned mode, VertexLoader* loader) {
    switch (mode) {
    case 0: Normal_ReadDirect<T, 1>(loader); break;
    case 1: Normal_ReadDirect<T, 3>(loader); break;
    case 2: Normal_ReadIndex<u8, T, 1>(loader); break;
    case 3: Normal_ReadIndex<u16, T, 1>(loader); break;
    case 4: Normal_ReadIndex<u8, T, 3>(loader); break;
    case 5: Normal_ReadIndex<u16, T, 3>(loader); break;
    case 6: Normal_ReadIndex_Indices3<u8, T>(loader); break;
    case 7: Normal_ReadIndex_Indices3<u16, T>(loader); break;
    default: assert(false);
    }
}

void check(unsigned type, unsigned mode, std::span<const u8> stream, const u8* array,
        u32 stride, const openshsm::experiment::GxVertexSources& source) {
    bytes = stream.subspan(12);
    cursor = 0;
    written.clear();
    VertexLoader loader;
    VertexLoaderManager::cached_arraybases.value = array;
    g_main_cp_state.array_strides.value = stride;
    switch (type) {
    case 0: dispatch<u8>(mode, &loader); break;
    case 1: dispatch<s8>(mode, &loader); break;
    case 2: dispatch<u16>(mode, &loader); break;
    case 3: dispatch<s16>(mode, &loader); break;
    default: dispatch<float>(mode, &loader); break;
    }
    assert(cursor + 8 == bytes.size());
    assert(written.size() == (source.has_nbt ? 9u : 3u));
    for (unsigned component = 0; component < written.size(); ++component) {
        assert(std::bit_cast<u32>(written[component]) == std::bit_cast<u32>(source.normals[component / 3][component % 3]));
    }
}
