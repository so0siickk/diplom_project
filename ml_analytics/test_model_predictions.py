"""
test_model_predictions.py
=========================
Sanity-check for the trained ML model (ai_module/model.pkl).

Generates mock feature vectors for 4 student archetypes and verifies
that predicted completion probabilities are in the expected direction.

Run with:
    code/.venv/Scripts/python.exe ml_analytics/test_model_predictions.py
"""

import os
import sys

import joblib
import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODEL_PATH = os.path.join(_ROOT, 'ai_module', 'model.pkl')
_META_PATH  = os.path.join(_ROOT, 'ai_module', 'meta.json')

# Feature order must match FEATURE_COLS in analytics/services.py
FEATURE_COLS = [
    'lesson_order',           # 0
    'module_order',           # 1
    'lesson_position_ratio',  # 2
    'prev_avg_score',         # 3
    'prev_avg_time',          # 4
    'prev_avg_attempts',      # 5
    'prev_completion_rate',   # 6
    'prev_lessons_done',      # 7
    'time_spent_seconds',     # 8
    'attempt_count',          # 9
    'quiz_taken',             # 10  NEW: 1=attempted, 0=never opened
    'quiz_score',             # 11  0.0 when quiz_taken=0
]

# ---------------------------------------------------------------------------
# Mock students: each row is one (student, lesson) prediction request
# ---------------------------------------------------------------------------
# Format: [lesson_order, module_order, lesson_position_ratio,
#          prev_avg_score, prev_avg_time, prev_avg_attempts,
#          prev_completion_rate, prev_lessons_done,
#          time_spent_seconds, attempt_count, quiz_score]

# Format: [lesson_order, module_order, lesson_position_ratio,
#          prev_avg_score, prev_avg_time, prev_avg_attempts,
#          prev_completion_rate, prev_lessons_done,
#          time_spent_seconds, attempt_count,
#          quiz_taken,   <- NEW feature #10
#          quiz_score]   <- feature #11 (0.0 when quiz_taken=0)

STUDENTS = [
    {
        "name": "Top student (quiz taken, high score)",
        "expected": "HIGH (>= 0.72)",
        "min_prob": 0.72,
        "features": [
            2,      # lesson_order
            1,      # module_order
            0.10,   # position
            0.92,   # prev_avg_score
            420,    # prev_avg_time
            1.1,    # prev_avg_attempts
            1.00,   # prev_completion_rate
            5,      # prev_lessons_done
            380,    # time_spent_seconds
            1,      # attempt_count
            1,      # quiz_taken=1
            0.95,   # quiz_score
        ],
    },
    {
        "name": "High scorer dropout (quiz taken, low completion)",
        "expected": "LOW (<= 0.45)",
        "max_prob": 0.45,
        "features": [
            4,
            3,
            0.60,   # mid-course
            0.82,   # great history scores
            380,
            1.3,
            0.30,   # BUT: only 30% completion rate despite good scores
            2,      # few lessons actually done
            350,
            2,
            1,      # quiz_taken=1
            0.88,   # high quiz score
        ],
    },
    {
        "name": "Low scorer persister (quiz not taken, completes anyway)",
        "expected": "MEDIUM (0.25 - 0.80)",
        "min_prob": 0.25,
        "max_prob": 0.80,
        "features": [
            5,
            2,
            0.50,
            0.35,   # poor history scores
            2100,   # spends a lot of time
            5.0,    # many attempts
            0.82,   # BUT: high completion rate despite bad scores
            7,
            2400,
            6,
            0,      # quiz_taken=0 — never opened the quiz
            0.0,    # quiz_score=0 (not taken)
        ],
    },
    {
        "name": "Struggling student (no quiz, disengaged)",
        "expected": "LOW (<= 0.40)",
        "max_prob": 0.40,
        "features": [
            5,
            3,
            0.65,
            0.28,   # poor history
            1800,
            5.2,
            0.38,   # low completion rate
            3,
            2100,
            6,
            0,      # quiz_taken=0
            0.0,
        ],
    },
    {
        "name": "New student (cold start, lesson 1)",
        "expected": "NEUTRAL (0.35 - 0.70)",
        "min_prob": 0.35,
        "max_prob": 0.70,
        "features": [
            1, 1, 0.05,
            0.0, 0.0, 1.0, 0.0, 0,
            0, 1,
            0,      # quiz_taken=0
            0.0,
        ],
    },
]

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not os.path.exists(_MODEL_PATH):
        print(f"[ERROR] Model not found at {_MODEL_PATH}")
        print("  Run: code/.venv/Scripts/python.exe ml_analytics/train.py --no-grid")
        sys.exit(1)

    model = joblib.load(_MODEL_PATH)
    print(f"Model loaded: {_MODEL_PATH}")

    # Print meta if available
    if os.path.exists(_META_PATH):
        import json
        with open(_META_PATH, encoding='utf-8') as f:
            meta = json.load(f)
        print(f"Trained at:   {meta.get('trained_at', 'unknown')[:19]}")
        print(f"ROC-AUC:      {meta.get('metrics', {}).get('roc_auc', 'N/A')}")
    print()

    X = np.array([s["features"] for s in STUDENTS], dtype=np.float64)
    probs = model.predict_proba(X)[:, 1]  # P(completed=1)

    print("=" * 70)
    print(f"  {'Student archetype':<35} {'P(complete)':>11}  {'Expected':>20}")
    print("=" * 70)

    passed = 0
    failed = 0

    for student, prob in zip(STUDENTS, probs):
        risk = 1.0 - prob
        min_p = student.get("min_prob", 0.0)
        max_p = student.get("max_prob", 1.0)
        ok = min_p <= prob <= max_p
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1

        print(
            f"  {student['name']:<35} "
            f"  p={prob:.4f}  risk={risk:.4f}  "
            f"[{status}]  {student['expected']}"
        )

    print("=" * 70)
    print(f"\nResults: {passed}/{len(STUDENTS)} passed, {failed} failed")

    # Feature importance via permutation (works with HistGradientBoostingClassifier)
    from sklearn.inspection import permutation_importance
    print()
    print("-" * 50)
    print("  Top-5 feature importances (permutation, ROC-AUC):")
    print("-" * 50)
    perm = permutation_importance(
        model, X, [s.get("min_prob", 0) > 0.5 for s in STUDENTS],
        n_repeats=5, scoring='roc_auc', random_state=42,
    )
    importances = sorted(
        zip(FEATURE_COLS, perm.importances_mean),
        key=lambda x: x[1], reverse=True,
    )
    for feat, imp in importances[:5]:
        bar = '#' * max(0, int(imp * 200))
        print(f"  {feat:<28} {imp:+.4f}  {bar}")

    # Sensitivity: quiz_taken effect (most important new feature)
    print()
    print("-" * 50)
    print("  Sensitivity: quiz_taken effect (struggling student base)")
    print("-" * 50)
    base = np.array(STUDENTS[3]["features"], dtype=np.float64).reshape(1, -1)
    for taken, score in [(0, 0.0), (1, 0.20), (1, 0.50), (1, 0.75), (1, 0.95)]:
        row = base.copy()
        row[0, 10] = taken   # quiz_taken index
        row[0, 11] = score   # quiz_score index
        p = model.predict_proba(row)[0, 1]
        bar = '#' * int(p * 30)
        label = f"taken={taken}, score={score:.2f}"
        print(f"  {label:<25} -> P(complete)={p:.4f}  {bar}")

    print()
    if failed == 0:
        print("All checks passed. Model predictions are directionally correct.")
    else:
        print(f"WARNING: {failed} check(s) failed. Review model or training data.")


if __name__ == "__main__":
    main()
