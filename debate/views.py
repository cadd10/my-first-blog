from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from . import debate_engine
from .models import Debate


def index(request):
    if request.method == 'POST':
        theme = request.POST.get('theme', '').strip()
        if theme:
            debate = Debate.objects.create(theme=theme)
            debate_engine.schedule_turns(debate)
            return redirect('debate_detail', pk=debate.pk)

    recent_debates = Debate.objects.all()[:10]
    return render(request, 'debate/index.html', {
        'recent_debates': recent_debates,
        'total_questions': debate_engine.TOTAL_QUESTIONS,
    })


def detail(request, pk):
    debate = get_object_or_404(Debate, pk=pk)
    return render(request, 'debate/detail.html', {
        'debate': debate,
        'duration_seconds': debate.duration_seconds,
    })


def messages_api(request, pk):
    debate = get_object_or_404(Debate, pk=pk)
    elapsed = (timezone.now() - debate.created_date).total_seconds()
    elapsed = max(0, min(elapsed, debate.duration_seconds))
    finished = elapsed >= debate.duration_seconds

    due_messages = list(debate.messages.filter(offset_seconds__lte=elapsed).order_by('sequence'))
    for message in due_messages:
        if not message.content:
            debate_engine.ensure_generated(message)

    summary = debate_engine.ensure_summary(debate) if finished else ''

    return JsonResponse({
        'elapsed': elapsed,
        'duration': debate.duration_seconds,
        'finished': finished,
        'messages': [
            {
                'sequence': message.sequence,
                'side': message.side,
                'side_label': message.get_side_display(),
                'turn_type': message.turn_type,
                'turn_type_label': message.get_turn_type_display(),
                'content': message.content,
                'is_correct': message.is_correct,
                'offset_seconds': message.offset_seconds,
            }
            for message in due_messages
        ],
        'summary': summary,
    })
