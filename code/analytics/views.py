from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.views.decorators.http import require_POST

from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from courses.models import Course, Lesson
from .models import UserLessonProgress
from .services import get_recommendations

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
    rows = (
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
        student = User(id=uid, username=row['username'])  # lightweight shell for ML call

        highest_risk_lesson: str | None = None
        risk_score: float | None = None

        course = enrolled.get(uid)
        if course is not None:
            # get_recommendations already excludes completed lessons and sorts by risk DESC
            try:
                student_obj = User.objects.get(id=uid)
                recs = get_recommendations(student_obj, course, top_n=1)
                if recs:
                    highest_risk_lesson = f"{recs[0]['module_title']} → {recs[0]['lesson_title']}"
                    risk_score = recs[0]['risk_score']
            except Exception:
                pass

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

