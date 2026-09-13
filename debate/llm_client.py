import json
import os
import urllib.error
import urllib.request

LM_STUDIO_BASE_URL = os.environ.get('LM_STUDIO_BASE_URL', 'http://localhost:1234/v1')
LM_STUDIO_MODEL = os.environ.get('LM_STUDIO_MODEL', 'local-model')
REQUEST_TIMEOUT_SECONDS = int(os.environ.get('LM_STUDIO_TIMEOUT_SECONDS', '90'))


class LLMUnavailable(Exception):
    """Raised when the local LLM server can't be reached or returns garbage."""


def chat(system_prompt, user_prompt, max_tokens=200, temperature=0.8):
    """Send one chat request to a local OpenAI-compatible server (LM Studio).

    Falls back to raising LLMUnavailable on any network or shape error so
    callers can substitute template text instead of breaking the debate.
    """
    url = f"{LM_STUDIO_BASE_URL.rstrip('/')}/chat/completions"
    payload = {
        'model': LM_STUDIO_MODEL,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        'temperature': temperature,
        'max_tokens': max_tokens,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise LLMUnavailable(f'could not reach local LLM server at {url}: {exc}') from exc

    try:
        return body['choices'][0]['message']['content'].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMUnavailable(f'unexpected response shape from local LLM server: {body}') from exc
