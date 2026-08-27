#pragma once
#include <string>
#include <vector>
#include <cstdint>
#include <unordered_map>

struct Stop {
    std::string id;
    std::string name;
    uint32_t stop_routes_offset;
    uint32_t stop_routes_count;
};

struct Route {
    std::string id;
    uint32_t route_stops_offset;
    uint32_t num_stops;
    uint32_t stop_times_offset;
    uint32_t num_trips;
};

struct StopTime {
    int arrival_time;   // Minutes since midnight
    int departure_time; // Minutes since midnight
};

// The core flattened data arrays used by RAPTOR
struct RaptorData {
    std::vector<Stop> stops;
    std::vector<Route> routes;
    
    // RouteStops[routes[i].route_stops_offset ... + routes[i].num_stops - 1]
    // contains the stop indices for route i
    std::vector<uint32_t> route_stops; 
    
    // StopRoutes[stops[i].stop_routes_offset ... + stops[i].stop_routes_count - 1]
    // contains the route indices that serve stop i
    std::vector<uint32_t> stop_routes;
    
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
