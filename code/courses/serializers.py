from rest_framework import serializers
from .models import Course, Module, Lesson


# ---------------------------------------------------------------------------
# READ serializers — deeply nested, used for GET list/detail
# ---------------------------------------------------------------------------

class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ['id', 'title', 'content', 'video_url', 'order']


class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ['id', 'title', 'description', 'order', 'lessons']


class CourseSerializer(serializers.ModelSerializer):
    owner = serializers.CharField(source='owner.username', read_only=True)
    modules = ModuleSerializer(many=True, read_only=True)
    is_enrolled = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ['id', 'title', 'description', 'owner', 'created_at', 'modules', 'is_enrolled']

    def get_is_enrolled(self, obj) -> bool:
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        user = request.user
        # Owners and admins always have full access — no enrollment needed
        if user.is_staff or obj.owner_id == user.pk:
            return True
        return obj.enrollments.filter(user=user).exists()


# ---------------------------------------------------------------------------
# WRITE serializers — flat, used for POST / PUT / PATCH
# ---------------------------------------------------------------------------

class CourseWriteSerializer(serializers.ModelSerializer):
    """
    POST /api/v1/courses/
    { "title": "...", "description": "..." }
    owner is set automatically from request.user in perform_create.
    """
    class Meta:
        model = Course
        fields = ['id', 'title', 'description']
        read_only_fields = ['id']


class ModuleWriteSerializer(serializers.ModelSerializer):
    """
    POST /api/v1/modules/
    { "course": 1, "title": "...", "description": "...", "order": 1 }
    """
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all())

    class Meta:
        model = Module
        fields = ['id', 'course', 'title', 'description', 'order']
        read_only_fields = ['id']


class LessonWriteSerializer(serializers.ModelSerializer):
    """
    POST /api/v1/lessons/
    { "module": 3, "title": "...", "content": "...", "video_url": null, "order": 1 }
    """
    module = serializers.PrimaryKeyRelatedField(queryset=Module.objects.select_related('course'))

    class Meta:
        model = Lesson
        fields = ['id', 'module', 'title', 'content', 'video_url', 'order']
        read_only_fields = ['id']
