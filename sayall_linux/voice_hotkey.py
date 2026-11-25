"""Paired voice shortcut lifetime driven by confirmed ATVV stream events."""
import logging

log=logging.getLogger('sayall.connection')

class VoiceHotkey:
    def __init__(self,settings,output):
        self.settings,self.output=settings,output
        self.active=False
        self.held=False
        self.last_error=None

    def begin(self):
        if self.active:return self.held
        self.last_error=None
        keys=(self.settings().get('hotkey') or {}).get('keys',[])
        if not keys:
            self.active=True
            log.info('event=voice_hotkey_skipped reason=disabled')
            return False
        if self.output.ui is None:
            self.last_error='按住说话快捷键输出未就绪，请启动按键监听'
            raise RuntimeError(self.last_error)
        try:
            self.output.execute({'type':'shortcut','chord':{'keys':list(keys)}},'begin','voice')
        except Exception:
            self.output.release('voice')
            raise
        self.active=self.held=True
        log.info('event=voice_hotkey_down key_count=%s',len(keys))
        return True

    def end(self,reason):
        try:
            if self.output.ui is not None:self.output.release('voice')
        except OSError as exc:
            self.last_error='虚拟输入设备已断开'
            log.warning('event=voice_hotkey_release_failed error_type=%s',type(exc).__name__)
        finally:
            if self.held:log.info('event=voice_hotkey_up reason=%s',reason)
            self.active=self.held=False
