from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICE = (
        ('student', 'Студент'),
        ('teacher', 'Преподаватель')
    )

    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICE,
        default='student',
        verbose_name='Роль'
    )

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"