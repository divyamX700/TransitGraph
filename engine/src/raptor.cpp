#include "raptor.h"
#include <algorithm>

using namespace std;

namespace {

const uint32_t NO_STOP = UINT32_MAX;

// How a vehicle label (arrival on board a vehicle) was reached
struct RideParent {
    uint32_t boarded_stop = NO_STOP;
    uint32_t route_idx = 0;
    uint32_t trip_idx = 0;
    bool boarded_after_walk = false;  // the boarding stop was reached on foot (else by another vehicle)
};

// How a walking label (arrival on foot) was reached
struct WalkParent {
    uint32_t from_stop = NO_STOP;     // NO_STOP: this is where the journey starts
    int minutes = 0;
    int meters = 0;
};

} // namespace

// A passenger at a stop is either there since a vehicle arrived (changing vehicles then takes
// TRANSFER_PENALTY_MINS) or there on foot (the walk already included getting to the platform).
// So every stop keeps two labels per round, arrival by vehicle and arrival on foot, and what
// matters for boarding is ready = min(by vehicle + penalty, on foot).
vector<vector<JourneyLeg>> Raptor::compute_pareto_routes(const string& source_id, const string& target_id, int departure_time) {
    vector<vector<JourneyLeg>> pareto_journeys;
    auto source_it = data.stop_id_to_index.find(source_id);
    auto target_it = data.stop_id_to_index.find(target_id);
    if (source_it == data.stop_id_to_index.end() || target_it == data.stop_id_to_index.end() || source_id == target_id) {
        return pareto_journeys;
    }

    const uint32_t ps = source_it->second;
    const uint32_t pt = target_it->second;
    const uint32_t num_stops = data.stops.size();
    const int R = MAX_ROUNDS + 1;  // round k = journeys using k vehicles

    vector<vector<int>> by_vehicle(R, vector<int>(num_stops, INF));
    vector<vector<int>> on_foot(R, vector<int>(num_stops, INF));
    vector<vector<int>> ready(R, vector<int>(num_stops, INF));         // earliest time a passenger can board at the stop
    vector<vector<char>> ready_on_foot(R, vector<char>(num_stops, 0)); // ... and whether that is on-foot
    vector<vector<RideParent>> ride_parent(R, vector<RideParent>(num_stops));
    vector<vector<WalkParent>> walk_parent(R, vector<WalkParent>(num_stops));
    vector<int> ready_star(num_stops, INF);    // best ready time over all rounds
    vector<int> star_vehicle(num_stops, INF);  // best arrival by vehicle over all rounds (a walk can start from it)
    int target_best = INF;                   // earliest arrival at the target so far

    vector<uint32_t> marked;                 // stops whose ready time improved in the previous round
    vector<char> is_marked(num_stops, 0);
    auto mark = [&](uint32_t p) {
        if (!is_marked[p]) { is_marked[p] = 1; marked.push_back(p); }
    };

    // Record a walking arrival at q in round k if it can still matter
    auto arrive_on_foot = [&](int k, uint32_t q, int arrival, const WalkParent& parent) {
        if (arrival >= target_best || (q != pt && arrival >= ready_star[q])) return;
        if (arrival < on_foot[k][q]) {
            on_foot[k][q] = arrival;
            walk_parent[k][q] = parent;
        }
        if (arrival < ready[k][q]) {
            ready[k][q] = arrival;
            ready_on_foot[k][q] = 1;
        }
        ready_star[q] = min(ready_star[q], arrival);
        if (q == pt) target_best = arrival;
        mark(q);
    };
    auto walk_from = [&](int k, uint32_t p, int arrival_at_p) {
        const Stop& s = data.stops[p];
        for (uint32_t i = 0; i < s.footpaths_count; ++i) {
            const Footpath& f = data.footpaths[s.footpaths_offset + i];
            arrive_on_foot(k, f.target_stop_idx, arrival_at_p + f.minutes, {p, f.minutes, f.meters});
        }
    };

    // Round 0: the passenger is at the origin and may walk to a nearby stop
    on_foot[0][ps] = departure_time;
    ready[0][ps] = departure_time;
    ready_on_foot[0][ps] = 1;
    ready_star[ps] = departure_time;
    mark(ps);
    walk_from(0, ps, departure_time);

    // A journey is recorded when the target is reached earlier than ever before in round k
    auto record = [&](int k, bool by_walk) {
        vector<JourneyLeg> journey;
        uint32_t curr = pt;
        int round = k;
        bool walking = by_walk;  // follow the on-foot label (else the by-vehicle label) at (curr, round)

        while (true) {
            JourneyLeg leg;
            if (walking) {
                const WalkParent& w = walk_parent[round][curr];
                if (w.from_stop == NO_STOP) break;  // reached the origin
                leg.from_stop_id = data.stops[w.from_stop].id;
                leg.to_stop_id = data.stops[curr].id;
                leg.route_id = "WALK";
                leg.line = "WALK";
                leg.mode = Mode::LOCAL;
                leg.is_walk = true;
                leg.walk_meters = w.meters;
                leg.arrival_time = on_foot[round][curr];
                leg.departure_time = leg.arrival_time - w.minutes;
                curr = w.from_stop;  // a walk leaves from a stop where a vehicle arrived: same round
                walking = (round == 0);  // round 0 walks start at the origin
            } else {
                const RideParent& p = ride_parent[round][curr];
                const Route& r = data.routes[p.route_idx];
                uint32_t board_seq = 0, alight_seq = 0;
                for (uint32_t j = 0; j < r.num_stops; ++j) {
                    uint32_t stop = data.route_stops[r.route_stops_offset + j];
                    if (stop == p.boarded_stop) board_seq = j;
                    if (stop == curr) alight_seq = j;
                }
                leg.from_stop_id = data.stops[p.boarded_stop].id;
                leg.to_stop_id = data.stops[curr].id;
                leg.route_id = r.id;
                leg.line = r.line;
                leg.mode = r.mode;
                leg.is_walk = false;
                leg.walk_meters = 0;
                leg.trip_id = data.trip_ids[p.route_idx][p.trip_idx];
                leg.departure_time = data.stop_times[r.stop_times_offset + p.trip_idx * r.num_stops + board_seq].departure_time;
                leg.arrival_time = data.stop_times[r.stop_times_offset + p.trip_idx * r.num_stops + alight_seq].arrival_time;
                curr = p.boarded_stop;
                round--;
                walking = p.boarded_after_walk;
            }
            journey.push_back(leg);
        }
        reverse(journey.begin(), journey.end());
        pareto_journeys.push_back(journey);
    };

    if (target_best != INF) record(0, true);  // the target is within walking distance of the origin

    vector<int> route_start(data.routes.size(), -1);  // route -> earliest marked position in it
    vector<uint32_t> queue;
    vector<uint32_t> improved;

    for (int k = 1; k <= MAX_ROUNDS; ++k) {
        const int target_before = target_best;

        // Collect the routes serving marked stops, each with the first marked stop along it
        queue.clear();
        for (uint32_t p : marked) {
            const Stop& s = data.stops[p];
            for (uint32_t i = 0; i < s.stop_routes_count; ++i) {
                const StopRoute& sr = data.stop_routes[s.stop_routes_offset + i];
                if (route_start[sr.route_idx] == -1) {
                    route_start[sr.route_idx] = sr.position;
                    queue.push_back(sr.route_idx);
                } else if ((int)sr.position < route_start[sr.route_idx]) {
                    route_start[sr.route_idx] = sr.position;
                }
            }
            is_marked[p] = 0;
        }
        marked.clear();
        if (queue.empty()) break;

        improved.clear();

        for (uint32_t r_idx : queue) {
            const Route& r = data.routes[r_idx];
            int t = -1;  // trip currently ridden, -1 for none
            uint32_t boarded_stop = NO_STOP;
            bool boarded_after_walk = false;

            for (uint32_t j = route_start[r_idx]; j < r.num_stops; ++j) {
                uint32_t pi = data.route_stops[r.route_stops_offset + j];

                // Does staying on the current trip improve what we know about pi? It does if the
                // passenger can board there sooner, or arrives earlier (earlier is worth keeping:
                // walking on from it may beat everything known about the neighbouring stops).
                if (t != -1) {
                    int arr_time = data.stop_times[r.stop_times_offset + t * r.num_stops + j].arrival_time;
                    int ready_here = arr_time + TRANSFER_PENALTY_MINS;
                    bool sooner_ready = ready_here < ready_star[pi];
                    if (arr_time < target_best && (pi == pt || sooner_ready || arr_time < star_vehicle[pi])) {
                        by_vehicle[k][pi] = arr_time;
                        ride_parent[k][pi] = {boarded_stop, r_idx, (uint32_t)t, boarded_after_walk};
                        star_vehicle[pi] = min(star_vehicle[pi], arr_time);
                        if (sooner_ready) {
                            ready[k][pi] = ready_here;
                            ready_on_foot[k][pi] = 0;
                            ready_star[pi] = ready_here;
                            mark(pi);
                        }
                        if (pi == pt) target_best = arr_time;
                        improved.push_back(pi);
                    }
                }

                // Can we catch an earlier trip here?
                if (ready[k - 1][pi] != INF) {
                    // earliest trip leaving pi at or after the ready time (trips never overtake)
                    int low = 0;
                    int high = r.num_trips - 1;
                    int best_trip_idx = -1;
                    while (low <= high) {
                        int mid = low + (high - low) / 2;
                        int dep_time = data.stop_times[r.stop_times_offset + mid * r.num_stops + j].departure_time;
                        if (dep_time >= ready[k - 1][pi]) {
                            best_trip_idx = mid;
                            high = mid - 1;
                        } else {
                            low = mid + 1;
                        }
                    }

                    if (best_trip_idx != -1 && (t == -1 || best_trip_idx < t)) {
                        t = best_trip_idx;
                        boarded_stop = pi;
                        boarded_after_walk = ready_on_foot[k - 1][pi];
                    }
                }
            }
            route_start[r_idx] = -1;
        }

        // Walk on from every stop a vehicle just reached
        for (uint32_t p : improved) {
            if (by_vehicle[k][p] != INF) walk_from(k, p, by_vehicle[k][p]);
        }

        // The target was reached earlier than with fewer vehicles: reconstruct that journey
        if (target_best < target_before) {
            record(k, !(by_vehicle[k][pt] == target_best));
        }
    }

    return pareto_journeys;
}
