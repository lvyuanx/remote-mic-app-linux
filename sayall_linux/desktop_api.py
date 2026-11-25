"""Linux implementation of the public SayAll frontend command contract."""
import asyncio
import copy
import json
import math
import os
from pathlib import Path
import platform
import tempfile
import time
from . import bridge
from .input_mapping import InputController
from .voice_hotkey import VoiceHotkey

VERSION = '0.2.8'

class DesktopAPI:
    def __init__(self, config_dir=None):
        self.directory = Path(config_dir or Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))/'sayall-linux')
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory/'settings.json'
        try:
            self.settings = json.loads(self.path.read_text())
        except FileNotFoundError:
            self.settings = {}
        self.task = None
        self.stop = None
        self.connection = dict(batteryLevel=None, phase='idle', remoteName=None, remoteModel='unknown', capabilities=None, voiceState='idle', decodedSamples=0, generation=0, reconnectAttempt=0, powerNotificationsAvailable=False, lastError=None, voiceAudioHealth='unknown', voiceAudioRateHz=None)
        self.audio = dict(phase='unconfigured', selectedEndpointId=None, selectedEndpointName=None, queuedSamples=0, submittedSamples=0, generation=0, lastError=None)
        self.raw = dict(phase='unsupported', matchedDeviceCount=0, rawEventCount=0, semanticEdgeCount=0, lastButton=None, lastIsPressed=None, activeButtons=[], lastError=None, staleRemoteEventCount=0)
        self.mapping = dict(enabled=True, gateActive=False, listenerActive=False, swallowedEdges=0, leakedDowns=0, firedGestures=0, lastFired=None, lastError=None)
        self.apps = {}
        self.voice_started = None
        self.native = None
        self.event_sink = None
        self.input = InputController(lambda:self.settings,self.input_event)
        self.raw = self.input.raw
        self.mapping = self.input.mapping
        self.voice = VoiceHotkey(lambda:self.settings,self.input)

    def input_event(self,event,value):
        if event=='input-stopping':self.voice.end('input_stopped')
        if self.event_sink:self.event_sink(event,value)

    def save(self, key, value):
        updated = {**self.settings, key: value}
        fd, tmp = tempfile.mkstemp(dir=self.directory, prefix='.settings-')
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(updated, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
            self.settings = updated
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
        return value

    def snapshot(self):
        return dict(appVersion=VERSION, platform=dict(platform='linux', windowsApiAvailable=False, bleScanAvailable=True, bleVoiceReady=self.connection['phase'] in ('ready','streaming'), wasapiReady=self.audio['phase'] in ('ready','streaming'), rawInputReady=self.raw['phase']=='ready', sendInputReady=self.input.ui is not None, voiceHotkeyReady=self.input.ui is not None, verificationStatus='Linux 蓝牙语音适配；按键和第三方应用功能正在移植', connection=self.connection.copy(), audio=self.audio.copy(), rawInput=self.raw.copy(), buttonMapping=self.mapping.copy()))

    def observe(self, event, value):
        if event == 'microphone':
            self.audio.update(phase='ready', selectedEndpointId=value, selectedEndpointName='SayAll_Microphone')
        elif event == 'battery':
            self.connection['batteryLevel'] = value
        elif event == 'device':
            self.connection['remoteName'] = value
        elif event == 'connecting':
            self.connection.update(phase='connecting')
        elif event == 'ready':
            self.connection.update(phase='ready', lastError=None)
            if value is not None:
                self.connection['capabilities'] = dict(version=value.version,codecs=value.codec,interaction=3,frameSize=value.frame_size,selectedCodec=value.codec,sampleRate=16000)
        elif event == 'interrupted':
            self.voice.end('interrupted')
            self.voice_started=None
        elif event == 'start':
            try:self.voice.begin()
            except Exception as exc:self.connection['lastError']=str(exc)
            self.connection.update(phase='streaming', voiceState='streaming', generation=self.connection['generation']+1)
            self.voice_started = time.monotonic()
        elif event == 'samples':
            self.connection['decodedSamples'] += value
            self.audio['submittedSamples'] += value
        elif event == 'stop':
            self.voice.end('stream_stopped')
            self.connection.update(phase='ready', voiceState='idle')
            if self.voice_started is not None:
                duration = time.monotonic()-self.voice_started
                self.voice_started = None
                usage = copy.deepcopy(self.settings.get('usage', dict(totalButtonPresses=0,totalVoiceSeconds=0,weekButtonPresses=0,longestVoiceSeconds=0,buttonPressesByControl={},voiceSessions=[],recentDays=[])))
                usage['totalVoiceSeconds'] += duration
                usage['longestVoiceSeconds'] = max(usage['longestVoiceSeconds'], duration)
                usage['voiceSessions'].insert(0, dict(endedAtMs=int(time.time()*1000),durationSeconds=duration,applicationName=None))
                usage['voiceSessions'] = usage['voiceSessions'][:100]
                self.save('usage', usage)

    def status(self, text):
        if text.startswith('连接中断'):
            self.voice.end('connection_lost')
            self.connection.update(phase='reconnecting', lastError=text, voiceState='idle', reconnectAttempt=self.connection['reconnectAttempt']+1)
            self.voice_started = None

    async def disconnect(self):
        self.voice.end('disconnect')
        await self.input.stop()
        if self.stop: self.stop.set()
        if self.task:
            try: await asyncio.wait_for(self.task, 25)
            except asyncio.TimeoutError:
                self.task.cancel()
                await asyncio.gather(self.task, return_exceptions=True)
            except Exception: pass
        self.task = None
        self.connection.update(phase='disconnected', voiceState='idle', remoteName=None, lastError=None, batteryLevel=None)
        self.audio.update(phase='unconfigured', selectedEndpointId=None, selectedEndpointName=None)
        return self.connection.copy()

    async def command(self, command, args):
        if command == 'check_app_update': raise RuntimeError('此 Linux 移植版尚未提供在线更新源，请使用本地安装包升级')
        if command == 'set_open_window_at_launch' and not args['enabled']: raise NotImplementedError('Linux: 后台启动需要系统托盘支持，此项尚未完成移植')
        if command == 'set_voice_hold_hotkey':
            hotkey=args['hotkey']
            if hotkey is not None:
                if not isinstance(hotkey,dict) or not isinstance(hotkey.get('keys'),list) or len(hotkey['keys'])>8 or not all(isinstance(key,str) for key in hotkey['keys']):raise ValueError('无效的语音快捷键')
                self.input.chord_codes(hotkey['keys'])
            self.voice.end('settings_changed')
            return self.save('hotkey',hotkey)
        if command == 'set_app_icon':
            from .icons import icon_name
            identifier=args['identifier']
            icon_name(identifier)
            previous=self.settings.get('icon','standard')
            try:
                if self.native:await self.native('apply_app_icon',{'identifier':identifier})
                return self.save('icon',identifier)
            except Exception:
                if self.native:
                    try:await self.native('apply_app_icon',{'identifier':previous})
                    except Exception:pass
                raise
        if command == 'get_runtime_snapshot': return self.snapshot()
        if command == 'get_connection_snapshot': return self.connection.copy()
        if command == 'get_audio_snapshot': return self.audio.copy()
        if command == 'scan_paired_remotes':
            return [dict(id=address,name=name,model=('rc003' if 'rc003' in name.lower() else 'rc001' if 'rc001' in name.lower() else 'unknown'),isSupportedCandidate=any(x in name.lower() for x in ('remote','rc001','rc003','遥控'))) for name,address in await bridge.scan()]
        if command == 'connect_remote':
            await self.disconnect()
            address = str(args['deviceId'])
            import re
            if not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}',address): raise ValueError('无效的蓝牙设备地址')
            self.save('lastRemote', address)
            self.stop = asyncio.Event()
            self.connection.update(phase='connecting',remoteName='蓝牙遥控器',reconnectAttempt=0,batteryLevel=None)
            async def connect():
                try: await bridge.run(address,self.stop,self.status,self.observe,lambda: self.settings.get("gain",0),microphone_name="sayall_remote")
                except Exception as exc:
                    self.connection.update(phase='failed',lastError=str(exc))
            self.task=asyncio.create_task(connect())
            await self.input.start()
            return self.connection.copy()
        if command == 'disconnect_remote': return await self.disconnect()
        if command == 'list_audio_endpoints':
            return [dict(id=self.audio['selectedEndpointId'],name='SayAll_Microphone',isVirtualCableCandidate=True)] if self.audio['selectedEndpointId'] else []
        if command == 'select_audio_endpoint':
            if args['endpointId'] != self.audio['selectedEndpointId']: raise ValueError('音频设备已失效，请刷新')
            return self.audio.copy()
        if command == 'get_gain_db': return self.settings.get('gain',0)
        if command == 'set_gain_db':
            value=float(args['gainDb'])
            if not math.isfinite(value): raise ValueError('无效的增益')
            return self.save('gain',max(0,min(24,value)))
        if command == 'get_button_mappings': return self.settings.get('mappings',dict(enabled=True,actions={}))
        if command == 'save_button_mappings':
            value=args['mappings']
            if not isinstance(value,dict) or not isinstance(value.get('actions'),dict): raise ValueError('无效的按键映射')
            result=self.save('mappings',value)
            self.mapping['enabled']=value.get('enabled',True)
            await self.input.stop()
            await self.input.start()
            return result
        if command == 'reset_button_mappings':
            result=self.save('mappings',dict(enabled=True,actions={}))
            self.mapping['enabled']=True
            await self.input.stop()
            await self.input.start()
            return result
        if command == 'get_button_mapping_snapshot': return {**self.mapping,'enabled': self.settings.get('mappings',{}).get('enabled',True)}
        if command == 'get_raw_input_snapshot': return self.raw.copy()
        if command == 'get_send_input_snapshot': return dict(phase='ready' if self.input.ui else 'unsupported',sentEvents=self.input.sent,lastError=self.mapping.get('lastError'))
        if command == 'start_raw_input': return await self.input.start()
        if command == 'stop_raw_input': return await self.input.stop()
        if command == 'test_button_mapping':
            if not self.input.ui:raise RuntimeError('Linux: 按键监听尚未就绪，请先连接遥控器并检查输入权限')
            action=self.settings.get('mappings',{}).get('actions',{}).get(args['button'],{}).get(args['trigger'])
            if action and action.get('type')!='disabled':self.input.execute(action,'pulse','test')
            return await self.command('get_send_input_snapshot',{})
        if command == 'get_capture_support': return dict(nativeArch='x64' if platform.machine()=='x86_64' else 'arm64',helperExpected='Linux evdev/uinput',available=True,reason=None)
        if command in ('get_rc003_task_status','enable_rc003_capture','disable_rc003_capture'):
            if command=='enable_rc003_capture':await self.input.start()
            elif command=='disable_rc003_capture':await self.input.stop()
            return dict(installed=True,authorizationRequired=False,enabled=bool(self.input.task and not self.input.task.done()),helperPath=None,lastError=self.raw['lastError'])
        if command == 'get_rc003_bridge_snapshot': return dict(phase='connected' if self.raw['phase']=='ready' else 'stopped',captureHealth='active' if self.raw['phase']=='ready' else 'off',captureUnavailable='none',captureRevoked='none',port=0,helperPid=0,acceptedTotal=0,deniedTotal=0,replacedTotal=0,edgesApplied=0,usagesDropped=0,malformedTotal=0,watchdogReleaseTotal=0,pressedUsages=[],lastError=None)
        if command == 'button_profiles_access': return dict(status='unavailable')
        if command == 'button_profiles_snapshot': return None
        if command == 'get_membership_snapshot': return dict(availability='unavailable',accountDisplayName=None,plusActive=False,accountSignedIn=False,syncState='unavailable')
        if command == 'get_usage_profile': return self.settings.get('usage',dict(totalButtonPresses=0,totalVoiceSeconds=0,weekButtonPresses=0,longestVoiceSeconds=0,buttonPressesByControl={},voiceSessions=[],recentDays=[]))
        if command == 'get_system_accent_color': return None
        if command in ('take_update_completed_version','get_application_icon','resolve_preset_target'): return None
        if command in ('report_theme_result','report_frontend_event'): return None
        if command == 'get_vokie_installation':
            from .vokie import installation
            return installation()
        if command == 'get_ime_status': return dict(detected=False,active=None,installed=[],expected=None,matchesExpected=None)
        preferences = {
            'theme_preference': ('theme','system','preference'), 'application_language': ('language','zh-Hans','language'),
            'open_window_at_launch': ('openWindow',True,'enabled'), 'voice_hold_hotkey': ('hotkey',None,'hotkey'),
            'other_voice_hotkey': ('otherHotkey',None,'keys'), 'voice_input_tool': ('voiceTool',None,'tool'),
            'lock_mapping_selection': ('locked',False,'locked'), 'app_icon': ('icon','standard','identifier')}
        for suffix,(key,default,param) in preferences.items():
            if command == 'get_'+suffix: return self.settings.get(key,default)
            if command in ('set_'+suffix,'save_'+suffix): return self.save(key,args[param])
        if command == 'get_app_update_preferences': return dict(includePrereleases=self.settings.get('prereleases',False))
        if command == 'set_app_update_preferences': return dict(includePrereleases=self.save('prereleases',bool(args['includePrereleases'])))
        if command == 'get_onboarding_state': return dict(flowVersion=1,completedVersion=1,step='complete',isActive=False)
        if command == 'get_combined_actions': return self.settings.get('macros',dict(formatVersion=1,definitions=[]))
        if command == 'save_macro':
            definition=args['definition']
            if not isinstance(definition.get('steps'),list) or not definition.get('macroId'): raise ValueError('无效的组合动作')
            library=copy.deepcopy(await self.command('get_combined_actions',{}))
            library['definitions']=[d for d in library['definitions'] if d['macroId']!=definition['macroId']]+[definition]
            return self.save('macros',library)
        if command == 'macro_references':
            library=await self.command('get_combined_actions',{})
            nested=[d['macroId'] for d in library['definitions'] if any(s.get('parameters',{}).get('nestedMacroId')==args['macroId'] for s in d['steps'])]
            buttons=[]
            for button,actions in self.settings.get('mappings',{}).get('actions',{}).items():
                for trigger,action in actions.items():
                    if isinstance(action,dict) and action.get('macroId')==args['macroId']: buttons.append(dict(button=button,trigger=trigger))
            return dict(buttons=buttons,nestedIn=nested)
        if command == 'delete_macro':
            refs=await self.command('macro_references',args)
            if refs['buttons'] or refs['nestedIn']: raise ValueError('请先移除引用此组合动作的按键或其他动作')
            library=copy.deepcopy(await self.command('get_combined_actions',{}))
            library['definitions']=[d for d in library['definitions'] if d['macroId']!=args['macroId']]
            self.save('macros',library)
            return dict(library=library,removedMacroIds=[args['macroId']],rewrittenMacroIds=[])
        if command == 'get_agent_access_snapshot': return dict(enabled=False,clients=[],authorizations=[])
        if command == 'get_transcript_history': return dict(enabled=False,audioEnabled=False,applications=[],records=[],recordings=[],totalCount=0,recentCount=0,archiveError=None)
        if command == 'get_common_phrase_editor_snapshot': return dict(available=False,groups=[],entries=[],bindings={},lastError=None)
        if command == 'get_diagnostic_report':
            return dict(schemaVersion=4,appVersion=VERSION,appBuild='linux',sourceRevision='unknown',buildChannel='local',windowsVersion=platform.release(),processArchitecture=platform.machine(),startupType='unknown',platform=self.snapshot()['platform'])
        if self.native:
            result=await self.native(command,args)
            if command=='import_button_mapping_configuration' and result is not None:
                await self.input.stop()
                await self.input.start()
            return result
        raise NotImplementedError('Linux: 此功能的 Linux 后端尚未完成移植：'+command)
