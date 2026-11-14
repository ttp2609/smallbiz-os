"""Regression tests for Vietnamese Edge-TTS NoAudioReceived handling (no network)."""
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from enhancements import synthesize_voice_file


class NoAudioReceived(Exception):
    pass


class TTSFallbackTests(unittest.TestCase):
    def fake_modules(self, behavior):
        module = types.ModuleType('edge_tts')
        exceptions = types.ModuleType('edge_tts.exceptions')
        exceptions.NoAudioReceived = NoAudioReceived
        class Communicate:
            def __init__(self, text, voice):
                self.text, self.voice = text, voice
            async def save(self, destination):
                behavior(self.voice, destination)
        module.Communicate = Communicate
        module.exceptions = exceptions
        return {'edge_tts': module, 'edge_tts.exceptions': exceptions}

    def test_vietnamese_retries_then_gtts_fallback(self):
        attempts=[]
        def unavailable(voice, dst):
            attempts.append(voice)
            raise NoAudioReceived('No audio was received')
        def fake_gtts_save(_tts, dst):
            Path(dst).write_bytes(b'ID3' + b'X'*200)
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'tts.mp3'
            with (patch.dict(sys.modules, self.fake_modules(unavailable)),
                  patch('gtts.gTTS.save',fake_gtts_save),
                  patch('enhancements.time.sleep')):
                engine=synthesize_voice_file('Xin chào', 'edge','vi','vi-VN-HoaiMyNeural', output)
            self.assertEqual(engine,'gtts-fallback')
            self.assertEqual(len(attempts),3)
            self.assertTrue(output.read_bytes().startswith(b'ID3'))

    def test_transient_failure_uses_original_voice_without_fallback(self):
        attempts=[]
        def available_on_second(voice, dst):
            attempts.append(voice)
            if len(attempts)==1: raise NoAudioReceived('No audio received')
            Path(dst).write_bytes(b'ID3' + b'Y'*180)
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'tts.mp3'
            with (patch.dict(sys.modules, self.fake_modules(available_on_second)),
                  patch('enhancements.time.sleep'),
                  patch('gtts.gTTS.save',side_effect=AssertionError('gTTS should not run'))):
                engine=synthesize_voice_file('Xin chào','edge','vi','vi-VN-HoaiMyNeural',output)
            self.assertEqual(engine,'edge')
            self.assertEqual(len(attempts),2)

    def test_other_language_still_reports_edge_failure(self):
        def unavailable(voice,dst): raise NoAudioReceived('No audio received')
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(sys.modules, self.fake_modules(unavailable)), patch('enhancements.time.sleep'):
                with self.assertRaises(NoAudioReceived):
                    synthesize_voice_file('Hello','edge','en','en-US-AriaNeural',Path(temp)/'tts.mp3')

    def test_gtts_engine_unchanged(self):
        def fake_gtts_save(_tts, dst): Path(dst).write_bytes(b'ID3'+b'Z'*200)
        with tempfile.TemporaryDirectory() as temp:
            with patch('gtts.gTTS.save',fake_gtts_save):
                self.assertEqual(synthesize_voice_file('Xin chào','gtts','vi','vi-VN-HoaiMyNeural',Path(temp)/'tts.mp3'),'gtts')


    def test_speak_endpoint_discloses_fallback_engine(self):
        from fastapi.testclient import TestClient
        from server import app
        from uuid import uuid4
        with TestClient(app) as c:
            login = c.post('/api/auth/login', json={'email':'demo@smallbiz.local','password':'demo123'})
            self.assertEqual(login.status_code, 200)
            created = c.post('/api/businesses', json={'name':'Voice Fix ' + uuid4().hex[:10]})
            self.assertEqual(created.status_code, 200)
            c.post('/api/auth/switch', json={'business_id':created.json()['id']})
            configured = c.put('/api/voice/config', json={
                'tts':'edge', 'language':'vi', 'voice':'vi-VN-HoaiMyNeural',
                'stt_language':'vi-VN', 'greeting':'Xin chào', 'enabled':False})
            self.assertEqual(configured.status_code, 200)
            def fake_synthesize(text, engine, language, voice, output):
                self.assertEqual(language, 'vi')
                Path(output).write_bytes(b'ID3' + b'X'*200)
                return 'gtts-fallback'
            with patch('enhancements.synthesize_voice_file', side_effect=fake_synthesize):
                r = c.post('/api/voice/speak',json={'text':'Xin chào'})
            self.assertEqual(r.status_code, 200, r.text[:150])
            self.assertEqual(r.headers['X-TTS-Engine'], 'gtts-fallback')
            self.assertTrue(r.content.startswith(b'ID3'))

if __name__=='__main__':
    unittest.main()
