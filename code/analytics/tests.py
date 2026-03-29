"""
analytics/tests.py
==================
Unit and integration tests for the analytics app.

Coverage:
  - build_feature_vector: shape, default values, history aggregation, position ratio
  - get_recommendations:  sorting, filtering, top_n
  - GET /analytics/api/recommendations/<course_id>/: auth, 404, response shape, mock model
"""

from unittest.mock import MagicMock, patch

import numpy as np
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from analytics.models import UserLessonProgress
from analytics.services import FEATURE_COLS, build_feature_vector, get_recommendations
from courses.models import Course, Lesson, Module

User = get_user_model()

RECOMMENDATIONS_URL = '/analytics/api/recommendations/{}/'


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def make_course(owner, title='Test Course'):
    """Creates Course -> 2 Modules -> 2 Lessons each (4 lessons total)."""
    course = Course.objects.create(owner=owner, title=title, description='desc')

    mod1 = Module.objects.create(course=course, title='Module 1', order=1)
    l1 = Lesson.objects.create(module=mod1, title='Lesson 1', content='c1', order=1)
    l2 = Lesson.objects.create(module=mod1, title='Lesson 2', content='c2', order=2)

    mod2 = Module.objects.create(course=course, title='Module 2', order=2)
    l3 = Lesson.objects.create(module=mod2, title='Lesson 3', content='c3', order=1)
    l4 = Lesson.objects.create(module=mod2, title='Lesson 4', content='c4', order=2)

    return course, mod1, mod2, l1, l2, l3, l4


def make_progress(user, lesson, *, is_completed, time_spent, attempts, score):
    return UserLessonProgress.objects.create(
        user=user,
        lesson=lesson,
        is_completed=is_completed,
        time_spent_seconds=time_spent,
        attempt_count=attempts,
        quiz_score=score,
    )


# ---------------------------------------------------------------------------
# 1. build_feature_vector — shape and defaults
# ---------------------------------------------------------------------------

class FeatureVectorShapeTests(APITestCase):
    """Tests that the feature vector always has the correct shape and dtype."""

    def setUp(self):
        self.teacher = User.objects.create_user('teacher_fv', role='teacher')
        self.student = User.objects.create_user('student_fv', role='student')
        self.course, _, _, self.l1, self.l2, self.l3, self.l4 = make_course(self.teacher)

    def test_shape_is_1x11(self):
        vec = build_feature_vector(self.student, self.l1)
        self.assertEqual(vec.shape, (1, len(FEATURE_COLS)),
                         msg='Feature vector must have shape (1, 11)')

    def test_dtype_is_float64(self):
        vec = build_feature_vector(self.student, self.l1)
        self.assertEqual(vec.dtype, np.float64)

    def test_no_nan_in_vector(self):
        vec = build_feature_vector(self.student, self.l1)
        self.assertFalse(np.isnan(vec).any(), msg='Feature vector must not contain NaN')

    def test_no_inf_in_vector(self):
        vec = build_feature_vector(self.student, self.l2)
        self.assertFalse(np.isinf(vec).any(), msg='Feature vector must not contain Inf')


# ---------------------------------------------------------------------------
# 2. build_feature_vector — first lesson: no prior history
# ---------------------------------------------------------------------------

class FeatureVectorFirstLessonTests(APITestCase):
    """
    The very first lesson in a course has no prior history.
    prev_* features must fall back to their defined defaults.
    """

    def setUp(self):
        self.teacher = User.objects.create_user('teacher_fl', role='teacher')
        self.student = User.objects.create_user('student_fl', role='student')
        self.course, _, _, self.l1, self.l2, self.l3, self.l4 = make_course(self.teacher)

    def _vec(self, lesson):
        return build_feature_vector(self.student, lesson)[0]

    def test_prev_avg_score_is_zero(self):
        self.assertAlmostEqual(self._vec(self.l1)[FEATURE_COLS.index('prev_avg_score')], 0.0)

    def test_prev_avg_time_is_zero(self):
        self.assertAlmostEqual(self._vec(self.l1)[FEATURE_COLS.index('prev_avg_time')], 0.0)

    def test_prev_avg_attempts_defaults_to_one(self):
        # Default is 1.0 (not 0) — you can't have zero attempts
        self.assertAlmostEqual(self._vec(self.l1)[FEATURE_COLS.index('prev_avg_attempts')], 1.0)

    def test_prev_completion_rate_is_zero(self):
        self.assertAlmostEqual(self._vec(self.l1)[FEATURE_COLS.index('prev_completion_rate')], 0.0)

    def test_prev_lessons_done_is_zero(self):
        self.assertAlmostEqual(self._vec(self.l1)[FEATURE_COLS.index('prev_lessons_done')], 0.0)

    def test_no_current_progress_time_is_zero(self):
        self.assertAlmostEqual(self._vec(self.l1)[FEATURE_COLS.index('time_spent_seconds')], 0.0)

    def test_no_current_progress_attempt_count_defaults_to_one(self):
        self.assertAlmostEqual(self._vec(self.l1)[FEATURE_COLS.index('attempt_count')], 1.0)

    def test_no_current_progress_quiz_score_is_zero(self):
        self.assertAlmostEqual(self._vec(self.l1)[FEATURE_COLS.index('quiz_score')], 0.0)

    def test_lesson_position_ratio_first_lesson(self):
        # 4 lessons total; first lesson = 1/4 = 0.25
        ratio = self._vec(self.l1)[FEATURE_COLS.index('lesson_position_ratio')]
        self.assertAlmostEqual(ratio, 0.25, places=5)

    def test_lesson_position_ratio_last_lesson(self):
        # last lesson = 4/4 = 1.0
        ratio = self._vec(self.l4)[FEATURE_COLS.index('lesson_position_ratio')]
        self.assertAlmostEqual(ratio, 1.0, places=5)


# ---------------------------------------------------------------------------
# 3. build_feature_vector — history aggregation (core logic)
# ---------------------------------------------------------------------------

class FeatureVectorAggregationTests(APITestCase):
    """
    Tests for the correctness of prev_* aggregation when prior
    UserLessonProgress records exist.
    """

    def setUp(self):
        self.teacher = User.objects.create_user('teacher_agg', role='teacher')
        self.student = User.objects.create_user('student_agg', role='student')
        self.course, mod1, mod2, self.l1, self.l2, self.l3, self.l4 = make_course(self.teacher)

        # l1 and l2 are in Module 1 (order=1)
        # l3 and l4 are in Module 2 (order=2)

        # Student completed l1 (module 1) with known metrics
        make_progress(self.student, self.l1,
                      is_completed=True, time_spent=120, attempts=2, score=0.8)

        # Student started l2 (same module) but did not complete
        make_progress(self.student, self.l2,
                      is_completed=False, time_spent=60, attempts=3, score=0.4)

    def _vec(self, lesson):
        return build_feature_vector(self.student, lesson)[0]

    # --- Testing prev_* for l3 (first lesson of Module 2)
    # l3 prev_qs: lessons in module with order < 2 → l1 (completed) and l2 (not completed)
    # Both l1 and l2 are in module 1 (order=1), which is < 2

    def test_prev_avg_score_two_records(self):
        # (0.8 + 0.4) / 2 = 0.6
        val = self._vec(self.l3)[FEATURE_COLS.index('prev_avg_score')]
        self.assertAlmostEqual(val, 0.6, places=5)

    def test_prev_avg_time_two_records(self):
        # (120 + 60) / 2 = 90.0
        val = self._vec(self.l3)[FEATURE_COLS.index('prev_avg_time')]
        self.assertAlmostEqual(val, 90.0, places=5)

    def test_prev_avg_attempts_two_records(self):
        # (2 + 3) / 2 = 2.5
        val = self._vec(self.l3)[FEATURE_COLS.index('prev_avg_attempts')]
        self.assertAlmostEqual(val, 2.5, places=5)

    def test_prev_completion_rate_one_of_two(self):
        # completed: l1=True, l2=False → 1/2 = 0.5
        val = self._vec(self.l3)[FEATURE_COLS.index('prev_completion_rate')]
        self.assertAlmostEqual(val, 0.5, places=5)

    def test_prev_lessons_done_one_of_two(self):
        val = self._vec(self.l3)[FEATURE_COLS.index('prev_lessons_done')]
        self.assertAlmostEqual(val, 1.0, places=5)

    def test_prev_avg_score_with_null_score(self):
        """Records with quiz_score=None must be excluded from score average."""
        make_progress(self.student, self.l4,
                      is_completed=True, time_spent=90, attempts=1, score=None)
        # For l4 prev: l1(0.8), l2(0.4) from earlier module + l3 from same module if exists
        # We only added progress for l1, l2, l4 — no progress for l3 yet
        # So prev for l4: l1(0.8), l2(0.4) from Module1 + l3 (no progress recorded)
        # Only l1 and l2 have recorded progress before l4
        val = self._vec(self.l4)[FEATURE_COLS.index('prev_avg_score')]
        # scores with values: 0.8, 0.4 (l4's own None is excluded; l3 has no record)
        self.assertAlmostEqual(val, 0.6, places=5)

    # --- Testing prev_* for l2 (second lesson of Module 1, same module as l1)

    def test_prev_avg_score_same_module_single_record(self):
        # l2 prev_same_module: l1 (order=1 < 2) → avg_score = 0.8
        val = self._vec(self.l2)[FEATURE_COLS.index('prev_avg_score')]
        self.assertAlmostEqual(val, 0.8, places=5)

    def test_prev_avg_time_same_module_single_record(self):
        val = self._vec(self.l2)[FEATURE_COLS.index('prev_avg_time')]
        self.assertAlmostEqual(val, 120.0, places=5)

    def test_prev_lessons_done_same_module_single_record(self):
        val = self._vec(self.l2)[FEATURE_COLS.index('prev_lessons_done')]
        self.assertAlmostEqual(val, 1.0, places=5)

    # --- Current lesson's own progress is reflected

    def test_current_lesson_time_used_when_progress_exists(self):
        # l2 has progress: time=60, attempts=3, score=0.4
        vec = self._vec(self.l2)
        self.assertAlmostEqual(vec[FEATURE_COLS.index('time_spent_seconds')], 60.0)
        self.assertAlmostEqual(vec[FEATURE_COLS.index('attempt_count')], 3.0)
        self.assertAlmostEqual(vec[FEATURE_COLS.index('quiz_score')], 0.4)

    def test_current_lesson_defaults_when_no_progress(self):
        # l3 has no progress record yet
        vec = self._vec(self.l3)
        self.assertAlmostEqual(vec[FEATURE_COLS.index('time_spent_seconds')], 0.0)
        self.assertAlmostEqual(vec[FEATURE_COLS.index('attempt_count')], 1.0)
        self.assertAlmostEqual(vec[FEATURE_COLS.index('quiz_score')], 0.0)

    def test_current_lesson_null_quiz_score_becomes_zero(self):
        """quiz_score=None in DB must be converted to 0.0 in the feature vector."""
        make_progress(self.student, self.l3,
                      is_completed=False, time_spent=45, attempts=2, score=None)
        vec = self._vec(self.l3)
        self.assertAlmostEqual(vec[FEATURE_COLS.index('quiz_score')], 0.0)


# ---------------------------------------------------------------------------
# 4. get_recommendations — sorting, filtering, top_n
# ---------------------------------------------------------------------------

class GetRecommendationsTests(APITestCase):
    """Unit tests for get_recommendations() with a mocked model."""

    def setUp(self):
        self.teacher = User.objects.create_user('teacher_rec', role='teacher')
        self.student = User.objects.create_user('student_rec', role='student')
        self.course, _, _, self.l1, self.l2, self.l3, self.l4 = make_course(self.teacher)

    def _mock_model(self, probs):
        """
        Returns a MagicMock that mimics sklearn's predict_proba.
        probs: list of P(completion) values, returned sequentially.
        """
        mock = MagicMock()
        # Each call returns [[P(0), P(1)]] — we return them in sequence
        side_effects = [np.array([[1 - p, p]]) for p in probs]
        mock.predict_proba.side_effect = side_effects
        return mock

    def test_returns_only_incomplete_lessons(self):
        make_progress(self.student, self.l1,
                      is_completed=True, time_spent=60, attempts=1, score=0.9)
        with patch('analytics.services.get_model',
                   return_value=self._mock_model([0.6, 0.5, 0.4])):
            recs = get_recommendations(self.student, self.course)
        ids = [r['lesson_id'] for r in recs]
        self.assertNotIn(self.l1.id, ids, msg='Completed lessons must be excluded')

    def test_all_completed_returns_empty_list(self):
        for lesson in [self.l1, self.l2, self.l3, self.l4]:
            make_progress(self.student, lesson,
                          is_completed=True, time_spent=60, attempts=1, score=0.9)
        with patch('analytics.services.get_model', return_value=self._mock_model([])):
            recs = get_recommendations(self.student, self.course)
        self.assertEqual(recs, [])

    def test_sorted_by_risk_score_descending(self):
        # Model predicts: l1=0.9 (low risk), l2=0.3 (high risk), l3=0.5, l4=0.7
        with patch('analytics.services.get_model',
                   return_value=self._mock_model([0.9, 0.3, 0.5, 0.7])):
            recs = get_recommendations(self.student, self.course, top_n=4)
        risk_scores = [r['risk_score'] for r in recs]
        self.assertEqual(risk_scores, sorted(risk_scores, reverse=True),
                         msg='Recommendations must be sorted by risk_score DESC')

    def test_highest_risk_is_first(self):
        with patch('analytics.services.get_model',
                   return_value=self._mock_model([0.9, 0.1, 0.5, 0.7])):
            recs = get_recommendations(self.student, self.course, top_n=4)
        # l2 has P=0.1 → risk=0.9, must be first
        self.assertEqual(recs[0]['lesson_id'], self.l2.id)

    def test_top_n_limits_results(self):
        with patch('analytics.services.get_model',
                   return_value=self._mock_model([0.8, 0.6, 0.4, 0.2])):
            recs = get_recommendations(self.student, self.course, top_n=2)
        self.assertEqual(len(recs), 2)

    def test_result_dict_has_required_keys(self):
        with patch('analytics.services.get_model',
                   return_value=self._mock_model([0.5, 0.5, 0.5, 0.5])):
            recs = get_recommendations(self.student, self.course, top_n=1)
        required_keys = {'lesson_id', 'lesson_title', 'module_title',
                         'completion_prob', 'risk_score'}
        self.assertEqual(required_keys, set(recs[0].keys()))

    def test_risk_score_equals_one_minus_prob(self):
        with patch('analytics.services.get_model',
                   return_value=self._mock_model([0.72, 0.55, 0.31, 0.88])):
            recs = get_recommendations(self.student, self.course, top_n=4)
        for r in recs:
            self.assertAlmostEqual(
                r['risk_score'], round(1.0 - r['completion_prob'], 4), places=4
            )

    def test_no_model_returns_neutral_prob(self):
        """When no model is loaded, completion_prob must be 0.5 for all lessons."""
        with patch('analytics.services.get_model', return_value=None):
            recs = get_recommendations(self.student, self.course, top_n=4)
        for r in recs:
            self.assertAlmostEqual(r['completion_prob'], 0.5)
            self.assertAlmostEqual(r['risk_score'], 0.5)


# ---------------------------------------------------------------------------
# 5. GET /analytics/api/recommendations/<course_id>/ — API endpoint
# ---------------------------------------------------------------------------

class RecommendationsAPITests(APITestCase):
    """
    Integration tests for the recommendations DRF endpoint.
    The ML model is mocked to remove dependency on model.pkl.
    """

    def setUp(self):
        self.teacher = User.objects.create_user('teacher_api', role='teacher')
        self.student = User.objects.create_user('student_api', role='student')
        self.course, _, _, self.l1, self.l2, self.l3, self.l4 = make_course(self.teacher)
        self.url = RECOMMENDATIONS_URL.format(self.course.id)

        # Default mock: model is loaded, returns uniform 0.5 probability
        self.mock_model = MagicMock()
        self.mock_model.predict_proba.return_value = np.array([[0.5, 0.5]])

    # --- Auth ---

    def test_unauthenticated_is_rejected(self):
        # DRF returns 403 with SessionAuthentication (no Bearer token configured yet).
        # After JWT is added in Stage 3, this will become 401.
        response = self.client.get(self.url)
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
            msg='Unauthenticated request must be rejected (401 or 403)',
        )

    def test_authenticated_returns_200(self):
        self.client.force_authenticate(user=self.student)
        with patch('analytics.services.get_model', return_value=self.mock_model):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # --- 404 ---

    def test_nonexistent_course_returns_404(self):
        self.client.force_authenticate(user=self.student)
        with patch('analytics.services.get_model', return_value=self.mock_model):
            response = self.client.get(RECOMMENDATIONS_URL.format(99999))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- Response shape ---

    def test_response_contains_course_id(self):
        self.client.force_authenticate(user=self.student)
        with patch('analytics.services.get_model', return_value=self.mock_model):
            response = self.client.get(self.url)
        self.assertEqual(response.data['course_id'], self.course.id)

    def test_response_contains_model_loaded_flag(self):
        self.client.force_authenticate(user=self.student)
        with patch('analytics.services.get_model', return_value=self.mock_model):
            response = self.client.get(self.url)
        self.assertIn('model_loaded', response.data)
        self.assertTrue(response.data['model_loaded'])

    def test_model_loaded_false_when_no_model(self):
        self.client.force_authenticate(user=self.student)
        with patch('analytics.services.get_model', return_value=None):
            response = self.client.get(self.url)
        self.assertFalse(response.data['model_loaded'])

    def test_response_recommendations_is_list(self):
        self.client.force_authenticate(user=self.student)
        with patch('analytics.services.get_model', return_value=self.mock_model):
            response = self.client.get(self.url)
        self.assertIsInstance(response.data['recommendations'], list)

    # --- Business logic through API ---

    def test_completed_lessons_absent_from_recommendations(self):
        make_progress(self.student, self.l1,
                      is_completed=True, time_spent=100, attempts=1, score=0.9)
        self.client.force_authenticate(user=self.student)
        with patch('analytics.services.get_model', return_value=self.mock_model):
            response = self.client.get(self.url)
        ids = [r['lesson_id'] for r in response.data['recommendations']]
        self.assertNotIn(self.l1.id, ids)

    def test_top_n_query_param_limits_results(self):
        self.client.force_authenticate(user=self.student)
        with patch('analytics.services.get_model', return_value=self.mock_model):
            response = self.client.get(self.url + '?top_n=2')
        self.assertLessEqual(len(response.data['recommendations']), 2)

    def test_recommendations_sorted_by_risk_desc(self):
        """Verify the endpoint returns items sorted by risk_score DESC."""
        # Mock: assign distinct probabilities so order is deterministic
        mock = MagicMock()
        mock.predict_proba.side_effect = [
            np.array([[0.8, 0.2]]),   # l1: risk=0.8
            np.array([[0.3, 0.7]]),   # l2: risk=0.3
            np.array([[0.6, 0.4]]),   # l3: risk=0.6
            np.array([[0.1, 0.9]]),   # l4: risk=0.1
        ]
        self.client.force_authenticate(user=self.student)
        with patch('analytics.services.get_model', return_value=mock):
            response = self.client.get(self.url + '?top_n=4')
        scores = [r['risk_score'] for r in response.data['recommendations']]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_recommendation_item_fields(self):
        """Each recommendation item must contain all required fields."""
        self.client.force_authenticate(user=self.student)
        with patch('analytics.services.get_model', return_value=self.mock_model):
            response = self.client.get(self.url + '?top_n=1')
        item = response.data['recommendations'][0]
        for field in ('lesson_id', 'lesson_title', 'module_title',
                      'completion_prob', 'risk_score'):
            self.assertIn(field, item, msg=f'Field "{field}" missing from response item')

    def test_all_completed_returns_empty_recommendations(self):
        for lesson in [self.l1, self.l2, self.l3, self.l4]:
            make_progress(self.student, lesson,
                          is_completed=True, time_spent=60, attempts=1, score=0.9)
        self.client.force_authenticate(user=self.student)
        with patch('analytics.services.get_model', return_value=self.mock_model):
            response = self.client.get(self.url)
        self.assertEqual(response.data['recommendations'], [])

    def test_teacher_can_also_access_endpoint(self):
        """The endpoint is not restricted to 'student' role."""
        self.client.force_authenticate(user=self.teacher)
        with patch('analytics.services.get_model', return_value=self.mock_model):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
