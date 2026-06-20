import { Layers, MapPin, Search, Brain, Zap, ShieldCheck } from 'lucide-react'

const features = [
  {
    icon: Layers,
    title: "Multi-Modal Analysis",
    description: "Paste an SMS, drop in a URL, or upload a WhatsApp screenshot. Satark AI reads all three — using OCR to pull text straight out of images."
  },
  {
    icon: MapPin,
    title: "Built Exclusively for India",
    description: "Trained on real Indian scam patterns — fake SBI KYC links, IRCTC ticket frauds, Aadhaar update scams. Understands English, Hindi, and Hinglish natively."
  },
  {
    icon: Search,
    title: "Deep URL Scanning",
    description: "Unwinds shortened links, detects typosquatted domains like 'hdfc-bank-update.com', and checks live phishing databases — not just surface-level pattern matching."
  },
  {
    icon: Brain,
    title: "Explainable AI, Not a Black Box",
    description: "Every verdict comes with the exact words and patterns that triggered it, plus a plain-language explanation of why — no unexplained 'spam' labels."
  },
  {
    icon: Zap,
    title: "Lightning-Fast Detection",
    description: "Powered by Groq's LPU architecture, the full pipeline — database check, URL scan, ML classification, AI explanation — completes in under half a second."
  },
  {
    icon: ShieldCheck,
    title: "ArmorIQ Security Layer",
    description: "Every request passes through custom middleware that sanitizes input and blocks prompt-injection attempts — so attackers can't trick the AI into marking a malicious link as safe."
  }
]

export default function FeatureShowcase() {
  return (
    <div className="w-full py-6 md:py-10 animate-fade-in">
      <div className="text-center mb-10">
        <div style={{ fontSize: 10, fontFamily: "'Outfit', sans-serif", fontWeight: 700, letterSpacing: '0.12em', color: '#DFFF00', marginBottom: '0.75rem', textTransform: 'uppercase' }}>
          WHY SATARK AI
        </div>
        <h2 style={{ fontFamily: "'Syncopate', sans-serif", fontSize: 'clamp(1.5rem, 3vw, 2rem)', fontWeight: 700, color: '#fff', lineHeight: 1.2 }}>
          One Platform. Every Scam Vector.
        </h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {features.map((feature, idx) => (
          <div 
            key={idx} 
            className="flex flex-col border transition-colors duration-300"
            style={{ 
              background: 'rgba(255,255,255,0.03)', 
              backdropFilter: 'blur(10px)', 
              borderColor: 'rgba(255,255,255,0.1)', 
              borderRadius: '1rem', 
              padding: '1.5rem' 
            }}
            onMouseEnter={e => e.currentTarget.style.borderColor = 'rgba(223,255,0,0.4)'}
            onMouseLeave={e => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)'}
          >
            <div 
              className="flex items-center justify-center mb-4 shrink-0"
              style={{ width: 40, height: 40, borderRadius: '0.5rem', background: 'rgba(223,255,0,0.1)' }}
            >
              <feature.icon size={20} style={{ color: '#DFFF00' }} />
            </div>
            <h3 style={{ color: '#fff', fontWeight: 700, fontSize: '1rem', marginBottom: '0.5rem', fontFamily: "'Outfit', sans-serif" }}>
              {feature.title}
            </h3>
            <p style={{ color: '#9CA3AF', fontSize: '0.875rem', lineHeight: 1.6, fontFamily: "'Outfit', sans-serif" }}>
              {feature.description}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
