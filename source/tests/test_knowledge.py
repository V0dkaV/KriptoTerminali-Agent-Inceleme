import asyncio
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from engine.knowledge import CARDS, SOURCES, VERSION, history_context, library_snapshot, research_context
from engine.local_ai import Experiment, LocalAI
from engine.agents import run_cycle


def test_reviewed_library_has_resolvable_primary_sources_and_no_mutable_leak():
    sources = {s['id'] for s in SOURCES}
    assert len({c['id'] for c in CARDS}) == len(CARDS)
    assert all(c['source_ids'] and set(c['source_ids']) <= sources for c in CARDS)
    assert all(s['url'].startswith('https://') for s in SOURCES)
    view = library_snapshot()
    view['cards'][0]['name'] = 'changed'
    view['sources'][0]['title'] = 'changed'
    assert library_snapshot()['cards'][0]['name'] != 'changed'
    assert library_snapshot()['sources'][0]['title'] != 'changed'


def test_bounded_rotation_reaches_entire_library_without_enabling_research_methods():
    seen = set()
    for cycle in range(35):
        context = research_context(cycle * 21600)
        assert len(context['cards']) == 5
        assert len(json.dumps(context)) < 2400
        seen.update(c['id'] for c in context['cards'])
    assert seen == {c['id'] for c in CARDS}
    for c in CARDS:
        if c['status'] != 'adaptive':
            with pytest.raises(ValidationError):
                Experiment(strategy='intraday', venue='Binance', symbol='BTCUSDT', market='spot',
                           methods=[c['id']], minimum_score=.5, hypothesis='A measurable, bounded paper experiment.')


def test_history_context_uses_recent_real_requested_history_only():
    records = [dict(symbol='BTCUSDT',venue='Binance',market='spot',months=12,interval='1d',
                    source=source,observed=observed,coverage={'status':'partial'},
                    summary=dict(trend='mixed',return_pct=4,max_drawdown_pct=10,as_of=99999,limitations=['Eksik veri']))
               for source,observed in [('PAPER',1),('DEMO',99999),('PAPER',99998)]]
    service = SimpleNamespace(latest_summaries=lambda: records)
    result = history_context(service,100000)
    assert len(result) == 1 and result[0]['coverage'] == 'partial'
    assert result[0]['limitations'] == ['Eksik veri']
    assert history_context(None) == []


def test_actual_coordinator_passes_knowledge_and_audits_context_without_orders():
    class Store:
        def __init__(self): self.values = {}
        def get(self,key,default=None): return self.values.get(key,default)
        def set(self,key,value): self.values[key] = value
    class AI:
        disabled = False
        def infer(self,payload):
            self.payload = payload
            return dict(summary='Kaynak kartlarıyla sınırlı araştırma değerlendirmesi.',events=[],knowledge_ids=[payload['knowledge']['cards'][0]['id']],
                        experiment=dict(strategy='intraday',venue='Binance',symbol='BTCUSDT',market='spot',
                                        methods=['breakout'],minimum_score=.5,hypothesis='Mevcut kırılım yöntemini maliyetli bağımsız dönemde karşılaştır.'))
    engine = SimpleNamespace(ai_cycle_lock=asyncio.Lock(),lock=asyncio.Lock(),news=[],controllers={},
             store=Store(),local_ai=AI(),settings=SimpleNamespace(local_ai_enabled=True,local_ai_research=False,allowlist=['BTCUSDT']),
             audit=lambda *args:None)
    asyncio.run(run_cycle(engine))
    assert engine.local_ai.payload['knowledge']['version'] == VERSION
    assert engine.local_ai.payload['requested_history'] == []
    assert engine.ai_report['knowledge']['card_ids']
    assert engine.store.get('local_ai_report')['knowledge']['version'] == VERSION
    assert not engine.store.get('local_ai_experiments')


def test_local_model_rejects_invented_knowledge_citations(tmp_path,monkeypatch):
    ai = LocalAI(tmp_path)
    ai.url = 'http://127.0.0.1:1'
    monkeypatch.setattr(ai,'ensure_ready',lambda:None)
    answer = dict(summary='Kaynaklı araştırma önerisinin yeterince uzun özeti.',events=[],knowledge_ids=['invented'],
                  experiment=dict(strategy='intraday',venue='Binance',symbol='BTCUSDT',market='spot',methods=['breakout'],minimum_score=.5,
                                  hypothesis='Kırılım yöntemini ayrı dönemde maliyetli karşılaştır.'))
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self,*args):
            return json.dumps(dict(choices=[dict(finish_reason='stop',message=dict(content=json.dumps(answer)))])).encode()
    monkeypatch.setattr('urllib.request.urlopen',lambda *args,**kwargs:Response())
    with pytest.raises(ValueError,match='yöntem kaynağı'):
        ai.infer(dict(events=[],knowledge=research_context(0)))
    assert not ai.busy
