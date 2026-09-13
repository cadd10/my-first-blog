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
        ('A', 'AI-A(賛成派)'),
        ('B', 'AI-B(反対派)'),
    ]

    debate = models.ForeignKey(Debate, on_delete=models.CASCADE, related_name='messages')
    side = models.CharField(max_length=1, choices=SIDE_CHOICES)
    content = models.TextField(blank=True)
    offset_seconds = models.PositiveIntegerField()
    sequence = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['offset_seconds']

    def __str__(self):
        return f'[{self.side}] {self.content[:20]}'
