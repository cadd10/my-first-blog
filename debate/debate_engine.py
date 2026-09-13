import random

from . import llm_client
from .models import DebateMessage

STANCE_LABELS = {'A': '賛成', 'B': '反対'}
SIDE_LABELS = {'A': 'AI-A(賛成派)', 'B': 'AI-B(反対派)'}

# Fallback phrasing used only when the local LLM server is unreachable.
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

TOTAL_TURNS = 12  # opening x2 + 4 rebuttal rounds x2 + closing x2


def schedule_turns(debate):
    """Create the empty turn schedule (side + timing) for a debate.

    Message content is intentionally left blank here and filled in later by
    `ensure_generated`, once real time reaches each turn's offset - that way
    creating a debate stays instant even though generating a turn means a
    live call to the local LLM server.
    """
    sides = []
    for _ in range(TOTAL_TURNS // 2):
        sides.append('A')
        sides.append('B')

    step = debate.duration_seconds / max(len(sides) - 1, 1)
    messages = []
    for i, side in enumerate(sides):
        offset = min(int(round(i * step)), max(debate.duration_seconds - 1, 0))
        messages.append(DebateMessage(debate=debate, side=side, content='', offset_seconds=offset, sequence=i))
    DebateMessage.objects.bulk_create(messages)


def _phase(sequence, total):
    if sequence <= 1:
        return 'opening'
    if sequence >= total - 2:
        return 'closing'
    return 'rebuttal'


def _fallback_turn(theme, side, phase):
    pool = PRO_REASONS if side == 'A' else CON_REASONS
    reason = random.choice(pool)
    stance = STANCE_LABELS[side]
    if phase == 'opening':
        return f'私は「{theme}」について{stance}の立場です。{reason}という点で、大きな意味があると考えます。'
    if phase == 'closing':
        return f'以上の議論を踏まえ、私は改めて「{theme}」に{stance}します。特に{reason}という点を強調して、議論を締めくくります。'
    return f'そのご意見も理解できますが、それでも{reason}という理由から、私はやはり{stance}の立場です。'


def _fallback_summary(theme):
    return (
        f'テーマ「{theme}」について、AI同士が議論を行いました。\n\n'
        '双方に説得力のある論点があり、立場によって評価が分かれる、一長一短のテーマであると言えるでしょう。'
    )


def _build_transcript(messages):
    lines = [f'{SIDE_LABELS[m.side]}: {m.content}' for m in messages if m.content]
    return '\n'.join(lines)


def ensure_generated(message):
    """Fill in a scheduled message's content, generating it now if needed."""
    if message.content:
        return message.content

    debate = message.debate
    phase = _phase(message.sequence, TOTAL_TURNS)
    stance = STANCE_LABELS[message.side]
    prior_messages = debate.messages.filter(sequence__lt=message.sequence).order_by('sequence')
    transcript = _build_transcript(prior_messages)

    system_prompt = (
        f'あなたはディベートAIです。テーマ「{debate.theme}」について{stance}の立場を最後まで貫いてください。'
        '相手の発言があれば具体的に踏まえて反応し、日本語で2〜3文程度の簡潔な発言だけを出力してください。'
        '前置きや自己紹介、相手の発言の引用は不要です。'
    )
    if phase == 'opening':
        instruction = 'これはあなたの最初の発言です。テーマに対するあなたの意見を述べてください。'
    elif phase == 'closing':
        instruction = 'これが最後の発言です。これまでの議論を踏まえて、簡潔に締めくくってください。'
    else:
        instruction = '相手の直前の発言に反論しつつ、あなたの立場を維持してください。'

    user_prompt = (f'これまでの議論:\n{transcript}\n\n' if transcript else '') + instruction

    try:
        content = llm_client.chat(system_prompt, user_prompt)
        if not content:
            raise llm_client.LLMUnavailable('empty response')
    except llm_client.LLMUnavailable:
        content = _fallback_turn(debate.theme, message.side, phase)

    message.content = content
    message.save(update_fields=['content'])
    return content


def ensure_summary(debate):
    if debate.summary:
        return debate.summary

    all_messages = debate.messages.order_by('sequence')
    transcript = _build_transcript(all_messages)

    system_prompt = (
        f'あなたは公平なモデレーターです。以下は「{debate.theme}」というテーマについて、'
        '賛成派(AI-A)と反対派(AI-B)が行った議論の全文です。'
    )
    user_prompt = (
        f'{transcript}\n\n'
        '両者の主張の要点をそれぞれ2〜3行でまとめ、最後に中立的な結論を1〜2行加えてください。'
        '日本語で、見出しや箇条書き記号は使わず、自然な文章でまとめてください。'
    )

    try:
        summary = llm_client.chat(system_prompt, user_prompt, max_tokens=400)
        if not summary:
            raise llm_client.LLMUnavailable('empty summary')
    except llm_client.LLMUnavailable:
        summary = _fallback_summary(debate.theme)

    debate.summary = summary
    debate.save(update_fields=['summary'])
    return summary
