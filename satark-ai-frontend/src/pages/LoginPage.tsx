import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { useEffect, useRef } from 'react'

// ── Google SVG ─────────────────────────────────────────────────────────────
function GoogleIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
    </svg>
  )
}

// ── Floating 3D Orbs background ────────────────────────────────────────────
function Orbs() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      {/* Acid orb */}
      <div style={{
        position: 'absolute', borderRadius: '50%',
        width: 600, height: 600,
        background: 'radial-gradient(circle, rgba(223,255,0,0.18), transparent 70%)',
        filter: 'blur(80px)',
        top: -200, left: -100,
        animation: 'orb-drift 8s ease-in-out infinite alternate',
      }} />
      {/* Plasma orb */}
      <div style={{
        position: 'absolute', borderRadius: '50%',
        width: 400, height: 400,
        background: 'radial-gradient(circle, rgba(191,90,242,0.18), transparent 70%)',
        filter: 'blur(80px)',
        bottom: -100, right: -50,
        animation: 'orb-drift 8s ease-in-out infinite alternate',
        animationDelay: '-4s',
      }} />
      {/* Cyan orb */}
      <div style={{
        position: 'absolute', borderRadius: '50%',
        width: 300, height: 300,
        background: 'radial-gradient(circle, rgba(0,255,255,0.12), transparent 70%)',
        filter: 'blur(80px)',
        top: '50%', left: '50%',
        transform: 'translate(-50%,-50%)',
        animation: 'orb-drift 8s ease-in-out infinite alternate',
        animationDelay: '-2s',
      }} />
    </div>
  )
}

// ── Brand ticker strip ─────────────────────────────────────────────────────
const TICKER_ITEMS = ['SBI', '★', 'HDFC', '★', 'IRCTC', '★', 'ICICI', '★', 'AADHAAR', '★', 'NPCI', '★', 'PAYTM', '★', 'UIDAI', '★', 'BHIM UPI', '★']

function Ticker() {
  const doubled = [...TICKER_ITEMS, ...TICKER_ITEMS]
  return (
    <div
      className="overflow-hidden w-full"
      style={{
        borderTop: '1px solid rgba(255,255,255,0.06)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        padding: '0.6rem 0',
      }}
      aria-hidden="true"
    >
      <div
        className="ticker-track flex gap-12 w-max"
        style={{
          fontFamily: "'Syncopate', sans-serif",
          fontSize: 11,
          textTransform: 'uppercase',
          letterSpacing: '0.2em',
          color: '#888',
        }}
      >
        {doubled.map((item, i) => (
          <span key={i}>{item}</span>
        ))}
      </div>
    </div>
  )
}

// ── Stats row ──────────────────────────────────────────────────────────────
const STATS = [
  { value: '2.3M+', label: 'Indians Targeted Daily' },
  { value: '94%',   label: 'Detection Accuracy' },
  { value: '<0.5s', label: 'Analysis Time' },
  { value: '12+',   label: 'Indian Brands Monitored' },
]

// ── Features grid ──────────────────────────────────────────────────────────
const FEATURES = [
  {
    icon: '🔍',
    title: 'URL Deep Scan',
    desc: 'Typosquatting detection, WHOIS age check, redirect chain analysis, PhishTank verification — all free.',
    accent: 'glass-acid',
  },
  {
    icon: '🧠',
    title: 'Explainable AI',
    desc: 'SHAP feature attributions visualise exactly WHY a message is flagged. No black boxes.',
    accent: 'glass-cyan',
  },
  {
    icon: '🇮🇳',
    title: 'Built for India',
    desc: 'Trained on SBI, HDFC, IRCTC, and 9 more Indian brands. Supports English, Hindi, and Hinglish.',
    accent: 'glass-acid',
  },
  {
    icon: '🛡️',
    title: 'ArmorIQ Security',
    desc: 'Every AI call is wrapped with prompt injection protection, intent verification and tamper-evident audit logs.',
    accent: 'glass-cyan',
  },
  {
    icon: '📷',
    title: 'Screenshot OCR',
    desc: 'Upload a WhatsApp or SMS screenshot. EasyOCR extracts text in English and Devanagari script.',
    accent: 'glass-acid',
  },
  {
    icon: '⚡',
    title: 'Groq Lightning Speed',
    desc: 'Groq LPU + Llama-3.1 delivers natural-language threat explanations in under 500 ms.',
    accent: 'glass-cyan',
  },
]

// ── Scroll reveal hook ─────────────────────────────────────────────────────
function useScrollReveal() {
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => entries.forEach(e => e.isIntersecting && e.target.classList.add('in-view')),
      { threshold: 0.12 }
    )
    document.querySelectorAll('.reveal').forEach((el, i) => {
      (el as HTMLElement).style.transitionDelay = `${i * 60}ms`
      observer.observe(el)
    })
    return () => observer.disconnect()
  }, [])
}

// ── Magnetic button hook ───────────────────────────────────────────────────
function useMagneticBtn(ref: React.RefObject<HTMLButtonElement | null>) {
  useEffect(() => {
    const btn = ref.current
    if (!btn) return
    const onMove = (e: MouseEvent) => {
      const r = btn.getBoundingClientRect()
      const x = (e.clientX - r.left - r.width / 2) * 0.28
      const y = (e.clientY - r.top - r.height / 2) * 0.28
      btn.style.transform = `translate(${x}px,${y}px)`
    }
    const onLeave = () => {
      btn.style.transform = 'translate(0,0)'
      btn.style.transition = 'transform 0.5s cubic-bezier(0.34,1.56,0.64,1)'
    }
    btn.addEventListener('mousemove', onMove)
    btn.addEventListener('mouseleave', onLeave)
    return () => {
      btn.removeEventListener('mousemove', onMove)
      btn.removeEventListener('mouseleave', onLeave)
    }
  }, [ref])
}

// ── Main Landing Page ──────────────────────────────────────────────────────
export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { login, setAuthData } = useAuthStore()
  const ctaBtnRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const token = params.get('token')
    const userStr = params.get('user')
    if (token && userStr) {
      try {
        const user = JSON.parse(decodeURIComponent(userStr))
        setAuthData(token, user)
        navigate('/analyze', { replace: true })
      } catch (e) {
        console.error("Failed to parse user from URL", e)
      }
    }
  }, [location, setAuthData, navigate])

  useScrollReveal()
  useMagneticBtn(ctaBtnRef)

  const handleGoogleSignIn = async () => {
    window.location.href = import.meta.env.VITE_API_BASE_URL + '/auth/google/login'
  }

  const handleDemoSignIn = async () => {
    try {
      await login({ email: 'demo@satark.ai', password: 'demo123' })
      navigate('/analyze', { replace: true })
    } catch (err) {
      console.error("Demo login failed:", err)
      alert("Demo login failed. Please ensure the backend is running and the database has been seeded.")
    }
  }

  return (
    <div className="min-h-screen bg-[#000] text-white relative overflow-x-hidden">
      {/* Noise overlay */}
      <div className="noise-overlay" />

      {/* ── Navbar ─────────────────────────────────────────────────────────── */}
      <nav
        className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 md:px-12 py-4"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.06)', background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(20px)' }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div style={{
            width: 34, height: 34,
            background: 'rgba(223,255,0,0.08)',
            border: '1px solid rgba(223,255,0,0.3)',
            borderRadius: 8,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.35C17.25 22.15 21 17.25 21 12V7L12 2z" fill="#DFFF00" opacity="0.9"/>
            </svg>
          </div>
          <span style={{ fontFamily: "'Syncopate', sans-serif", fontWeight: 700, fontSize: 14, letterSpacing: '0.05em' }}>
            SATARK AI
          </span>
        </div>

        {/* Nav links */}
        <div className="hidden md:flex items-center gap-10" style={{ fontFamily: "'Outfit', sans-serif", fontSize: 12, fontWeight: 500, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#666' }}>
          <a href="#features" className="hover:text-white transition-colors duration-200">Features</a>
          <a href="#how" className="hover:text-white transition-colors duration-200">How It Works</a>
          <a href="#stats" className="hover:text-white transition-colors duration-200">Stats</a>
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={handleGoogleSignIn}
            className="hidden sm:flex items-center gap-2 transition-all duration-200"
            style={{
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.12)',
              borderRadius: 12,
              padding: '0.5rem 1.25rem',
              fontSize: 13,
              fontWeight: 500,
              cursor: 'pointer',
              color: '#fff',
            }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = 'rgba(223,255,0,0.4)')}
            onMouseLeave={e => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.12)')}
          >
            <GoogleIcon size={16} />
            Sign in
          </button>
        </div>
      </nav>

      {/* ── Hero Section ───────────────────────────────────────────────────── */}
      <section
        className="relative min-h-screen flex flex-col items-center justify-center px-6 pt-32 pb-20 bg-grid"
      >
        {/* Network Image Background Highlight */}
        <div 
          className="absolute inset-0 pointer-events-none mix-blend-screen"
          style={{
            backgroundImage: "url('/network-bg.jpeg')",
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            opacity: 0.6,
            maskImage: 'radial-gradient(ellipse 70% 60% at 50% 50%, #000 30%, transparent 90%)',
            WebkitMaskImage: 'radial-gradient(ellipse 70% 60% at 50% 50%, #000 30%, transparent 90%)'
          }}
        />
        
        <Orbs />

        {/* FOMO badge */}
        <div
          className="reveal inline-flex items-center gap-2 mb-10"
          style={{
            background: 'rgba(223,255,0,0.06)',
            border: '1px solid rgba(223,255,0,0.2)',
            borderRadius: 100,
            padding: '0.35rem 1rem',
            fontSize: 11,
            fontFamily: "'Outfit', sans-serif",
            fontWeight: 500,
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            color: '#DFFF00',
          }}
        >
          <span className="fomo-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: '#DFFF00', display: 'inline-block' }} />
          Powered by Groq Llama-3.1 · Built for India
        </div>

        {/* Hero headline */}
        <h1
          className="reveal text-center font-black tracking-tighter leading-[0.9] mb-8"
          style={{
            fontFamily: "'Syncopate', sans-serif",
            fontSize: 'clamp(2.8rem, 9vw, 8rem)',
            textTransform: 'uppercase',
          }}
        >
          DETECT
          <br />
          <span className="text-gradient-threat">PHISHING</span>
          <br />
          INSTANTLY.
        </h1>

        {/* Subheadline */}
        <p
          className="reveal text-center max-w-2xl mx-auto mb-12 drop-shadow-lg"
          style={{ 
            color: '#fff', 
            fontSize: 'clamp(1rem, 1.8vw, 1.2rem)', 
            lineHeight: 1.7,
            textShadow: '0 2px 10px rgba(0,0,0,0.8)'
          }}
        >
          India's first explainable phishing detection engine. Analyse any SMS, email,
          WhatsApp message, or URL. Get AI-powered threat analysis and risk indicators in under half a second.
        </p>

        {/* Magnetic CTA */}
        <div className="reveal flex flex-col sm:flex-row items-center justify-center gap-4">
          <button
            id="hero-signin-btn"
            onClick={handleGoogleSignIn}
            className="flex items-center justify-center gap-3 transition-all duration-200 btn-acid"
            style={{
              padding: '0.875rem 1.5rem',
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
              minWidth: 260,
              borderRadius: 0
            }}
          >
            <GoogleIcon size={18} />
            Sign in with Google
          </button>
        </div>

        {/* Trusted brands */}
        <p className="reveal mt-10" style={{ color: '#444', fontSize: 12, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
          Detects attacks on →
          <span style={{ color: '#DFFF00', marginLeft: 8 }}>SBI · HDFC · IRCTC · AADHAAR · UPI · PAYTM</span>
        </p>
      </section>

      {/* ── Ticker ─────────────────────────────────────────────────────────── */}
      <Ticker />

      {/* ── Stats ──────────────────────────────────────────────────────────── */}
      <section id="stats" className="py-24 px-6 md:px-12 max-w-6xl mx-auto">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-px" style={{ background: 'rgba(255,255,255,0.06)' }}>
          {STATS.map((stat, i) => (
            <div
              key={i}
              className="reveal flex flex-col items-center justify-center py-12 px-6"
              style={{ background: '#000' }}
            >
              <span
                style={{
                  fontFamily: "'Syncopate', sans-serif",
                  fontSize: 'clamp(2rem, 5vw, 3.5rem)',
                  fontWeight: 700,
                  color: '#DFFF00',
                  lineHeight: 1,
                  display: 'block',
                }}
              >
                {stat.value}
              </span>
              <span
                style={{
                  fontSize: 11,
                  textTransform: 'uppercase',
                  letterSpacing: '0.15em',
                  color: '#555',
                  marginTop: '0.6rem',
                  textAlign: 'center',
                }}
              >
                {stat.label}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* ── Features ───────────────────────────────────────────────────────── */}
      <section id="features" className="py-24 px-6 md:px-12 max-w-6xl mx-auto">
        <div className="reveal text-center mb-16">
          <h2
            style={{
              fontFamily: "'Syncopate', sans-serif",
              fontSize: 'clamp(1.8rem, 4vw, 3rem)',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '-0.02em',
              marginBottom: '1rem',
            }}
          >
            Every Weapon You Need
          </h2>
          <p style={{ color: '#666', fontSize: 'clamp(0.9rem, 1.5vw, 1.1rem)' }}>
            A complete AI security stack, all free and open-source.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((feat, i) => (
            <div
              key={i}
              className={`reveal card-3d glass ${feat.accent} scanlines relative p-7`}
            >
              <div style={{ fontSize: 32, marginBottom: '1.25rem' }}>{feat.icon}</div>
              <h3
                style={{
                  fontFamily: "'Syncopate', sans-serif",
                  fontSize: 13,
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  marginBottom: '0.75rem',
                }}
              >
                {feat.title}
              </h3>
              <p style={{ color: '#888', fontSize: 14, lineHeight: 1.7 }}>{feat.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── How It Works ───────────────────────────────────────────────────── */}
      <section id="how" className="py-24 px-6 md:px-12 max-w-5xl mx-auto">
        <div className="reveal text-center mb-16">
          <h2
            style={{
              fontFamily: "'Syncopate', sans-serif",
              fontSize: 'clamp(1.8rem, 4vw, 3rem)',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '-0.02em',
            }}
          >
            How It Works
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {[
            { step: '01', title: 'Paste or Upload', desc: 'Drop any suspicious SMS, email body, URL, or WhatsApp screenshot into the analyser.' },
            { step: '02', title: 'AI Analyses', desc: 'ArmorIQ sanitizes your input. Groq LLM + SHAP + URL analysis run in parallel in under 500ms.' },
            { step: '03', title: 'Get Verdict', desc: 'Receive a clear SAFE / SUSPICIOUS / PHISHING verdict with SHAP feature explanations and a risk score.' },
          ].map((item, i) => (
            <div key={i} className="reveal glass p-7 relative">
              <div
                style={{
                  fontFamily: "'Syncopate', sans-serif",
                  fontSize: 'clamp(3rem, 6vw, 5rem)',
                  fontWeight: 700,
                  color: 'rgba(223,255,0,0.08)',
                  lineHeight: 1,
                  marginBottom: '1rem',
                }}
              >
                {item.step}
              </div>
              <h3
                style={{
                  fontFamily: "'Syncopate', sans-serif",
                  fontSize: 13,
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  color: '#DFFF00',
                  marginBottom: '0.75rem',
                }}
              >
                {item.title}
              </h3>
              <p style={{ color: '#777', fontSize: 14, lineHeight: 1.7 }}>{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Final CTA ──────────────────────────────────────────────────────── */}
      <section className="py-32 px-6 text-center relative overflow-hidden">
        <Orbs />
        <div className="reveal relative z-10">
          <h2
            className="text-3d"
            style={{
              fontFamily: "'Syncopate', sans-serif",
              fontSize: 'clamp(2.5rem, 7vw, 6rem)',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '-0.03em',
              color: '#DFFF00',
              marginBottom: '1.5rem',
            }}
          >
            STAY SATARK.
          </h2>
          <p style={{ color: '#666', fontSize: 16, marginBottom: '2.5rem' }}>
            Join thousands of Indians who analyse suspicious messages before clicking.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button
              onClick={handleGoogleSignIn}
              className="btn-acid transition-all duration-200 flex items-center justify-center gap-3"
              style={{ 
                fontSize: 14, 
                padding: '0.8rem 1.5rem', 
                cursor: 'pointer',
                minWidth: 240,
                borderRadius: 0
              }}
            >
              <GoogleIcon size={18} />
              Continue with Google
            </button>
          </div>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────────────────────────── */}
      <footer
        className="px-6 md:px-12 py-10 flex flex-col md:flex-row items-center justify-between gap-4"
        style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
      >
        <div className="flex items-center gap-3">
          <div style={{ width: 28, height: 28, background: 'rgba(223,255,0,0.08)', border: '1px solid rgba(223,255,0,0.25)', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.35C17.25 22.15 21 17.25 21 12V7L12 2z" fill="#DFFF00" opacity="0.9"/>
            </svg>
          </div>
          <span style={{ fontFamily: "'Syncopate', sans-serif", fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#555' }}>
            SATARK AI
          </span>
        </div>

        <p style={{ color: '#444', fontSize: 12 }}>
          Built with ❤️ for India · Powered by Groq · Open Source
        </p>

        <p style={{ color: '#333', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}>
          v1.0.0 · {new Date().getFullYear()}
        </p>
      </footer>
    </div>
  )
}
