import { useEffect, useId, useRef, useState } from 'react'
import { X } from '@phosphor-icons/react'
import { searchStations } from './api.js'
import { StationBadges } from './Tags.jsx'

// A station picker: type a name (or a word of it), pick from the list. Metro and local stations can
// share a name ("Andheri"), so every suggestion says which it is.
export default function StationInput({ label, value, onChange, placeholder }) {
  const id = useId()
  const listId = `${id}-list`
  const [text, setText] = useState(value?.name || '')
  const [options, setOptions] = useState([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const [waiting, setWaiting] = useState(false)
  const box = useRef(null)
  const request = useRef(0)

  // keep the text in step when the value is changed from outside (swap, a shared link)
  // (not when the value was just cleared by typing: the box keeps what is being typed)
  const typed = useRef(false)
  useEffect(() => {
    if (typed.current) { typed.current = false; return }
    setText(value?.name || '')
  }, [value])

  useEffect(() => {
    const away = (e) => { if (!box.current?.contains(e.target)) setOpen(false) }
    document.addEventListener('pointerdown', away)
    return () => document.removeEventListener('pointerdown', away)
  }, [])

  function typing(e) {
    const q = e.target.value
    setText(q)
    typed.current = Boolean(value)
    onChange(null)
    const mine = ++request.current
    if (q.trim().length < 2) { setOptions([]); setWaiting(false); setOpen(false); return }
    setWaiting(true)
    setOpen(true)
    setTimeout(async () => {
      if (mine !== request.current) return
      try {
        const found = await searchStations(q.trim())
        if (mine !== request.current) return
        setOptions(found.slice(0, 8))
        setActive(found.length ? 0 : -1)
      } catch { setOpen(false) }
      if (mine === request.current) setWaiting(false)
    }, 90)
  }

  function choose(s) {
    request.current++
    setText(s.name)
    onChange(s)
    setOpen(false)
  }

  function keys(e) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      if (!options.length) return
      e.preventDefault()
      setOpen(true)
      setActive((a) => (e.key === 'ArrowDown' ? (a + 1) % options.length : (a - 1 + options.length) % options.length))
    } else if (e.key === 'Enter' && open && options[active]) {
      e.preventDefault()
      choose(options[active])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className="field" ref={box}>
      <label className="field-label" htmlFor={id}>{label}</label>
      <div className={`field-box${value ? ' chosen' : ''}`}>
        <input
          id={id}
          className="field-input"
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && active >= 0 ? `${id}-o${active}` : undefined}
          autoComplete="off"
          autoCapitalize="words"
          spellCheck="false"
          placeholder={placeholder}
          value={text}
          onChange={typing}
          onKeyDown={keys}
          onFocus={(e) => { e.target.select(); if (options.length) setOpen(true) }}
          onBlur={() => setOpen(false)}
        />
        {value && <span className="option-tags"><StationBadges station={value} /></span>}
        {text && (
          <button type="button" className="icon-btn" aria-label={`Clear ${label}`}
            onClick={() => { setText(''); onChange(null); setOptions([]); setOpen(false) }}>
            <X size={16} weight="bold" />
          </button>
        )}
      </div>
      {open && (
        <ul className="options" id={listId} role="listbox" aria-label={`${label} suggestions`}>
          {options.map((s, i) => (
            <li
              key={s.id}
              id={`${id}-o${i}`}
              role="option"
              aria-selected={i === active}
              className={i === active ? 'on' : ''}
              onPointerDown={(e) => { e.preventDefault(); choose(s) }}
              onMouseMove={() => setActive(i)}
            >
              <span className="option-name">{s.name}</span>
              <span className="option-tags"><StationBadges station={s} /></span>
            </li>
          ))}
          {waiting && options.length === 0 && [0, 1, 2].map((n) => <li key={n} className="skeleton-option" role="presentation"><span className="skel" /></li>)}
          {!waiting && options.length === 0 && <li className="none" role="presentation">No station matches “{text}”</li>}
        </ul>
      )}
    </div>
  )
}
