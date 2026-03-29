"""
evaluate.py
===========
Загружает обученную модель из ai_module/model.pkl и выводит полный
отчёт по метрикам на свежей выборке из Django ORM.

Запуск:
    python ml_analytics/evaluate.py
    python ml_analytics/evaluate.py --test-size 0.3
"""

import argparse
import json
import os
import sys

import joblib
import numpy as np
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    classification_report,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import StratifiedShuffleSplit

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CODE_DIR = os.path.join(_ROOT, 'code')
sys.path.insert(0, os.path.join(_ROOT, 'ml_analytics'))
sys.path.insert(0, _CODE_DIR)
os.chdir(_CODE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from dataset_builder import FEATURE_COLS, TARGET_COL, build_dataset  # noqa: E402

MODEL_PATH = os.path.join(_ROOT, 'ai_module', 'model.pkl')
META_PATH = os.path.join(_ROOT, 'ai_module', 'meta.json')


def evaluate(test_size: float = 0.20) -> None:
    # --- Загрузка модели ---
    if not os.path.exists(MODEL_PATH):
        print(f'[ERROR] Модель не найдена: {MODEL_PATH}')
        print('Запустите: python ml_analytics/train.py')
        sys.exit(1)

    model = joblib.load(MODEL_PATH)

    with open(META_PATH, encoding='utf-8') as f:
        meta = json.load(f)

    print('=' * 60)
    print('  LMS Adaptive — Model Evaluation')
    print('=' * 60)
    print(f'  Модель обучена : {meta["trained_at"]}')
    print(f'  Train size     : {meta["train_size"]}')
    print(f'  Test size (meta): {meta["test_size"]}')
    print()

    # --- Данные ---
    df = build_dataset()
    X = df[FEATURE_COLS].values
    y = df[TARGET_COL].values

    sss = StratifiedShuffleSplit(n_splits=1, test_size=test_size, random_state=42)
    _, test_idx = next(sss.split(X, y))
    X_test = X[test_idx]
    y_test = y[test_idx]

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    has_both_classes = len(np.unique(y_test)) > 1

    print('-' * 60)
    print('  ОСНОВНЫЕ МЕТРИКИ')
    print('-' * 60)
    print(f'  Accuracy  : {acc:.4f}  ({acc*100:.1f}%)')

    if has_both_classes:
        auc = roc_auc_score(y_test, y_prob)
        print(f'  ROC-AUC   : {auc:.4f}')

        # Оценка качества
        if auc >= 0.85:
            grade = 'Отлично'
        elif auc >= 0.75:
            grade = 'Хорошо (цель ВКР достигнута)'
        elif auc >= 0.65:
            grade = 'Удовл. (нужно больше данных)'
        else:
            grade = 'Недостаточно (проверьте данные)'
        print(f'  Оценка    : {grade}')
    else:
        auc = None
        print('  ROC-AUC   : N/A (один класс в тест-выборке)')

    print()
    print('-' * 60)
    print('  CLASSIFICATION REPORT')
    print('-' * 60)
    print(classification_report(
        y_test, y_pred,
        target_names=['Не завершил (0)', 'Завершил (1)'],
        digits=4,
    ))

    # --- Confusion matrix (текстовая) ---
    from sklearn.metrics import confusion_matrix
    cm = confusion_matrix(y_test, y_pred)
    print('-' * 60)
    print('  CONFUSION MATRIX')
    print('-' * 60)
    print(f'  {"":20} Предсказано 0   Предсказано 1')
    print(f'  {"Реальный 0":20} {cm[0,0]:^15} {cm[0,1]:^15}')
    print(f'  {"Реальный 1":20} {cm[1,0]:^15} {cm[1,1]:^15}')

    if has_both_classes:
        # --- ROC-кривая (текстовая ASCII) ---
        fpr, tpr, thresholds = roc_curve(y_test, y_prob)
        print()
        print('-' * 60)
        print(f'  ROC CURVE (AUC = {auc:.4f})')
        print('-' * 60)
        _print_ascii_roc(fpr, tpr)

    # --- Feature importances ---
    print()
    print('-' * 60)
    print('  FEATURE IMPORTANCES (из meta.json)')
    print('-' * 60)
    fi = meta.get('feature_importances', {})
    sorted_fi = sorted(fi.items(), key=lambda x: x[1], reverse=True)
    for feat, imp in sorted_fi:
        bar = '#' * int(imp * 50)
        print(f'  {feat:<28} {imp:.4f}  {bar}')

    print()
    print('=' * 60)


def _print_ascii_roc(fpr: np.ndarray, tpr: np.ndarray, width: int = 40, height: int = 12) -> None:
    """Печатает ROC-кривую в ASCII-арт прямо в консоль."""
    grid = [['·'] * width for _ in range(height)]

    for f, t in zip(fpr, tpr):
        x = min(int(f * (width - 1)), width - 1)
        y = min(int((1 - t) * (height - 1)), height - 1)
        grid[y][x] = '#'

    # Диагональ (random baseline)
    for i in range(min(width, height)):
        x = int(i / (min(width, height) - 1) * (width - 1))
        y = int(i / (min(width, height) - 1) * (height - 1))
        if grid[y][x] == '·':
            grid[y][x] = '-'

    print(f'  TPR ^')
    for i, row in enumerate(grid):
        label = '1.0 |' if i == 0 else '0.5 |' if i == height // 2 else '    |'
        print(f'  {label} {"".join(row)}')
    print(f'  0.0 +{"-" * width}> FPR')
    print(f'       0{" " * (width // 2 - 1)}0.5{" " * (width // 2 - 2)}1.0')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--test-size', type=float, default=0.20)
    args = parser.parse_args()
    evaluate(test_size=args.test_size)
