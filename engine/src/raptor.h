#pragma once
#include "raptor_types.h"
#include <string>
#include <vector>

const int INF = 1e9;
const int MAX_ROUNDS = 6;
const int TRANSFER_PENALTY_MINS = 5;

struct JourneyLeg {
    std::string from_stop_id;
    std::string to_stop_id;
    std::string route_id;
    std::string trip_id;
    int departure_time;
    int arrival_time;
};

class Raptor {
    const RaptorData& data;

public:
    Raptor(const RaptorData& d) : data(d) {}
    
    // Returns a list of JourneyLegs representing the fastest path
    // For Pareto-optimal, we could return multiple paths (one for each k where arrival improves).
    // For simplicity, returning the absolute earliest arrival over all rounds.
    std::vector<std::vector<JourneyLeg>> compute_pareto_routes(const std::string& source_id, const std::string& target_id, int departure_time);
};
