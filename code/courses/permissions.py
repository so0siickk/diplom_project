from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOwnerOrReadOnly(BasePermission):
    """
    - SAFE_METHODS (GET, HEAD, OPTIONS): any authenticated user.
    - Mutating methods: only the course owner or an admin.

    Works for Course (obj.owner), Module (obj.course.owner),
    and Lesson (obj.module.course.owner).
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.is_staff:
            return True
        owner = _resolve_owner(obj)
        return owner == request.user


class IsEnrolledOrOwner(BasePermission):
    """
    For SAFE_METHODS: user must be enrolled in the course OR be the course owner OR admin.
    For mutating methods: course owner or admin only.

    Used on LessonViewSet to gate lesson content behind enrollment.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        owner = _resolve_owner(obj)
        if owner == request.user:
            return True
        if request.method in SAFE_METHODS:
            # Lazy import avoids circular dependency at module level
            from .models import Enrollment
            course = _resolve_course(obj)
            return (
                course is not None
                and Enrollment.objects.filter(user=request.user, course=course).exists()
            )
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_owner(obj):
    """Return the Course.owner for Course, Module, or Lesson instances."""
    if hasattr(obj, 'owner'):    # Course
        return obj.owner
    if hasattr(obj, 'course'):   # Module
        return obj.course.owner
    if hasattr(obj, 'module'):   # Lesson
        return obj.module.course.owner
    return None


def _resolve_course(obj):
    """Return the Course for Course, Module, or Lesson instances."""
    from .models import Course as CourseModel
    if isinstance(obj, CourseModel):
        return obj
    if hasattr(obj, 'course'):   # Module
        return obj.course
    if hasattr(obj, 'module'):   # Lesson
        return obj.module.course
    return None
