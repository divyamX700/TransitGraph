#include "raptor.h"
#include <iostream>
#include <algorithm>
#include <set>
#include <unordered_map>

using namespace std;

struct ParentPointer {
    uint32_t boarded_stop_idx = -1;
    uint32_t route_idx = -1;
    uint32_t trip_idx = -1;
};

vector<vector<JourneyLeg>> Raptor::compute_pareto_routes(const string& source_id, const string& target_id, int departure_time) {
    vector<vector<JourneyLeg>> pareto_journeys;
    if (data.stop_id_to_index.find(source_id) == data.stop_id_to_index.end() || 
        data.stop_id_to_index.find(target_id) == data.stop_id_to_index.end()) {
        return pareto_journeys;
    }
    
    uint32_t ps = data.stop_id_to_index.at(source_id);
    uint32_t pt = data.stop_id_to_index.at(target_id);
    uint32_t num_stops = data.stops.size();
    
    vector<vector<int>> tau(MAX_ROUNDS + 1, vector<int>(num_stops, INF));
    vector<int> tau_star(num_stops, INF);
    vector<vector<ParentPointer>> parents(MAX_ROUNDS + 1, vector<ParentPointer>(num_stops));
    
    tau[0][ps] = departure_time;
    tau_star[ps] = departure_time;
    
    vector<bool> marked(num_stops, false);
    marked[ps] = true;
    
    for (int k = 1; k <= MAX_ROUNDS; ++k) {
        // Accumulate routes serving marked stops
        unordered_map<uint32_t, uint32_t> Q; // route_idx -> stop_idx in route
        
        for (uint32_t p = 0; p < num_stops; ++p) {
            if (marked[p]) {
                for (uint32_t i = 0; i < data.stops[p].stop_routes_count; ++i) {
                    uint32_t r_idx = data.stop_routes[data.stops[p].stop_routes_offset + i];
                    // Find where p is in route r_idx
                    const Route& r = data.routes[r_idx];
                    uint32_t p_seq_idx = -1;
                    for (uint32_t j = 0; j < r.num_stops; ++j) {
                        if (data.route_stops[r.route_stops_offset + j] == p) {
                            p_seq_idx = j;
                            break;
                        }
                    }
                    if (p_seq_idx == -1) continue;
                    
                    if (Q.find(r_idx) != Q.end()) {
                        if (p_seq_idx < Q[r_idx]) Q[r_idx] = p_seq_idx;
                    } else {
                        Q[r_idx] = p_seq_idx;
                    }
                }
                marked[p] = false;
            }
        }
        
        if (Q.empty()) break;
        
        // Traverse each route
        for (const auto& kv : Q) {
            uint32_t r_idx = kv.first;
            uint32_t start_seq_idx = kv.second;
            const Route& r = data.routes[r_idx];
            
            int t = -1; // current trip_idx
            uint32_t boarded_stop = -1;
            
            for (uint32_t j = start_seq_idx; j < r.num_stops; ++j) {
                uint32_t pi = data.route_stops[r.route_stops_offset + j];
                
                // Can the label be improved?
                if (t != -1) {
                    int arr_time = data.stop_times[r.stop_times_offset + t * r.num_stops + j].arrival_time;
                    if (arr_time < min(tau_star[pi], tau_star[pt])) {
                        tau[k][pi] = arr_time;
                        tau_star[pi] = arr_time;
                        marked[pi] = true;
                        parents[k][pi] = {boarded_stop, r_idx, (uint32_t)t};
                    }
                }
                
                // Can we catch an earlier trip?
                if (tau[k-1][pi] != INF) {
                    int dep_time_needed = tau[k-1][pi];
                    // Apply 5-minute penalty if transferring (k > 1)
                    if (k > 1 && pi != ps) dep_time_needed += TRANSFER_PENALTY_MINS;
                    
                    // O(log T) Binary Search over chronologically sorted trips
                    int low = 0;
                    int high = r.num_trips - 1;
                    int best_trip_idx = -1;
                    
                    while (low <= high) {
                        int mid = low + (high - low) / 2;
                        int dep_time = data.stop_times[r.stop_times_offset + mid * r.num_stops + j].departure_time;
                        
                        if (dep_time >= dep_time_needed) {
                            best_trip_idx = mid;
                            high = mid - 1; // Look for earlier valid trips
                        } else {
                            low = mid + 1; // Look for later trips
                        }
                    }
                    
                    if (best_trip_idx != -1) {
                        if (t == -1 || best_trip_idx < t) {
                            t = best_trip_idx;
                            boarded_stop = pi;
                        }
                    }
                }
            }
        }
        
        // Reconstruct journey if target was reached and improved in this round
        if (tau[k][pt] != INF && tau[k][pt] == tau_star[pt]) {
            vector<JourneyLeg> journey;
            uint32_t curr = pt;
            int curr_round = k;
            
            while (curr_round > 0 && curr != ps) {
                const auto& p = parents[curr_round][curr];
                if (p.route_idx == -1) break; // Should not happen if path exists
                
                const Route& r = data.routes[p.route_idx];
                
                // Find sequence index of boarded_stop and curr (alight stop)
                uint32_t board_seq = -1, alight_seq = -1;
                for (uint32_t j = 0; j < r.num_stops; ++j) {
                    if (data.route_stops[r.route_stops_offset + j] == p.boarded_stop_idx) board_seq = j;
                    if (data.route_stops[r.route_stops_offset + j] == curr) alight_seq = j;
                }
                
                JourneyLeg leg;
                leg.from_stop_id = data.stops[p.boarded_stop_idx].id;
                leg.to_stop_id = data.stops[curr].id;
                leg.route_id = r.id;
                leg.trip_id = data.trip_ids[p.route_idx][p.trip_idx];
                leg.departure_time = data.stop_times[r.stop_times_offset + p.trip_idx * r.num_stops + board_seq].departure_time;
                leg.arrival_time = data.stop_times[r.stop_times_offset + p.trip_idx * r.num_stops + alight_seq].arrival_time;
                
                journey.push_back(leg);
                
                curr = p.boarded_stop_idx;
                curr_round--;
            }
            
            reverse(journey.begin(), journey.end());
            pareto_journeys.push_back(journey);
        }
    }
    
    return pareto_journeys;
}
