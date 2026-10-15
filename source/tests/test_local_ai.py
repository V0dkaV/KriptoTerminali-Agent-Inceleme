from datetime import datetime,timezone
import pytest
from pydantic import ValidationError

from engine.local_ai import Experiment,Assessment,active_news_risk
from engine.adaptive import train_candidate,select
from engine.research import demo_candles


def proposal():
    return dict(strategy='intraday',venue='Binance',symbol='BTCUSDT',market='futures',
                methods=['momentum','pullback'],minimum_score=.55,hypothesis='Maliyetli değerlendirmede iki trend yöntemini karşılaştır.')


def test_ai_cannot_emit_code_orders_or_unbounded_policies():
    for change in ({'code':'delete files'},{'minimum_score':.1},{'methods':['martingale']},{'leverage':100}):
        with pytest.raises(ValidationError):Experiment.model_validate({**proposal(),**change})


@pytest.mark.parametrize('age,confidence,verification,url,expected',[
    (100,.9,'official','https://www.federalreserve.gov/test','pause'),
    (90000,.9,'official','https://www.federalreserve.gov/test','observe'),
    (100,.7,'official','https://www.federalreserve.gov/test','observe'),
    (100,.9,'publisher','https://www.federalreserve.gov/test','observe'),
    (100,.9,'official','https://example.com/test','observe')])
def test_news_influence_requires_fresh_source_and_sufficient_confidence(age,confidence,verification,url,expected):
    now=200000
    event=dict(id='event',verification=verification,url=url,
               published_at=datetime.fromtimestamp(now-age,timezone.utc).isoformat())
    report=dict(created_at=now,events=[dict(event_id='event',risk='pause',confidence=confidence,assets=['BTC'],rationale='Kaynakla bağlı test gerekçesi.')])
    assert active_news_risk(report,'BTCUSDT',[event],now)[0]==expected
    assert active_news_risk(report,'ETHUSDT',[event],now)[0]=='observe'
    assert active_news_risk(report,'BTCUSDT',[event],now+901)[0]=='observe'


def test_generated_experiment_really_changes_bounded_policy():
    rows=demo_candles(count=4000)
    baseline=train_candidate(rows,'intraday','futures')
    candidate=train_candidate(rows,'intraday','futures',proposal=proposal())
    assert candidate['policy']['methods']==['momentum','pullback']
    assert candidate['policy']['minimum_score']==.55
    assert candidate['version']!=baseline['version']
    assert select(candidate,[dict(method='reversion',features=[0.0]*19)],qualified=False) is None


def test_assessment_is_not_arbitrary_action():
    with pytest.raises(ValidationError):
        Assessment.model_validate(dict(event_id='x',risk='buy',confidence=.9,assets=['BTC'],rationale='This should never submit an order.'))
