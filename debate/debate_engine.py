import random

from . import llm_client
from .models import DebateMessage

SIDE_LABELS = {'A': 'AI-A(出題者)', 'B': 'AI-B(回答者)'}

# Fallback phrasing used only when the local LLM server is unreachable.
FALLBACK_QUESTION_TEMPLATES = [
    '「{theme}」について、代表的な特徴を1つ挙げてください。',
    '「{theme}」に関連する用語を1つ説明してください。',
    '「{theme}」について、多くの人が誤解しがちなポイントは何でしょうか?',
]

TOTAL_QUESTIONS = 4
TURNS_PER_QUESTION = 3  # question -> answer -> verdict
TOTAL_TURNS = TOTAL_QUESTIONS * TURNS_PER_QUESTION


def schedule_turns(debate):
    """Create the empty turn schedule (side/type + timing) for a quiz.

    Message content is intentionally left blank here and filled in later by
    `ensure_generated`, once real time reaches each turn's offset - that way
    creating a quiz stays instant even though generating a turn means a live
    call to the local LLM server.
    """
    turns = []
    for _ in range(TOTAL_QUESTIONS):
        turns.append(('A', 'question'))
        turns.append(('B', 'answer'))
        turns.append(('A', 'verdict'))

    step = debate.duration_seconds / max(len(turns) - 1, 1)
    messages = []
    for i, (side, turn_type) in enumerate(turns):
        offset = min(int(round(i * step)), max(debate.duration_seconds - 1, 0))
        messages.append(DebateMessage(
            debate=debate, side=side, turn_type=turn_type,
            content='', offset_seconds=offset, sequence=i,
        ))
    DebateMessage.objects.bulk_create(messages)


def _group_sequences(sequence):
    q_index = sequence // TURNS_PER_QUESTION
    base = q_index * TURNS_PER_QUESTION
    return q_index, base, base + 1, base + 2


def _fallback_question(theme):
    template = random.choice(FALLBACK_QUESTION_TEMPLATES)
    return template.format(theme=theme)


def _fallback_answer():
    return '(ローカルAIサーバーに接続できなかったため、サンプル回答です)テーマに関する一般的な知識をもとにお答えします。'


def _fallback_verdict():
    return 'ローカルAIサーバーに接続できなかったため、正誤判定はスキップされました。', None


def _generate_question(debate, message):
    q_index, _, _, _ = _group_sequences(message.sequence)
    prior_questions = list(
        debate.messages.filter(turn_type='question', sequence__lt=message.sequence)
        .order_by('sequence').values_list('content', flat=True)
    )
    system_prompt = (
        'あなたはクイズ出題者AIです。日本語で一問一答形式のクイズを1問だけ出題してください。'
        '問題文だけを簡潔に出力し、解答や解説は書かないでください。選択肢も不要です。'
    )
    user_prompt = f'テーマ「{debate.theme}」に関するクイズを出してください。これは第{q_index + 1}問目です。'
    if prior_questions:
        prior_list = '\n'.join(f'- {q}' for q in prior_questions)
        user_prompt += f'\n\nこれまでに出した問題(重複しないようにしてください):\n{prior_list}'

    try:
        content = llm_client.chat(system_prompt, user_prompt)
        if not content:
            raise llm_client.LLMUnavailable('empty response')
    except llm_client.LLMUnavailable as exc:
        print(f'[debate] question generation fell back to template: {exc}')
        content = _fallback_question(debate.theme)

    message.content = content
    message.save(update_fields=['content'])
    return content


def _generate_answer(debate, message):
    _, q_seq, _, _ = _group_sequences(message.sequence)
    question_message = debate.messages.get(sequence=q_seq)
    question_text = question_message.content or ensure_generated(question_message)

    system_prompt = (
        'あなたはクイズ回答者AIです。出題されたクイズに対して、自分の知識をもとに答えを1つ、'
        '日本語で簡潔に述べてください。わからない場合は推測でも構いません。'
    )
    user_prompt = f'問題: {question_text}'

    try:
        content = llm_client.chat(system_prompt, user_prompt)
        if not content:
            raise llm_client.LLMUnavailable('empty response')
    except llm_client.LLMUnavailable as exc:
        print(f'[debate] answer generation fell back to template: {exc}')
        content = _fallback_answer()

    message.content = content
    message.save(update_fields=['content'])
    return content


def _generate_verdict(debate, message):
    _, q_seq, a_seq, _ = _group_sequences(message.sequence)
    question_message = debate.messages.get(sequence=q_seq)
    answer_message = debate.messages.get(sequence=a_seq)
    question_text = question_message.content or ensure_generated(question_message)
    answer_text = answer_message.content or ensure_generated(answer_message)

    system_prompt = (
        'あなたはクイズ出題者AIです。回答者の答えが正しいかどうかを判定してください。'
        '1行目に「正解」または「不正解」のどちらかだけを書き、2行目以降で正しい答えを短く説明してください。'
    )
    user_prompt = f'問題: {question_text}\n回答者の答え: {answer_text}'

    try:
        raw = llm_client.chat(system_prompt, user_prompt, max_tokens=800)
        if not raw:
            raise llm_client.LLMUnavailable('empty response')
        first_line, _, _ = raw.partition('\n')
        if '不正解' in first_line:
            is_correct = False
        elif '正解' in first_line:
            is_correct = True
        else:
            is_correct = None
        content = raw
    except llm_client.LLMUnavailable as exc:
        print(f'[debate] verdict generation fell back to template: {exc}')
        content, is_correct = _fallback_verdict()

    message.content = content
    message.is_correct = is_correct
    message.save(update_fields=['content', 'is_correct'])
    return content


def ensure_generated(message):
    """Fill in a scheduled message's content, generating it now if needed."""
    if message.content:
        return message.content

    debate = message.debate
    if message.turn_type == 'question':
        return _generate_question(debate, message)
    if message.turn_type == 'answer':
        return _generate_answer(debate, message)
    return _generate_verdict(debate, message)


def ensure_summary(debate):
    if debate.summary:
        return debate.summary

    questions = list(debate.messages.filter(turn_type='question').order_by('sequence'))
    verdicts = list(debate.messages.filter(turn_type='verdict').order_by('sequence'))

    graded = [v for v in verdicts if v.is_correct is not None]
    correct_count = sum(1 for v in graded if v.is_correct)

    lines = []
    if graded:
        lines.append(f'クイズ結果: 全{len(questions)}問中 {correct_count}問正解でした。')
    else:
        lines.append(f'クイズ結果: 全{len(questions)}問。')
    lines.append('')

    for i, question in enumerate(questions):
        verdict = verdicts[i] if i < len(verdicts) else None
        if verdict is None or verdict.is_correct is None:
            mark = '?'
        elif verdict.is_correct:
            mark = '○'
        else:
            mark = '×'
        lines.append(f'{mark} 第{i + 1}問: {question.content}')

    summary = '\n'.join(lines)
    debate.summary = summary
    debate.save(update_fields=['summary'])
    return summary
