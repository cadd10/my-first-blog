from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .debate_engine import generate_debate
from .models import Debate


def index(request):
    if request.method == 'POST':
        theme = request.POST.get('theme', '').strip()
        if theme:
            debate = Debate.objects.create(theme=theme)
            generate_debate(debate)
            return redirect('debate_detail', pk=debate.pk)

    recent_debates = Debate.objects.all()[:10]
    return render(request, 'debate/index.html', {'recent_debates': recent_debates})


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

    visible_messages = debate.messages.filter(offset_seconds__lte=elapsed)

    return JsonResponse({
        'elapsed': elapsed,
        'duration': debate.duration_seconds,
        'finished': finished,
        'messages': [
            {
                'side': message.side,
                'side_label': message.get_side_display(),
                'content': message.content,
                'offset_seconds': message.offset_seconds,
            }
            for message in visible_messages
        ],
        'summary': debate.summary if finished else '',
    })
