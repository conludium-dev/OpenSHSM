#include "loader/loader.h"
#include "analyzer/analyzer.h"
#include "recompiler/recompiler.h"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>

int main(int argc, char** argv) {
    if (argc != 3) {
        return 2;
    }
    nwii::loader::Executable executable;
    if (!executable.load_dol(argv[1])) {
        return 3;
    }
    nwii::analyzer::Analyzer analyzer(executable);
    analyzer.analyze();
    nwii::recomp::Recompiler recompiler(analyzer);
    const std::filesystem::path output(argv[2]);
    std::filesystem::create_directories(output);
    size_t functions = 0;
    size_t sites = 0;
    for (const auto& [address, function] : analyzer.get_functions()) {
        size_t count = 0;
        for (const auto& instruction : function.instructions) {
            if ((instruction.opcode >> 26) == 17) {
                ++count;
            }
        }
        if (count == 0) {
            continue;
        }
        std::ofstream stream(output / (std::to_string(address) + ".cpp"));
        stream << recompiler.generate_function_cpp(function);
        if (!stream) {
            throw std::runtime_error("Cannot preserve generated function");
        }
        ++functions;
        sites += count;
    }
    std::cout << "SC_FUNCTIONS " << functions << " SC_SITES " << sites << '\n';
    return sites == 0 ? 4 : 0;
}
