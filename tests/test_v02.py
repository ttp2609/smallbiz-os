"""V0.2 API, tenant, provider, workflow and Twilio HMAC tests. Network calls mocked."""
import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
import uuid
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from server import app


class FakeHTTPResponse:
    def __init__(self, data=None):
        import json
        self.data = data or {'choices': [{'message': {'content': 'Hello! We can help you book an appointment.'}}]}
        self.status_code = 200
        self.headers = {'content-type': 'application/json'}
        self.content = json.dumps(self.data).encode('utf-8')
        self.text = self.content.decode('utf-8')
    def raise_for_status(self):
        return None
    def json(self):
        return self.data


class Version02Tests(TestCase):
    def setUp(self):
        self.c = TestClient(app)
        login = self.c.post('/api/auth/login', json={'email': 'demo@smallbiz.local', 'password': 'demo123'})
        self.assertEqual(login.status_code, 200, login.text)
        new = self.c.post('/api/businesses', json={'name': 'V02 ' + uuid.uuid4().hex[:10]})
        self.assertEqual(new.status_code, 200, new.text)
        self.biz = new.json()['id']
        self.c.post('/api/auth/switch', json={'business_id': self.biz})
        self.contact = self.c.post('/api/contacts', json={
            'name': 'Test Client', 'phone': '+14155550123', 'consent_sms': True}).json()['id']

    def tearDown(self):
        os.environ.pop('SMALLBIZ_ENABLE_LIVE_SMS', None)

    def test_provider_encrypted_and_not_cross_tenant(self):
        res = self.c.put('/api/ai/provider', json={
            'provider': 'openai', 'model': 'my-model', 'api_key': 'secret-value-v02', 'auto_reply': True})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertTrue(res.json()['key_set'])
        self.assertNotIn('secret-value-v02', str(res.json()))
        with __import__('server').database() as db:
            item = __import__('server').one(db, 'SELECT ai_key_enc FROM integrations WHERE business_id=?', (self.biz,))
            self.assertNotIn('secret-value-v02', item['ai_key_enc'])
        # Re-saving without a new key preserves the encrypted secret.
        self.c.put('/api/ai/provider', json={'provider': 'openai', 'model': 'my-model', 'api_key': ''})
        self.assertTrue(self.c.get('/api/ai/provider').json()['key_set'])
        member = self.c.post('/api/members', json={
            'name': 'Restricted', 'email': 'staff'+uuid.uuid4().hex[:9]+'@demo.local',
            'password': 'password1234', 'role': 'staff'})
        self.assertEqual(member.status_code, 200)
        # Another workspace cannot accidentally inherit credentials.
        both = self.c.post('/api/auth/switch', json={'business_id': 1})
        self.assertEqual(both.status_code, 200)
        self.assertEqual(self.c.get('/api/ai/provider').json()['provider'], 'none')

    def test_custom_provider_security_and_mock_model(self):
        bad = self.c.put('/api/ai/provider', json={
            'provider': 'custom', 'base_url': 'http://169.254.169.254/latest', 'model': 'm', 'api_key': 'k'})
        self.assertEqual(bad.status_code, 400)
        self.c.put('/api/ai/provider', json={'provider': 'groq', 'model': 'sample-model', 'api_key': 'test-key'})
        with patch('enhancements.httpx.post', return_value=FakeHTTPResponse()) as call:
            r = self.c.post('/api/ai/chat', json={'message': 'Can you help me?'})
            self.assertEqual(r.status_code, 200, r.text)
            self.assertIn('book an appointment', r.json()['reply'])
            self.assertIn('api.groq.com', call.call_args.args[0])

    def test_custom_gateway_requests_non_stream_json_and_preserves_model_id(self):
        import httpx
        with patch('enhancements.validate_custom_url', return_value='https://api.ttpstudio.io.vn/v1'):
            saved = self.c.put('/api/ai/provider', json={
                'provider':'custom', 'base_url':'https://api.ttpstudio.io.vn/v1',
                'model':'ag/gemini-3.8-flash-low', 'api_key':'demo-gateway-secret'})
        self.assertEqual(saved.status_code,200,saved.text)
        payload={'choices':[{'message':{'content':'Hello from proxy'}}]}
        response=httpx.Response(200,json=payload,request=httpx.Request("POST","https://api.ttpstudio.io.vn/v1/chat/completions"))
        with patch('enhancements.httpx.post',return_value=response) as outgoing:
            result=self.c.post('/api/ai/provider/test')
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(outgoing.call_args.args[0],'https://api.ttpstudio.io.vn/v1/chat/completions')
        kwargs=outgoing.call_args.kwargs
        self.assertEqual(kwargs['json']['model'],'ag/gemini-3.8-flash-low')
        self.assertIs(kwargs['json'].get('stream'),False)
        self.assertEqual(kwargs['headers'].get('Accept'),'application/json')
        self.assertNotIn('demo-gateway-secret',str(result.json()))

    def test_gateway_empty_nonjson_and_sse_responses_have_actionable_errors(self):
        import httpx
        self.c.put('/api/ai/provider', json={
            'provider':'openai', 'model':'test-model', 'api_key':'fake-key'})
        bad_responses = [
            (httpx.Response(200,content=b'',headers={'Content-Type':'application/json'},request=httpx.Request('POST','https://api.openai.com/v1/chat/completions')), 'empty body'),
            (httpx.Response(200,text='<html>Cloudflare Access</html>',headers={'Content-Type':'text/html'},request=httpx.Request('POST','https://api.openai.com/v1/chat/completions')), 'HTML'),
            (httpx.Response(200,text='data: {"choices":[]}\n\n',headers={'Content-Type':'text/event-stream'},request=httpx.Request('POST','https://api.openai.com/v1/chat/completions')), 'SSE'),
            (httpx.Response(401,json={'error':{'message':'Invalid API key'}},request=httpx.Request('POST','https://api.openai.com/v1/chat/completions')), 'HTTP 401'),
            (httpx.Response(404,json={'error':{'message':'Model not found'}},request=httpx.Request('POST','https://api.openai.com/v1/chat/completions')), 'HTTP 404'),
        ]
        for upstream, expected in bad_responses:
            with self.subTest(expected=expected), patch('enhancements.httpx.post',return_value=upstream):
                result=self.c.post('/api/ai/provider/test')
            self.assertEqual(result.status_code,502,result.text)
            self.assertIn(expected,result.json()['detail'])
            self.assertNotIn('fake-key',result.text)

    def test_ai_auto_reply_uses_selected_provider_only_in_builtin_mode(self):
        self.c.put('/api/ai/provider', json={
            'provider': 'openai', 'model': 'test-model', 'api_key': 'fake-key', 'auto_reply': True})
        init = self.c.post('/api/demo/inbound-sms', json={'contact_id': self.contact, 'text': 'First message'})
        conv = init.json()['conversation_id']
        self.c.patch(f'/api/conversations/{conv}', json={'ai_mode': 'builtin'})
        with patch('enhancements.httpx.post', return_value=FakeHTTPResponse()):
            next_sms = self.c.post('/api/demo/inbound-sms', json={
                'contact_id': self.contact, 'text': 'Can I book?', 'event_key': uuid.uuid4().hex})
        self.assertEqual(next_sms.status_code, 200, next_sms.text)
        msgs = self.c.get(f'/api/conversations/{conv}/messages').json()
        self.assertTrue(any(m['author'] == 'builtin_ai' and m['direction'] == 'outbound' for m in msgs))
        self.assertFalse(any(m['author'] == 'builtin_ai' for m in msgs if m['body'] == 'First message'))

    def _live_twilio(self):
        os.environ['SMALLBIZ_ENABLE_LIVE_SMS'] = '1'
        sid = 'AC' + 'a'*32
        token = 'twilio-demo-signing-key'
        number = '+1500555' + f'{self.biz:04d}'
        r = self.c.put('/api/sms/config', json={
            'mode': 'twilio', 'account_sid': sid, 'auth_token': token, 'phone_number': number})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()['token_set'])
        self.assertNotIn(token, str(r.json()))
        return token, number

    @staticmethod
    def _signature(url, body, token):
        source = url + ''.join(k + str(body[k]) for k in sorted(body))
        return base64.b64encode(hmac.new(token.encode(), source.encode(), hashlib.sha1).digest()).decode()

    def test_twilio_live_outbound_consent_and_signed_inbound(self):
        token, number = self._live_twilio()
        with patch('enhancements.httpx.post', return_value=FakeHTTPResponse({'sid':'SM'+'a'*32})) as call:
            inbound = self.c.post('/api/demo/inbound-sms', json={'contact_id':self.contact, 'text':'Hi'})
            conv = inbound.json()['conversation_id']
            send = self.c.post(f'/api/conversations/{conv}/messages', json={'body':'Hello customer'})
            self.assertEqual(send.status_code, 200, send.text)
            self.assertEqual(send.json()['status'], 'queued')
            self.assertIn('Messages.json', call.call_args.args[0])
        # A signed Twilio webhook creates a new contact, but does NOT infer consent.
        form = {'To': number, 'From': '+14155550999', 'Body': 'I need help', 'MessageSid': 'SMsignedtest'}
        url = 'http://testserver/api/hooks/twilio/sms'
        signature = self._signature(url, form, token)
        signed = self.c.post('/api/hooks/twilio/sms', data=form,
                             headers={'X-Twilio-Signature':signature})
        self.assertEqual(signed.status_code, 200, signed.text)
        self.assertTrue(signed.text.startswith('<Response'))
        self.assertEqual(self.c.post('/api/hooks/twilio/sms', data=form, headers={}).status_code,403)
        self.assertEqual(self.c.post('/api/hooks/twilio/sms', data=form,
                                    headers={'X-Twilio-Signature':signature}).status_code,200)
        new_ct = next(c for c in self.c.get('/api/contacts').json() if c['phone']==form['From'])
        self.assertFalse(new_ct['consent_sms'])
        conv = next(c for c in self.c.get('/api/conversations').json() if c['contact_id']==new_ct['id'])
        out = self.c.post(f'/api/conversations/{conv["id"]}/messages', json={'body':'Unsolicited SMS'})
        self.assertEqual(out.json()['status'], 'blocked_no_consent')
        os.environ.pop('SMALLBIZ_ENABLE_LIVE_SMS',None)

    def test_voice_tts_preview_and_signed_public_audio(self):
        from pathlib import Path
        self.c.put('/api/voice/config', json={
            'tts':'gtts','language':'en','voice':'en-US-AriaNeural','stt_language':'en-US',
            'greeting':'Welcome customer','enabled':False})
        def fake_save(_tts, path):
            Path(path).write_bytes(b'ID3' + b'X'*180)
        with patch('gtts.gTTS.save', fake_save):
            preview = self.c.post('/api/voice/speak',json={'text':'Hello customer'})
            self.assertEqual(preview.status_code,200,preview.text[:100])
            self.assertIn('audio/mpeg',preview.headers['content-type'])
            self.assertTrue(preview.content.startswith(b'ID3'))

    def test_live_delivery_status_requires_signature(self):
        token,number=self._live_twilio()
        os.environ['SMALLBIZ_PUBLIC_BASE_URL']='https://app.example.org'
        try:
            with patch('enhancements.httpx.post',return_value=FakeHTTPResponse({'sid':'SM'+'f'*32})):
                inbox=self.c.post('/api/demo/inbound-sms',json={'contact_id':self.contact,'text':'Hi'}).json()
                send=self.c.post(f'/api/conversations/{inbox["conversation_id"]}/messages',json={'body':'Hello'}).json()
                self.assertEqual(send['status'],'queued')
            form={'From':number,'To':'+14155550123','MessageSid':'SM'+'f'*32,'MessageStatus':'delivered'}
            url='https://app.example.org/api/hooks/twilio/status'
            r=self.c.post('/api/hooks/twilio/status',data=form,
                          headers={'X-Twilio-Signature':self._signature(url,form,token)})
            self.assertEqual(r.status_code,200,r.text)
            self.assertTrue(r.json()['matched'])
            msgs=self.c.get(f'/api/conversations/{inbox["conversation_id"]}/messages').json()
            self.assertEqual(next(x for x in msgs if x['id']==send['id'])['status'],'delivered')
            self.assertEqual(self.c.post('/api/hooks/twilio/status',data=form).status_code,403)
        finally:
            os.environ.pop('SMALLBIZ_PUBLIC_BASE_URL',None)

    def test_workflow_dry_run_is_non_mutating_and_live_event_runs_mock(self):
        flow = {
            'name': 'New SMS thank-you', 'enabled': True,
            'nodes': [
                {'id':'start','type':'trigger_sms','x':10,'y':20,'config':{}},
                {'id':'gate','type':'condition_consent','x':280,'y':20,'config':{}},
                {'id':'send','type':'action_sms','x':550,'y':20,'config':{'text':'Welcome {{first_name}}!'}},
            ],
            'edges':[{'from':'start','to':'gate','branch':'next'}, {'from':'gate','to':'send','branch':'yes'}]
        }
        added = self.c.post('/api/workflows', json=flow)
        self.assertEqual(added.status_code,200,added.text)
        fid=added.json()['id']
        pre = len(self.c.get('/api/conversations').json())
        dry = self.c.post(f'/api/workflows/{fid}/test', json={'contact_id':self.contact,'text':'Hi'})
        self.assertEqual(dry.status_code, 200, dry.text)
        self.assertTrue(any('Would send SMS' in s for s in dry.json()['trace']))
        self.assertEqual(pre,len(self.c.get('/api/conversations').json()))
        real = self.c.post('/api/demo/inbound-sms', json={'contact_id':self.contact,'text':'Hi'})
        conv = real.json()['conversation_id']
        msgs = self.c.get(f'/api/conversations/{conv}/messages').json()
        self.assertEqual(len([x for x in msgs if x['body']=='Welcome Test!']),1)
        self.assertTrue(self.c.get('/api/workflows').json()['runs'])
        invalid = dict(flow)
        invalid['edges'] = flow['edges'] + [{'from':'send','to':'start','branch':'next'}]
        self.assertEqual(self.c.put(f'/api/workflows/{fid}',json=invalid).status_code,400)

    def test_simulated_inbound_never_sends_real_sms_even_when_live_mode_is_on(self):
        self._live_twilio()
        self.c.put('/api/ai/provider', json={
            'provider':'openai','model':'stub-model','api_key':'fake-key','auto_reply':True})
        first=self.c.post('/api/demo/inbound-sms',json={'contact_id':self.contact,'text':'Hi'}).json()
        self.c.patch(f'/api/conversations/{first["conversation_id"]}',json={'ai_mode':'builtin'})
        calls=[]
        def fake_post(url,*args,**kwargs):
            calls.append(url)
            if 'Messages.json' in url:
                raise AssertionError('Simulated inbound may not send an actual Twilio SMS')
            return FakeHTTPResponse()
        with patch('enhancements.httpx.post',side_effect=fake_post):
            r=self.c.post('/api/demo/inbound-sms',json={'contact_id':self.contact,'text':'How are you?'})
            self.assertEqual(r.status_code,200,r.text)
        self.assertTrue(calls)
        msgs=self.c.get(f'/api/conversations/{first["conversation_id"]}/messages').json()
        self.assertEqual(next(x for x in msgs if x['author']=='builtin_ai')['status'],'mock_sent')

    def test_voice_twiml_webhook_signature_and_language(self):
        token, number = self._live_twilio()
        self.assertEqual(self.c.put('/api/voice/config', json={
            'tts':'gtts','language':'vi','voice':'vi-VN-HoaiMyNeural',
            'stt_language':'vi-VN','greeting':'Xin chào, tôi có thể giúp gì?',
            'enabled':True}).status_code,200)
        form={'To':number,'From':'+14155550125','CallSid':'CAexample'}
        sig=self._signature('http://testserver/api/hooks/twilio/voice',form,token)
        response=self.c.post('/api/hooks/twilio/voice',data=form,headers={'X-Twilio-Signature':sig})
        self.assertEqual(response.status_code,200,response.text)
        self.assertIn('<Gather',response.text)
        self.assertIn('vi-VN',response.text)
        self.assertIn('Xin chào',response.text)
        self.assertEqual(self.c.post('/api/hooks/twilio/voice',data=form).status_code,403)
        os.environ.pop('SMALLBIZ_ENABLE_LIVE_SMS',None)

    def _whatsapp(self, auto_reply=True):
        self.wa_phone = str(100000000 + self.biz)
        self.wa_secret = 'test-meta-app-secret'
        result = self.c.put('/api/whatsapp/config', json={
            'phone_number_id': self.wa_phone, 'access_token': 'fake-wa-token',
            'app_secret': self.wa_secret, 'verify_token': 'test-wa-verification',
            'auto_reply': auto_reply})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertNotIn(self.wa_secret, result.text)
        self.assertNotIn('fake-wa-token', result.text)

    def _wa_inbound(self, text, sender='14155550123', message_id=None, timestamp=None, signed=True):
        raw = json.dumps({'object': 'whatsapp_business_account', 'entry': [{'changes': [{
            'field': 'messages', 'value': {'metadata': {'phone_number_id': self.wa_phone},
            'messages': [{'id': message_id or uuid.uuid4().hex, 'from': sender,
                'timestamp': str(timestamp or int(datetime.now(timezone.utc).timestamp())),
                'type': 'text', 'text': {'body': text}}]}}]}]}).encode()
        headers = {'Content-Type': 'application/json'}
        if signed:
            headers['X-Hub-Signature-256'] = 'sha256=' + hmac.new(self.wa_secret.encode(), raw, hashlib.sha256).hexdigest()
        return self.c.post('/api/hooks/whatsapp', content=raw, headers=headers)

    def _wa_conv(self):
        return next(c for c in self.c.get('/api/conversations').json() if c['channel'] == 'WhatsApp')

    def test_whatsapp_verification_signature_and_channel_separation(self):
        self._whatsapp(False)
        query = {'hub.mode': 'subscribe', 'hub.verify_token': 'test-wa-verification', 'hub.challenge': '12345'}
        self.assertEqual(self.c.get('/api/hooks/whatsapp', params=query).text, '12345')
        query['hub.verify_token'] = 'wrong'
        self.assertEqual(self.c.get('/api/hooks/whatsapp', params=query).status_code, 403)
        sms = self.c.post('/api/demo/inbound-sms', json={'contact_id': self.contact, 'text': 'SMS'}).json()
        self.assertEqual(self._wa_inbound('Hello', signed=False).status_code, 403)
        self.assertFalse(any(c['channel'] == 'WhatsApp' for c in self.c.get('/api/conversations').json()))
        self.assertEqual(self._wa_inbound('WhatsApp', message_id='same-id').status_code, 200)
        self._wa_inbound('WhatsApp', message_id='same-id')
        conv = self._wa_conv()
        self.assertEqual(conv['contact_id'], self.contact)
        self.assertNotEqual(conv['id'], sms['conversation_id'])
        self.assertEqual(len(self.c.get(f'/api/conversations/{conv["id"]}/messages').json()), 1)

    def test_whatsapp_auto_reply_existing_contact_and_stop_start(self):
        self._whatsapp()
        self.c.put('/api/ai/provider', json={'provider': 'openai', 'api_key': 'fake-key', 'model': 'test', 'auto_reply': False})
        def fake_post(url, **kwargs):
            return FakeHTTPResponse({'messages': [{'id': 'wamid.out'}]}) if 'graph.facebook.com' in url else FakeHTTPResponse()
        with patch('enhancements.httpx.post', side_effect=fake_post) as upstream:
            self._wa_inbound('What services do you offer?')
            conv = self._wa_conv()
            messages = self.c.get(f'/api/conversations/{conv["id"]}/messages').json()
            self.assertTrue(any(m['author'] == 'builtin_ai' and m['status'] == 'sent' for m in messages), messages)
            self.assertTrue(any('graph.facebook.com' in call.args[0] for call in upstream.call_args_list))
            upstream.reset_mock()
            self._wa_inbound('STOP')
            self._wa_inbound('Another question')
            upstream.assert_not_called()
            blocked = self.c.post(f'/api/conversations/{conv["id"]}/messages', json={'body': 'Manual reply'})
            self.assertEqual(blocked.json()['status'], 'blocked_no_consent')
            upstream.assert_not_called()
            self._wa_inbound('START')
            self.assertTrue(upstream.called)
            self.c.patch(f'/api/conversations/{conv["id"]}', json={'ai_mode': 'human'})
            upstream.reset_mock()
            self._wa_inbound('Please help')
            upstream.assert_not_called()

    def test_whatsapp_old_inbound_cannot_reopen_service_window(self):
        self._whatsapp(False)
        expired = int((datetime.now(timezone.utc) - timedelta(hours=25)).timestamp())
        self._wa_inbound('Delayed webhook', timestamp=expired)
        conv = self._wa_conv()
        with patch('enhancements.httpx.post') as upstream:
            result = self.c.post(f'/api/conversations/{conv["id"]}/messages', json={'body': 'Reply'})
        self.assertEqual(result.json()['status'], 'blocked_outside_service_window')
        upstream.assert_not_called()

    def test_whatsapp_new_customer_does_not_gain_sms_consent(self):
        self._whatsapp(False)
        self.assertEqual(self._wa_inbound('Hello', sender='14155550888').status_code, 200)
        contact = next(c for c in self.c.get('/api/contacts').json() if c['phone'] == '+14155550888')
        self.assertTrue(contact['consent_whatsapp'])
        self.assertFalse(contact['consent_sms'])

    def test_channel_configuration_is_owner_only_and_tenant_scoped(self):
        self._whatsapp(False)
        email = 'channels-' + uuid.uuid4().hex[:9] + '@demo.local'
        result = self.c.post('/api/members', json={'name': 'Channel staff', 'email': email, 'password': 'password1234', 'role': 'staff'})
        self.assertEqual(result.status_code, 200, result.text)
        staff = TestClient(app)
        self.assertEqual(staff.post('/api/auth/login', json={'email': email, 'password': 'password1234'}).status_code, 200)
        for path, body in [('/api/whatsapp/config', {}), ('/api/calls/config', {}), ('/api/ai/provider', {'business_rules': 'Unapproved change'})]:
            self.assertEqual(staff.put(path, json=body).status_code, 403)
        self.c.post('/api/auth/switch', json={'business_id': 1})
        self.assertFalse(self.c.get('/api/whatsapp/config').json()['access_token_set'])
        self.assertEqual(self.c.get('/api/calls/config').json()['transfer_number'], '')

    def test_transfer_rejects_invalid_and_same_twilio_number(self):
        _, number = self._live_twilio()
        for transfer in ('invalid', number):
            self.assertEqual(self.c.put('/api/calls/config', json={'transfer_number': transfer, 'fallback': 'sms'}).status_code, 400)
        self.assertEqual(self.c.put('/api/calls/config', json={'fallback': 'invalid'}).status_code, 400)

    def _voice_setup(self, fallback='ai'):
        token, number = self._live_twilio()
        self.c.put('/api/voice/config', json={'enabled': True, 'greeting': 'Welcome to our business'})
        result = self.c.put('/api/calls/config', json={'transfer_number': '+14155550988', 'fallback': fallback})
        self.assertEqual(result.status_code, 200, result.text)
        return token, {'To': number, 'From': '+14155550123', 'CallSid': 'CA' + uuid.uuid4().hex}

    def _voice_hook(self, path, form, token):
        return self.c.post(path, data=form, headers={'X-Twilio-Signature': self._signature('http://testserver' + path, form, token)})

    def test_call_transfer_busy_falls_back_to_ai_and_completed_hangs_up(self):
        token, form = self._voice_setup()
        response = self._voice_hook('/api/hooks/twilio/voice', form, token)
        self.assertIn('<Dial', response.text)
        self.assertIn('+14155550988', response.text)
        path = '/api/hooks/twilio/voice/dial-result'
        for status in ('busy', 'no-answer', 'failed', 'canceled'):
            response = self._voice_hook(path, dict(form, DialCallStatus=status), token)
            self.assertIn('<Gather', response.text)
            self.assertNotIn('<Dial', response.text)
        self.assertIn('<Hangup', self._voice_hook(path, dict(form, DialCallStatus='completed'), token).text)
        self.assertEqual(self.c.post(path, data=form).status_code, 403)

    def test_call_fallback_none_does_not_start_ai(self):
        token, form = self._voice_setup('none')
        response = self._voice_hook('/api/hooks/twilio/voice/dial-result', dict(form, DialCallStatus='busy'), token)
        self.assertNotIn('<Gather', response.text)
        self.assertIn('<Hangup', response.text)

    def test_call_sms_sends_once_and_respects_live_gate_and_consent(self):
        token, form = self._voice_setup('sms')
        path = '/api/hooks/twilio/voice/dial-result'
        form['DialCallStatus'] = 'no-answer'
        with patch('enhancements.httpx.post', return_value=FakeHTTPResponse({'sid': 'SMtest'})) as upstream:
            response = self._voice_hook(path, form, token)
            self.assertEqual(upstream.call_count, 1)
            self.assertIn('sending a text', response.text)
            self._voice_hook(path, form, token)
            self.assertEqual(upstream.call_count, 1)
            upstream.reset_mock()
            for caller in ('+14155550777',):
                self._voice_hook(path, dict(form, From=caller, CallSid=uuid.uuid4().hex), token)
            with __import__('server').database() as db:
                db.execute('UPDATE contacts SET consent_sms=0 WHERE id=?', (self.contact,))
            self._voice_hook(path, dict(form, CallSid=uuid.uuid4().hex), token)
            upstream.assert_not_called()
            with __import__('server').database() as db:
                db.execute('UPDATE contacts SET consent_sms=1 WHERE id=?', (self.contact,))
            os.environ.pop('SMALLBIZ_ENABLE_LIVE_SMS', None)
            response = self._voice_hook(path, dict(form, CallSid=uuid.uuid4().hex), token)
            self.assertNotIn('sending a text', response.text)
            upstream.assert_not_called()

    def test_call_sms_mock_does_not_claim_delivery(self):
        token, form = self._voice_setup('sms')
        config = self.c.get('/api/sms/config').json()
        self.c.put('/api/sms/config', json={'mode': 'mock', 'account_sid': config['account_sid'], 'phone_number': form['To']})
        response = self._voice_hook('/api/hooks/twilio/voice/dial-result', dict(form, DialCallStatus='busy'), token)
        self.assertNotIn('sent a text', response.text)
        self.assertNotIn('sending a text', response.text)
        conv = next(c for c in self.c.get('/api/conversations').json() if c['channel'] == 'SMS')
        self.assertEqual(self.c.get(f'/api/conversations/{conv["id"]}/messages').json()[-1]['status'], 'mock_sent')

    def test_business_guidance_preserves_base_rules_in_ai_context(self):
        guidance = 'Answer warmly; hand pricing exceptions to the owner.'
        self.c.put('/api/ai/provider', json={'provider': 'openai', 'api_key': 'fake-key', 'model': 'test', 'business_rules': guidance})
        self.assertEqual(self.c.get('/api/ai/provider').json()['business_rules'], guidance)
        with patch('enhancements.httpx.post', return_value=FakeHTTPResponse()) as upstream:
            self.assertEqual(self.c.post('/api/ai/chat', json={'message': 'What can you do?'}).status_code, 200)
        system = upstream.call_args.kwargs['json']['messages'][0]['content']
        self.assertIn(guidance, system)
        self.assertIn('Never invent prices', system)
        self.assertIn('unless a booking tool confirmed it', system)


if __name__=='__main__':
    import unittest
    unittest.main()
