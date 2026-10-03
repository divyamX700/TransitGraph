import { useEffect, useState } from 'react'

// Light / dark / follow the system. The choice is remembered; the CSS reads data-theme on <html>.
const KEY = 'transitgraph-theme'
const MODES = ['system', 'light', 'dark']

export function storedMode() {
  try { return MODES.includes(localStorage.getItem(KEY)) ? localStorage.getItem(KEY) : 'system' } catch { return 'system' }
}

export function applyMode(mode) {
  const root = document.documentElement
  if (mode === 'system') root.removeAttribute('data-theme')
  else root.dataset.theme = mode
  try { localStorage.setItem(KEY, mode) } catch { /* private mode: the choice just is not remembered */ }
  window.dispatchEvent(new Event('transitgraph-theme'))
}

const systemDark = () => window.matchMedia('(prefers-color-scheme: dark)').matches
export const isDark = () => {
  const t = document.documentElement.dataset.theme
  return t ? t === 'dark' : systemDark()
}

// true while the page is in dark mode, following the toggle and the system setting live
export function useDark() {
  const [dark, setDark] = useState(isDark)
  useEffect(() => {
    const on = () => setDark(isDark())
    const m = window.matchMedia('(prefers-color-scheme: dark)')
    window.addEventListener('transitgraph-theme', on)
    m.addEventListener('change', on)
    return () => { window.removeEventListener('transitgraph-theme', on); m.removeEventListener('change', on) }
  }, [])
  return dark
}

export function nextMode(mode) {
  return MODES[(MODES.indexOf(mode) + 1) % MODES.length]
}
