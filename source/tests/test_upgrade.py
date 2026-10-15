from engine.core import Engine


def test_v02_account_survives_learning_upgrade(tmp_path):
    old=Engine(tmp_path)
    settings=old.settings.model_dump()
    for key in ('local_ai_enabled','local_ai_news_controls','local_ai_research'):settings.pop(key)
    settings['paper_balance']=1000
    old.store.set('settings',settings)
    account=old.new_state('PAPER')
    account.update(initial=1000,peak=1000,day_equity=1000,running=True,
                   wallets={key:250 for key in account['wallets']},
                   learning={'old':dict(status='observing',samples=100,score=.5)})
    old.store.set('state:PAPER',account)
    old.store.set('mode','PAPER')
    old.store.audit('PAPER','entry','Preserved old audit record')
    old.store.db.close()
    upgraded=Engine(tmp_path)
    assert upgraded.equity()==1000
    assert upgraded.state['initial']==1000 and not upgraded.state['running']
    assert upgraded.state['learning']['old']['samples']==100
    assert upgraded.store.audit_list('PAPER')[0]['message']=='Preserved old audit record'
    assert upgraded.settings.local_ai_enabled
