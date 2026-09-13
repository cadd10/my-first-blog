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
    """Return everything generated so far, generating one more turn if needed.

    Turns are no longer paced against a fixed wall-clock schedule - local
    LLM generation speed varies wildly by hardware/model, and a strict
    per-turn time slot meant a slow model could burn through the whole
    quiz duration on just the first question. Instead, each poll advances
    the quiz by generating the single next pending turn (if any), so the
    quiz always finishes once every turn has content, however long that
    takes - `duration_seconds` is only a display hint for the countdown.
    """
    debate = get_object_or_404(Debate, pk=pk)
    elapsed = (timezone.now() - debate.created_date).total_seconds()

    all_messages = list(debate.messages.order_by('sequence'))
    next_pending = next((m for m in all_messages if not m.content), None)
    if next_pending is not None:
        debate_engine.ensure_generated(next_pending)

    finished = all(m.content for m in all_messages)
    visible_messages = [m for m in all_messages if m.content]
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
            for message in visible_messages
        ],
        'summary': summary,
    })
