import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

const isGameRoute =
  typeof window !== 'undefined' &&
  (window.location.pathname === '/game' ||
    window.location.pathname.startsWith('/game/'))

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App gameMode={isGameRoute} />
  </StrictMode>,
)
