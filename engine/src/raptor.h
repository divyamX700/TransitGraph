#pragma once
#include "raptor_types.h"
#include <string>
#include <vector>

const int INF = 1e9;
const int MAX_ROUNDS = 6;               // up to 6 vehicles, i.e. 5 changes
const int TRANSFER_PENALTY_MINS = 5;    // changing vehicles at a stop

struct JourneyLeg {
    std::string from_stop_id;
    std::string to_stop_id;
    std::string route_id;  // shape id for the map ("WALK" for a walking leg)
    std::string line;      // line id (CR_MAIN, M1, ...) or "WALK"
    std::string trip_id;   // empty for a walking leg
    Mode mode;
    bool is_walk;
    int walk_meters;       // walking legs only
    int departure_time;    // minutes since midnight of the query day; 1440+ is the next day
    int arrival_time;
};

class Raptor {
    const RaptorData& data;

public:
    Raptor(const RaptorData& d) : data(d) {}

    // The Pareto front of journeys for a departure time: one journey for every number of
    // vehicles that arrives earlier than any journey using fewer vehicles, fewest vehicles first.
    // Walking between stops (footpaths) does not count as a vehicle.
    std::vector<std::vector<JourneyLeg>> compute_pareto_routes(const std::string& source_id, const std::string& target_id, int departure_time);
};
