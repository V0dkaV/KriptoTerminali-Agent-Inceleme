import json

import pytest

from engine.grounding import BLOCKED_ANSWER, conversation_grounding, grounded_conversation
from engine.local_ai import LocalAI


@pytest.mark.parametrize('answer', [
    'Bakiyenin %10 kadarıyla marjin kullanmanı öneririm.',
    'Kaldıracı 5x seçebilirsin.',
    'Başlangıç için 100 USDT ayır.',
    'Bitcoin fiyatı 80000 dolar.',
    'Başarı ihtimali 0,85.',
    'Yüzde on risk uygundur.',
    'Beş kat kaldıraç uygundur.',
    'Yüz dolar ile başlayalım.',
    'Yüz dolarlık pozisyon açabilirsin.',
    'Paranın yarısını kullan.',
    'Tüm parayla pozisyon dene.',
    'Use five times leverage.',
    'Use ten percent of your account.',
    'Use half your capital.',
    'Sermayenin onda birini kullan.',
    'Riski ５x kaldıraçla artır.',
    'Kesin kâr elde edebilirsin.',
    'Garantili kazanç sağlar.',
    'Kâr garantisi veriyorum.',
    'You should buy BTC.',
    'BTC almalısın.',
    'Kaldıracı artır.',
    'Kaldıracını artırmanı öneririm.',
    'BTC al.',
    'İşlemini açtım ve stopunu değiştirdim.',
])
def test_unsupported_financial_claims_are_replaced(answer):
    result = grounded_conversation(answer, ['trend-200'], facts_at=1234)
    assert result['answer'] == BLOCKED_ANSWER
    assert result['knowledge_ids'] == []
    assert result['grounding']['status'] == 'blocked'
    assert result['grounding']['reasons']
    assert result['grounding']['facts_at'] == 1234


@pytest.mark.parametrize('answer', [
    'Trend filtresi ile kanal kırılımı birlikte incelenebilir. Kâr garantisi yoktur.',
    'Bir yöntem kartını açıklayabilirim; somut işlem için planı incelemek gerekir.',
    'Qwen3-4B yerel çalışır. Ön eğitim ağırlıkları burada değişmez.',
    'Qwen3 4B Q4_K_M yerel modeldir.',
    'trend-200 kaynak kartı bir araştırma yöntemini anlatır.',
    'Hesap durumunu kayıt ekranından kontrol edebilirsin. Emir yetkim yok.',
])
def test_qualitative_explanations_and_exact_identity_references_remain(answer):
    result = grounded_conversation(answer, ['trend-200'])
    assert result['answer'] == answer
    assert result['knowledge_ids'] == ['trend-200']
    assert result['grounding']['status'] == 'qualitative'
    assert not result['grounding']['reasons']


def test_matching_an_input_number_does_not_validate_its_meaning():
    # Even if a balance is known, inferring an allocation from that number is unsafe.
    assert conversation_grounding('100 USDT ile bir emir aç.')['status'] == 'blocked'
    assert conversation_grounding('trend-2000 kaynağı uygundur.', ['trend-200'])['status'] == 'blocked'


@pytest.mark.parametrize('answer,blocked', [
    ('Bakiyenin %10 kadarını ayır.', True),
    ('Trend yöntemlerini kaynak kartlarıyla açıklayabilirim.', False),
])
def test_actual_converse_applies_guard_after_schema_validation(tmp_path, monkeypatch, answer, blocked):
    model = LocalAI(tmp_path)
    monkeypatch.setattr(model, 'ensure_ready', lambda: None)
    model.url = 'http://127.0.0.1:1234'

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, limit):
            return json.dumps({'choices': [{'finish_reason': 'stop', 'message': {
                'content': json.dumps({'answer': answer, 'knowledge_ids': ['trend-200']})
            }}]}).encode()

    requests = []
    def respond(request, timeout):
        requests.append(json.loads(request.data))
        return Response()

    monkeypatch.setattr('engine.local_ai.urllib.request.urlopen', respond)
    result = model.converse({'facts': {'observed': 1234, 'balance': 100},
                             'knowledge': {'cards': [{'id': 'trend-200'}]}})
    assert result['grounding']['status'] == ('blocked' if blocked else 'qualitative')
    assert result['answer'] == (BLOCKED_ANSWER if blocked else answer)
    assert result['grounding']['facts_at'] == 1234
    assert not model.busy
    assert len(requests) == 1
    assert 'yalnız nitel' in requests[0]['messages'][0]['content']


def test_unknown_source_still_rejected_before_guard(tmp_path, monkeypatch):
    model = LocalAI(tmp_path)
    monkeypatch.setattr(model, 'ensure_ready', lambda: None)
    model.url = 'http://127.0.0.1:1234'

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, limit):
            return json.dumps({'choices': [{'finish_reason': 'stop', 'message': {
                'content': json.dumps({'answer': 'trend-200 açıklaması.', 'knowledge_ids': ['trend-200']})
            }}]}).encode()

    monkeypatch.setattr('engine.local_ai.urllib.request.urlopen', lambda *args, **kwargs: Response())
    with pytest.raises(ValueError, match='Bilinmeyen'):
        model.converse({'knowledge': {'cards': []}})
    assert not model.busy
