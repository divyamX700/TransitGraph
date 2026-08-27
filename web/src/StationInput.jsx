import { useState, useEffect, useRef } from 'react'

export default function StationInput({ label, value, onChange, placeholder, id }) {
  const [query, setQuery] = useState(value?.name || '')
  const [suggestions, setSuggestions] = useState([])
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const debounce = useRef(null)
  const containerRef = useRef(null)

  // Sync query text whenever external value changes (swap, clear, etc.)
  useEffect(() => {
    setQuery(value?.name || '')
  }, [value])

  function handleInput(e) {
    const q = e.target.value
    setQuery(q)
    onChange(null) // clear selection

    clearTimeout(debounce.current)
    if (q.length < 2) { setSuggestions([]); setOpen(false); return }

    debounce.current = setTimeout(async () => {
      const res = await fetch(`/api/stations?prefix=${encodeURIComponent(q)}`)
      const data = await res.json()
      setSuggestions(data.slice(0, 8))
      setOpen(data.length > 0)
      setActiveIndex(-1)
    }, 120)
  }

  function handleSelect(station) {
    setQuery(station.name)
    onChange(station)
    setOpen(false)
    setSuggestions([])
    setActiveIndex(-1)
  }

  function handleKeyDown(e) {
    if (!open || suggestions.length === 0) return
    
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex(prev => (prev < suggestions.length - 1 ? prev + 1 : prev))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex(prev => (prev > 0 ? prev - 1 : -1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (activeIndex >= 0 && activeIndex < suggestions.length) {
        handleSelect(suggestions[activeIndex])
      }
    } else if (e.key === 'Escape') {
      setOpen(false)
      setActiveIndex(-1)
    }
  }

  // Close on outside click
  useEffect(() => {
    function handler(e) {
      if (!containerRef.current?.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div className="input-group" ref={containerRef}>
      <label className="input-label" htmlFor={id}>{label}</label>
      <input
        id={id}
        className="station-input"
        type="text"
        value={query}
        onChange={handleInput}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        autoComplete="off"
        onFocus={() => suggestions.length > 0 && setOpen(true)}
      />
      {open && (
        <div className="autocomplete-dropdown" role="listbox">
          {suggestions.map((s, idx) => (
            <div
              key={s.id}
              className={`autocomplete-item${activeIndex === idx ? ' active' : ''}`}
              role="option"
              aria-selected={activeIndex === idx}
              onMouseDown={() => handleSelect(s)}
              onMouseEnter={() => setActiveIndex(idx)}
            >
              <span className="autocomplete-item-name">{s.name}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
