"""Restricted remote evdev capture, gestures and Wayland-compatible uinput output."""
import asyncio
import logging
import os
from pathlib import Path

log = logging.getLogger('sayall.connection')
SUPPORTED_IDS = {(0x2717, 0x32b8)}

def configured(action):
    return isinstance(action, dict) and action.get('type') not in (None, 'disabled')

class GestureEngine:
    def __init__(self, execute, report=lambda *_: None, double_delay=.3, long_delay=.55):
        self.execute, self.report = execute, report
        self.double_delay, self.long_delay = double_delay, long_delay
        self.states = {}
        self.tasks = set()

    def spawn(self, coroutine):
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        def done(task):
            self.tasks.discard(task)
            if not task.cancelled():
                error = task.exception()
                if error: self.report('action-error', str(error))
        task.add_done_callback(done)
        return task

    def fire(self, button, state, trigger, held=False):
        action = state['actions'].get(trigger)
        if not configured(action): action = {'type':'passthrough', 'code':state['code']}
        self.execute(action, 'begin' if held else 'pulse', button)
        self.report('gesture', {'button':button,'trigger':trigger})

    def edge(self, button, code, value, actions):
        if value == 2: return
        state = self.states.get(button)
        if value == 1:
            if state and state['down']: return
            second = bool(state and state.get('single_task') and not state['single_task'].done())
            if second: state['single_task'].cancel()
            state = dict(down=True, code=code, actions=actions, second=second, long_fired=False, held=False, long_task=None, single_task=None)
            self.states[button] = state
            if not configured(actions.get('double')) and not configured(actions.get('long')):
                self.fire(button,state,'single',held=True)
                state['held'] = True
            elif configured(actions.get('long')):
                async def long_press():
                    await asyncio.sleep(self.long_delay)
                    if state['down']:
                        self.fire(button,state,'long',held=True)
                        state['held'] = state['long_fired'] = True
                state['long_task'] = self.spawn(long_press())
        elif value == 0 and state and state['down']:
            actions = state['actions']
            state['down'] = False
            if state['long_task']: state['long_task'].cancel()
            if state['held']:
                self.execute(None,'end',button)
            elif state['second'] and configured(actions.get('double')):
                self.fire(button,state,'double')
            elif configured(actions.get('double')):
                async def single_press():
                    await asyncio.sleep(self.double_delay)
                    self.fire(button,state,'single')
                state['single_task'] = self.spawn(single_press())
            else:
                self.fire(button,state,'single')

    async def close(self):
        for task in list(self.tasks): task.cancel()
        await asyncio.gather(*list(self.tasks),return_exceptions=True)
        for button,state in self.states.items():
            if state.get('held'): self.execute(None,'end',button)
        self.states.clear()

class InputController:
    def __init__(self, settings, report=lambda *_:None):
        self.settings, self.report = settings, report
        self.task = None
        self.ui = None
        self.device = None
        self.engine = None
        self.owners = {}
        self.key_counts = {}
        self.raw = dict(phase='stopped',matchedDeviceCount=0,rawEventCount=0,semanticEdgeCount=0,lastButton=None,lastIsPressed=None,activeButtons=[],lastError=None,staleRemoteEventCount=0)
        self.mapping = dict(enabled=True,gateActive=False,listenerActive=False,swallowedEdges=0,leakedDowns=0,firedGestures=0,lastFired=None,lastError=None)
        self.sent = 0

    def candidates(self):
        expected = self.settings().get('lastRemote','').lower().replace(':','')
        paths = []
        for event in Path('/sys/class/input').glob('event*'):
            root = event/'device'
            try:
                identity = (int((root/'id/vendor').read_text(),16),int((root/'id/product').read_text(),16))
                if identity not in SUPPORTED_IDS or int((root/'id/bustype').read_text(),16)!=5: continue
                unique = (root/'uniq').read_text().strip().lower().replace(':','')
                if expected and unique != expected: continue
                paths.append('/dev/input/'+event.name)
            except (OSError,ValueError): pass
        return [] if not expected and len(paths)>1 else paths

    async def start(self):
        if self.task and not self.task.done(): return self.raw.copy()
        self.raw.update(phase='starting',lastError=None)
        self.task = asyncio.create_task(self.serve())
        return self.raw.copy()

    async def stop(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task,return_exceptions=True)
            self.task = None
        self.raw.update(phase='stopped',matchedDeviceCount=0,activeButtons=[])
        self.mapping.update(listenerActive=False,gateActive=False)
        return self.raw.copy()

    def key(self, code, pressed, owner):
        from evdev import ecodes as e
        held = self.owners.setdefault(owner,[])
        if pressed and code not in held:
            held.append(code)
            count = self.key_counts.get(code,0)
            self.key_counts[code] = count+1
            if not count: self.ui.write(e.EV_KEY,code,1); self.sent+=1
        elif not pressed and code in held:
            held.remove(code)
            count = self.key_counts.get(code,0)-1
            if count<=0:
                self.key_counts.pop(code,None)
                self.ui.write(e.EV_KEY,code,0); self.sent+=1
            else:self.key_counts[code]=count
        self.ui.syn()

    def release(self,owner):
        for code in reversed(tuple(self.owners.get(owner,()))): self.key(code,False,owner)
        self.owners.pop(owner,None)

    def chord_codes(self,keys):
        from evdev import ecodes as e
        names={'control':'LEFTCTRL','left_control':'LEFTCTRL','right_control':'RIGHTCTRL','shift':'LEFTSHIFT','left_shift':'LEFTSHIFT','right_shift':'RIGHTSHIFT','alt':'LEFTALT','left_alt':'LEFTALT','right_alt':'RIGHTALT','left_windows':'LEFTMETA','right_windows':'RIGHTMETA','return':'ENTER','escape':'ESC','page_up':'PAGEUP','page_down':'PAGEDOWN','apps':'COMPOSE','volume_mute':'MUTE','volume_down':'VOLUMEDOWN','volume_up':'VOLUMEUP','media_play_pause':'PLAYPAUSE','media_next_track':'NEXTSONG','media_previous_track':'PREVIOUSSONG','media_prev':'PREVIOUSSONG','media_next':'NEXTSONG','oem_plus':'EQUAL','oem_minus':'MINUS','oem_comma':'COMMA','oem_period':'DOT','oem1':'SEMICOLON','oem2':'SLASH','oem3':'GRAVE','oem4':'LEFTBRACE','oem5':'BACKSLASH','oem6':'RIGHTBRACE','oem7':'APOSTROPHE','numpad_enter':'KPENTER','numpad_add':'KPPLUS','numpad_subtract':'KPMINUS','numpad_multiply':'KPASTERISK','numpad_divide':'KPSLASH','numpad_decimal':'KPDOT'}
        result=[]
        for key in keys:
            name = 'KEY_'+names.get(key,('KP'+key[6:]) if key.startswith('numpad') and key[6:].isdigit() else key[5:] if key.startswith('digit') and key[5:].isdigit() else key.upper())
            if name not in e.ecodes: raise ValueError('不支持的 Linux 按键：'+key)
            result.append(e.ecodes[name])
        return list(dict.fromkeys(result))

    def execute(self,action,mode,owner):
        from evdev import ecodes as e
        if mode=='end': self.release(owner); return
        kind=action.get('type')
        presets={'app_switcher':['alt','tab'],'page_up':['page_up'],'page_down':['page_down'],'scroll_to_top':['control','home'],'scroll_to_bottom':['control','end']}
        if kind in ('shortcut','passthrough') or kind in presets:
            codes=[action['code']] if kind=='passthrough' else self.chord_codes(action.get('chord',{}).get('keys',[]) if kind=='shortcut' else presets[kind])
            if not codes: return
            for code in codes:self.key(code,True,owner)
            if mode=='pulse':self.release(owner)
        elif kind=='scroll':
            self.ui.write(e.EV_REL,e.REL_WHEEL,(1 if action.get('direction')=='up' else -1)*max(1,min(20,int(action.get('steps',1)))))
            self.ui.syn()
        elif kind=='mouse_move':
            direction=action.get('direction','right')
            self.ui.write(e.EV_REL,e.REL_X if direction in ('left','right') else e.REL_Y,(1 if direction in ('right','down') else -1)*max(1,min(500,int(action.get('distance',30)))))
            self.ui.syn()
        elif kind=='mouse_click':
            code={'left':e.BTN_LEFT,'double_left':e.BTN_LEFT,'right':e.BTN_RIGHT,'middle':e.BTN_MIDDLE}.get(action.get('kind'))
            if code is None:raise ValueError('未知鼠标动作')
            for _ in range(2 if action.get('kind')=='double_left' else 1):self.key(code,True,owner);self.release(owner)
        else:raise NotImplementedError('此动作的 Linux 执行尚未实现：'+str(kind))

    def on_gesture(self,event,value):
        if event=='gesture':
            self.mapping['firedGestures']+=1
            self.mapping['lastFired']=value
            log.info('event=mapping_executed button=%s trigger=%s',value['button'],value['trigger'])
        elif event=='action-error':
            self.mapping['lastError']=value
            log.warning('event=mapping_failed reason=%s',value)
        self.report(event,value)

    def consume_voice_key(self,code,value):
        from evdev import ecodes as e
        if code!=e.KEY_F5:return False
        # This is invoked only on the selected remote's grabbed event node.
        # The remote's F5 is its microphone report, never an OS refresh key.
        if value in (0,1):
            log.info('event=remote_voice_key pressed=%s',bool(value))
            self.report('voice-edge',dict(isPressed=bool(value)))
        return True

    async def serve(self):
        try:
            from evdev import InputDevice,UInput,ecodes as e
        except ImportError:
            self.raw.update(phase='failed',lastError='缺少 python3-evdev，请重新安装应用')
            return
        codes = {e.KEY_UP:'up',e.KEY_DOWN:'down',e.KEY_LEFT:'left',e.KEY_RIGHT:'right',e.KEY_ENTER:'ok',e.KEY_OK:'ok',e.KEY_SELECT:'ok',e.KEY_POWER:'power',e.KEY_HOMEPAGE:'home',e.KEY_HOME:'home',e.KEY_MENU:'menu',e.KEY_CONTEXT_MENU:'menu',e.KEY_BACK:'back',e.KEY_ESC:'back',e.KEY_TV:'tv',e.KEY_MUTE:'volume_mute',e.KEY_VOLUMEUP:'volume_up',e.KEY_VOLUMEDOWN:'volume_down'}
        while True:
            try:
                paths=self.candidates()
                if not paths:
                    self.raw.update(phase='awaiting',matchedDeviceCount=0)
                    await asyncio.sleep(2);continue
                self.device=InputDevice(paths[0])
                keys=sorted({v for k,v in e.ecodes.items() if k.startswith('KEY_') and 0<v<e.KEY_MAX}|{e.BTN_LEFT,e.BTN_RIGHT,e.BTN_MIDDLE})
                self.ui=UInput({e.EV_KEY:keys,e.EV_REL:[e.REL_X,e.REL_Y,e.REL_WHEEL,e.REL_HWHEEL],e.EV_REP:[]},name='SayAll Virtual Input',vendor=0x1209,product=0x5359,version=1)
                # Ignore keys already down at capture start to avoid unmatched releases.
                self.ignore_keys=set(self.device.active_keys())
                self.device.grab()
                self.engine=GestureEngine(self.execute,self.on_gesture)
                self.raw.update(phase='ready',matchedDeviceCount=1,lastError=None)
                self.mapping.update(listenerActive=True,gateActive=True,lastError=None)
                log.info('event=input_capture_ready device_count=1')
                async for event in self.device.async_read_loop():
                    if event.type==e.EV_SYN and event.code==e.SYN_DROPPED:raise RuntimeError('输入事件丢失，正在重新同步')
                    if event.type!=e.EV_KEY:continue
                    self.raw['rawEventCount']+=1
                    if event.code in self.ignore_keys:
                        if event.value==0:self.ignore_keys.discard(event.code)
                        continue
                    if self.consume_voice_key(event.code,event.value):continue
                    button=codes.get(event.code)
                    if button and event.value in (0,1):
                        self.raw.update(lastButton=button,lastIsPressed=bool(event.value),semanticEdgeCount=self.raw['semanticEdgeCount']+1)
                        active=set(self.raw['activeButtons'])
                        if event.value:active.add(button)
                        else:active.discard(button)
                        self.raw['activeButtons']=sorted(active)
                        self.report('edge',dict(button=button,isPressed=bool(event.value)))
                        log.info('event=remote_button button=%s pressed=%s',button,bool(event.value))
                    settings=self.settings().get('mappings',{})
                    actions=settings.get('actions',{}).get(button,{}) if settings.get('enabled',True) else {}
                    # Keep an already-held mapped key paired even after config changes.
                    captured=bool(button and self.engine.states.get(button,{}).get('down'))
                    if event.value==0 and 'raw:'+str(event.code) in self.owners:
                        self.key(event.code,False,'raw:'+str(event.code))
                    elif button and (captured or any(configured(actions.get(t)) for t in ('single','double','long'))):
                        self.mapping['swallowedEdges']+=1
                        self.engine.edge(button,event.code,event.value,actions)
                    else:
                        if event.value in (0,1):self.key(event.code,bool(event.value),'raw:'+str(event.code))
                    if not button and event.value==1:log.info('event=unrecognized_remote_key code=%s',event.code)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                message='没有遥控器或虚拟输入权限，请重新安装应用并启用输入访问' if isinstance(exc,PermissionError) else str(exc)
                self.raw.update(phase='failed',lastError=message)
                self.mapping['lastError']=message
                log.warning('event=input_capture_failed error_type=%s',type(exc).__name__)
            finally:
                self.report('input-stopping',None)
                if self.engine:
                    try:await self.engine.close()
                    except OSError:pass
                    self.engine=None
                if self.ui:
                    for owner in list(self.owners):
                        try:self.release(owner)
                        except OSError:pass
                    self.ui.close();self.ui=None
                    self.owners.clear();self.key_counts.clear()
                if self.device:
                    try:self.device.ungrab()
                    except OSError:pass
                    self.device.close();self.device=None
                self.mapping.update(listenerActive=False,gateActive=False)
                self.raw.update(activeButtons=[],matchedDeviceCount=0)
            await asyncio.sleep(2)
