import json
import struct
import unittest
from pathlib import Path
from sayall_linux.protocol import Capabilities, Decoder, Pipeline

class ProtocolTests(unittest.TestCase):
    def test_adpcm_golden(self):
        self.assertEqual(Decoder().decode(bytes.fromhex('007f80ff')), [0, 0, 11, -19, -23, -20, -72, -184])

    def test_upstream_rc001_replay(self):
        fixture = json.loads((Path(__file__).parent / 'rc001-short-voice.json').read_text())
        p = Pipeline()
        self.assertEqual(p.control(bytes.fromhex(fixture['capabilitiesHex'])), 'ready')
        samples = b''
        for event in fixture['events']:
            data = bytes.fromhex(event['valueHex'])
            if event['channel'] == 'control':
                p.control(data)
            else:
                samples += p.audio(data)
        self.assertEqual(len(samples) // 2, fixture['expected']['decodedSamples'])
        self.assertFalse(p.streaming)

    def test_sync_discards_partial_and_updates_decoder(self):
        p = Pipeline()
        p.control(bytes.fromhex('0b010002030004'))
        p.control(bytes.fromhex('04030201'))
        self.assertEqual(p.audio(b'\x00\x00'), b'')
        p.control(bytes.fromhex('0a00000000640a'))
        samples = struct.unpack('<8h', p.audio(b'\0'*4))
        self.assertTrue(all(sample >= 100 for sample in samples))
        p.control(b'\x00')
        self.assertEqual(p.audio(b'\x11'*4), b'')

    def test_capabilities_variants_and_rejections(self):
        self.assertEqual(Capabilities.parse(bytes.fromhex('0b0100000200780000')).codec, 2)
        self.assertEqual(Capabilities.parse(bytes.fromhex('0b0001000200780000')).open_command(), b'\x0c\x00\x02')
        for data in (b'', bytes.fromhex('0b010001030078'), bytes.fromhex('0b000100020078')):
            with self.assertRaises(ValueError):
                Capabilities.parse(data)
        with self.assertRaises(ValueError):
            Pipeline().control(b'\x04')

if __name__ == '__main__':
    unittest.main()
