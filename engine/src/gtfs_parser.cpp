#include "gtfs_parser.h"
#include <fstream>
#include <iostream>
#include <vector>
#include <unordered_map>
#include <algorithm>
#include <cstdlib>

using namespace std;

// A GTFS table: rows of cells, with columns looked up by header name.
struct Table {
    unordered_map<string, size_t> column;
    vector<vector<string>> rows;

    // Cell of `row` in column `name`, or "" if the file has no such column or the row is short
    const string& get(const vector<string>& row, const string& name) const {
        static const string empty;
        auto it = column.find(name);
        return (it == column.end() || it->second >= row.size()) ? empty : row[it->second];
    }
};

// Splits one CSV line; a cell may be double-quoted to contain commas
vector<string> split_csv_line(const string& line) {
    vector<string> cells;
    string cell;
    bool quoted = false;
    for (size_t i = 0; i < line.size(); ++i) {
        char c = line[i];
        if (quoted) {
            if (c == '"' && i + 1 < line.size() && line[i + 1] == '"') { cell += '"'; ++i; }
            else if (c == '"') quoted = false;
            else cell += c;
        } else if (c == '"') quoted = true;
        else if (c == ',') { cells.push_back(cell); cell.clear(); }
        else cell += c;
    }
    cells.push_back(cell);
    return cells;
}

// Reads a GTFS file; a missing file gives an empty table (the caller decides if that is an error)
Table read_table(const string& path) {
    Table table;
    ifstream file(path);
    if (!file.is_open()) return table;
    string line;
    bool header = true;
    while (getline(file, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty()) continue;
        vector<string> cells = split_csv_line(line);
        if (header) {
            for (size_t i = 0; i < cells.size(); ++i) table.column[cells[i]] = i;
            header = false;
        } else {
            table.rows.push_back(std::move(cells));
        }
    }
    return table;
}

// GTFS times may run past 24:00:00 for services after midnight
int parse_time(const string& time_str) {
    int h, m, s;
    if (sscanf(time_str.c_str(), "%d:%d:%d", &h, &m, &s) == 3) {
        return h * 60 + m;
    }
    return 0;
}

// GTFS route_type: 1 = subway/metro, 12 = monorail, anything else (2 = rail) = local train
Mode mode_from_route_type(const string& route_type) {
    if (route_type == "1") return Mode::METRO;
    if (route_type == "12") return Mode::MONORAIL;
    return Mode::LOCAL;
}

struct RawTrip {
    string shape_id;  // one stop sequence, split into RAPTOR routes below
    string route_id;  // the line (routes.txt)
};

struct RawStopTime {
    int arrival_time;
    int departure_time;
    uint32_t stop_idx;
    int stop_sequence;
};

RaptorData GTFSParser::parse(const string& gtfs_dir) {
    RaptorData data;

    cerr << "Parsing stops.txt..." << endl;
    Table stops_csv = read_table(gtfs_dir + "/stops.txt");
    for (const auto& row : stops_csv.rows) {
        Stop s;
        s.id = stops_csv.get(row, "stop_id");
        if (s.id.empty()) continue;
        s.stop_routes_offset = 0;
        s.stop_routes_count = 0;
        s.footpaths_offset = 0;
        s.footpaths_count = 0;
        data.stop_id_to_index[s.id] = data.stops.size();
        data.stops.push_back(s);
    }

    cerr << "Parsing routes.txt..." << endl;
    unordered_map<string, Mode> line_mode;
    Table routes_csv = read_table(gtfs_dir + "/routes.txt");
    for (const auto& row : routes_csv.rows) {
        line_mode[routes_csv.get(row, "route_id")] = mode_from_route_type(routes_csv.get(row, "route_type"));
    }

    cerr << "Parsing trips.txt..." << endl;
    unordered_map<string, RawTrip> trips;
    Table trips_csv = read_table(gtfs_dir + "/trips.txt");
    for (const auto& row : trips_csv.rows) {
        string id = trips_csv.get(row, "trip_id");
        trips[id] = {trips_csv.get(row, "shape_id"), trips_csv.get(row, "route_id")};
    }

    cerr << "Parsing stop_times.txt..." << endl;
    unordered_map<string, vector<RawStopTime>> trip_stop_times;
    Table stop_times_csv = read_table(gtfs_dir + "/stop_times.txt");
    for (const auto& row : stop_times_csv.rows) {
        string trip_id = stop_times_csv.get(row, "trip_id");
        auto stop_it = data.stop_id_to_index.find(stop_times_csv.get(row, "stop_id"));
        if (stop_it == data.stop_id_to_index.end() || trips.find(trip_id) == trips.end()) continue;

        RawStopTime rst;
        rst.arrival_time = parse_time(stop_times_csv.get(row, "arrival_time"));
        rst.departure_time = parse_time(stop_times_csv.get(row, "departure_time"));
        rst.stop_idx = stop_it->second;
        rst.stop_sequence = atoi(stop_times_csv.get(row, "stop_sequence").c_str());
        trip_stop_times[trip_id].push_back(rst);
    }

    // Fix times that wrap at midnight, and add a copy of every trip a day later (a 48 hour window)
    vector<string> original_trip_ids;
    for (auto& kv : trips) original_trip_ids.push_back(kv.first);

    for (const string& tid : original_trip_ids) {
        auto& sts = trip_stop_times[tid];
        if (sts.empty()) { trips.erase(tid); trip_stop_times.erase(tid); continue; }
        sort(sts.begin(), sts.end(), [](const RawStopTime& a, const RawStopTime& b) {
            return a.stop_sequence < b.stop_sequence;
        });

        // Fix rollover for feeds that wrap times at 24:00 instead of counting on
        int last_time = -1;
        for (auto& st : sts) {
            if (last_time != -1 && st.arrival_time < last_time - 60) {
                st.arrival_time += 24 * 60;
                st.departure_time += 24 * 60;
            }
            last_time = st.departure_time;
        }

        string next_day_tid = tid + "_nextday";
        trips[next_day_tid] = trips[tid];
        for (const auto& st : sts) {
            RawStopTime next_st = st;
            next_st.arrival_time += 24 * 60;
            next_st.departure_time += 24 * 60;
            trip_stop_times[next_day_tid].push_back(next_st);
        }
    }

    // A RAPTOR route is a set of trips with the same stop sequence. The compiler gives each stop
    // sequence its own shape_id, so trips are grouped by shape first.
    cerr << "Building RAPTOR routes..." << endl;
    unordered_map<string, vector<string>> route_to_trips;
    for (const auto& kv : trips) {
        route_to_trips[kv.second.shape_id].push_back(kv.first);
    }

    // stop -> (route, position in the route), collected here and flattened below
    vector<vector<StopRoute>> stop_to_routes(data.stops.size());

    for (auto& kv : route_to_trips) {
        const string& shape_id = kv.first;
        auto& trip_ids = kv.second;
        if (trip_ids.empty()) continue;

        // Sort trips by departure time at the first stop (ties by id, for a deterministic build)
        sort(trip_ids.begin(), trip_ids.end(), [&trip_stop_times](const string& a, const string& b) {
            int da = trip_stop_times[a].front().departure_time;
            int db = trip_stop_times[b].front().departure_time;
            return da != db ? da < db : a < b;
        });

        // RAPTOR assumes the trips of a route never overtake each other (the binary search over
        // departures relies on it). Trains with identical stops can still differ in speed, so
        // split the shape into groups in which no trip overtakes an earlier one.
        vector<vector<string>> groups;
        for (const string& tid : trip_ids) {
            const auto& cur = trip_stop_times[tid];
            bool placed = false;
            for (auto& group : groups) {
                const auto& prev = trip_stop_times[group.back()];
                // trips of one route call at the same stops (a shape id is a short hash, so check)
                bool overtakes = cur.size() != prev.size();
                for (size_t j = 0; j < cur.size() && !overtakes; ++j) {
                    overtakes = cur[j].stop_idx != prev[j].stop_idx ||
                                cur[j].departure_time < prev[j].departure_time ||
                                cur[j].arrival_time < prev[j].arrival_time;
                }
                if (!overtakes) { group.push_back(tid); placed = true; break; }
            }
            if (!placed) groups.push_back({tid});
        }

        const RawTrip& first_trip = trips[trip_ids[0]];
        auto mode_it = line_mode.find(first_trip.route_id);

        for (const auto& group : groups) {
            // The stop sequence is the same for every trip of the shape
            const auto& first_trip_sts = trip_stop_times[group[0]];

            Route r;
            r.id = shape_id; // several routes may share a shape; the map only needs the shape
            r.line = first_trip.route_id;
            r.mode = mode_it == line_mode.end() ? Mode::LOCAL : mode_it->second;
            r.num_stops = first_trip_sts.size();
            r.num_trips = group.size();
            r.route_stops_offset = data.route_stops.size();
            r.stop_times_offset = data.stop_times.size();

            uint32_t route_idx = data.routes.size();
            data.routes.push_back(r);

            uint32_t position = 0;
            for (const auto& st : first_trip_sts) {
                data.route_stops.push_back(st.stop_idx);
                stop_to_routes[st.stop_idx].push_back({route_idx, position++});
            }

            for (const string& tid : group) {
                for (const auto& st : trip_stop_times[tid]) {
                    data.stop_times.push_back({st.arrival_time, st.departure_time});
                }
            }
            data.trip_ids.push_back(group);
        }
    }

    // stop -> routes serving it, in compressed sparse rows
    for (size_t i = 0; i < data.stops.size(); i++) {
        data.stops[i].stop_routes_offset = data.stop_routes.size();
        data.stops[i].stop_routes_count = stop_to_routes[i].size();
        for (const StopRoute& sr : stop_to_routes[i]) data.stop_routes.push_back(sr);
    }

    // Footpaths (transfers.txt): walking links between stops, in compressed sparse rows
    vector<vector<Footpath>> walks(data.stops.size());
    Table transfers_csv = read_table(gtfs_dir + "/transfers.txt");
    for (const auto& row : transfers_csv.rows) {
        auto from = data.stop_id_to_index.find(transfers_csv.get(row, "from_stop_id"));
        auto to = data.stop_id_to_index.find(transfers_csv.get(row, "to_stop_id"));
        if (from == data.stop_id_to_index.end() || to == data.stop_id_to_index.end()) {
            cerr << "transfers.txt: unknown stop in " << transfers_csv.get(row, "from_stop_id") << " -> "
                 << transfers_csv.get(row, "to_stop_id") << ", skipped" << endl;
            continue;
        }
        if (from->second == to->second) continue;
        int seconds = atoi(transfers_csv.get(row, "min_transfer_time").c_str());
        walks[from->second].push_back({to->second, (seconds + 59) / 60, atoi(transfers_csv.get(row, "distance_m").c_str())});
    }
    for (size_t i = 0; i < data.stops.size(); i++) {
        data.stops[i].footpaths_offset = data.footpaths.size();
        data.stops[i].footpaths_count = walks[i].size();
        for (const Footpath& f : walks[i]) data.footpaths.push_back(f);
    }

    cerr << "GTFS parsing complete. Loaded " << data.stops.size() << " stops, " << data.routes.size()
         << " routes and " << data.footpaths.size() << " footpaths." << endl;
    return data;
}
