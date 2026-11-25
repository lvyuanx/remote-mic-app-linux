"""A temporary PulseAudio/PipeWire sink exposed as a microphone."""
import asyncio
import shutil
import subprocess
import uuid
import shlex

class VirtualMicrophone:
    def __init__(self, name=None):
        self.modules = []
        self.stable = name is not None
        self.sink = name or 'sayall_' + uuid.uuid4().hex[:12]
        self.source = self.sink + '_mic'
        self.player = None
        self.queue = asyncio.Queue(maxsize=40)
        self.writer_task = None

    def _pactl(self, *args):
        result = subprocess.run(['pactl', *args], text=True, capture_output=True, check=True, timeout=8)
        return result.stdout.strip()

    async def start(self):
        if not shutil.which('pactl') or not shutil.which('paplay'):
            raise RuntimeError('缺少 pactl 或 paplay，请安装 pulseaudio-utils')
        try:
            if self.stable:
                # The desktop is single-instance. Reclaim only its own stale
                # modules, identified by exact reserved name and description.
                stale=[]
                for row in self._pactl('list','short','modules').splitlines():
                    fields=row.split('\t')
                    if len(fields)<3:continue
                    args=shlex.split(fields[2])
                    sink=fields[1]=='module-null-sink' and 'sink_name='+self.sink in args and 'sink_properties=device.description=SayAll_Output' in args
                    source=fields[1]=='module-remap-source' and 'source_name='+self.source in args and 'source_properties=device.description=SayAll_Microphone' in args
                    if sink or source:stale.append((fields[0],sink))
                for module_id,_ in sorted(stale,key=lambda item:item[1]):self._pactl('unload-module',module_id)
            self.modules.append(self._pactl('load-module', 'module-null-sink', 'sink_name='+self.sink, 'rate=16000', 'channels=1', 'sink_properties=device.description=SayAll_Output'))
            self.modules.append(self._pactl('load-module', 'module-remap-source', 'master='+self.sink+'.monitor', 'source_name='+self.source, 'source_properties=device.description=SayAll_Microphone'))
            self.player = await asyncio.create_subprocess_exec('paplay', '--raw', '--format=s16le', '--rate=16000', '--channels=1', '--latency-msec=50', '--process-time-msec=10', '--device='+self.sink, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            self.writer_task = asyncio.create_task(self._write())
        except BaseException:
            await self.close()
            raise

    async def _write(self):
        while True:
            data = await self.queue.get()
            if self.player.returncode is not None:
                raise RuntimeError('音频播放器已退出')
            self.player.stdin.write(data)
            await asyncio.wait_for(self.player.stdin.drain(), timeout=3)

    def push(self, pcm):
        if not pcm:
            return
        if self.writer_task.done():
            self.writer_task.result()
        if self.queue.full():
            self.queue.get_nowait()  # Prefer current speech over stale audio.
        self.queue.put_nowait(pcm)

    async def close(self):
        if self.writer_task:
            self.writer_task.cancel()
            await asyncio.gather(self.writer_task, return_exceptions=True)
            self.writer_task = None
        if self.player:
            if self.player.returncode is None:
                self.player.terminate()
                try:
                    await asyncio.wait_for(self.player.wait(), 2)
                except asyncio.TimeoutError:
                    self.player.kill()
                    await self.player.wait()
            self.player = None
        for module in reversed(self.modules):
            try:
                self._pactl('unload-module', module)
            except (OSError, subprocess.SubprocessError):
                pass
        self.modules.clear()
