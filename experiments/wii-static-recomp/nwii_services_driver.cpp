#include "loader/loader.h"
#include "analyzer/analyzer.h"
#include "recompiler/recompiler.h"
#include "analyzer_profile.h"
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
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
        throw std::runtime_error("Missing or malformed experimental analyzer profile");
    }
    nwii::loader::Executable executable;
    if (!executable.load_dol(argv[1])) {
        return 3;
    }
    nwii::analyzer::Analyzer analyzer(executable);
    analyzer.analyze();
    const std::filesystem::path output(argv[2]);
    std::filesystem::create_directories(output);
    std::ofstream inventory(output / "selected-ir.tsv");
    std::ofstream switches(output / "selected-switches.tsv");
    std::ofstream bodies(output / "selected-bodies.cpp");
    std::set<uint32_t> directCallees;
    nwii::recomp::Recompiler recompiler(analyzer);
    for (const auto& [entry, boundary] : profileBounds) {
        auto found = analyzer.get_functions().find(entry);
        if (found == analyzer.get_functions().end() || !found->second.hle_hook_name.empty()) {
            throw std::runtime_error("Missing original function or rejected automatic HLE classification");
        }
        const auto& function = found->second;
        if (function.start_address != entry || function.end_address > boundary) {
            throw std::runtime_error("Selected IR exceeds independently supplied function boundary");
        }
        for (const auto& instruction : function.instructions) {
            if (instruction.address < entry || instruction.address >= boundary) {
                throw std::runtime_error("Out-of-function instruction in selected IR");
            }
            inventory << std::hex << entry << '\t' << instruction.address << '\t' << instruction.opcode << '\n';
            if ((instruction.opcode >> 26) == 18) {
                int32_t displacement = instruction.opcode & 0x3fffffc;
                if (displacement & 0x2000000) {
                    displacement -= 0x4000000;
                }
                uint32_t target = instruction.opcode & 2 ? displacement : instruction.address + displacement;
                if (target < entry || target >= boundary) {
                    directCallees.insert(target);
                }
            }
        }
        for (uint32_t target : function.jump_table_targets) {
            switches << std::hex << entry << '\t' << target << '\n';
        }
        bodies << recompiler.generate_function_cpp(function) << '\n';
        std::cout << "profile " << std::hex << entry << " end " << function.end_address << std::dec
                  << " instructions " << function.instructions.size() << " switches " << function.jump_table_targets.size() << '\n';
    }
    bodies.close();
    std::ofstream generated(output / "selected.cpp");
    generated << "#include \"runtime/cpu_context.h\"\nusing nwii::runtime::CPUContext;\n";
    for (uint32_t entry : directCallees) {
        generated << "void func_" << std::hex << std::uppercase << entry << "(CPUContext&);\n";
    }
    std::ifstream emitted(output / "selected-bodies.cpp");
    generated << emitted.rdbuf();
}
