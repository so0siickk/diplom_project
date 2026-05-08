"""
Heuristic risk calculator for the Instructor Dashboard.

Computes a dropout-risk score [0.05, 0.95] for every student using three signals:
  1. avg submission score  (essays + code, 0-10 scale)  weight 0.65
  2. lesson completion rate (completed / total)          weight 0.35
  3. failed code penalty   (+0.05 per FAILED record, cap +0.10)

Expected buckets:
  top students   score>8  + high completion  ->  risk 0.10-0.25
  mid students   score 4-7 + partial         ->  risk 0.40-0.60
  lagging        score<4  or few lessons      ->  risk 0.80-0.95

Results are saved to analytics.StudentRiskScore (one row per student, upsert).
The analytics service reads this table as a fallback when model.pkl is absent,
so the Instructor Dashboard shows real-looking risk scores without the ML model.

Run:
    python manage.py calculate_risks
    python manage.py calculate_risks --dry-run
    python manage.py calculate_risks --verbosity 2   # per-student output
"""
import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from analytics.models import StudentRiskScore, UserLessonProgress
from assignments.models import CodeSubmission, EssaySubmission
from courses.models import Lesson

User = get_user_model()

# ---------------------------------------------------------------------------
# Heuristic weights and tuning constants
# ---------------------------------------------------------------------------

_W_SCORE      = 0.65   # weight of normalised avg submission score
_W_COMPLETION = 0.35   # weight of lesson completion rate
_FAILED_STEP  = 0.05   # risk added per FAILED CodeSubmission
_FAILED_CAP   = 0.10   # maximum total penalty for failures
_NOISE_STD    = 0.025  # Gaussian noise std for realistic spread


# ---------------------------------------------------------------------------
# Pure heuristic function (easy to unit-test in isolation)
# ---------------------------------------------------------------------------

def compute_risk(
    avg_score: float | None,
    completion_rate: float,
    failed_code: int,
    *,
    seed: int | None = None,
) -> float:
    """
    Maps student metrics to a risk score in [0.05, 0.95].

    avg_score       -- mean submission score on a 0-10 scale; None = no submissions yet
    completion_rate -- fraction of total lessons completed (0.0-1.0)
    failed_code     -- number of CodeSubmission records with status FAILED
    seed            -- optional RNG seed for reproducible tests
    """
    if seed is not None:
        random.seed(seed)

    if avg_score is not None:
        score_signal = avg_score / 10.0
    else:
        # No submissions: neutral-negative signal (student is inactive)
        score_signal = 0.45

    base = 1.0 - _W_SCORE * score_signal - _W_COMPLETION * completion_rate
    penalty = min(_FAILED_CAP, _FAILED_STEP * failed_code)
    noise = random.gauss(0.0, _NOISE_STD)

    return round(max(0.05, min(0.95, base + penalty + noise)), 4)


# ---------------------------------------------------------------------------
# Management command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = 'Computes heuristic risk scores for all students and writes to StudentRiskScore.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Compute and print risk scores without saving to the DB.',
        )

    def handle(self, *args, **options) -> None:
        dry_run: bool = options['dry_run']
        verbose: bool = options.get('verbosity', 1) >= 2 or dry_run

        students = list(
            User.objects.filter(role='student', is_staff=False).order_by('id')
        )
        if not students:
            self.stdout.write(self.style.WARNING('No student accounts found. Aborting.'))
            return

        total_lessons = Lesson.objects.count()
        if total_lessons == 0:
            self.stdout.write(self.style.WARNING('No lessons found. Aborting.'))
            return

        self.stdout.write(
            f'Students: {len(students)} | Total lessons: {total_lessons}'
        )
        if dry_run:
            self.stdout.write('[dry-run] No data will be written to DB.')

        saved = 0
        buckets = {'top': 0, 'mid': 0, 'lag': 0}

        for student in students:
            # ----------------------------------------------------------------
            # 1. Lesson completion rate
            # ----------------------------------------------------------------
            completed_count = UserLessonProgress.objects.filter(
                user=student, is_completed=True
            ).count()
            completion_rate = completed_count / total_lessons

            # ----------------------------------------------------------------
            # 2. Average submission score (0-10)
            # ----------------------------------------------------------------
            essay_scores = list(
                EssaySubmission.objects
                .filter(student=student, score__isnull=False)
                .values_list('score', flat=True)
            )
            code_scores = list(
                CodeSubmission.objects
                .filter(student=student, score__isnull=False)
                .values_list('score', flat=True)
            )
            all_scores = essay_scores + code_scores
            avg_score: float | None = (
                sum(all_scores) / len(all_scores) if all_scores else None
            )

            # ----------------------------------------------------------------
            # 3. Failed code submissions
            # ----------------------------------------------------------------
            failed_count = CodeSubmission.objects.filter(
                student=student,
                status=CodeSubmission.Status.FAILED,
            ).count()

            # ----------------------------------------------------------------
            # 4. Heuristic score
            # ----------------------------------------------------------------
            risk = compute_risk(avg_score, completion_rate, failed_count)

            # Classify into display bucket
            if risk < 0.35:
                buckets['top'] += 1
                bucket_label = 'top'
            elif risk < 0.70:
                buckets['mid'] += 1
                bucket_label = 'mid'
            else:
                buckets['lag'] += 1
                bucket_label = 'lag'

            # ----------------------------------------------------------------
            # 5. Persist (unless dry-run)
            # ----------------------------------------------------------------
            if not dry_run:
                StudentRiskScore.objects.update_or_create(
                    user=student,
                    defaults={'risk_score': risk},
                )
                saved += 1

            if verbose:
                avg_str = f'{avg_score:.2f}' if avg_score is not None else 'n/a '
                self.stdout.write(
                    f'  {student.username:<22} '
                    f'score={avg_str}  '
                    f'comp={completion_rate:.2f}  '
                    f'failed={failed_count}  '
                    f'risk={risk:.4f}  [{bucket_label}]'
                )

        # ----------------------------------------------------------------
        # Summary
        # ----------------------------------------------------------------
        action = 'Computed (not saved)' if dry_run else 'Saved'
        self.stdout.write(
            f'{action}: {len(students)} students | '
            f'top={buckets["top"]}  '
            f'mid={buckets["mid"]}  '
            f'lag={buckets["lag"]}'
        )

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Done. {saved} StudentRiskScore records updated.'
                )
            )
