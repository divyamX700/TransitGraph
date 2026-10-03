import React from 'react'
import ReactDOM from 'react-dom/client'
import 'leaflet/dist/leaflet.css'
import './fonts.css'
import './index.css'
import App from './App.jsx'
import { applyMode, storedMode } from './theme.js'

applyMode(storedMode()) // before the first paint, so there is no flash of the wrong theme

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
