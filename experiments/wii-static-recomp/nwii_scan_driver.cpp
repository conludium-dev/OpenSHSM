#include "loader/loader.h"
#include "analyzer/analyzer.h"
#include "recompiler/recompiler.h"
#include <filesystem>
#include <fstream>
#include <iostream>

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
    const auto& functions = analyzer.get_functions();
    auto found = functions.find(0x8019D434);
    if (found == functions.end() || found->second.end_address != 0x8019D564 ||
            found->second.instructions.size() != 76) {
        return 4;
    }
    nwii::recomp::Recompiler recompiler(analyzer);
    std::ofstream output(argv[2]);
    output << recompiler.generate_function_cpp(found->second);
    if (!output) {
        return 5;
    }
    std::cout << "SCAN_WII_FUNCTION_GENERATED_76_WORDS_NOT_GAME_VERIFIED\n";
}
