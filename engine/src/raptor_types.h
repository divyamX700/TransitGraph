#pragma once
#include <string>
#include <vector>
#include <cstdint>
#include <unordered_map>

enum class Mode : uint8_t { LOCAL = 0, METRO = 1, MONORAIL = 2 };

inline const char* mode_name(Mode m) {
    switch (m) {
        case Mode::METRO: return "METRO";
        case Mode::MONORAIL: return "MONORAIL";
        default: return "LOCAL";
    }
}

struct Stop {
    std::string id;
    std::string name;
    uint32_t stop_routes_offset;
    uint32_t stop_routes_count;
    uint32_t footpaths_offset;
    uint32_t footpaths_count;
};

struct Route {
    std::string id;    // shape id: what the map draws
    std::string line;  // line id from routes.txt (CR_MAIN, M1, ...)
    Mode mode;
    uint32_t route_stops_offset;
    uint32_t num_stops;
    uint32_t stop_times_offset;
    uint32_t num_trips;
};

struct StopTime {
    int arrival_time;   // Minutes since midnight
    int departure_time; // Minutes since midnight
};

// A route serving a stop, and where in the route's stop sequence the stop is.
struct StopRoute {
    uint32_t route_idx;
    uint32_t position;
};

// A walking link between two different stops (e.g. a local station and a nearby metro station).
struct Footpath {
    uint32_t target_stop_idx;
    int minutes;
    int meters;
};

// The core flattened data arrays used by RAPTOR
struct RaptorData {
    std::vector<Stop> stops;
    std::vector<Route> routes;

    // RouteStops[routes[i].route_stops_offset ... + routes[i].num_stops - 1]
    // contains the stop indices for route i
    std::vector<uint32_t> route_stops;

    // StopRoutes[stops[i].stop_routes_offset ... + stops[i].stop_routes_count - 1]
    // contains the routes that serve stop i (and the stop's position in each)
    std::vector<StopRoute> stop_routes;

    // Footpaths[stops[i].footpaths_offset ... + stops[i].footpaths_count - 1]
    // contains the walking links leaving stop i (compressed sparse rows)
    std::vector<Footpath> footpaths;

    // StopTimes[routes[i].stop_times_offset + k * routes[i].num_stops + j]
    // contains the StopTime for the k-th trip at the j-th stop of route i.
    // Trips are sorted by departure time at the first stop.
    std::vector<StopTime> stop_times;

    // String mappings for JSON parsing/output
    std::unordered_map<std::string, uint32_t> stop_id_to_index;

    // For reconstructing the trip ID
    // Trip string IDs mapped per route. trip_ids[route_idx][trip_idx] -> string
    std::vector<std::vector<std::string>> trip_ids;
};
