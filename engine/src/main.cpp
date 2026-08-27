#include "gtfs_parser.h"
#include "raptor.h"
#include "lru_cache.h"
#include <iostream>
#include <sstream>
#include <string>

using namespace std;

string format_time(int mins) {
    int h = (mins / 60) % 24;
    int m = mins % 60;
    char buf[10];
    snprintf(buf, sizeof(buf), "%02d:%02d", h, m);
    return string(buf);
}

// Convert journeys to JSON manually to avoid external dependencies
string journeys_to_json(const vector<vector<JourneyLeg>>& journeys) {
    stringstream ss;
    ss << "[";
    for (size_t i = 0; i < journeys.size(); ++i) {
        ss << "[";
        for (size_t j = 0; j < journeys[i].size(); ++j) {
            const auto& leg = journeys[i][j];
            ss << "{";
            ss << "\"from\": \"" << leg.from_stop_id << "\", ";
            ss << "\"to\": \"" << leg.to_stop_id << "\", ";
            ss << "\"route_id\": \"" << leg.route_id << "\", ";
            ss << "\"trip_id\": \"" << leg.trip_id << "\", ";
            ss << "\"dep\": \"" << format_time(leg.departure_time) << "\", ";
            ss << "\"arr\": \"" << format_time(leg.arrival_time) << "\"";
            ss << "}";
            if (j < journeys[i].size() - 1) ss << ", ";
        }
        ss << "]";
        if (i < journeys.size() - 1) ss << ", ";
    }
    ss << "]";
    return ss.str();
}

int main(int argc, char** argv) {
    string gtfs_dir = argc > 1 ? argv[1] : "data/gtfs";
    
    // 1. Initialize data structures
    RaptorData data = GTFSParser::parse(gtfs_dir);
    Raptor raptor(data);
    
    // 2. Initialize LRU Cache for the queries
    LRUCache<string, string> cache(1000);
    
    cout << "READY" << endl;
    
    // 3. Persistent Event Loop listening to Node.js via stdin
    string line;
    while (getline(cin, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line == "EXIT") break;
        
        // Expected format: UUID|SOURCE,TARGET,DEPARTURE_TIME_MINS
        size_t pipe_pos = line.find('|');
        if (pipe_pos == string::npos) {
            cout << "error|{\"error\": \"Invalid format missing UUID\"}" << endl;
            continue;
        }
        string uuid = line.substr(0, pipe_pos);
        string query_str = line.substr(pipe_pos + 1);
        
        stringstream ss(query_str);
        string source, target, time_str;
        getline(ss, source, ',');
        getline(ss, target, ',');
        getline(ss, time_str, ',');
        
        if (source.empty() || target.empty() || time_str.empty()) {
            cout << uuid << "|{\"error\": \"Invalid format\"}" << endl;
            continue;
        }
        
        string cache_key = query_str;
        string json_result;
        
        if (cache.get(cache_key, json_result)) {
            // Cache Hit
            cout << uuid << "|{\"cached\": true, \"routes\": " << json_result << "}" << endl;
        } else {
            // Cache Miss -> Run RAPTOR
            int dep_time = stoi(time_str);
            auto journeys = raptor.compute_pareto_routes(source, target, dep_time);
            
            json_result = journeys_to_json(journeys);
            cache.put(cache_key, json_result);
            
            cout << uuid << "|{\"cached\": false, \"routes\": " << json_result << "}" << endl;
        }
    }
    
    return 0;
}
