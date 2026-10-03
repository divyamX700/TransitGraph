// Prefix trie for station search: insert words, then find every station with a word starting with a prefix.
class TrieNode {
  constructor() {
    this.children = {};
    this.stationIds = []; // stations whose word ends here
  }
}

class PrefixTrie {
  constructor() {
    this.root = new TrieNode();
  }

  insert(word, stationId) {
    let node = this.root;
    for (const char of word.toLowerCase()) {
      node = node.children[char] ||= new TrieNode();
    }
    if (!node.stationIds.includes(stationId)) node.stationIds.push(stationId);
  }

  // Station ids under the prefix, each once
  searchPrefix(prefix) {
    let node = this.root;
    for (const char of prefix.toLowerCase()) {
      node = node.children[char];
      if (!node) return [];
    }
    const found = new Set();
    const stack = [node];
    while (stack.length) {
      const n = stack.pop();
      n.stationIds.forEach((id) => found.add(id));
      stack.push(...Object.values(n.children));
    }
    return [...found];
  }
}

module.exports = PrefixTrie;
