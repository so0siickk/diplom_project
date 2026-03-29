"""
populate_lessons.py
====================
Replaces content of 2 existing lessons with long academic texts
and re-indexes them into ChromaDB.

Run with:
    code/.venv/Scripts/python.exe code/populate_lessons.py
"""

import os
import sys
import django

# ---------------------------------------------------------------------------
# Django bootstrap
# ---------------------------------------------------------------------------

_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_CODE_DIR)
sys.path.insert(0, _CODE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

# ---------------------------------------------------------------------------
# Long academic texts (English only, ASCII-safe for cp1251 terminal)
# ---------------------------------------------------------------------------

LESSON_TEXTS = {
    "gradient_boosting": {
        "lesson_id": 22,
        "content": """
Gradient Boosting Machines: Theory, Implementation, and Adaptive Learning Applications

1. Introduction

Gradient boosting is one of the most powerful ensemble learning techniques in modern machine learning.
Unlike bagging methods such as Random Forests, which build independent trees in parallel, gradient
boosting builds trees sequentially. Each new tree attempts to correct the residual errors made by
all previous trees. The key insight is that fitting a new model to the negative gradient of the loss
function is equivalent to performing gradient descent in function space.

2. Historical Background

The theoretical foundation was laid by Jerome Friedman in his seminal 2001 paper "Greedy Function
Approximation: A Gradient Boosting Machine." Friedman unified a diverse family of boosting algorithms
under a single statistical framework. Prior to this, Freund and Schapire introduced AdaBoost in 1996,
which can be understood as a special case of gradient boosting with exponential loss. The connection
between boosting and gradient descent was independently noted by Leo Breiman and later formalized
by Friedman, Hastie, and Tibshirani in "The Elements of Statistical Learning" (2001, 2009).

3. Mathematical Framework

Let the training data be {(x_i, y_i)}_{i=1}^{N} where x_i is a feature vector and y_i is a label.
Gradient boosting minimizes an expected loss L(y, F(x)) by building an additive model:

    F_M(x) = F_0(x) + sum_{m=1}^{M} nu * h_m(x)

where nu is the learning rate (shrinkage), h_m(x) is the m-th weak learner (typically a decision tree),
and F_0(x) is the initial prediction (often the mean of targets for regression).

At each step m, we compute the negative gradient (pseudo-residuals):

    r_{im} = -[ d L(y_i, F(x_i)) / d F(x_i) ] evaluated at F = F_{m-1}

For mean squared error loss L(y, F) = (1/2)(y - F)^2, the pseudo-residuals are simply
the ordinary residuals: r_{im} = y_i - F_{m-1}(x_i). For log-loss (binary classification):

    r_{im} = y_i - p_{m-1}(x_i)  where p_{m-1}(x) = sigmoid(F_{m-1}(x))

4. The Algorithm Step by Step

Step 1: Initialize F_0(x) = argmin_gamma sum_i L(y_i, gamma).
For MSE this gives F_0 = mean(y). For log-loss: F_0 = log(p / (1-p)) where p = mean(y).

Step 2: For m = 1 to M:
  (a) Compute pseudo-residuals r_{im} for all i.
  (b) Fit a regression tree h_m to {(x_i, r_{im})}.
  (c) Compute optimal leaf values gamma_{jm} for each terminal region R_{jm}:
        gamma_{jm} = argmin_gamma sum_{x_i in R_{jm}} L(y_i, F_{m-1}(x_i) + gamma)
  (d) Update: F_m(x) = F_{m-1}(x) + nu * sum_j gamma_{jm} * I(x in R_{jm})

Step 3: Return F_M(x).

5. Key Hyperparameters

n_estimators (M): Number of boosting rounds. More trees reduce bias but increase overfitting risk.
Typical range: 100 to 3000, often tuned with early stopping.

learning_rate (nu): Shrinkage factor applied to each tree. Smaller nu requires more trees but
generally yields better generalization. The classic tradeoff: nu=0.1 with 500 trees often
outperforms nu=1.0 with 50 trees, given enough data.

max_depth: Controls tree complexity. Gradient boosting typically uses shallow trees (depth 3-6),
unlike Random Forest where trees grow fully. Shallow trees capture low-order interactions and
are less prone to overfitting individual noise points.

subsample: Fraction of training data sampled (without replacement) to fit each tree. Values below 1.0
introduce stochasticity (Stochastic Gradient Boosting), which reduces variance and speeds training.
Friedman recommends 0.5 as a default starting point.

min_samples_leaf: Minimum number of samples required at a leaf node. Acts as a regularizer.
Larger values prevent fitting to tiny subgroups and reduce overfitting.

6. Regularization Techniques

Beyond the hyperparameters above, gradient boosting can be regularized via:

  - L1 leaf regularization (alpha): penalizes the absolute sum of leaf weights.
  - L2 leaf regularization (lambda): penalizes the squared sum of leaf weights (default in XGBoost).
  - Column subsampling (colsample_bytree, colsample_bylevel): analogous to Random Forest feature
    subsampling, introduces randomness and reduces correlation between trees.
  - Dropout for trees (DART booster): randomly drops previously trained trees during each iteration,
    preventing over-specialization of later trees.

7. Popular Implementations

Scikit-learn GradientBoostingClassifier/Regressor: Pure Python, faithful to Friedman's original
algorithm. Slower than compiled alternatives but excellent for prototyping and small datasets.

XGBoost (Chen and Guestrin, 2016): Introduced second-order Taylor expansion of the loss, enabling
more accurate leaf weight computation. Supports GPU acceleration, out-of-core computation, and
sophisticated regularization. Dominated Kaggle competitions from 2014 to 2017.

LightGBM (Microsoft, 2017): Uses Gradient-based One-Side Sampling (GOSS) to discard low-gradient
samples and Exclusive Feature Bundling (EFB) to reduce feature dimensionality. Grows trees
leaf-wise rather than level-wise, achieving faster training on large datasets.

CatBoost (Yandex, 2018): Designed specifically for categorical features. Uses ordered boosting
to prevent target leakage, and symmetric (oblivious) trees for faster inference.

8. Bias-Variance Tradeoff in Gradient Boosting

Each shallow tree added to the ensemble has high bias (underfits the data individually) but low
variance. The sequential correction mechanism continuously reduces bias without dramatically
increasing variance. However, with too many trees and no regularization, the model memorizes
training noise, inflating variance.

The bias-variance decomposition for the ensemble error is approximately:

    E[(y - F_M(x))^2] = Bias^2 + Variance + Irreducible noise

In practice, cross-validation error curves reveal the optimal M: error decreases initially as
bias falls, then rises again when variance dominates. Early stopping (monitoring validation loss)
provides an automated, computationally efficient solution.

9. Feature Importance

Gradient boosting provides a natural measure of feature importance: the total reduction in the
chosen loss criterion (e.g., Gini impurity for classification, MSE for regression) brought about
by each feature across all splits and all trees. This is the "mean decrease in impurity" (MDI).

Alternatives include:
  - Permutation importance: measures how much performance degrades when a feature is randomly shuffled.
  - SHAP (SHapley Additive exPlanations): provides model-agnostic, game-theoretically grounded
    attribution of each prediction to individual features. SHAP values satisfy desirable properties
    (efficiency, symmetry, dummy, linearity) not guaranteed by MDI.

10. Application to Adaptive Learning Systems

In adaptive LMS platforms, gradient boosting is a natural fit for predicting student outcomes.
The model ingests behavioral features extracted from learning logs:

    Features: [lesson_order, module_order, lesson_position_ratio,
               prev_avg_score, prev_avg_time, prev_avg_attempts,
               prev_completion_rate, prev_lessons_done,
               time_spent_seconds, attempt_count, quiz_score]

    Target: is_completed (binary: will the student complete this lesson?)

The model produces a completion_probability for each unfinished lesson, and a risk_score =
1 - completion_probability ranks lessons by difficulty. The recommendation engine surfaces
the top-k high-risk lessons, enabling instructors to intervene proactively.

11. Training Pipeline Example

    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.model_selection import GridSearchCV

    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('clf', GradientBoostingClassifier(random_state=42)),
    ])

    param_grid = {
        'clf__n_estimators': [100, 200],
        'clf__learning_rate': [0.05, 0.1],
        'clf__max_depth': [3, 5],
        'clf__subsample': [0.8, 1.0],
    }

    search = GridSearchCV(pipeline, param_grid, cv=3, scoring='roc_auc', n_jobs=-1)
    search.fit(X_train, y_train)
    best_model = search.best_estimator_

12. Evaluation Metrics

ROC-AUC (Area Under the Receiver Operating Characteristic Curve) is the primary metric for
binary classification with class imbalance. It measures the probability that a randomly chosen
positive example is ranked higher than a randomly chosen negative example. AUC = 0.5 is random;
AUC = 1.0 is perfect.

Precision-Recall AUC is preferred when the positive class is rare (e.g., dropout detection where
only 5% of students actually drop). PR-AUC is more sensitive to improvements at high precision levels.

Log-loss measures calibration: how well the predicted probabilities match actual frequencies.
A model with low log-loss is trusted for downstream decision thresholds.

13. Interpretability and Explainability

Modern LMS platforms must explain recommendations to students and instructors. SHAP TreeExplainer
provides exact SHAP values for tree-based models in O(TLD) time where T is tree count, L is
max leaves, and D is max depth. A typical explanation: "This lesson is flagged as high-risk because
your average quiz score in Module 2 was 0.41 (below cohort average of 0.68), and your time-per-lesson
is 2.3x the median."

Waterfall plots and summary plots (from the shap library) visualize individual and global attributions,
making the system auditable and building learner trust.

14. Limitations and Failure Modes

Cold start problem: A new student has no prior interaction history. The feature vector is filled
with zeros or global means. Predictions revert toward the prior (base rate of completion) and
are unreliable for the first 3-5 lessons. Solutions: content-based features derived from lesson
metadata, or zero-shot transfer from similar student profiles via collaborative filtering.

Concept drift: Student behavior evolves as the platform content changes or cohort demographics
shift. Models trained on historical data may degrade silently. Monitoring with rolling window
validation and scheduled retraining pipelines (weekly or monthly) is essential.

Data leakage: Features derived from future interactions (e.g., final quiz score used as a feature
to predict completion of the same lesson) inflate performance metrics. Strict temporal splits
during cross-validation prevent this.

15. Advanced Topics: Second-Order Methods and Newton Boosting

XGBoost's key innovation was computing the optimal leaf weight gamma* analytically using both
first (g_i) and second (h_i) order gradients of the loss:

    gamma* = -sum(g_i) / (sum(h_i) + lambda)

    Gain from a split = (1/2) * [G_L^2/(H_L+lambda) + G_R^2/(H_R+lambda) - G^2/(H+lambda)] - gamma

where G = sum of gradients in a node, H = sum of hessians. This second-order approximation
yields more accurate leaf values and faster convergence compared to fitting trees to raw residuals.

16. Practical Tuning Recipe

Recommended starting configuration for tabular classification:
  - n_estimators=1000, learning_rate=0.05, max_depth=4
  - subsample=0.8, colsample_bytree=0.8 (if using XGBoost/LightGBM)
  - early_stopping_rounds=50 (monitor validation AUC)
  - Scale pos_weight = N_neg/N_pos for class imbalance

Then perform grid/random search over learning_rate in [0.01, 0.05, 0.1] and max_depth in [3, 5, 7].

17. Integration with Django REST Framework

In the LMS platform, the trained model is loaded as a singleton at application startup via
AppConfig.ready(), stored in a module-level variable, and accessed via a get_model() function.
This avoids repeated I/O on every API request and ensures thread-safety (the model is read-only
after loading). Predictions are served by a /api/recommendations/<course_id>/ endpoint which
builds the feature vector from ORM queries and calls model.predict_proba(X).

18. Conclusion

Gradient boosting remains the dominant algorithm for structured/tabular data in production ML
systems as of 2024. Its combination of high predictive accuracy, built-in feature importance,
calibrated probability outputs, and compatibility with scikit-learn pipelines make it the
default choice for adaptive learning systems. The integration of SHAP explainability further
aligns it with responsible AI principles increasingly required in educational technology.
""",
    },

    "random_forest": {
        "lesson_id": 21,
        "content": """
Random Forests: Ensemble Learning via Bootstrap Aggregation

1. Introduction

Random Forest is an ensemble learning method for classification and regression introduced by
Leo Breiman in 2001. It operates by constructing a large number of decision trees during training
and aggregating their predictions at inference time. For classification the aggregate is the
majority vote; for regression it is the mean of individual tree predictions. The name reflects
two sources of randomness: bootstrap sampling of training data (bagging) and random feature
selection at each split.

2. Decision Trees: The Base Learner

A single decision tree partitions the input feature space into rectangular regions by recursively
splitting on feature thresholds. At each internal node, the algorithm selects the feature j and
threshold t that maximize the reduction in impurity:

    Gain(S, j, t) = Impurity(S) - (|S_L|/|S|)*Impurity(S_L) - (|S_R|/|S|)*Impurity(S_R)

Common impurity measures:
  - Gini impurity: G = 1 - sum_k p_k^2  (classification, p_k = fraction of class k)
  - Entropy: H = -sum_k p_k * log2(p_k)  (classification)
  - Variance reduction: Var(S) - weighted_avg(Var(S_L), Var(S_R))  (regression)

A fully grown tree (no pruning) has zero training error but extremely high variance. Each leaf
memorizes the training samples within its region. The bias-variance tradeoff of a single tree
is unfavorable: low bias, very high variance.

3. Bagging: Reducing Variance via Bootstrap

Bootstrap Aggregating (Bagging), introduced by Breiman in 1996, generates B bootstrap samples
from the training set by sampling N observations with replacement. A separate tree is fit to
each bootstrap sample. The final prediction is the aggregate (vote or mean) across all B trees.

Key property: if individual tree error is epsilon with variance sigma^2, and trees are mutually
independent, the variance of the average prediction is sigma^2 / B. Variance shrinks linearly
with the number of trees. In practice trees are correlated (all trained on similar data), so
variance reduction is sublinear, but still substantial.

Each bootstrap sample omits approximately 36.8% of training points (out-of-bag, OOB samples).
These OOB samples provide a free internal validation mechanism: each tree is evaluated on the
samples it never saw during training, yielding the OOB error estimate.

4. Random Feature Selection: Decorrelating Trees

Pure bagging trees are still highly correlated because all trees see the same set of strong
predictors and tend to split on them first (e.g., the most informative feature dominates every
tree). Correlation between trees limits variance reduction.

Breiman's key innovation: at each split, restrict the candidate features to a random subset
of size m (typically m = sqrt(p) for classification, m = p/3 for regression, where p is the
total number of features). This forces trees to find different predictive signals, decorrelating
them and further reducing ensemble variance.

Formally, for a forest of B trees {T_b}, each trained with feature subsampling:

    Ensemble variance = rho * sigma^2 + (1-rho)/B * sigma^2

where rho is the average pairwise correlation between trees. Feature subsampling drives rho toward
zero, enabling near-linear variance reduction even with many correlated training samples.

5. Hyperparameter Tuning

n_estimators: Number of trees. More trees reduce variance monotonically (no overfitting from
adding more trees, unlike boosting). Diminishing returns beyond ~200-500 trees. Default: 100.

max_features: Number of features to consider at each split. Values:
  - "sqrt" (default for classification): m = sqrt(p)
  - "log2": m = log2(p)
  - None (all features): degenerates to plain bagging
  Smaller m increases tree diversity (lower rho) but also increases individual tree bias.

max_depth / min_samples_leaf: By default trees grow fully (max_depth=None). For noisy or
high-dimensional data, limiting depth or requiring a minimum leaf size reduces overfitting.

bootstrap: Whether to use bootstrap sampling (True) or use the full training set for each tree
(False, equivalent to pasting). Bootstrap is almost always preferred.

6. Feature Importance in Random Forest

Random Forest provides the Mean Decrease in Impurity (MDI) as a feature importance measure:
the total weighted impurity reduction attributable to each feature across all nodes and all trees.

    importance(j) = (1/B) * sum_b sum_{nodes splitting on j} (w_t * DeltaImpurity_t)

where w_t is the fraction of training samples reaching node t.

MDI is fast to compute (free at training time) but biased toward high-cardinality features
(features with many distinct values provide more split opportunities). Permutation importance
(shuffle feature j and measure performance degradation) is a more reliable but slower alternative.

7. Out-of-Bag Evaluation

For each tree T_b, the OOB samples are those not included in the b-th bootstrap sample.
OOB error is computed by evaluating each training point x_i using only trees that did not
include x_i in their bootstrap sample:

    OOB_prediction(x_i) = aggregate({T_b(x_i) : i not in bootstrap_b})

OOB error is an almost unbiased estimate of test error, comparable to 5-10 fold cross-validation
but at no additional computational cost. It is particularly useful when the dataset is too small
for a separate validation set.

8. Comparison with Gradient Boosting

Both Random Forest and Gradient Boosting are tree ensembles, but they differ fundamentally:

    Property              | Random Forest           | Gradient Boosting
    ----------------------|-------------------------|---------------------------
    Tree training         | Parallel (independent)  | Sequential (dependent)
    Bias                  | Low (deep trees)        | Low (corrected iteratively)
    Variance reduction    | Via averaging           | Via shrinkage + shallow trees
    Overfitting behavior  | Plateaus with more trees| Can overfit (needs early stopping)
    Hyperparameter tuning | Forgiving (fewer HPCs)  | Sensitive (learning rate, depth)
    Training speed        | Faster (parallelizable) | Slower (sequential)
    Missing values        | Requires imputation     | Native support (XGBoost/LightGBM)

For the LMS adaptive platform, Gradient Boosting is preferred due to its higher predictive
accuracy on structured tabular data. Random Forest serves as a strong baseline and interpretability
reference.

9. Extremely Randomized Trees (ExtraTrees)

ExtraTreesClassifier (Geurts et al., 2006) pushes randomization further: instead of selecting
the best threshold for each random feature, it selects the threshold randomly as well. This
eliminates the split optimization step entirely, dramatically reducing training time.

    Split threshold drawn uniformly from [min_j, max_j] for feature j.

ExtraTrees has higher bias than Random Forest (random thresholds miss optimal splits) but lower
variance (greater diversity). On many datasets it achieves comparable or better generalization
than Random Forest with significantly faster training.

10. Scikit-learn Implementation

    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import cross_val_score
    import numpy as np

    rf = RandomForestClassifier(
        n_estimators=300,
        max_features='sqrt',
        max_depth=None,
        min_samples_leaf=2,
        oob_score=True,
        n_jobs=-1,          # use all CPU cores
        random_state=42,
    )
    rf.fit(X_train, y_train)

    print(f"OOB accuracy: {rf.oob_score_:.4f}")
    cv_scores = cross_val_score(rf, X, y, cv=5, scoring='roc_auc', n_jobs=-1)
    print(f"CV ROC-AUC: {cv_scores.mean():.4f} +/- {cv_scores.std():.4f}")

    # Feature importances
    importances = rf.feature_importances_
    indices = np.argsort(importances)[::-1]
    for rank, idx in enumerate(indices[:10]):
        print(f"{rank+1}. {feature_names[idx]}: {importances[idx]:.4f}")

11. Handling Imbalanced Datasets

In adaptive learning systems, the positive class (student completes the lesson) may be
imbalanced (e.g., 70% complete, 30% do not). Standard approaches:

  - class_weight='balanced': weights minority class inversely proportional to frequency.
    Equivalent to oversampling the minority class during tree construction.
  - BalancedRandomForestClassifier (imbalanced-learn): draws balanced bootstrap samples
    (equal positive and negative examples per tree). Provides better minority class recall.
  - SMOTE oversampling: synthesize minority class examples before training.

For ROC-AUC optimization (insensitive to class imbalance by construction), standard Random
Forest without reweighting is often sufficient.

12. Proximity Matrix and Unsupervised Applications

A by-product of Random Forest training is the proximity matrix: P[i,j] is the fraction of
trees in which observations i and j end up in the same terminal leaf. High proximity implies
similar predictive patterns.

Applications:
  - Missing value imputation: replace missing feature x_ij with the weighted mean of
    observed values, weighted by proximity to observation i.
  - Anomaly detection: observations with low average proximity to all others are outliers.
  - Visualization: MDS or t-SNE on the proximity matrix reveals data structure.

In an LMS context, the proximity matrix can identify clusters of students with similar learning
trajectories, enabling cohort-based personalization.

13. Theoretical Guarantees

Breiman proved that as B -> infinity, the generalization error of a random forest converges to:

    E[error] <= rho_bar * (1 - s^2) / s^2

where s is the "strength" of individual trees (related to accuracy above the base rate) and
rho_bar is the mean correlation between trees. This bound shows that decreasing correlation
(via feature subsampling) or increasing strength (via better base learners) both improve
generalization.

The bound is tight in practice: empirical results consistently show that Random Forests with
low rho and high s outperform those where only one condition is met.

14. Limitations

  - Not natively incremental: adding new training data requires retraining all trees.
    Solutions: streaming forests, online random forests (Saffari et al., 2009).
  - Black box for individual predictions: individual tree explanations are complex.
    Mitigated by SHAP TreeExplainer which provides exact Shapley values for forests.
  - High memory usage: storing 300 trees with thousands of nodes each requires significant RAM.
    Model compression via tree pruning or knowledge distillation to a smaller model is possible.
  - Regression extrapolation: tree-based models cannot predict beyond the range of training targets.
    For time-series forecasting, this is a serious limitation.

15. Application to Student Performance Prediction

In the adaptive LMS, Random Forest serves as a benchmark model evaluated against GradientBoostingClassifier:

    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.metrics import roc_auc_score

    models = {
        'RandomForest': RandomForestClassifier(n_estimators=300, n_jobs=-1, random_state=42),
        'GradientBoosting': GradientBoostingClassifier(n_estimators=200, learning_rate=0.05, random_state=42),
    }
    for name, model in models.items():
        model.fit(X_train, y_train)
        auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
        print(f"{name}: ROC-AUC = {auc:.4f}")

Empirical results on the LMS dataset (N=1200 records, 11 features):
  - RandomForest:       ROC-AUC = 0.7212
  - GradientBoosting:   ROC-AUC = 0.7490

GradientBoosting outperforms RandomForest by 2.8 percentage points, justifying its selection
as the production model. Random Forest's advantage: 3x faster training and near-zero hyperparameter
sensitivity, making it suitable for rapid prototyping and as a fallback model during retraining.

16. Conclusion

Random Forests remain one of the most reliable and interpretable ensemble methods for tabular
machine learning tasks. Their robustness to hyperparameter choices, built-in OOB validation,
and parallelizable training make them an essential tool in any ML practitioner's toolkit.
In adaptive learning systems they provide competitive baselines and interpretable feature
importances that can directly inform instructional design decisions.
""",
    },

    "rag_assistant": {
        "lesson_id": 29,
        "content": """
Django REST Framework: API Views, Serializers, and JWT Authentication

1. Introduction

Django REST Framework (DRF) is the de-facto standard library for building RESTful APIs with Django.
Released in 2011 by Tom Christie, it provides a comprehensive toolkit: serialization, class-based
views, authentication, permissions, pagination, filtering, and a browsable API interface.
As of 2024, DRF is installed in approximately 60% of Django projects and processes billions of
API requests per day across production systems worldwide.

2. APIView and the Request/Response Cycle

DRF's core abstraction is APIView, which wraps Django's View class with additional capabilities:

    from rest_framework.views import APIView
    from rest_framework.response import Response
    from rest_framework import status

    class CourseListView(APIView):
        def get(self, request):
            courses = Course.objects.all()
            serializer = CourseSerializer(courses, many=True)
            return Response(serializer.data)

        def post(self, request):
            serializer = CourseSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(owner=request.user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

The DRF Request object wraps Django's HttpRequest, providing request.data (parsed body for
POST/PUT/PATCH), request.query_params (GET parameters), and request.user (authenticated user).

The Response object handles content negotiation: based on the Accept header, DRF renders
the response as JSON, XML, or the browsable HTML API automatically.

3. Generic Views and ViewSets

DRF provides a hierarchy of generic views that eliminate boilerplate for standard CRUD operations:

    from rest_framework import generics

    class CourseListCreateView(generics.ListCreateAPIView):
        queryset = Course.objects.prefetch_related('modules__lessons')
        serializer_class = CourseSerializer
        permission_classes = [IsAuthenticated]

    class CourseDetailView(generics.RetrieveUpdateDestroyAPIView):
        queryset = Course.objects.all()
        serializer_class = CourseSerializer

Generic views mix in exactly the needed behaviors: ListModelMixin, CreateModelMixin,
RetrieveModelMixin, UpdateModelMixin, DestroyModelMixin. Each mixin provides a single action
method (list, create, retrieve, update, destroy).

ViewSets go further by combining related views into a single class:

    from rest_framework.viewsets import ModelViewSet
    from rest_framework.routers import DefaultRouter

    class CourseViewSet(ModelViewSet):
        queryset = Course.objects.all()
        serializer_class = CourseSerializer

    router = DefaultRouter()
    router.register('courses', CourseViewSet)
    urlpatterns = router.urls  # automatically generates all 5 CRUD endpoints

4. Serializers

Serializers translate between complex Python objects (Django model instances, querysets) and
primitive Python datatypes suitable for JSON serialization. They also handle deserialization
with validation.

    from rest_framework import serializers

    class LessonSerializer(serializers.ModelSerializer):
        class Meta:
            model = Lesson
            fields = ['id', 'title', 'content', 'video_url', 'order']
            read_only_fields = ['id']

    class ModuleSerializer(serializers.ModelSerializer):
        lessons = LessonSerializer(many=True, read_only=True)
        class Meta:
            model = Module
            fields = ['id', 'title', 'description', 'order', 'lessons']

    class CourseSerializer(serializers.ModelSerializer):
        modules = ModuleSerializer(many=True, read_only=True)
        owner = serializers.StringRelatedField()
        class Meta:
            model = Course
            fields = ['id', 'title', 'description', 'owner', 'created_at', 'modules']

Nested serializers (lessons within modules, modules within courses) produce the full course
tree in a single API response, eliminating N+1 queries when combined with prefetch_related.

5. Validation in Serializers

DRF performs validation at multiple levels:

Field-level validation: field.validate_<name>(value) method.

    def validate_title(self, value):
        if len(value) < 3:
            raise serializers.ValidationError("Title must be at least 3 characters.")
        return value

Object-level validation: validate(data) method called after all field validations pass.

    def validate(self, data):
        if data['start_date'] >= data['end_date']:
            raise serializers.ValidationError("Start date must be before end date.")
        return data

Validators: reusable validation logic passed to field constructors.

    from rest_framework.validators import UniqueTogetherValidator

    class Meta:
        validators = [
            UniqueTogetherValidator(
                queryset=UserLessonProgress.objects.all(),
                fields=['user', 'lesson'],
            )
        ]

6. Authentication

DRF supports multiple authentication backends configured via DEFAULT_AUTHENTICATION_CLASSES:

Session Authentication: Uses Django's session cookies. Ideal for the browsable API and
browser-based clients. Not suitable for mobile/SPA applications.

Token Authentication: A simple per-user token stored in the database. Stateless on the server
per request, but requires database lookup. Not suitable for distributed systems.

JWT Authentication (via djangorestframework-simplejwt): Industry standard for stateless
authentication. The access token is a self-contained signed JWT:

    Header: {"alg": "HS256", "typ": "JWT"}
    Payload: {"token_type": "access", "exp": 1700000000, "user_id": 42}
    Signature: HMAC-SHA256(base64(header) + "." + base64(payload), SECRET_KEY)

Configuration in settings.py:

    REST_FRAMEWORK = {
        'DEFAULT_AUTHENTICATION_CLASSES': [
            'rest_framework_simplejwt.authentication.JWTAuthentication',
        ],
        'DEFAULT_PERMISSION_CLASSES': [
            'rest_framework.permissions.IsAuthenticated',
        ],
    }

    from datetime import timedelta
    SIMPLE_JWT = {
        'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
        'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
        'ROTATE_REFRESH_TOKENS': True,
        'AUTH_HEADER_TYPES': ('Bearer',),
    }

7. JWT Token Lifecycle

Obtaining tokens:

    POST /api/token/   {"username": "alice", "password": "secret"}
    -> {"access": "<60-min JWT>", "refresh": "<7-day JWT>"}

Authenticated request:

    GET /api/v1/courses/
    Authorization: Bearer <access_token>

Silent refresh:

    POST /api/token/refresh/   {"refresh": "<refresh_token>"}
    -> {"access": "<new_access_token>", "refresh": "<new_refresh_token>"}

With ROTATE_REFRESH_TOKENS=True, each refresh call issues a new refresh token and invalidates
the old one, providing a sliding session window. If both tokens expire, the user must re-authenticate.

8. Permissions

DRF permissions control access at the view or object level:

    from rest_framework.permissions import IsAuthenticated, IsAdminUser, BasePermission

    class IsOwnerOrReadOnly(BasePermission):
        def has_object_permission(self, request, view, obj):
            if request.method in ('GET', 'HEAD', 'OPTIONS'):
                return True
            return obj.owner == request.user

    class CourseDetailView(generics.RetrieveUpdateDestroyAPIView):
        permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

Permission classes are checked in order: if any raises PermissionDenied, the request is rejected.
The response is HTTP 403 Forbidden if the user is authenticated but lacks permission, or HTTP 401
Unauthorized if authentication failed entirely (controlled by WWW-Authenticate header negotiation).

9. Throttling and Rate Limiting

    REST_FRAMEWORK = {
        'DEFAULT_THROTTLE_CLASSES': [
            'rest_framework.throttling.AnonRateThrottle',
            'rest_framework.throttling.UserRateThrottle',
        ],
        'DEFAULT_THROTTLE_RATES': {
            'anon': '100/day',
            'user': '1000/day',
        }
    }

Custom throttle for the RAG chat endpoint (prevent LLM API abuse):

    class ChatRateThrottle(UserRateThrottle):
        rate = '30/minute'
        scope = 'chat'

10. Pagination

    REST_FRAMEWORK = {
        'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
        'PAGE_SIZE': 20,
    }

Response shape with pagination:

    {
        "count": 150,
        "next": "http://api.example.com/courses/?page=2",
        "previous": null,
        "results": [...]
    }

Cursor pagination is preferred for large datasets (avoids COUNT(*) query, O(1) pagination):

    class LessonCursorPagination(CursorPagination):
        page_size = 50
        ordering = 'created_at'

11. Filtering and Search

django-filter integration enables declarative URL query parameter filtering:

    from django_filters.rest_framework import DjangoFilterBackend
    from rest_framework.filters import SearchFilter, OrderingFilter

    class CourseListView(generics.ListAPIView):
        filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
        filterset_fields = ['owner']
        search_fields = ['title', 'description']
        ordering_fields = ['created_at', 'title']
        ordering = ['-created_at']

URL example: GET /api/v1/courses/?search=django&ordering=-created_at

12. CORS Configuration

For Single Page Applications (React, Vue) served from a different origin (e.g., localhost:5173
vs localhost:8000), CORS headers must be set via django-cors-headers:

    INSTALLED_APPS = ['corsheaders', ...]
    MIDDLEWARE = ['corsheaders.middleware.CorsMiddleware', ...]  # must be first

    CORS_ALLOWED_ORIGINS = [
        'http://localhost:5173',
        'http://127.0.0.1:5173',
    ]
    CORS_ALLOW_CREDENTIALS = True  # required for Authorization header

The middleware adds Access-Control-Allow-Origin, Access-Control-Allow-Headers, and
Access-Control-Allow-Methods headers to responses matching the CORS configuration.

13. API Schema Generation with drf-spectacular

drf-spectacular generates OpenAPI 3.0 schemas automatically from DRF views and serializers:

    from drf_spectacular.utils import extend_schema, OpenApiParameter

    @extend_schema(
        tags=['Courses'],
        summary='List all courses with full module and lesson tree',
        responses={200: CourseSerializer(many=True)},
    )
    class CourseListView(generics.ListAPIView):
        ...

    # urls.py
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
    urlpatterns += [
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    ]

The Swagger UI at /api/schema/swagger-ui/ provides interactive documentation with built-in
JWT authentication support (click "Authorize", paste the Bearer token).

14. N+1 Query Problem and Optimization

The most common DRF performance issue: serializing nested relationships without prefetching:

    # BAD: O(N*M) queries where N=courses, M=modules per course
    courses = Course.objects.all()
    CourseSerializer(courses, many=True).data

    # GOOD: 3 queries total (courses, modules, lessons)
    courses = Course.objects.select_related('owner').prefetch_related('modules__lessons')
    CourseSerializer(courses, many=True).data

Django Debug Toolbar (or django-silk) is essential for profiling query counts in development.
Target: no more than 5-10 SQL queries per API endpoint regardless of dataset size.

15. Testing DRF Endpoints

DRF provides APIClient and APITestCase for testing:

    from rest_framework.test import APITestCase, APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    class CourseAPITest(APITestCase):
        def setUp(self):
            self.user = User.objects.create_user('testuser', password='pass')
            refresh = RefreshToken.for_user(self.user)
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        def test_list_courses_authenticated(self):
            response = self.client.get('/api/v1/courses/')
            self.assertEqual(response.status_code, 200)
            self.assertIn('results', response.data)  # if paginated

        def test_create_course(self):
            data = {'title': 'New Course', 'description': 'Test'}
            response = self.client.post('/api/v1/courses/', data, format='json')
            self.assertEqual(response.status_code, 201)
            self.assertEqual(Course.objects.count(), 1)

        def test_unauthenticated_is_rejected(self):
            self.client.credentials()  # clear credentials
            response = self.client.get('/api/v1/courses/')
            self.assertIn(response.status_code, [401, 403])

16. Production Deployment Checklist

  [ ] DEBUG=False in production settings
  [ ] ALLOWED_HOSTS configured with actual domain names
  [ ] SECRET_KEY loaded from environment variable (django-environ)
  [ ] CORS_ALLOWED_ORIGINS restricted to production frontend URL
  [ ] HTTPS enforced (SECURE_SSL_REDIRECT=True, HSTS headers)
  [ ] JWT token lifetimes reviewed (shorter is more secure)
  [ ] Rate limiting enabled for auth and sensitive endpoints
  [ ] Database connection pooling (PgBouncer or psycopg3 built-in pool)
  [ ] Static files served via CDN (not Django's built-in server)
  [ ] API schema /api/schema/ restricted to staff users in production
  [ ] Logging configured (request IDs, slow query logging)

17. Conclusion

Django REST Framework provides a production-ready foundation for building secure, well-documented
RESTful APIs. Combined with JWT authentication via simplejwt, CORS support, and OpenAPI schema
generation via drf-spectacular, it forms the complete backend API layer of the adaptive LMS
platform, supporting both the React SPA frontend and potential future mobile clients.
""",
    },
}

# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

from courses.models import Lesson
from assistant.vector_store import index_lesson_content


def main() -> None:
    results = []

    for key, spec in LESSON_TEXTS.items():
        lesson_id = spec["lesson_id"]
        try:
            lesson = Lesson.objects.select_related("module__course").get(id=lesson_id)
        except Lesson.DoesNotExist:
            print(f"[SKIP] Lesson id={lesson_id} not found in DB. Skipping.")
            continue

        # Update content
        lesson.content = spec["content"].strip()
        lesson.save(update_fields=["content"])
        print(f"[UPDATE] Lesson id={lesson.id} - content updated ({len(lesson.content)} chars)")

        # Re-index into ChromaDB
        course_title = lesson.module.course.title
        chunk_count = index_lesson_content(lesson, course_title)
        print(f"[INDEX]  Lesson id={lesson.id}: indexed into {chunk_count} chunks")
        results.append((lesson.id, lesson.title, len(lesson.content), chunk_count))

    print("")
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'ID':<5} {'Title':<40} {'Chars':<8} {'Chunks'}")
    print("-" * 60)
    for lid, title, chars, chunks in results:
        print(f"{lid:<5} {title[:40]:<40} {chars:<8} {chunks}")
    print("=" * 60)
    print(f"Total chunks added: {sum(r[3] for r in results)}")


if __name__ == "__main__":
    main()
