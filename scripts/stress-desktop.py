import os,sys,json,time,subprocess
from gi.repository import GLib
from sayall_linux.desktop import run
failures=[]
def hook(window,view,api,close):
    from sayall_linux.bluez import cached_devices
    import asyncio
    remotes=asyncio.run(cached_devices()) if os.environ.get('SAYALL_STRESS_BLUETOOTH')=='1' else []
    remote=next((d for d in remotes if d.name and '遥控' in d.name and d.details['props'].get('Paired')),None)
    started=time.monotonic()
    last_reply=[started]
    count=[0]
    def tick():
        def done(view,result,*_):
            try:
                data=json.loads(view.evaluate_javascript_finish(result).to_string())
                if not data['editor']:raise RuntimeError('editor missing')
                last_reply[0]=time.monotonic()
                count[0]+=1
                if count[0]%10==0:print('GUI heartbeat',count[0],flush=True)
                if count[0]==10:
                    window.iconify()
                    second=subprocess.run([sys.executable,'-m','sayall_linux'],timeout=5)
                    if second.returncode:raise RuntimeError('repeat launch failed')
                if count[0]==30:
                    if 'event=window_activated' not in (api.directory/'connection.log').read_text():raise RuntimeError('socket activation missing')
                    print('repeat launch activation passed',flush=True)
            except Exception as exc:
                failures.append(str(exc));close()
        view.evaluate_javascript('''(()=>{
          if(!document.querySelector('.mapping-editor'))document.querySelector('.mapping-cell:not(:disabled)')?.click();
          for(let i=0;i<50;i++) window.webkit.messageHandlers.linux.postMessage(JSON.stringify({id:100000+i,command:'get_runtime_snapshot',args:{padding:'x'.repeat(30000)}}));
          return JSON.stringify({editor:!!document.querySelector('.mapping-editor'),now:Date.now()});
        })()''',-1,None,None,None,done,None)
        if time.monotonic()-started>18:
            print('END replies:',count[0],flush=True)
            if count[0]<50:failures.append('insufficient GUI replies')
            if remote:
                print('Bluetooth state:',api.connection['phase'],'battery:',api.connection['batteryLevel'],flush=True)
                if api.connection['phase']!='ready':failures.append('Bluetooth not ready')
            close();return False
        return True
    def begin():
        view.evaluate_javascript("document.querySelector('.mapping-cell:not(:disabled)')?.click()",-1,None,None,None,None,None)
        if remote:
            view.evaluate_javascript('window.webkit.messageHandlers.linux.postMessage('+json.dumps(json.dumps(dict(id=90000,command='connect_remote',args={'deviceId':remote.address})))+')',-1,None,None,None,None,None)
        def choose():
            view.evaluate_javascript("[...document.querySelectorAll('.mapping-editor .chip')].find(b=>b.textContent.trim()==='Enter')?.click()",-1,None,None,None,None,None)
            return False
        GLib.timeout_add(300,choose)
        GLib.timeout_add(100,tick)
        return False
    GLib.timeout_add(2500,begin)
run(hook)
if failures: raise RuntimeError(';'.join(failures))
print('clean shutdown passed',flush=True)
