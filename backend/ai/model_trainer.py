"""
Phishing classifier trainer for Satark AI.

Dataset: UCI SMS Spam Collection (public domain)
  URL: https://archive.ics.uci.edu/ml/machine-learning-databases/00228/smsspamcollection.zip

Pipeline:
  TfidfVectorizer(max_features=10000, ngram_range=(1,2), analyzer='char_wb')
    → MultinomialNB(alpha=0.1)

Character-level n-grams (char_wb) are chosen over word n-grams because:
  - They are robust to obfuscated spellings used by phishers (e.g. "Fr33", "cl1ck")
  - They capture sub-word patterns: "http://" as a bigram fragment
  - They gracefully handle Hindi/Hinglish without a language-specific tokeniser

Run this script directly to train and save the model:
  python -m backend.ai.model_trainer

The script also runs an end-to-end SHAP test on three sample messages.
"""

import io
import logging
import os
import urllib.request
import zipfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = _REPO_ROOT / "data"
MODEL_PATH = DATA_DIR / "model.pkl"
DATASET_PATH = DATA_DIR / "sms_spam.tsv"

UCI_URL = (
    "https://archive.ics.uci.edu/ml/machine-learning-databases"
    "/00228/smsspamcollection.zip"
)

# ── Extra Indian phishing training samples ────────────────────────────────────
# Augment the English-only UCI corpus with India-specific phishing patterns.
INDIAN_PHISHING_SAMPLES = [
    ("spam", "Your SBI account has been blocked. Verify at http://sbi-secure.xyz immediately."),
    ("spam", "URGENT: HDFC Bank: Your account will be closed! Click http://hdfc-login.ml now."),
    ("spam", "Congratulations! You won Rs 50000 in IRCTC lucky draw. Claim: http://irctc-prize.tk"),
    ("spam", "Dear ICICI customer, your KYC is pending. Update: http://icici-kyc.ga/update"),
    ("spam", "Aapka Aadhaar card suspend ho gaya hai. Verify karein: http://uidai-verify.pw"),
    ("spam", "Paytm: Rs 2000 cashback milega aapko. Link: http://paytm-cashback.click"),
    ("spam", "Income Tax refund pending Rs 8420. Claim now: http://incometax-refund.top"),
    ("spam", "Dear user, your UPI PIN will expire. Reset: http://npci-upi.link/reset"),
    ("spam", "BHIM App: Suspicious login detected. Secure your account: http://bhim-secure.xyz"),
    ("spam", "Free Jio recharge Rs 399 for all users! Hurry: http://jio-offer.ml/free"),
    ("ham", "Your OTP for SBI netbanking is 834721. Do not share this with anyone."),
    ("ham", "Dear customer, your HDFC credit card statement for May is ready. Login to netbanking."),
    ("ham", "IRCTC: Your ticket PNR 4567890123 is confirmed. Train 12301 departs 06:15."),
    ("ham", "Aapka ICICI account mein Rs 5000 credit hua hai."),
    ("ham", "Your Paytm wallet has been credited with Rs 150 cashback on your last transaction."),
]


def _download_dataset() -> None:
    """Downloads and extracts the UCI SMS Spam dataset if not already present."""
    if DATASET_PATH.exists():
        logger.info(f"Dataset already exists at {DATASET_PATH}")
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Downloading UCI SMS Spam Collection from {UCI_URL} …")

    with urllib.request.urlopen(UCI_URL, timeout=30) as response:
        zip_bytes = response.read()

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        with zf.open("SMSSpamCollection") as f:
            raw = f.read().decode("utf-8", errors="replace")

    with open(DATASET_PATH, "w", encoding="utf-8") as out:
        out.write(raw)

    logger.info(f"Dataset saved to {DATASET_PATH}")


def _load_dataset() -> pd.DataFrame:
    """Loads the TSV dataset and returns a labelled DataFrame."""
    _download_dataset()
    df = pd.read_csv(
        DATASET_PATH,
        sep="\t",
        header=None,
        names=["label", "text"],
        encoding="utf-8",
    )
    df["label"] = df["label"].str.strip()
    df = df.dropna(subset=["text", "label"])
    return df


def _augment_with_indian_samples(df: pd.DataFrame) -> pd.DataFrame:
    """Appends India-specific phishing and legitimate SMS samples."""
    extra = pd.DataFrame(INDIAN_PHISHING_SAMPLES, columns=["label", "text"])
    # Oversample Indian phishing messages (×5) to prevent UCI majority-class bias
    extra_spam = extra[extra["label"] == "spam"]
    extra_ham = extra[extra["label"] == "ham"]
    augmented = pd.concat(
        [df, extra_ham, pd.concat([extra_spam] * 5, ignore_index=True)],
        ignore_index=True,
    )
    return augmented.sample(frac=1, random_state=42).reset_index(drop=True)


def normalize_numbers(text: str) -> str:
    import re
    # Convert "15,000" or "₹15,000" or "Rs 15,000" into a clean token
    text = re.sub(r'[₹]|Rs\.?\s*', 'RUPEE_ ', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d{1,3}(?:,\d{2,3})+)', lambda m: 'AMOUNT_' + 
                  ('LARGE' if int(m.group(1).replace(',','')) >= 10000 
                   else 'MEDIUM'), text)
    text = re.sub(r'\b\d{10}\b', 'PHONE_NUMBER', text)  # 10-digit Indian numbers
    text = re.sub(r'\b\d{4,9}\b', 'NUMBER_TOKEN', text)  # other multi-digit numbers
    return text

def preprocess_for_tokens(text: str) -> str:
    import re
    text = normalize_numbers(text)
    # Split URLs into domain + path words, keep them readable
    text = re.sub(r'https?://', ' ', text)
    text = re.sub(r'[/?&=]', ' ', text)        # break up URL structure
    text = re.sub(r'([a-z])-([a-z])', r'\1 \2', text)  # "hdfc-verify" -> "hdfc verify"
    text = re.sub(r'\.(com|xyz|in|co|tk|ml)\b', r' DOT_\1', text)  # flag suspicious TLDs as a token
    return text

def build_pipeline() -> Pipeline:
    """Returns the untrained sklearn Pipeline."""
    return Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    max_features=5000,
                    ngram_range=(1, 2),
                    analyzer="word",
                    token_pattern=r'(?u)\b\w[\w\-\.]*\b',
                    stop_words=None,
                    preprocessor=preprocess_for_tokens,
                    strip_accents="unicode",
                    sublinear_tf=True,      # log(1+tf) dampens high-freq terms
                ),
            ),
            (
                "nb",
                MultinomialNB(alpha=0.1),  # low alpha = less smoothing = sharper decision
            ),
        ]
    )


def train() -> Pipeline:
    """
    Full training routine:
      1. Download + augment dataset.
      2. Train the Pipeline.
      3. Evaluate on held-out test set.
      4. Save to disk with joblib.

    Returns:
        The fitted Pipeline.
    """
    logger.info("=== Satark AI — Phishing Classifier Training ===")

    # 1. Data
    df = _load_dataset()
    df = _augment_with_indian_samples(df)
    logger.info(f"Total samples: {len(df)}  (spam={sum(df.label=='spam')}, ham={sum(df.label=='ham')})")

    X = df["text"].tolist()
    # Binary labels: 1 = phishing/spam, 0 = safe/ham
    y = (df["label"] == "spam").astype(int).tolist()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # 2. Train
    logger.info("Training TF-IDF + MultinomialNB pipeline …")
    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train)

    # 3. Evaluate
    y_pred = pipeline.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    logger.info(f"\nAccuracy: {acc:.4f}")
    logger.info("\n" + classification_report(y_test, y_pred, target_names=["Safe", "Phishing"]))

    # 4. Save
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    logger.info(f"Model saved → {MODEL_PATH}")

    return pipeline


# ── SHAP test ─────────────────────────────────────────────────────────────────

def _run_shap_test(pipeline: Pipeline) -> None:
    """
    Runs the SHAP explainer on three representative messages and prints
    the top features driving each prediction.
    """
    from backend.ai.shap_explainer import SHAPExplainer

    test_cases = [
        (
            "PHISHING (SBI typosquat)",
            "Your SBI account is blocked! Verify now at http://sbi-secure-login.xyz or lose access."
        ),
        (
            "PHISHING (prize scam)",
            "Congratulations! You've won Rs 1,00,000 in Paytm lucky draw. Click http://paytm-prize.tk to claim."
        ),
        (
            "SAFE (IRCTC ticket)",
            "IRCTC: Booking confirmed. PNR 4512387690, Train 12301 New Delhi→Mumbai, Departs 06:15."
        ),
        (
            "PHISHING (Job Scam)",
            "Dear Candidate, You have been selected for Data Entry job. Work from home. Earn Rs 15,000/month. WhatsApp CV: wa.me/919988776655"
        ),
    ]

    explainer = SHAPExplainer(pipeline)

    print("\n" + "=" * 70)
    print("SHAP FEATURE ATTRIBUTION TEST")
    print("=" * 70)

    for label, text in test_cases:
        pred_proba = pipeline.predict_proba([text])[0]
        pred_label = "PHISHING" if pipeline.predict([text])[0] == 1 else "SAFE"
        shap_features = explainer.explain(text, top_n=8)

        print(f"\n[{label}]")
        print(f"  Text    : {text[:80]}…" if len(text) > 80 else f"  Text    : {text}")
        print(f"  Predict : {pred_label}  (P_phishing={pred_proba[1]:.4f})")
        print("  Top SHAP features:")
        if shap_features:
            for feat, val in shap_features.items():
                direction = "→ phishing" if val > 0 else "→ safe    "
                bar = "█" * min(int(abs(val) * 40), 20)
                print(f"    {feat!r:30s}  {val:+.4f}  {direction}  {bar}")
        else:
            print("    (no discriminative features found)")

    print("\n" + "=" * 70)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    fitted_pipeline = train()
    _run_shap_test(fitted_pipeline)
