from django.db import models
from django.utils import timezone


class Debate(models.Model):
    theme = models.CharField(max_length=200)
    created_date = models.DateTimeField(default=timezone.now)
    duration_seconds = models.PositiveIntegerField(default=180)
    summary = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_date']

    def __str__(self):
        return self.theme

    @property
    def is_finished(self):
        elapsed = (timezone.now() - self.created_date).total_seconds()
        return elapsed >= self.duration_seconds


class DebateMessage(models.Model):
    SIDE_CHOICES = [
        ('A', 'AI-A(出題者)'),
        ('B', 'AI-B(回答者)'),
    ]

    TURN_TYPE_CHOICES = [
        ('question', '出題'),
        ('answer', '回答'),
        ('verdict', '判定'),
    ]

    debate = models.ForeignKey(Debate, on_delete=models.CASCADE, related_name='messages')
    side = models.CharField(max_length=1, choices=SIDE_CHOICES)
    turn_type = models.CharField(max_length=10, choices=TURN_TYPE_CHOICES, default='question')
    content = models.TextField(blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    offset_seconds = models.PositiveIntegerField()
    sequence = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['offset_seconds']

    def __str__(self):
        return f'[{self.side}/{self.turn_type}] {self.content[:20]}'
