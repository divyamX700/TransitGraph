// Layout audit for the running app. Load it into the page (e.g. from the browser console or a
// <script> tag served by the dev server) and call `await uiAudit({ steps: true, legend: true })`.
// It returns a list of problems; an empty list means the checks passed for this viewport, theme
// and state. The checks are the ones a person makes by eye: nothing sticks out of the screen,
// nothing is cut off, targets are big enough to tap, step rows line up, text is readable.
window.uiAudit = async function uiAudit({ steps = false, legend = false } = {}) {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
  const problems = []
  // a hidden tab does not advance CSS transitions, which would show half-finished states: settle them
  const calm = document.createElement('style')
  calm.textContent = '*, *::before, *::after { transition: none !important; animation: none !important; }'
  document.head.appendChild(calm)
  const visible = (el) => {
    const r = el.getBoundingClientRect()
    const s = getComputedStyle(el)
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'
  }
  const inMap = (el) => el.closest('.leaflet-container') && !el.closest('.legend')
  const label = (el) => `${el.tagName.toLowerCase()}${el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : ''}${el.textContent ? ' "' + el.textContent.trim().slice(0, 28) + '"' : ''}`

  if (steps) {
    const head = document.querySelector('.journey-head')
    if (head && head.getAttribute('aria-expanded') !== 'true') head.click()
    await sleep(350)
  }
  if (legend) {
    const d = document.querySelector('.legend')
    if (d) d.open = true
    await sleep(150)
  }
  document.querySelector('.rail')?.scrollTo(0, 0)

  const vw = document.documentElement.clientWidth
  const vh = window.innerHeight

  // 1. nothing wider than the page
  if (document.documentElement.scrollWidth > vw + 1) problems.push(`page scrolls sideways (${document.documentElement.scrollWidth} > ${vw})`)
  for (const el of document.querySelectorAll('body *')) {
    if (!visible(el) || inMap(el) || el.closest('.sr-only') || el.classList.contains('sr-only')) continue
    const r = el.getBoundingClientRect()
    if (r.right > vw + 1 || r.left < -1) problems.push(`sticks out horizontally: ${label(el)} (${Math.round(r.left)}..${Math.round(r.right)} of ${vw})`)
  }

  // 2. text that is cut off
  for (const el of document.querySelectorAll('.rail *, .bar *, .legend *')) {
    // .s-name: station names in the phone summary shorten with an ellipsis on purpose
    if (!visible(el) || el.closest('.sr-only') || el.classList.contains('s-name')) continue
    const s = getComputedStyle(el)
    if ((s.overflowX === 'hidden' || s.textOverflow === 'ellipsis') && el.scrollWidth > el.clientWidth + 1 && el.children.length === 0) {
      problems.push(`text cut off: ${label(el)}`)
    }
  }
  for (const el of document.querySelectorAll('.journey, .legend')) {
    for (const child of el.querySelectorAll('*')) {
      if (!visible(child)) continue
      const r = child.getBoundingClientRect(), p = el.getBoundingClientRect()
      if (r.right > p.right + 1 || r.left < p.left - 1) problems.push(`overflows its card: ${label(child)}`)
    }
  }

  // 3. tap targets
  for (const el of document.querySelectorAll('button, input, summary, [role=option], a.wordmark')) {
    if (!visible(el) || inMap(el)) continue
    const r = el.getBoundingClientRect()
    if (r.height < 40 || r.width < 40) problems.push(`small target ${Math.round(r.width)}x${Math.round(r.height)}: ${label(el)}`)
  }

  // 4. step rows: time, line node and text share a centre line
  for (const row of document.querySelectorAll('.row.stop')) {
    const node = row.querySelector('.node')?.getBoundingClientRect()
    const time = row.querySelector('.r-time')?.getBoundingClientRect()
    const body = row.querySelector('.r-body')?.getBoundingClientRect()
    if (!node || !time || !body) continue
    const c = node.top + node.height / 2
    if (Math.abs(c - (time.top + time.height / 2)) > 4) problems.push(`step time off the line: ${row.textContent.trim().slice(0, 30)}`)
    if (Math.abs(c - (body.top + body.height / 2)) > 4) problems.push(`step text off the line: ${row.textContent.trim().slice(0, 30)}`)
  }
  const rails = [...document.querySelectorAll('.route .rail')].map((r) => r.getBoundingClientRect().left)
  if (rails.length && Math.max(...rails) - Math.min(...rails) > 1) problems.push('step line is not a straight column')

  // 5. contrast of text against its background
  const parse = (c) => { const m = c.match(/[\d.]+/g); return m ? m.slice(0, 4).map(Number) : null }
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4 }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b) }
  const bgOf = (el) => { for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c && (c[3] === undefined || c[3] > 0.9)) return c } return [255, 255, 255] }
  const seen = new Set()
  for (const el of document.querySelectorAll('.rail *, .bar *, .legend *')) {
    if (!visible(el) || el.closest('.sr-only') || !el.childNodes.length) continue
    if (![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue
    const s = getComputedStyle(el)
    const fg = parse(s.color)
    if (!fg) continue
    const a = lum(fg), b = lum(bgOf(el))
    const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
    const large = parseFloat(s.fontSize) >= 24 || (parseFloat(s.fontSize) >= 18.66 && +s.fontWeight >= 700)
    const key = s.color + bgOf(el).join() + s.fontSize
    if (ratio < (large ? 3 : 4.5) && !seen.has(key)) { seen.add(key); problems.push(`low contrast ${ratio.toFixed(2)}: ${label(el)}`) }
  }

  // 6. the app itself
  if (!document.fonts.check('600 20px Khand') || !document.fonts.check('400 16px Hind')) problems.push('fonts not loaded')
  if (!document.querySelector('.mark')) problems.push('logo mark missing')
  const bar = document.querySelector('.bar')?.getBoundingClientRect()
  if (bar && bar.height > 80) problems.push(`header too tall (${Math.round(bar.height)}px)`)
  const rail = document.querySelector('.rail')
  const map = document.querySelector('.mapbox')?.getBoundingClientRect()
  if (map && map.height < 160) problems.push(`map too small (${Math.round(map.height)}px)`)
  if (rail && rail.getBoundingClientRect().height < 200) problems.push('results area too small')

  return { viewport: `${vw}x${vh}`, theme: document.documentElement.dataset.theme || 'system', problems }
}
