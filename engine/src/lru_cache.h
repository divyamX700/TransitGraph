#pragma once
#include <unordered_map>
#include <list>
#include <string>

template<typename K, typename V>
class LRUCache {
private:
    size_t capacity;
    std::list<std::pair<K, V>> items;
    std::unordered_map<K, typename std::list<std::pair<K, V>>::iterator> cache;

public:
    LRUCache(size_t capacity) : capacity(capacity) {}

    bool get(const K& key, V& value) {
        auto it = cache.find(key);
        if (it == cache.end()) {
            return false;
        }
        // Move to front (most recently used)
        items.splice(items.begin(), items, it->second);
        value = it->second->second;
        return true;
    }

    void put(const K& key, const V& value) {
        auto it = cache.find(key);
        if (it != cache.end()) {
            items.splice(items.begin(), items, it->second);
            it->second->second = value;
            return;
        }

        if (items.size() == capacity) {
            auto last = items.back();
            cache.erase(last.first);
            items.pop_back();
        }

        items.emplace_front(key, value);
        cache[key] = items.begin();
    }
};
