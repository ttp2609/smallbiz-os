"""Integration example — deliberately contains NO AI model or generated reply.

Run after signing in to UI > AI Integration > copy business token:
  export SMALLBIZ_AI_TOKEN='...'
  python examples/external_ai_adapter.py

This example READS pending messages only. Implement your own AI service separately.
"""
import json
import os
import urllib.request

BASE = os.environ.get('SMALLBIZ_URL', 'http://127.0.0.1:8000')
TOKEN = os.environ.get('SMALLBIZ_AI_TOKEN', '')


def request(path, payload=None):
    headers = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=body, headers=headers,
                                 method='POST' if payload is not None else 'GET')
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)


def get_pending_messages():
    return request('/api/integrations/ai/inbox')


def get_context(conversation_id):
    return request(f'/api/integrations/ai/context/{conversation_id}')


def send_reply(conversation_id, inbound_message_id, reply_text):
    """Call ONLY after your separate AI agent generated and approved a reply."""
    return request('/api/integrations/ai/reply', {
        'conversation_id': conversation_id,
        'inbound_message_id': inbound_message_id,
        'reply': reply_text,
    })


def main():
    if not TOKEN:
        raise SystemExit('Set SMALLBIZ_AI_TOKEN from the owner-only AI Integration page')
    pending = get_pending_messages()
    print(f'Pending external AI jobs: {len(pending)}')
    for item in pending:
        ctx = get_context(item['conversation_id'])
        print(json.dumps({
            'message_id': item['message_id'],
            'conversation_id': item['conversation_id'],
            'business': ctx['business']['name'],
            'contact': item['contact_name'],
            'inbound_text': item['body'],
            'knowledge_count': len(ctx['knowledge']),
        }, ensure_ascii=False, indent=2))
    print('No AI response generated or sent. Add your agent logic to call send_reply(...).')


if __name__ == '__main__':
    main()
