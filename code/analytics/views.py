from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Min, Q
from django.views.decorators.http import require_POST

from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from courses.models import Course, Lesson
from .models import UserLessonProgress
from .services import get_recommendations, get_model

User = get_user_model()


@extend_schema(
    tags=['Analytics'],
    summary='Profile stats for the authenticated user',
    responses={200: {
        'type': 'object',
        'properties': {
            'username':          {'type': 'string'},
            'role':              {'type': 'string'},
            'lessons_completed': {'type': 'integer'},
            'lessons_started':   {'type': 'integer'},
            'avg_score':         {'type': 'number', 'nullable': True},
            'courses_enrolled':  {'type': 'integer'},
        },
    }},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_stats(request):
    """GET /analytics/api/profile/ — aggregated learning stats for the current user."""
    agg = (
        UserLessonProgress.objects
        .filter(user=request.user)
        .aggregate(
            lessons_completed=Count('id', filter=Q(is_completed=True)),
            lessons_started=Count('id'),
            avg_score=Avg('quiz_score'),       # NULL entries excluded by Avg automatically
        )
    )
    courses_enrolled = (
        Course.objects
        .filter(modules__lessons__student_progress__user=request.user)
        .distinct()
        .count()
    )
    return Response({
        'username':          request.user.username,
        'role':              request.user.role,
        'lessons_completed': agg['lessons_completed'],
        'lessons_started':   agg['lessons_started'],
        'avg_score':         round(agg['avg_score'], 3) if agg['avg_score'] is not None else None,
        'courses_enrolled':  courses_enrolled,
    })


@extend_schema(
    tags=['Analytics'],
    summary='Per-student stats with ML risk data (teacher/staff only)',
    responses={200: {
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {
                'user_id':             {'type': 'integer'},
                'username':            {'type': 'string'},
                'lessons_completed':   {'type': 'integer'},
                'avg_score':           {'type': 'number', 'nullable': True},
                'highest_risk_lesson': {'type': 'string', 'nullable': True},
                'risk_score':          {'type': 'number', 'nullable': True},
            },
        },
    }},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def students_stats(request):
    """
    GET /analytics/api/students-stats/

    Aggregates progress for all students. Only accessible to teachers and staff.
    For each student, ML recommendations are queried for the first enrolled course
    to surface the highest-risk pending lesson.
    """
    if request.user.role != 'teacher' and not request.user.is_staff:
        return Response({'detail': 'Permission denied.'}, status=403)

    # One query: per-user aggregation over progress records
    rows = list(
        User.objects
        .filter(role='student')
        .annotate(
            lessons_completed=Count(
                'progress__id', filter=Q(progress__is_completed=True)
            ),
            avg_score=Avg('progress__quiz_score'),
        )
        .order_by('username')
        .values('id', 'username', 'lessons_completed', 'avg_score')
    )

    # Pre-fetch heuristic risk scores — one query, no per-row lookups
    from analytics.models import StudentRiskScore
    risk_cache: dict[int, float] = {
        r['user_id']: r['risk_score']
        for r in StudentRiskScore.objects.values('user_id', 'risk_score')
    }

    # Pre-fetch full User objects to avoid User.objects.get() inside the loop
    student_map: dict[int, User] = {
        u.pk: u
        for u in User.objects.filter(role='student')
    }

    # Prefetch one course per student for ML lookup (cheapest: first enrolled course)
    enrolled: dict[int, Course | None] = {}
    for course in Course.objects.prefetch_related('modules__lessons').all():
        for uid in (
            UserLessonProgress.objects
            .filter(lesson__module__course=course)
            .values_list('user_id', flat=True)
            .distinct()
        ):
            if uid not in enrolled:
                enrolled[uid] = course

    result = []
    for row in rows:
        uid = row['id']
        avg = row['avg_score']

        highest_risk_lesson: str | None = None
        risk_score: float | None = None

        course = enrolled.get(uid)
        student_obj = student_map.get(uid)
        if course is not None and student_obj is not None:
            try:
                recs = get_recommendations(student_obj, course, top_n=1)
                if recs:
                    highest_risk_lesson = (
                        f"{recs[0]['module_title']} → {recs[0]['lesson_title']}"
                    )
                    risk_score = recs[0]['risk_score']
            except Exception:
                pass

        # Fallback: use pre-computed heuristic when ML model absent
        # or student finished all lessons (get_recommendations returns [])
        if risk_score is None:
            risk_score = risk_cache.get(uid)

        result.append({
            'user_id':             uid,
            'username':            row['username'],
            'lessons_completed':   row['lessons_completed'],
            'avg_score':           round(avg, 3) if avg is not None else None,
            'highest_risk_lesson': highest_risk_lesson,
            'risk_score':          risk_score,
        })

    return Response(result)


@login_required
@require_POST
def complete_lesson(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)

    progress, _ = UserLessonProgress.objects.get_or_create(
        user=request.user,
        lesson=lesson,
    )
    progress.is_completed = True
    progress.save()

    return redirect('lesson-detail-html', pk=lesson_id)


@extend_schema(
    tags=['Analytics'],
    summary='Mark a lesson as completed for the authenticated user',
    request={'application/json': {'type': 'object', 'properties': {
        'time_spent_seconds': {'type': 'integer', 'example': 300},
        'quiz_score': {'type': 'number', 'example': 0.85},
    }}},
    responses={200: {'type': 'object', 'properties': {
        'lesson_id': {'type': 'integer'},
        'is_completed': {'type': 'boolean'},
        'created': {'type': 'boolean'},
    }}},
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_lesson_api(request, lesson_id: int):
    """POST /analytics/api/complete/<lesson_id>/ — mark lesson completed via JWT."""
    lesson = get_object_or_404(Lesson, id=lesson_id)

    progress, created = UserLessonProgress.objects.get_or_create(
        user=request.user,
        lesson=lesson,
    )
    progress.is_completed = True
    if 'time_spent_seconds' in request.data:
        progress.time_spent_seconds = int(request.data['time_spent_seconds'])
    if 'quiz_score' in request.data:
        progress.quiz_score = float(request.data['quiz_score'])
    progress.save()

    return Response({
        'lesson_id': lesson.id,
        'is_completed': True,
        'created': created,
    })


@extend_schema(
    tags=['Analytics'],
    summary='Get ML-based lesson recommendations for a course',
    parameters=[
        OpenApiParameter('course_id', OpenApiTypes.INT, OpenApiParameter.PATH,
                         description='Course ID'),
        OpenApiParameter('top_n', OpenApiTypes.INT, OpenApiParameter.QUERY,
                         description='Number of recommendations to return (default 5, max 20)',
                         required=False),
    ],
    responses={200: {
        'type': 'object',
        'properties': {
            'course_id': {'type': 'integer'},
            'course_title': {'type': 'string'},
            'model_loaded': {'type': 'boolean'},
            'recommendations': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'lesson_id': {'type': 'integer'},
                        'lesson_title': {'type': 'string'},
                        'module_title': {'type': 'string'},
                        'completion_prob': {'type': 'number'},
                        'risk_score': {'type': 'number'},
                    },
                },
            },
        },
    }},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recommendations_api(request, course_id: int):
    """
    GET /api/recommendations/<course_id>/

    Returns the top-N uncompleted lessons with the highest failure risk
    for the authenticated user in the specified course.

    Query params:
        top_n (int, default=5) -- number of lessons to return

    Response 200:
        {
            "course_id": 1,
            "model_loaded": true,
            "recommendations": [
                {
                    "lesson_id": 12,
                    "lesson_title": "...",
                    "module_title": "...",
                    "completion_prob": 0.32,
                    "risk_score": 0.68
                },
                ...
            ]
        }

    Response 404: course not found.
    """
    course = get_object_or_404(Course, id=course_id)
    top_n = min(int(request.query_params.get('top_n', 5)), 20)

    from .services import get_model
    recommendations = get_recommendations(request.user, course, top_n=top_n)

    return Response({
        'course_id': course.id,
        'course_title': course.title,
        'model_loaded': get_model() is not None,
        'recommendations': recommendations,
    })


def _risk_level(risk_score: float) -> str:
    if risk_score > 0.6:
        return 'red'
    if risk_score > 0.3:
        return 'yellow'
    return 'green'


@extend_schema(
    tags=['Analytics'],
    summary='Risk analytics dashboard for teachers/staff',
    responses={200: {
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {
                'user_id':           {'type': 'integer'},
                'username':          {'type': 'string'},
                'average_score':     {'type': 'number', 'description': '0–100'},
                'completed_lessons': {'type': 'integer'},
                'risk_score':        {'type': 'number', 'description': '0.0–1.0'},
                'risk_level':        {'type': 'string', 'enum': ['green', 'yellow', 'red']},
                'problematic_topic': {'type': 'string', 'nullable': True},
            },
        },
    }},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_risk_analytics(request) -> Response:
    """
    GET /analytics/api/risk/

    Per-student risk summary for the teacher dashboard.
    Access: teachers (role='teacher') and staff only.

    Risk score formula (prototype stub):
        risk_score = 1.0 - (average_score / 100)
    Replace with ML model output once model.pkl is deployed.
    """
    if request.user.role != 'teacher' and not request.user.is_staff:
        return Response({'detail': 'Permission denied.'}, status=403)

    # One query: aggregate per student
    rows = list(
        User.objects
        .filter(role='student')
        .annotate(
            avg_quiz_score=Avg('progress__quiz_score'),
            completed_lessons=Count(
                'progress__id', filter=Q(progress__is_completed=True)
            ),
        )
        .order_by('username')
        .values('id', 'username', 'avg_quiz_score', 'completed_lessons')
    )

    # One query: worst-scoring lesson per student
    # Progress records are ordered ascending by quiz_score so the first record
    # per user is the lesson with the lowest score.
    worst_lesson: dict[int, str] = {}
    for rec in (
        UserLessonProgress.objects
        .filter(user__role='student', quiz_score__isnull=False)
        .order_by('quiz_score')
        .values('user_id', 'lesson__title')
    ):
        uid = rec['user_id']
        if uid not in worst_lesson:
            worst_lesson[uid] = rec['lesson__title']

    result = []
    for row in rows:
        avg_qs = row['avg_quiz_score']  # 0–1 float or None
        average_score = round(avg_qs * 100, 1) if avg_qs is not None else 0.0
        risk_score = round(1.0 - (average_score / 100), 4)

        result.append({
            'user_id':           row['id'],
            'username':          row['username'],
            'average_score':     average_score,
            'completed_lessons': row['completed_lessons'],
            'risk_score':        risk_score,
            'risk_level':        _risk_level(risk_score),
            'problematic_topic': worst_lesson.get(row['id']),
        })

    return Response(result)

