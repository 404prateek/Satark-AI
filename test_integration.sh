#!/bin/bash
set -u

echo "============================================================"
echo "🛡️ SATARK AI — INTEGRATION TEST SUITE"
echo "============================================================"

FAILS=0

# Helper to print colored status
function print_status() {
    local check_name="$1"
    local status="$2"
    if [ "$status" == "PASS" ]; then
        echo -e "\033[32m[PASS]\033[0m $check_name"
    else
        echo -e "\033[31m[FAIL]\033[0m $check_name"
        FAILS=$((FAILS + 1))
    fi
}

echo -n "1. Checking if model.pkl exists... "
if [ -f "data/model.pkl" ] || [ -f "backend/data/model.pkl" ]; then
    print_status "model.pkl found" "PASS"
else
    print_status "model.pkl NOT found" "FAIL"
fi

echo -n "2. Checking backend health check... "
HEALTH=$(curl -s http://localhost:8000/health | grep -i '"status": *"ok"')
if [ -n "$HEALTH" ]; then
    print_status "Backend is running (200 OK)" "PASS"
else
    print_status "Backend health check failed" "FAIL"
fi

echo -n "3. Logging in as demo@satark.ai... "
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"demo@satark.ai","password":"demo123"}' | grep -oP '"access_token":"\K[^"]+')

if [ -n "$TOKEN" ]; then
    print_status "Login successful, token acquired" "PASS"
else
    print_status "Login failed" "FAIL"
fi

echo "4. Testing Phishing Analysis (Hindi KYC Scam)..."
RESPONSE_PHISHING=$(curl -s -X POST http://localhost:8000/api/v1/analyze/message \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"message":"प्रिय ग्राहक, आपका SBI खाता KYC सत्यापन के लिए अनुरोध किया गया है। अभी लिंक पर क्लिक करें: bit.ly/sbi-kyc99 अन्यथा आपका खाता 24 घंटे में बंद हो जाएगा।"}')

VERDICT_PHISHING=$(echo "$RESPONSE_PHISHING" | grep -oP '"verdict":"\K[^"]+')
RISK_PHISHING=$(echo "$RESPONSE_PHISHING" | grep -oP '"risk_score":\K[0-9]+' | head -n 1)

echo "Response Preview:"
echo "$RESPONSE_PHISHING" | head -c 300
echo "..."

if [ "$VERDICT_PHISHING" == "PHISHING" ] || [ "$VERDICT_PHISHING" == "SUSPICIOUS" ]; then
    if [ "$RISK_PHISHING" -ge 50 ]; then
        print_status "Phishing detected with score >= 50" "PASS"
    else
        print_status "Score too low ($RISK_PHISHING)" "FAIL"
    fi
else
    print_status "Did not detect as PHISHING/SUSPICIOUS (Verdict: $VERDICT_PHISHING)" "FAIL"
fi

echo "5. Testing Safe Analysis (OTP)..."
RESPONSE_SAFE=$(curl -s -X POST http://localhost:8000/api/v1/analyze/message \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"message":"Your OTP is 482917, valid for 10 minutes. Do not share with anyone."}')

VERDICT_SAFE=$(echo "$RESPONSE_SAFE" | grep -oP '"verdict":"\K[^"]+')
RISK_SAFE=$(echo "$RESPONSE_SAFE" | grep -oP '"risk_score":\K[0-9]+' | head -n 1)

if [ "$VERDICT_SAFE" == "SAFE" ] && [ "$RISK_SAFE" -lt 40 ]; then
    print_status "Safe message verified (Score: $RISK_SAFE)" "PASS"
else
    print_status "Safe message failed (Verdict: $VERDICT_SAFE, Score: $RISK_SAFE)" "FAIL"
fi

echo -n "6. Checking Scan History... "
HISTORY_RESPONSE=$(curl -s -X GET "http://localhost:8000/api/v1/history?limit=10" \
     -H "Authorization: Bearer $TOKEN")

HISTORY_TOTAL=$(echo "$HISTORY_RESPONSE" | grep -oP '"total":\K[0-9]+')

if [ -n "$HISTORY_TOTAL" ] && [ "$HISTORY_TOTAL" -ge 2 ]; then
    print_status "History contains >= 2 items (Total: $HISTORY_TOTAL)" "PASS"
else
    print_status "History check failed" "FAIL"
fi

echo "============================================================"
if [ $FAILS -eq 0 ]; then
    echo -e "\033[32mALL CHECKS PASSED!\033[0m Ready for demo."
    exit 0
else
    echo -e "\033[31m$FAILS CHECK(S) FAILED.\033[0m"
    exit 1
fi
