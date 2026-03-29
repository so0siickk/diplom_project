from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from courses.models import Course, Lesson
from .models import UserLessonProgress
from .services import get_recommendations


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

