from __future__ import annotations

import argparse
import asyncio
import json
import multiprocessing
import os
import socket
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path


def wait_parent_eof(stream):
    """Poll the raw pipe without a pending synchronous stdin read.

    A blocking TextIO read on the retained Windows standard-input pipe prevents
    spawned Python workers from completing their standard-stream bootstrap.
    PeekNamedPipe does not reserve that handle while the owner is idle.
    """
    fd=stream.fileno()
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        import msvcrt
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        peek=kernel.PeekNamedPipe
        peek.argtypes=[wintypes.HANDLE,wintypes.LPVOID,wintypes.DWORD,
                       ctypes.POINTER(wintypes.DWORD),ctypes.POINTER(wintypes.DWORD),ctypes.POINTER(wintypes.DWORD)]
        peek.restype=wintypes.BOOL
        handle=msvcrt.get_osfhandle(fd)
        available=wintypes.DWORD()
        while True:
            if not peek(handle,None,0,None,ctypes.byref(available),None):
                return  # Broken/closed/invalid ownership channel: fail closed.
            if available.value:
                if not os.read(fd,min(available.value,4096)):
                    return
            time.sleep(.1)
    else:
        import select
        while True:
            readable,_,_=select.select([fd],[],[],.1)
            if readable and not os.read(fd,4096):
                return


def supervise_parent(app,server,stream):
    """The desktop retains this private pipe for the entire engine lifetime.

    A daemon reader avoids a blocking default-executor thread on normal shutdown.
    All state writes remain on the engine's event loop and under its central lock.
    """
    original_lifespan=app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with original_lifespan(application):
            loop=asyncio.get_running_loop()
            paused_durably=threading.Event()

            async def persist_and_stop():
                try:
                    async with application.state.engine.lock:
                        engine=application.state.engine
                        engine.state['running']=False
                        engine.audit('parent_lost','Masaüstü bağlantısı kapandı; yeni sanal girişler durduruldu.')
                        engine.save()
                        paused_durably.set()
                finally:
                    server.should_exit=True

            def disconnected():
                # Gate entries before waiting for the state/persistence lock.
                application.state.engine.closing=True
                application.state.engine.state['running']=False
                task=asyncio.create_task(persist_and_stop())
                task.add_done_callback(lambda value:None if value.cancelled() else value.exception())

            def watch():
                try:
                    wait_parent_eof(stream)
                except (OSError,ValueError):
                    pass
                # urllib/DNS or other default-executor work can outlive coroutine
                # cancellation. After owner death, never retain engine.lock forever.
                # Normal shutdown with the owner's pipe open does not arm this timer.
                def bound_shutdown():
                    threading.Event().wait(10)
                    os._exit(0 if paused_durably.is_set() else 4)
                threading.Thread(target=bound_shutdown,name='ownership-shutdown-deadline',daemon=True).start()
                try:
                    loop.call_soon_threadsafe(disconnected)
                except RuntimeError:
                    pass  # Normal shutdown already closed the event loop.

            threading.Thread(target=watch,name='desktop-ownership',daemon=True).start()
            yield

    app.router.lifespan_context=lifespan


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',required=True)
    args=parser.parse_args()
    Path(args.data_dir).mkdir(parents=True,exist_ok=True)
    lock=open(Path(args.data_dir)/'engine.lock','a+b')
    lock.seek(0)
    if os.name=='nt':
        import msvcrt
        try: msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:
            print('KRIPTO_ERROR motor_already_running',flush=True)
            return 2
    bootstrap=json.loads(sys.stdin.readline())
    token=bootstrap.get('token','')
    if len(token)<32: return 3
    from engine.server import create_app
    import uvicorn
    app=create_app(args.data_dir,token)
    for venue,value in bootstrap.get('credentials',{}).items():
        from engine.market import Exchange
        app.state.engine.credentials[venue]=Exchange(venue,value['key'],value['secret'],value.get('testnet',False))
        app.state.engine.connections[venue].update(status='stored',testnet=value.get('testnet',False))
    app.state.engine.telegram=bootstrap.get('telegram')
    app.state.engine.ai_key=bootstrap.get('ai')
    sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    sock.bind(('127.0.0.1',0))
    port=sock.getsockname()[1]
    print('KRIPTO_READY '+json.dumps(dict(port=port)),flush=True)
    config=uvicorn.Config(app,host='127.0.0.1',port=port,log_level='error',access_log=False)
    server=uvicorn.Server(config)
    app.state.shutdown=lambda:setattr(server,'should_exit',True)
    if bootstrap.get('watch_parent') is True:
        supervise_parent(app,server,sys.stdin)
    server.run(sockets=[sock])
    return 0


if __name__=='__main__':
    multiprocessing.freeze_support()
    if not getattr(sys,'frozen',False):
        sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
    raise SystemExit(main())
