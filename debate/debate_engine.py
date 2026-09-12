import random

from .models import DebateMessage

PRO_REASONS = [
    '多くの人にとって利便性が向上する',
    '長期的に見て社会全体の利益になる',
    '実際に多くの成功事例が存在する',
    'コストよりも得られる価値の方が大きい',
    '変化を恐れず新しい可能性を追求すべきだ',
    '現状の課題を解決する有効な手段になる',
]

CON_REASONS = [
    '見落とされがちなリスクが存在する',
    '全ての人に平等に恩恵があるとは限らない',
    '拙速に進めると思わぬ弊害を生む可能性がある',
    '代替となる手段の方がリスクが低い',
    '短期的な利益に惑わされるべきではない',
    '慎重な検討がまだ不十分だ',
]

REBUTTAL_ROUNDS = 4


def _pick(pool, used):
    available = [item for item in pool if item not in used]
    if not available:
        available = list(pool)
    choice = random.choice(available)
    used.add(choice)
    return choice


def _build_turns(theme):
    used_pro, used_con = set(), set()
    pro_open = _pick(PRO_REASONS, used_pro)
    con_open = _pick(CON_REASONS, used_con)

    turns = [
        ('A', f'私は「{theme}」について賛成の立場です。{pro_open}という点で、大きなメリットがあると考えます。'),
        ('B', f'私は「{theme}」について反対の立場です。{con_open}という点を懸念しています。'),
    ]

    for _ in range(REBUTTAL_ROUNDS):
        pro_reason = _pick(PRO_REASONS, used_pro)
        con_reason = _pick(CON_REASONS, used_con)
        turns.append(('A', f'たしかにそのご指摘も一理ありますが、それでも{pro_reason}という理由から、私は賛成の立場を維持します。'))
        turns.append(('B', f'そのお考えは理解できますが、{con_reason}という点から、私はやはり反対の立場です。'))

    pro_close = _pick(PRO_REASONS, used_pro)
    con_close = _pick(CON_REASONS, used_con)
    turns.append(('A', f'以上の議論を踏まえ、私は改めて「{theme}」に賛成します。特に{pro_close}という点を強調して、議論を締めくくります。'))
    turns.append(('B', f'様々な意見が出ましたが、私はやはり「{theme}」には反対です。とりわけ{con_close}という点を重く見るべきだと考えます。'))

    return turns, pro_open, pro_close, con_open, con_close


def generate_debate(debate):
    """Pre-generate a full debate transcript and summary for the given Debate.

    The whole exchange is created up front and spread across
    ``debate.duration_seconds`` via each message's ``offset_seconds``; the
    frontend reveals messages as real time passes to simulate a live debate.
    """
    theme = debate.theme
    duration = debate.duration_seconds

    turns, pro_open, pro_close, con_open, con_close = _build_turns(theme)

    step = duration / max(len(turns) - 1, 1)
    messages = []
    for i, (side, content) in enumerate(turns):
        offset = min(int(round(i * step)), max(duration - 1, 0))
        messages.append(DebateMessage(debate=debate, side=side, content=content, offset_seconds=offset))
    DebateMessage.objects.bulk_create(messages)

    debate.summary = (
        f'テーマ「{theme}」について、AI同士が議論を行いました。\n\n'
        f'AI-A(賛成派)は「{pro_open}」「{pro_close}」といった理由から、一貫して賛成の立場を取りました。\n'
        f'AI-B(反対派)は「{con_open}」「{con_close}」といった理由から、一貫して反対の立場を取りました。\n\n'
        f'双方に説得力のある論点があり、「{theme}」については立場によって評価が分かれる、'
        f'一長一短のテーマであると言えるでしょう。'
    )
    debate.save()
