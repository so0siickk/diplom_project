"""
train.py
========
Обучает ML-модель на данных из Django ORM.

Pipeline:
    числовые признаки → StandardScaler → GradientBoostingClassifier
    с подбором гиперпараметров через GridSearchCV (3-fold CV, ROC-AUC).

Артефакты (сохраняются в ai_module/):
    model.pkl   — обученный sklearn Pipeline (scaler + clf)
    meta.json   — метаданные: дата, признаки, лучшие параметры, метрики

Запуск:
    python ml_analytics/train.py
    python ml_analytics/train.py --no-grid   # быстро, без перебора
    python ml_analytics/train.py --test-size 0.25
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# Bootstrap Django перед импортом dataset_builder
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CODE_DIR = os.path.join(_ROOT, 'code')
sys.path.insert(0, os.path.join(_ROOT, 'ml_analytics'))
sys.path.insert(0, _CODE_DIR)
os.chdir(_CODE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from dataset_builder import FEATURE_COLS, TARGET_COL, build_dataset  # noqa: E402

AI_MODULE_DIR = os.path.join(_ROOT, 'ai_module')
MODEL_PATH = os.path.join(AI_MODULE_DIR, 'model.pkl')
META_PATH = os.path.join(AI_MODULE_DIR, 'meta.json')

PARAM_GRID = {
    'clf__n_estimators': [100, 200],
    'clf__max_depth': [3, 5],
    'clf__learning_rate': [0.05, 0.1],
    'clf__subsample': [0.8, 1.0],
}

FAST_PARAMS = {
    'n_estimators': 200,
    'max_depth': 4,
    'learning_rate': 0.08,
    'subsample': 0.85,
    'min_samples_leaf': 5,
    'random_state': 42,
}


def _build_pipeline(params: dict | None = None) -> Pipeline:
    clf_params = params or FAST_PARAMS
    return Pipeline([
        ('scaler', StandardScaler()),
        ('clf', GradientBoostingClassifier(**clf_params)),
    ])


def train(use_grid: bool = True, test_size: float = 0.20) -> dict:
    print('=' * 60)
    print('  LMS Adaptive — ML Training')
    print('=' * 60)

    # --- Данные ---
    df = build_dataset()
    if len(df) < 30:
        print(
            f'[WARN] Мало данных ({len(df)} записей). '
            'Запустите generate_synthetic_data --records 1000'
        )

    X = df[FEATURE_COLS].values
    y = df[TARGET_COL].values

    # Стратифицированный split
    sss = StratifiedShuffleSplit(n_splits=1, test_size=test_size, random_state=42)
    train_idx, test_idx = next(sss.split(X, y))
    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    print(f'\nTrain: {len(X_train)} | Test: {len(X_test)}')
    print(f'Class balance (train): {y_train.mean():.1%} позитивных\n')

    # --- Обучение ---
    if use_grid and len(X_train) >= 50:
        print('GridSearchCV (3-fold, scoring=roc_auc) ...')
        pipe = _build_pipeline()
        gs = GridSearchCV(
            pipe,
            PARAM_GRID,
            cv=3,
            scoring='roc_auc',
            n_jobs=-1,
            verbose=1,
            refit=True,
        )
        gs.fit(X_train, y_train)
        best_model = gs.best_estimator_
        best_params = {
            k.replace('clf__', ''): v
            for k, v in gs.best_params_.items()
        }
        print(f'\nЛучшие параметры: {best_params}')
        print(f'CV ROC-AUC:       {gs.best_score_:.4f}')
    else:
        if use_grid:
            print(f'[INFO] Данных < 50, пропускаем GridSearch, используем FAST_PARAMS.')
        print('Обучение с фиксированными параметрами...')
        best_model = _build_pipeline()
        best_model.fit(X_train, y_train)
        best_params = FAST_PARAMS
        print('Обучение завершено.')

    # --- Метрики ---
    y_pred = best_model.predict(X_test)
    y_prob = best_model.predict_proba(X_test)[:, 1]

    metrics = {
        'accuracy': float(accuracy_score(y_test, y_pred)),
        'roc_auc': float(roc_auc_score(y_test, y_prob)) if len(np.unique(y_test)) > 1 else None,
    }

    print('\n' + '-' * 50)
    print('  РЕЗУЛЬТАТЫ НА TEST SET')
    print('-' * 50)
    print(f'  Accuracy : {metrics["accuracy"]:.4f}')
    if metrics['roc_auc'] is not None:
        print(f'  ROC-AUC  : {metrics["roc_auc"]:.4f}')
    else:
        print('  ROC-AUC  : N/A (только один класс в тесте)')
    print()
    print(classification_report(y_test, y_pred, target_names=['Не завершил', 'Завершил']))

    # --- Feature importance ---
    clf = best_model.named_steps['clf']
    importances = sorted(
        zip(FEATURE_COLS, clf.feature_importances_),
        key=lambda x: x[1],
        reverse=True,
    )
    print('-' * 50)
    print('  ВАЖНОСТЬ ПРИЗНАКОВ (top-7)')
    print('-' * 50)
    for feat, imp in importances[:7]:
        bar = '#' * int(imp * 40)
        print(f'  {feat:<28} {imp:.4f} {bar}')

    # --- Сохранение ---
    os.makedirs(AI_MODULE_DIR, exist_ok=True)
    joblib.dump(best_model, MODEL_PATH)

    meta = {
        'trained_at': datetime.now(timezone.utc).isoformat(),
        'feature_cols': FEATURE_COLS,
        'target_col': TARGET_COL,
        'train_size': int(len(X_train)),
        'test_size': int(len(X_test)),
        'best_params': best_params,
        'metrics': metrics,
        'feature_importances': {k: round(float(v), 6) for k, v in importances},
    }
    with open(META_PATH, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f'\nМодель сохранена: {MODEL_PATH}')
    print(f'Метаданные:       {META_PATH}')
    print('=' * 60)

    return metrics


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-grid', action='store_true', help='Без GridSearchCV')
    parser.add_argument('--test-size', type=float, default=0.20)
    args = parser.parse_args()

    train(use_grid=not args.no_grid, test_size=args.test_size)
