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
    std::filesystem::path output(argv[2]);
    std::filesystem::create_directories(output);
    std::ofstream catalogue(output / "nwii-functions.tsv");
    for (const auto& [address, function] : analyzer.get_functions()) {
        catalogue << std::hex << address << '\t' << function.end_address << std::dec << '\t' << function.instructions.size()
                  << '\t' << function.hle_hook_name << '\n';
    }
    nwii::recomp::Recompiler recompiler(analyzer);
    std::ofstream generated(output / "selected.cpp");
    generated << "#include \"runtime/cpu_context.h\"\nusing nwii::runtime::CPUContext;\n";
    for (uint32_t address : {0x800c770cu, 0x800c7720u, 0x800f3e60u}) {
        auto function = analyzer.get_functions().find(address);
        if (function == analyzer.get_functions().end()) {
            throw std::runtime_error("Required researched function was not discovered automatically");
        }
        if (!function->second.hle_hook_name.empty()) {
            throw std::runtime_error("Automatic HLE classification is not accepted for this milestone");
        }
        std::cout << "selected " << std::hex << address << " end " << function->second.end_address << std::dec
                  << " instructions " << function->second.instructions.size() << '\n';
        generated << recompiler.generate_function_cpp(function->second) << '\n';
    }
    std::cout << "Discovered " << analyzer.get_functions().size() << " functions\n";
}
