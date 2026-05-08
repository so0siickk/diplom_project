from django.contrib import admin

from .models import AIEvaluation, AssignmentSubmission, CodeSubmission, EssaySubmission, OpenAssignment


class SubmissionInline(admin.TabularInline):
    model = AssignmentSubmission
    extra = 0
    readonly_fields = ("student", "submitted_at", "status", "final_score")
    fields = ("student", "submitted_at", "status", "final_score")
    show_change_link = True


@admin.register(OpenAssignment)
class OpenAssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "created_by", "lesson", "max_score", "is_active", "created_at")
    list_filter = ("is_active", "created_by")
    search_fields = ("title", "description")
    raw_id_fields = ("lesson", "created_by")
    inlines = [SubmissionInline]


class AIEvaluationInline(admin.StackedInline):
    model = AIEvaluation
    extra = 0
    readonly_fields = ("score", "feedback", "model_name", "evaluated_at")
    can_delete = False


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "student", "assignment", "status", "final_score", "submitted_at"
    )
    list_filter = ("status", "assignment__created_by")
    search_fields = ("student__username", "assignment__title")
    raw_id_fields = ("student", "assignment")
    readonly_fields = ("submitted_at",)
    inlines = [AIEvaluationInline]


@admin.register(AIEvaluation)
class AIEvaluationAdmin(admin.ModelAdmin):
    list_display = ("submission", "score", "model_name", "evaluated_at")
    readonly_fields = ("evaluated_at",)


@admin.register(CodeSubmission)
class CodeSubmissionAdmin(admin.ModelAdmin):
    list_display = ("uuid", "student", "assignment", "status", "score", "submitted_at")
    list_filter = ("status", "assignment__assignment_type")
    search_fields = ("student__username", "assignment__title", "uuid")
    readonly_fields = ("uuid", "submitted_at", "output", "ai_feedback", "score")
    raw_id_fields = ("student", "assignment")


@admin.register(EssaySubmission)
class EssaySubmissionAdmin(admin.ModelAdmin):
    list_display = ("student", "assignment", "score", "created_at")
    list_filter = ("assignment__assignment_type",)
    search_fields = ("student__username", "assignment__title")
    readonly_fields = ("created_at", "ai_feedback", "score")
    raw_id_fields = ("student", "assignment")
