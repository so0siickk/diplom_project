from django.urls import path
from .views import (
    complete_lesson,
    complete_lesson_api,
    profile_stats,
    students_stats,
    recommendations_api,
)

urlpatterns = [
    path('complete/<int:lesson_id>/', complete_lesson, name='complete-lesson'),
    path('api/complete/<int:lesson_id>/',   complete_lesson_api, name='complete-lesson-api'),
    path('api/profile/',                    profile_stats,       name='profile-stats'),
    path('api/students-stats/',             students_stats,      name='students-stats'),
    path('api/recommendations/<int:course_id>/', recommendations_api, name='recommendations-api'),
]
