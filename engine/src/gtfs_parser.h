#pragma once
#include <string>
#include "raptor_types.h"

class GTFSParser {
public:
    static RaptorData parse(const std::string& gtfs_dir);
};
