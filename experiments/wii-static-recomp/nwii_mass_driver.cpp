#include "loader/loader.h"
#include "analyzer/analyzer.h"
#include "recompiler/recompiler.h"
#include "analyzer_profile.h"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <stdexcept>

namespace {
std::map<uint32_t, uint32_t> profileBounds;
std::map<uint32_t, uint32_t> profileTables;
}

namespace nwii::analyzer {
bool experimentFunctionContains(uint32_t entry, uint32_t address) {
    auto found = profileBounds.find(entry);
    return found == profileBounds.end() || (entry <= address && address < found->second);
}

uint32_t experimentJumpTableLimit(uint32_t base) {
    auto found = profileTables.find(base);
    return found == profileTables.end() ? 0 : found->second;
}
}

int main(int argc, char** argv) {
    if (argc != 4) {
        return 2;
    }
    std::ifstream profile(argv[3]);
    char kind;
    uint32_t start, end;
    while (profile >> kind >> std::hex >> start >> end) {
        if (kind == 'F' && start < end) {
            profileBounds.emplace(start, end);
        } else if (kind == 'T' && end > 0 && end <= 1024) {
            profileTables.emplace(start, end);
        } else {
            throw std::runtime_error("Invalid experimental analyzer profile");
        }
    }
    if (!profile.eof() || profileBounds.empty()) {
        return 3;
    }
    nwii::loader::Executable executable;
    if (!executable.load_dol(argv[1])) {
        return 4;
    }
    nwii::analyzer::Analyzer analyzer(executable);
    analyzer.analyze();
    const std::filesystem::path output(argv[2]);
    std::filesystem::create_directories(output);
    std::ofstream catalogue(output / "functions.tsv");
    std::ofstream instructions(output / "instructions.tsv");
    std::ofstream hle(output / "rejected-automatic-hle.tsv");
    auto& functions = const_cast<std::map<uint32_t, nwii::analyzer::Function>&>(analyzer.get_functions());
    for (auto& [entry, function] : functions) {
        catalogue << std::hex << entry << '\t' << function.start_address << '\t' << function.end_address << std::dec
                  << '\t' << function.instructions.size() << '\t' << function.jump_table_targets.size() << '\n';
        for (const auto& instruction : function.instructions) {
            instructions << std::hex << entry << '\t' << instruction.address << '\t' << instruction.opcode << '\n';
        }
        if (!function.hle_hook_name.empty()) {
            hle << std::hex << entry << '\t' << function.hle_hook_name << '\n';
            function.hle_hook_name.clear();
        }
    }
    nwii::recomp::RecompilerConfig config;
    config.project_name = "OpenSHSMExperimentalMass";
    config.output_dir = output.string();
    config.split_output = true;
    config.instructions_per_file = 12000;
    nwii::recomp::Recompiler recompiler(analyzer, nullptr, config);
    std::ofstream manifest(output / "generated-files.txt");
    for (const auto& file : recompiler.generate_cpp(executable.entry_point)) {
        manifest << file << '\n';
    }
    std::cout << "Mass translation candidates=" << functions.size() << " entry=" << std::hex << executable.entry_point << '\n';
}
