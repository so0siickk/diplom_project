from django.contrib import admin
from .models import Assignment, Course, Module, Lesson


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'owner', 'created_at']


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'order']
    list_filter = ['course']


class AssignmentInline(admin.TabularInline):
    model = Assignment
    extra = 1
    fields = ['order', 'title', 'assignment_type', 'max_score', 'description']
    ordering = ['order']


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ['title', 'module', 'order']
    list_filter = ['module__course']
    inlines = [AssignmentInline]


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'lesson', 'assignment_type', 'max_score', 'order']
    list_filter = ['assignment_type', 'lesson__module__course']
    search_fields = ['title', 'lesson__title']
