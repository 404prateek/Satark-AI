-- =============================================================================
-- Satark AI — Demo Seed Data
-- Run AFTER init.sql: psql -U postgres -d satark_ai -f database/seed.sql
--
-- Demo user: email=demo@satark.ai  password=demo123 (bcrypt, 12 rounds)
-- The bcrypt hash below was generated with Python:
--   from passlib.hash import bcrypt
--   bcrypt.hash("demo123", rounds=12)
-- =============================================================================

BEGIN;

-- =============================================================================
-- 1. DEMO USER
-- =============================================================================
INSERT INTO users (
    id, email, username, password_hash, role, is_active, created_at, updated_at
) VALUES (
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'demo@satark.ai',
    'demo_user',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TiIRmkO1a1kYOvSzMoEG0V5tDEYS',
    'analyst',
    TRUE,
    NOW() - INTERVAL '30 days',
    NOW() - INTERVAL '1 hour'
) ON CONFLICT (email) DO NOTHING;


-- =============================================================================
-- 2. DEMO SCANS (10 rows: mix of SAFE / SUSPICIOUS / PHISHING)
-- =============================================================================

-- ── Scan 1: PHISHING — SBI fake link via SMS ─────────────────────────────────
INSERT INTO scans (
    id, user_id, input_type, raw_input, language, verdict, risk_score,
    confidence, model_version, shap_features, explanation, groq_model, created_at
) VALUES (
    gen_random_uuid(),
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'message',
    'URGENT: Your SBI account has been suspended. Verify immediately at http://sbi-secure-verify.xyz or lose access permanently.',
    'en',
    'PHISHING',
    94.7,
    0.97,
    'v1.0',
    '[{"feature":"sbi-secure","value":0.412},{"feature":"suspended","value":0.289},{"feature":"verify immediately","value":0.201},{"feature":".xyz","value":0.187},{"feature":"URGENT","value":0.154}]',
    'This message exhibits classic phishing characteristics. The domain "sbi-secure-verify.xyz" is a typosquat impersonating the State Bank of India. The use of urgency ("URGENT", "suspended", "permanently") is a hallmark social engineering tactic to bypass rational evaluation. The .xyz TLD is heavily abused for phishing. Do NOT click the link.',
    'llama-3.1-70b-versatile',
    NOW() - INTERVAL '2 days'
),

-- ── Scan 2: PHISHING — HDFC KYC scam ─────────────────────────────────────────
(
    gen_random_uuid(),
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'message',
    'Dear HDFC Customer, Your KYC is incomplete. Update within 24 hours at http://hdfc-kyc-update.ml to avoid account closure.',
    'en',
    'PHISHING',
    91.2,
    0.94,
    'v1.0',
    '[{"feature":"hdfc-kyc","value":0.387},{"feature":"account closure","value":0.276},{"feature":"24 hours","value":0.198},{"feature":".ml","value":0.165},{"feature":"KYC","value":0.143}]',
    'High-confidence phishing. ".ml" is a free TLD used almost exclusively for phishing. The message impersonates HDFC Bank with a false KYC deadline — Indian banks never send KYC update links via SMS. The domain was registered 3 days ago.',
    'llama-3.1-70b-versatile',
    NOW() - INTERVAL '5 days'
),

-- ── Scan 3: PHISHING — Paytm prize scam ──────────────────────────────────────
(
    gen_random_uuid(),
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'message',
    'Congratulations! You have won Rs 1,00,000 in Paytm Diwali Lucky Draw. Claim your prize: http://paytm-prize-claim.tk/win',
    'en',
    'PHISHING',
    88.5,
    0.91,
    'v1.0',
    '[{"feature":"paytm-prize","value":0.356},{"feature":"won Rs","value":0.312},{"feature":"Lucky Draw","value":0.245},{"feature":".tk","value":0.201},{"feature":"Claim","value":0.178}]',
    'Prize-baiting phishing targeting Paytm users. The ".tk" TLD (Tokelau) has been heavily abused for free phishing domains. No legitimate payment platform distributes cash prizes via SMS with external claim links.',
    'llama-3.1-70b-versatile',
    NOW() - INTERVAL '1 day'
),

-- ── Scan 4: PHISHING — Aadhaar suspension ────────────────────────────────────
(
    gen_random_uuid(),
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'url',
    'http://aadhaar-uidai-verify.pw/update-details',
    'en',
    'PHISHING',
    96.1,
    0.98,
    'v1.0',
    '[{"feature":"aadhaar-uidai","value":0.445},{"feature":".pw","value":0.223},{"feature":"update-details","value":0.189},{"feature":"domain_age_3d","value":0.167}]',
    'Confirmed phishing URL impersonating UIDAI (Aadhaar). The ".pw" TLD is in the top 5 most-abused free TLDs. The domain "aadhaar-uidai-verify.pw" was registered 3 days ago. The official UIDAI portal is uidai.gov.in — only .gov.in domains are legitimate.',
    'llama-3.1-70b-versatile',
    NOW() - INTERVAL '3 hours'
),

-- ── Scan 5: SUSPICIOUS — Unknown shortener ────────────────────────────────────
(
    gen_random_uuid(),
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'url',
    'https://bit.ly/3xK9mPq',
    'en',
    'SUSPICIOUS',
    58.3,
    0.72,
    'v1.0',
    '[{"feature":"bit.ly","value":0.231},{"feature":"redirect_chain_3","value":0.198},{"feature":"final_domain_age_12d","value":0.145}]',
    'URL shortener detected with 3 redirect hops. The final destination is a 12-day-old domain, which is a moderate risk indicator. While bit.ly is itself a legitimate service, the redirect chain pattern and young destination domain warrant caution. Verify the destination independently before clicking.',
    'llama-3.1-70b-versatile',
    NOW() - INTERVAL '6 hours'
),

-- ── Scan 6: SUSPICIOUS — Hinglish scam attempt ───────────────────────────────
(
    gen_random_uuid(),
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'message',
    'Aapka IRCTC account mein problem hai. Abhi verify karein: http://irctc-help.top',
    'hinglish',
    'SUSPICIOUS',
    67.4,
    0.81,
    'v1.0',
    '[{"feature":"irctc-help","value":0.298},{"feature":".top","value":0.187},{"feature":"verify karein","value":0.156},{"feature":"problem hai","value":0.098}]',
    'Hinglish-language message impersonating IRCTC. The ".top" TLD is frequently abused for phishing. The urgency framing in Hinglish ("Abhi verify karein") mimics IRCTC support language. Official IRCTC communications come from @irctc.co.in email addresses, never via SMS with external links.',
    'llama-3.1-70b-versatile',
    NOW() - INTERVAL '12 hours'
),

-- ── Scan 7: SUSPICIOUS — Low-confidence prize SMS ─────────────────────────────
(
    gen_random_uuid(),
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'message',
    'You have been selected for a special offer. Visit our website for details.',
    'en',
    'SUSPICIOUS',
    42.1,
    0.58,
    'v1.0',
    '[{"feature":"selected for","value":0.156},{"feature":"special offer","value":0.134},{"feature":"our website","value":0.089}]',
    'Mildly suspicious message using generic prize-bait language ("selected", "special offer") without a specific URL. Could be spam or a low-effort phishing probe. No brand impersonation detected. Treat with caution but not high confidence.',
    'llama-3.1-70b-versatile',
    NOW() - INTERVAL '18 hours'
),

-- ── Scan 8: SAFE — OTP message ────────────────────────────────────────────────
(
    gen_random_uuid(),
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'message',
    'Your SBI OTP is 847291 for transaction of Rs 1,500 at Amazon. Valid for 10 minutes. Do not share this OTP with anyone.',
    'en',
    'SAFE',
    4.2,
    0.96,
    'v1.0',
    '[{"feature":"Do not share","value":-0.312},{"feature":"OTP is","value":-0.278},{"feature":"Valid for 10","value":-0.198},{"feature":"transaction","value":-0.145}]',
    'This is a legitimate bank OTP message. Key safe indicators: no external URLs, explicit instruction not to share, standard OTP format from SBI, and transaction context. The negative SHAP values confirm all features push strongly toward the SAFE classification.',
    'llama-3.1-70b-versatile',
    NOW() - INTERVAL '4 days'
),

-- ── Scan 9: SAFE — IRCTC booking confirmation ─────────────────────────────────
(
    gen_random_uuid(),
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'message',
    'IRCTC: Your booking is confirmed. PNR 4512387690, Train 12301 Rajdhani Exp, New Delhi to Mumbai, 20-Jun. Journey Date: 20-Jun-2024.',
    'en',
    'SAFE',
    2.1,
    0.98,
    'v1.0',
    '[{"feature":"booking is confirmed","value":-0.389},{"feature":"PNR","value":-0.301},{"feature":"Rajdhani Exp","value":-0.267},{"feature":"Journey Date","value":-0.198}]',
    'Legitimate IRCTC booking confirmation. Contains standard PNR, train name, route, and date information. No external links, no urgency language, no requests for personal information. All SHAP features confidently push toward SAFE.',
    'llama-3.1-70b-versatile',
    NOW() - INTERVAL '7 days'
),

-- ── Scan 10: SAFE — HDFC credit card statement ───────────────────────────────
(
    gen_random_uuid(),
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'message',
    'Dear Customer, your HDFC Bank Credit Card statement for May 2024 is now available. Log in to NetBanking at netbanking.hdfcbank.com to view.',
    'en',
    'SAFE',
    8.7,
    0.93,
    'v1.0',
    '[{"feature":"hdfcbank.com","value":-0.267},{"feature":"statement for May","value":-0.234},{"feature":"NetBanking","value":-0.198},{"feature":"Credit Card statement","value":-0.167}]',
    'Legitimate HDFC Bank statement notification. The URL references the official "hdfcbank.com" domain (not a lookalike). The message is informational with no urgency or fear tactics. Recommends using NetBanking through the official domain, not an unfamiliar link.',
    'llama-3.1-70b-versatile',
    NOW() - INTERVAL '10 days'
);


-- =============================================================================
-- 3. SAMPLE THREAT REPORT for the top PHISHING scan
-- =============================================================================
INSERT INTO threat_reports (
    id, scan_id, user_id, severity, category, title, description,
    affected_brand, malicious_url, confidence, is_verified, is_public, auto_generated, created_at
)
SELECT
    gen_random_uuid(),
    s.id,
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'CRITICAL',
    'brand_impersonation',
    'SBI Phishing via Fake SMS — .xyz Domain',
    'Attacker registered sbi-secure-verify.xyz 3 days before this scan and is distributing phishing SMS targeting SBI customers across India. Messages use account suspension threats to induce urgency.',
    'SBI',
    'http://sbi-secure-verify.xyz',
    0.97,
    FALSE,
    TRUE,
    TRUE,
    NOW() - INTERVAL '2 days'
FROM scans s
WHERE s.raw_input LIKE '%sbi-secure-verify.xyz%'
LIMIT 1;


-- =============================================================================
-- 4. SAMPLE AUDIT LOGS
-- =============================================================================
INSERT INTO audit_logs (
    id, user_id, event_type, description, ip_address, created_at
) VALUES
(
    gen_random_uuid(),
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'LOGIN_SUCCESS',
    'User demo@satark.ai authenticated successfully via password.',
    '103.26.75.12',
    NOW() - INTERVAL '1 hour'
),
(
    gen_random_uuid(),
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'SCAN_CREATED',
    'New scan submitted: input_type=message verdict=PHISHING risk_score=94.7',
    '103.26.75.12',
    NOW() - INTERVAL '2 days'
);

COMMIT;
