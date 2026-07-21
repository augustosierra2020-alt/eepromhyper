#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <vector>
#include <cmath>

namespace py = pybind11;

// Retorna uma lista de diferenças. Extremamente rápido no C++.
std::vector<std::map<std::string, int>> compare_hex_fast(const std::string& ori, const std::string& mod, int max_diffs) {
    std::vector<std::map<std::string, int>> diffs;
    size_t min_len = std::min(ori.size(), mod.size());

    for (size_t i = 0; i < min_len; ++i) {
        if (ori[i] != mod[i]) {
            std::map<std::string, int> diff;
            diff["EnderecoInt"] = i;
            diff["ByteOriginal"] = static_cast<unsigned char>(ori[i]);
            diff["ByteModificado"] = static_cast<unsigned char>(mod[i]);
            diffs.push_back(diff);
            
            if (diffs.size() >= static_cast<size_t>(max_diffs)) break;
        }
    }
    return diffs;
}

// Vinculando a função C++ ao Python
PYBIND11_MODULE(hypertork_cpp, m) {
    m.doc() = "HyperTork Engine de Alta Performance em C++";
    m.def("compare_hex_fast", &compare_hex_fast, "Compara dois arquivos HEX nativamente");
}