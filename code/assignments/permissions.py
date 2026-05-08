from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsTeacher(BasePermission):
    """Разрешает доступ только пользователям с ролью 'teacher' или staff."""

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.role == "teacher" or request.user.is_staff)
        )


class IsTeacherOrReadOnly(BasePermission):
    """
    Безопасные методы (GET, HEAD, OPTIONS) — доступны любому аутентифицированному.
    Небезопасные методы — только преподавателю или staff.
    """

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.role == "teacher" or request.user.is_staff


class IsAssignmentAuthorOrReadOnly(BasePermission):
    """
    Изменять и удалять задание может только его автор (или staff).
    Читать могут все аутентифицированные пользователи.
    """

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in SAFE_METHODS:
            return True
        return obj.created_by_id == request.user.pk or request.user.is_staff


class IsSubmissionOwnerOrTeacher(BasePermission):
    """
    Студент видит только свои ответы.
    Преподаватель и staff видят все ответы на задания своих курсов.
    """

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if user.is_staff:
            return True
        if user.role == "teacher":
            # Преподаватель может смотреть любой ответ на своё задание
            return obj.assignment.created_by_id == user.pk
        # Студент — только свой ответ
        return obj.student_id == user.pk
