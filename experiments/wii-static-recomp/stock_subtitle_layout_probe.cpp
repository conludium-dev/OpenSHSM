#include <algorithm>
#include <filesystem>
#include <map>
#include <set>
#include <vector>
#include <iostream>
#include "PhoneLayout.h"

int main(int argc, char** argv) {
    if (argc < 2) { return 2; }
    PhoneLayout layout;
    layout.load(argv[1]);
    if (layout.root.type != "Subtitles") { return 3; }
    size_t scripts = 0, cues = 0;
    std::map<std::string, size_t> matching_properties;
    for (const auto& script : layout.root.children) {
        if (script.type != "Script") { return 4; }
        ++scripts;
        for (const auto& cue : script.children) {
            if (cue.type != "Text") { return 5; }
            ++cues;
            for (const auto& attribute : cue.attrs) {
                for (int i = 2; i < argc; ++i) {
                    if (attribute.second == argv[i]) { ++matching_properties[attribute.first]; }
                }
            }
        }
    }
    std::cout << "SCRIPTS " << scripts << " CUES " << cues << " RECORDS " << layout.records << "\n";
    for (const auto& property : matching_properties) {
        std::cout << "MATCH_PROPERTY " << property.first << " " << property.second << "\n";
    }
    return 0;
}
