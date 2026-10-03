// Least recently used cache: a map for O(1) lookup and a doubly linked list for recency order.
class Node {
  constructor(key, value) {
    this.key = key;
    this.value = value;
    this.prev = null;
    this.next = null;
  }
}

class LRUCache {
  constructor(capacity) {
    this.capacity = capacity;
    this.map = new Map();

    // sentinels, so adding and removing never has to check for an empty list
    this.head = new Node(null, null);
    this.tail = new Node(null, null);
    this.head.next = this.tail;
    this.tail.prev = this.head;
  }

  _remove(node) {
    const prev = node.prev;
    const next = node.next;
    prev.next = next;
    next.prev = prev;
  }

  _add(node) {
    // Add right after head (most recently used)
    const next = this.head.next;
    this.head.next = node;
    node.prev = this.head;
    node.next = next;
    next.prev = node;
  }

  get(key) {
    if (this.map.has(key)) {
      const node = this.map.get(key);
      // Move to front (most recently used)
      this._remove(node);
      this._add(node);
      return node.value;
    }
    return null;
  }

  set(key, value) {
    if (this.map.has(key)) {
      const node = this.map.get(key);
      node.value = value;
      this._remove(node);
      this._add(node);
    } else {
      if (this.map.size >= this.capacity) {
        // evict the least recently used entry, just before the tail
        const lruNode = this.tail.prev;
        this._remove(lruNode);
        this.map.delete(lruNode.key);
      }
      const newNode = new Node(key, value);
      this._add(newNode);
      this.map.set(key, newNode);
    }
  }
}

module.exports = LRUCache;
