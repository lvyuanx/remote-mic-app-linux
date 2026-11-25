"""ATVV and high-nibble-first IMA ADPCM, derived from SayAll for Windows.

Copyright contributors to GetSayAll/remote-mic-app-windows. GPL-3.0-only.
"""
import struct
from dataclasses import dataclass

SERVICE = 'ab5e0001-5a21-4f05-bc7d-af01f617b664'
TRANSMIT = 'ab5e0002-5a21-4f05-bc7d-af01f617b664'
AUDIO = 'ab5e0003-5a21-4f05-bc7d-af01f617b664'
CONTROL = 'ab5e0004-5a21-4f05-bc7d-af01f617b664'
GET_CAPABILITIES = bytes.fromhex('0a0100000303')
STEP = (7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,34,37,41,45,50,55,60,66,73,80,88,97,107,118,130,143,157,173,190,209,230,253,279,307,337,371,408,449,494,544,598,658,724,796,876,963,1060,1166,1282,1411,1552,1707,1878,2066,2272,2499,2749,3024,3327,3660,4026,4428,4871,5358,5894,6484,7132,7845,8630,9493,10442,11487,12635,13899,15289,16818,18500,20350,22385,24623,27086,29794,32767)
INDEX = (-1,-1,-1,-1,2,4,6,8)

@dataclass
class Capabilities:
    version: int
    codec: int
    frame_size: int

    @classmethod
    def parse(cls, data):
        if len(data) < 7 or data[0] != 0x0b:
            raise ValueError('无效的设备能力响应')
        version = int.from_bytes(data[1:3], 'big')
        if version < 0x100 and len(data) < 9:
            raise ValueError('设备能力响应过短')
        codecs = data[3] if version >= 0x100 else data[4]
        if version >= 0x100 and not codecs and len(data) >= 9 and data[4] & 3:
            codecs = data[4]
        if not codecs & 2:
            raise ValueError('设备不支持 16 kHz ADPCM 音频')
        frame_size = int.from_bytes(data[5:7], 'big') or 120
        if frame_size > 4096:
            raise ValueError('设备报告的音频帧过大')
        return cls(version, 2, frame_size)

    def open_command(self):
        return bytes((12, 0)) if self.version >= 0x100 else bytes((12, 0, self.codec))

class Decoder:
    def __init__(self):
        self.reset()

    def reset(self, predictor=0, index=0):
        self.predictor = max(-32768, min(32767, predictor))
        self.index = max(0, min(88, index))

    def decode(self, data):
        result = []
        for byte in data:
            for nibble in (byte >> 4, byte & 15):
                step = STEP[self.index]
                diff = (step >> 3) + ((step >> 2) if nibble & 1 else 0) + ((step >> 1) if nibble & 2 else 0) + (step if nibble & 4 else 0)
                self.predictor = max(-32768, min(32767, self.predictor + (-diff if nibble & 8 else diff)))
                self.index = max(0, min(88, self.index + INDEX[nibble & 7]))
                result.append(self.predictor)
        return result

class Pipeline:
    def __init__(self):
        self.capabilities = None
        self.decoder = Decoder()
        self.pending = bytearray()
        self.streaming = False
        self.session_id = 0
        self.sync = None

    def control(self, data):
        if not data:
            raise ValueError('空控制消息')
        op = data[0]
        if op == 0x0b:
            self.capabilities = Capabilities.parse(data)
            return 'ready'
        if op == 0x08:
            if not self.capabilities:
                raise ValueError('设备尚未完成能力协商')
            return 'open'
        if op == 0x04:
            if not self.capabilities:
                raise ValueError('设备尚未完成能力协商')
            if len(data) >= 3 and data[2] != 2:
                raise ValueError('设备选择了不支持的音频编码')
            self.session_id = data[3] if len(data) >= 4 else 0
            self.pending.clear()
            self.sync = None
            self.decoder.reset()
            self.streaming = True
            return 'start'
        if op == 0x00:
            self.streaming = False
            self.pending.clear()
            self.sync = None
            return 'stop'
        if op == 0x0a and self.streaming:
            if len(data) < 7:
                raise ValueError('解码同步消息过短')
            self.pending.clear()
            self.sync = (int.from_bytes(data[4:6], 'big', signed=True), data[6])
            return 'sync'
        return 'unknown'

    def audio(self, data):
        if not self.streaming or not self.capabilities:
            return b''
        self.pending.extend(data)
        size = self.capabilities.frame_size
        samples = []
        while len(self.pending) >= size:
            frame = self.pending[:size]
            del self.pending[:size]
            if self.sync is not None:
                self.decoder.reset(*self.sync)
                self.sync = None
            samples.extend(self.decoder.decode(frame))
        # Match the upstream three-point smoothing on each decoded batch.
        filtered = samples.copy()
        for i in range(1, len(samples) - 1):
            filtered[i] = (samples[i-1] + 2*samples[i] + samples[i+1]) >> 2
        return struct.pack('<' + 'h' * len(filtered), *filtered)
