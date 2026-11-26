"""Privately scope per-stage GLSL temporaries; validate the existing GL compiler result."""
def generator(text):
    start = '        fs << "    // TEV Stage " << i << "\\n";'
    end = '        fs << "    tevReg[" << (int)stage.alphaRegId << "].a = aOut;\\n";'
    assert text.count(start) == text.count(end) == 1
    return text.replace(start, start + '\n        fs << "    {\\n";').replace(end, end + '\n        fs << "    }\\n";')

def renderer(text):
    start = text.index('static GLuint CompileShader(')
    end = text.index('\nstatic void DiagnoseGL(', start)
    replacement = '''static GLuint CompileShader(const char *vs, const char *fs) {
    const auto started = std::chrono::steady_clock::now();
    const auto compile = [](GLenum kind, const char* source) {
        GLuint shader = glCreateShader(kind);
        glShaderSource(shader, 1, &source, nullptr);
        glCompileShader(shader);
        GLint status = 0;
        glGetShaderiv(shader, GL_COMPILE_STATUS, &status);
        if (!status) {
            GLint size = 0;
            glGetShaderiv(shader, GL_INFO_LOG_LENGTH, &size);
            std::vector<char> log(size > 0 ? size : 1, 0);
            glGetShaderInfoLog(shader, log.size(), nullptr, log.data());
            glDeleteShader(shader);
            throw std::runtime_error(std::string("GX shader compilation failed: ") + log.data());
        }
        return shader;
    };
    GLuint vertex = compile(GL_VERTEX_SHADER, vs);
    GLuint fragment = 0;
    try {
        fragment = compile(GL_FRAGMENT_SHADER, fs);
    } catch (...) {
        glDeleteShader(vertex);
        throw;
    }
    GLuint program = glCreateProgram();
    glAttachShader(program, vertex);
    glAttachShader(program, fragment);
    glLinkProgram(program);
    glDeleteShader(vertex);
    glDeleteShader(fragment);
    GLint status = 0;
    glGetProgramiv(program, GL_LINK_STATUS, &status);
    if (!status) {
        GLint size = 0;
        glGetProgramiv(program, GL_INFO_LOG_LENGTH, &size);
        std::vector<char> log(size > 0 ? size : 1, 0);
        glGetProgramInfoLog(program, log.size(), nullptr, log.data());
        glDeleteProgram(program);
        throw std::runtime_error(std::string("GX shader link failed: ") + log.data());
    }
    static unsigned samples = 0;
    if (std::getenv("NWII_SHADERPROFILE") && samples++ < 64) {
        const auto us = std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::steady_clock::now() - started).count();
        std::cout << "[Shader compile] stages=" << unsigned(g_state.numTevStages)
            << " us=" << us << " linked=1\\n";
    }
    return program;
}
'''
    return '#include <chrono>\n#include <iostream>\n#include <stdexcept>\n' + text[:start] + replacement + text[end:]
