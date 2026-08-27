#include "gtfs_parser.h"
#include <fstream>
#include <sstream>
#include <iostream>
#include <vector>
#include <unordered_map>
#include <algorithm>
#include <set>

using namespace std;

// Simple CSV parser
vector<vector<string>> read_csv(const string& path) {
    vector<vector<string>> data;
    ifstream file(path);
    if (!file.is_open()) {
        cerr << "Could not open " << path << endl;
        return data;
    }
    string line;
    bool first = true;
    while (getline(file, line)) {
        // Handle CRLF
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (first) { first = false; continue; } // skip header
        
        stringstream ss(line);
        string cell;
        vector<string> row;
        while (getline(ss, cell, ',')) {
            row.push_back(cell);
        }
        if (!row.empty()) data.push_back(row);
    }
    return data;
}

int parse_time(const string& time_str) {
    int h, m, s;
    if (sscanf(time_str.c_str(), "%d:%d:%d", &h, &m, &s) == 3) {
        return h * 60 + m;
    }
    return 0;
}

struct RawTrip {
    string trip_id;
    string shape_id; // Maps to RAPTOR Route
};

struct RawStopTime {
    int arrival_time;
    int departure_time;
    uint32_t stop_idx;
    int stop_sequence;
};

RaptorData GTFSParser::parse(const string& gtfs_dir) {
    RaptorData data;
    
    cout << "Parsing stops.txt..." << endl;
    auto stops_csv = read_csv(gtfs_dir + "/stops.txt");
    for (const auto& row : stops_csv) {
        if (row.size() >= 2) {
            Stop s;
            s.id = row[0];
            s.name = row[1];
            s.stop_routes_offset = 0;
            s.stop_routes_count = 0;
            data.stop_id_to_index[s.id] = data.stops.size();
            data.stops.push_back(s);
        }
    }
    
    cout << "Parsing trips.txt..." << endl;
    unordered_map<string, RawTrip> trips;
    auto trips_csv = read_csv(gtfs_dir + "/trips.txt");
    for (const auto& row : trips_csv) {
        if (row.size() >= 5) {
            trips[row[2]] = {row[2], row[4]};
        }
    }
    
    cout << "Parsing stop_times.txt..." << endl;
    // Map trip_id to list of raw stop times
    unordered_map<string, vector<RawStopTime>> trip_stop_times;
    auto stop_times_csv = read_csv(gtfs_dir + "/stop_times.txt");
    for (const auto& row : stop_times_csv) {
        if (row.size() >= 5) {
            string trip_id = row[0];
            string stop_id = row[3];
            if (data.stop_id_to_index.find(stop_id) == data.stop_id_to_index.end()) continue;
            
            RawStopTime rst;
            rst.arrival_time = parse_time(row[1]);
            rst.departure_time = parse_time(row[2]);
            rst.stop_idx = data.stop_id_to_index[stop_id];
            rst.stop_sequence = stoi(row[4]);
            trip_stop_times[trip_id].push_back(rst);
        }
    }
    
    // Fix midnight rollover within trips and duplicate for 48h window
    vector<string> original_trip_ids;
    for (auto& kv : trips) original_trip_ids.push_back(kv.first);
    
    for (const string& tid : original_trip_ids) {
        auto& sts = trip_stop_times[tid];
        // Sort by sequence
        sort(sts.begin(), sts.end(), [](const RawStopTime& a, const RawStopTime& b) {
            return a.stop_sequence < b.stop_sequence;
        });
        
        // Fix rollover
        int last_time = -1;
        for (auto& st : sts) {
            if (last_time != -1 && st.arrival_time < last_time - 60) {
                // If it jumps back (e.g. 23:55 to 00:10), add 24h.
                // We use -60 to allow minor parsing inconsistencies, though they shouldn't exist.
                st.arrival_time += 24 * 60;
                st.departure_time += 24 * 60;
            }
            last_time = st.departure_time;
        }
        
        // Duplicate for next day
        string next_day_tid = tid + "_nextday";
        trips[next_day_tid] = trips[tid];
        for (const auto& st : sts) {
            RawStopTime next_st = st;
            next_st.arrival_time += 24 * 60;
            next_st.departure_time += 24 * 60;
            trip_stop_times[next_day_tid].push_back(next_st);
        }
    }
    
    // In RAPTOR, a route is a set of trips with the EXACT same sequence of stops.
    // By definition of our GTFS compiler, `shape_id` uniquely identifies a stop sequence!
    cout << "Building RAPTOR routes..." << endl;
    
    // Group trips by shape_id
    unordered_map<string, vector<string>> route_to_trips;
    for (const auto& kv : trips) {
        route_to_trips[kv.second.shape_id].push_back(kv.first);
    }
    
    // Temporary structure to hold routes associated with each stop
    vector<set<uint32_t>> stop_to_routes(data.stops.size());
    
    for (auto& kv : route_to_trips) {
        string shape_id = kv.first;
        auto& trip_ids = kv.second;
        if (trip_ids.empty()) continue;
        
        // Sort trips by departure time at the first stop
        sort(trip_ids.begin(), trip_ids.end(), [&trip_stop_times](const string& a, const string& b) {
            return trip_stop_times[a].front().departure_time < trip_stop_times[b].front().departure_time;
        });
        
        // Get the stop sequence from the first trip
        const auto& first_trip_sts = trip_stop_times[trip_ids[0]];
        vector<uint32_t> sequence;
        for (const auto& st : first_trip_sts) sequence.push_back(st.stop_idx);
        
        Route r;
        r.id = shape_id;
        r.num_stops = sequence.size();
        r.num_trips = trip_ids.size();
        r.route_stops_offset = data.route_stops.size();
        r.stop_times_offset = data.stop_times.size();
        
        uint32_t route_idx = data.routes.size();
        data.routes.push_back(r);
        
        // Add to route_stops
        for (uint32_t stop_idx : sequence) {
            data.route_stops.push_back(stop_idx);
            stop_to_routes[stop_idx].insert(route_idx);
        }
        
        // Add to stop_times
        vector<string> r_trip_ids;
        for (const string& tid : trip_ids) {
            r_trip_ids.push_back(tid);
            const auto& sts = trip_stop_times[tid];
            for (const auto& st : sts) {
                data.stop_times.push_back({st.arrival_time, st.departure_time});
            }
        }
        data.trip_ids.push_back(r_trip_ids);
    }
    
    // Finalize stop_routes
    for (size_t i = 0; i < data.stops.size(); i++) {
        data.stops[i].stop_routes_offset = data.stop_routes.size();
        data.stops[i].stop_routes_count = stop_to_routes[i].size();
        for (uint32_t route_idx : stop_to_routes[i]) {
            data.stop_routes.push_back(route_idx);
        }
    }
    
    cout << "GTFS parsing complete. Loaded " << data.stops.size() << " stops and " << data.routes.size() << " routes." << endl;
    return data;
}
