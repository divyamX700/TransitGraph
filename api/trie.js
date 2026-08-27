class TrieNode {
    constructor() {
        this.children = {};
        this.isEndOfWord = false;
        this.stationIds = []; // Stores matching GTFS station IDs
    }
}

class PrefixTrie {
    constructor() {
        this.root = new TrieNode();
    }
    
    insert(word, stationId) {
        let node = this.root;
        for (let char of word.toLowerCase()) {
            if (!node.children[char]) {
                node.children[char] = new TrieNode();
            }
            node = node.children[char];
        }
        node.isEndOfWord = true;
        if (!node.stationIds.includes(stationId)) {
            node.stationIds.push(stationId);
        }
    }
    
    searchPrefix(prefix) {
        let node = this.root;
        for (let char of prefix.toLowerCase()) {
            if (!node.children[char]) return [];
            node = node.children[char];
        }
        return this.collectAll(node);
    }
    
    collectAll(node) {
        let results = [];
        if (node.isEndOfWord) {
            results.push(...node.stationIds);
        }
        for (let char in node.children) {
            results.push(...this.collectAll(node.children[char]));
        }
        return [...new Set(results)]; // unique
    }
}

module.exports = PrefixTrie;
