import { Link } from 'react-router-dom'
import { LogOut } from 'lucide-react'
import { useAuthStore } from '../../store/authStore'

export default function Navbar() {
  const { user, logout } = useAuthStore()

  return (
    <nav
      className="sticky top-0 z-40 flex items-center justify-between px-6 md:px-10 h-16 w-full"
      style={{
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        background: 'rgba(0,0,0,0.85)',
        backdropFilter: 'blur(20px)',
      }}
    >
      {/* Logo as Home Link */}
      <Link 
        to="/" 
        className="flex items-center gap-2.5 transition-opacity hover:opacity-80 cursor-pointer"
        title="Reset and go to home"
      >
        <div style={{
          width: 30, height: 30,
          background: 'rgba(223,255,0,0.08)',
          border: '1px solid rgba(223,255,0,0.3)',
          borderRadius: 7,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.35C17.25 22.15 21 17.25 21 12V7L12 2z" fill="#DFFF00" />
          </svg>
        </div>
        <span style={{ fontFamily: "'Syncopate', sans-serif", fontWeight: 700, fontSize: 13, letterSpacing: '0.06em', color: '#fff' }}>
          SATARK AI
        </span>
      </Link>

      {/* Right side */}
      <div className="flex items-center gap-6">
        {user && (
          <span style={{ color: '#555', fontSize: 13 }}>
            {user.username ?? user.email}
          </span>
        )}
        <button
          id="logout-btn"
          onClick={logout}
          className="flex items-center gap-1.5 transition-colors duration-200"
          style={{ color: '#555', fontSize: 13, cursor: 'pointer', background: 'none', border: 'none' }}
          onMouseEnter={e => (e.currentTarget.style.color = '#fff')}
          onMouseLeave={e => (e.currentTarget.style.color = '#555')}
          aria-label="Logout"
        >
          <LogOut size={15} />
          <span className="hidden sm:inline">Logout</span>
        </button>
      </div>
    </nav>
  )
}
