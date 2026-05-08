from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CodeAssignmentViewSet, EssayAssignmentViewSet, OpenAssignmentViewSet, SubmissionViewSet

router = DefaultRouter()
router.register(r"assignments", OpenAssignmentViewSet, basename="assignment")
router.register(r"submissions", SubmissionViewSet, basename="submission")
router.register(r"code-assignments", CodeAssignmentViewSet, basename="code-assignment")
router.register(r"essay-assignments", EssayAssignmentViewSet, basename="essay-assignment")

urlpatterns = [
    path("api/v1/", include(router.urls)),
]
