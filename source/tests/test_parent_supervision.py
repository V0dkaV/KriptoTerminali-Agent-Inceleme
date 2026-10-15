"""Real isolated process tests: never control the user's installed application."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

from engine.store import Store


ROOT=Path(__file__).resolve().parents[1]
TOKEN='isolated-parent-watchdog-'+'a'*48
# Exercise the actual HTTP server, durable state and Windows lock while removing
# background internet dependencies. The optional blocking worker models an HTTP
# or DNS call that cannot be cancelled by cancelling its awaiting coroutine.
HARNESS=r'''
import asyncio,os,time
from pathlib import Path
import engine.core as core
async def idle(*args,**kwargs):
    await asyncio.Event().wait()
for name in ('prices','news_loop','scan','local_ai_loop'):
    setattr(core.Engine,name,idle)
core.listen=idle
if os.environ.get('KRIPTO_SUPERVISION_BLOCKING')=='1':
    async def blocked(self):
        def worker():
            (self.store.path/'blocking-worker-started').write_text('started')
            time.sleep(60)
        await asyncio.to_thread(worker)
    core.Engine.prices=blocked
from engine.main import main
raise SystemExit(main())
'''


def request(port,path,body=None):
    req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=2) as response:
        return json.loads(response.read())


def wait_health(port):
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        try:
            assert request(port,'/health')['ok']
            return
        except (OSError,urllib.error.URLError):
            time.sleep(.05)
    raise AssertionError('isolated engine did not become ready')


def spawn_engine(data,watch=True,blocking=False):
    proc=subprocess.Popen([sys.executable,'-c',HARNESS,'--data-dir',str(data)],
        cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
        text=True,encoding='utf-8',env={**os.environ,'KRIPTO_DISABLE_LOCAL_AI':'1','PYTHONUTF8':'1',
                                      'KRIPTO_SUPERVISION_BLOCKING':'1' if blocking else '0'})
    proc.stdin.write(json.dumps(dict(token=TOKEN,watch_parent=watch))+'\n');proc.stdin.flush()
    line=proc.stdout.readline()
    assert line.startswith('KRIPTO_READY '),line
    port=json.loads(line[13:])['port'];wait_health(port)
    return proc,port


def test_ownership_eof_stops_running_engine_saves_pause_and_releases_lock(tmp_path):
    proc,port=spawn_engine(tmp_path)
    try:
        assert request(port,'/command',dict(kind='start'))['ok']
        assert request(port,'/snapshot')['running']
        proc.stdin.close()
        assert proc.wait(timeout=25)==0
    finally:
        if proc.poll() is None:
            proc.kill();proc.wait(timeout=10)
    store=Store(tmp_path)
    try:
        assert not store.get('state:PAPER')['running']
        assert any(x['kind']=='parent_lost' for x in store.audit_list('PAPER'))
    finally:store.db.close()
    # A fresh engine must acquire the same Windows ownership lock and retain data.
    restarted,port=spawn_engine(tmp_path)
    try:
        assert not request(port,'/snapshot')['running']
        restarted.stdin.close()
        assert restarted.wait(timeout=25)==0
    finally:
        if restarted.poll() is None:restarted.kill();restarted.wait(timeout=10)


def test_standalone_callers_without_watchdog_may_close_bootstrap_pipe(tmp_path):
    proc,port=spawn_engine(tmp_path,watch=False)
    try:
        proc.stdin.close()
        time.sleep(.25)
        assert proc.poll() is None and request(port,'/health')['ok']
        assert request(port,'/shutdown',{})['ok']
        assert proc.wait(timeout=25)==0
    finally:
        if proc.poll() is None:proc.kill();proc.wait(timeout=10)


def test_normal_shutdown_does_not_wait_for_retained_parent_pipe(tmp_path):
    proc,port=spawn_engine(tmp_path)
    try:
        assert request(port,'/shutdown',{})['ok']
        assert proc.wait(timeout=25)==0
    finally:
        proc.stdin.close()
        if proc.poll() is None:proc.kill();proc.wait(timeout=10)


def test_owner_death_has_bounded_shutdown_with_uncancellable_executor_work(tmp_path):
    proc,port=spawn_engine(tmp_path,blocking=True)
    try:
        deadline=time.monotonic()+5
        while not (tmp_path/'blocking-worker-started').exists() and time.monotonic()<deadline:
            time.sleep(.05)
        assert (tmp_path/'blocking-worker-started').exists()
        assert request(port,'/command',dict(kind='start'))['ok']
        started=time.monotonic();proc.stdin.close()
        assert proc.wait(timeout=15)==0
        assert time.monotonic()-started<15
    finally:
        if proc.poll() is None:proc.kill();proc.wait(timeout=10)
    store=Store(tmp_path)
    try:
        assert not store.get('state:PAPER')['running']
        assert any(x['kind']=='parent_lost' for x in store.audit_list('PAPER'))
    finally:store.db.close()
    restarted,port=spawn_engine(tmp_path)
    try:
        assert not request(port,'/snapshot')['running']
        restarted.stdin.close();assert restarted.wait(timeout=15)==0
    finally:
        if restarted.poll() is None:restarted.kill();restarted.wait(timeout=10)


def test_retained_owner_pipe_allows_real_spawned_backtest_and_training_workers(tmp_path):
    proc,port=spawn_engine(tmp_path,watch=True)
    try:
        for kind,months in [('backtest',7),('ml',36)]:
            result=request(port,'/jobs',dict(kind=kind,strategy='intraday',symbol='BTCUSDT',
                venue='Binance',market='spot',source='DEMO',months=months,fee_bps=10,slippage_bps=3))
            assert result['ok']
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                snapshot=request(port,'/snapshot')
                job=next(j for j in snapshot['jobs'] if j['id']==result['id'])
                assert job['status']!='error',job
                if job['status']=='done':break
                time.sleep(.1)
            assert job['status']=='done',job
            report=request(port,'/report/'+result['id'])
            assert report['source']=='DEMO'
            if kind=='ml':assert report['model_sha256']
        assert not proc.stdin.closed and proc.poll() is None
        assert request(port,'/shutdown',{})['ok']
        assert proc.wait(timeout=15)==0
    finally:
        proc.stdin.close()
        if proc.poll() is None:proc.kill();proc.wait(timeout=10)


@pytest.mark.skipif(os.name!='nt',reason='Windows desktop process-ownership acceptance')
def test_abrupt_parent_death_does_not_leave_orphan_engine(tmp_path):
    helper=r'''
import subprocess,sys,json,os
p=subprocess.Popen([sys.executable,'-c',sys.argv[4],'--data-dir',sys.argv[1]],cwd=sys.argv[2],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8',env={**os.environ,'KRIPTO_DISABLE_LOCAL_AI':'1','PYTHONUTF8':'1','KRIPTO_SUPERVISION_BLOCKING':'0'})
p.stdin.write(json.dumps({'token':sys.argv[3],'watch_parent':True})+'\n');p.stdin.flush()
print(json.dumps({'pid':p.pid,'ready':p.stdout.readline().strip()}),flush=True)
sys.stdin.read(1)
os._exit(17)
'''
    parent=subprocess.Popen([sys.executable,'-c',helper,str(tmp_path),str(ROOT),TOKEN,HARNESS],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8')
    record=json.loads(parent.stdout.readline());port=json.loads(record['ready'][13:])['port']
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    kernel.WaitForSingleObject.restype=wintypes.DWORD
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x00100000,False,record['pid'])
    assert handle
    try:
        wait_health(port)
        assert request(port,'/command',dict(kind='start'))['ok']
        parent.stdin.write('x');parent.stdin.flush()
        assert parent.wait(timeout=5)==17
        assert kernel.WaitForSingleObject(handle,25000)==0
        store=Store(tmp_path)
        try:assert not store.get('state:PAPER')['running']
        finally:store.db.close()
    finally:
        if parent.poll() is None:parent.kill();parent.wait(timeout=10)
        if kernel.WaitForSingleObject(handle,0)!=0:
            try:request(port,'/shutdown',{})
            except OSError:pass
        kernel.CloseHandle(handle)
