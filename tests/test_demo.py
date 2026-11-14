"""Runnable smoke + tenant safety tests: python -m unittest discover -s tests -v"""
import os
import tempfile
import unittest
from pathlib import Path

_tmp = tempfile.TemporaryDirectory(prefix='smallbiz-test-')
os.environ['SMALLBIZ_DB'] = str(Path(_tmp.name) / 'test.sqlite3')
from fastapi.testclient import TestClient  # noqa: E402
from server import app  # noqa: E402


class DemoTests(unittest.TestCase):
    def login(self, email='demo@smallbiz.local'):
        client = TestClient(app)
        res = client.post('/api/auth/login', json={'email':email,'password':'demo123'})
        self.assertEqual(res.status_code,200,res.text)
        return client

    def test_auth_and_tenant_isolation(self):
        guest=TestClient(app)
        self.assertEqual(guest.get('/api/contacts').status_code,401)
        luna=self.login('luna@demo.local')
        bright=self.login('bright@demo.local')
        luna_ids={x['id'] for x in luna.get('/api/contacts').json()}
        bright_ids={x['id'] for x in bright.get('/api/contacts').json()}
        self.assertTrue(luna_ids)
        self.assertTrue(bright_ids)
        self.assertTrue(luna_ids.isdisjoint(bright_ids))
        self.assertEqual(luna.get(f'/api/contacts/{next(iter(bright_ids))}/timeline').status_code,404)
        self.assertEqual(bright.patch(f'/api/contacts/{next(iter(luna_ids))}',json={
            'name':'Wrong tenant','phone':'+15550000001'}).status_code,404)
        self.assertEqual(luna.post('/api/auth/switch',json={'business_id':2}).status_code,404)
        both=self.login()
        self.assertEqual(both.post('/api/auth/switch',json={'business_id':2}).status_code,200)
        self.assertEqual(both.get('/api/auth/me').json()['business_id'],2)

    def test_contacts_notes_and_mock_inbox(self):
        c=self.login('luna@demo.local')
        r=c.post('/api/contacts',json={'name':'Test Person','phone':'+15125559998','consent_sms':True})
        self.assertEqual(r.status_code,200,r.text)
        ct=r.json()['id']
        self.assertEqual(c.post(f'/api/contacts/{ct}/notes',json={'text':'Prefers Friday mornings'}).status_code,200)
        self.assertEqual(len(c.get(f'/api/contacts/{ct}/timeline').json()['notes']),1)
        sms=c.post('/api/demo/inbound-sms',json={'contact_id':ct,'text':'Can I book a service?','event_key':'sms-test-one'})
        self.assertEqual(sms.status_code,200,sms.text)
        self.assertFalse(sms.json()['ai_queued'])
        duplicate=c.post('/api/demo/inbound-sms',json={'contact_id':ct,'text':'Can I book a service?','event_key':'sms-test-one'})
        self.assertTrue(duplicate.json()['duplicate'])
        conversation=sms.json()['conversation_id']
        out=c.post(f'/api/conversations/{conversation}/messages',json={'body':'Of course! This is a demo.'})
        self.assertEqual(out.json()['provider'],'mock')
        self.assertEqual(len(c.get(f'/api/conversations/{conversation}/messages').json()),2)

    def test_missed_call_consent_and_dedup(self):
        c=self.login('luna@demo.local')
        yes=c.post('/api/contacts',json={'name':'Consented','phone':'+15125551111','consent_sms':True}).json()['id']
        no=c.post('/api/contacts',json={'name':'Not Consented','phone':'+15125552222','consent_sms':False}).json()['id']
        r=c.post('/api/demo/missed-call',json={'contact_id':yes,'event_key':'call-a'}).json()
        self.assertTrue(r['mock_textback_sent'])
        n=c.post('/api/demo/missed-call',json={'contact_id':no,'event_key':'call-b'}).json()
        self.assertFalse(n['mock_textback_sent'])
        self.assertTrue(c.post('/api/demo/missed-call',json={'contact_id':yes,'event_key':'call-a'}).json()['duplicate'])
        self.assertFalse(c.post('/api/demo/missed-call',json={'contact_id':yes,'event_key':'call-a-again'}).json()['mock_textback_sent'])
        self.assertEqual(len(c.get(f'/api/conversations/{r["conversation_id"]}/messages').json()),1)

    def test_booking_and_double_booking_guard(self):
        from datetime import datetime,timedelta,timezone
        c=self.login('luna@demo.local')
        ids=c.get('/api/contacts').json()
        service=c.get('/api/services').json()[0]
        staff=c.get('/api/staff').json()[0]
        start=(datetime.now(timezone.utc)+timedelta(days=9)).replace(hour=17,minute=0,second=0,microsecond=0).isoformat()
        body={'contact_id':ids[0]['id'],'service_id':service['id'],'staff_id':staff['id'],'starts_at':start}
        a=c.post('/api/appointments',json=body)
        self.assertEqual(a.status_code,200,a.text)
        self.assertEqual(c.post('/api/appointments',json=body).status_code,409)
        self.assertEqual(c.patch(f'/api/appointments/{a.json()["id"]}',json={'status':'cancelled'}).status_code,200)
        b=c.post('/api/appointments',json=body)
        self.assertEqual(b.status_code,200,b.text)
        self.assertEqual(c.patch(f'/api/appointments/{a.json()["id"]}',json={'status':'confirmed'}).status_code,409)

    def test_external_ai_contract_and_handoff(self):
        c=self.login('luna@demo.local')
        token=c.get('/api/ai').json()['token']
        self.assertTrue(token)
        contact=c.get('/api/contacts').json()[0]['id']
        sms=c.post('/api/demo/inbound-sms',json={'contact_id':contact,'text':'I need a booking','event_key':'ai-contract-test'}).json()
        conv=sms['conversation_id']
        self.assertEqual(c.patch(f'/api/conversations/{conv}',json={'ai_mode':'external'}).status_code,200)
        ai=TestClient(app,headers={'Authorization':f'Bearer {token}'})
        pending=ai.get('/api/integrations/ai/inbox')
        self.assertEqual(pending.status_code,200,pending.text)
        self.assertIn(sms['message_id'],[x['message_id'] for x in pending.json()])
        context=ai.get(f'/api/integrations/ai/context/{conv}').json()
        self.assertEqual(context['business']['name'],'Luna Nail Studio')
        self.assertGreater(len(context['staff']),0)
        self.assertGreater(len(context['services']),0)
        from datetime import datetime,timedelta
        date=(datetime.now()+timedelta(days=10)).date().isoformat()
        av=ai.get('/api/integrations/ai/availability',params={'date':date,'staff_id':context['staff'][0]['id'],'service_id':context['services'][0]['id']})
        self.assertEqual(av.status_code,200,av.text)
        self.assertIn('slots',av.json())
        payload={'conversation_id':conv,'inbound_message_id':sms['message_id'],'reply':'Sure, which service?'}
        rep=ai.post('/api/integrations/ai/reply',json=payload)
        self.assertEqual(rep.status_code,200,rep.text)
        self.assertEqual(rep.json()['provider'],'mock')
        self.assertTrue(ai.post('/api/integrations/ai/reply',json=payload).json()['duplicate'])
        self.assertEqual(ai.get('/api/integrations/ai/context/999999').status_code,404)
        self.assertEqual(ai.post('/api/integrations/ai/handoff',json={'conversation_id':conv}).status_code,200)
        self.assertEqual(ai.post('/api/integrations/ai/reply',json=payload).status_code,409)
        no_token=TestClient(app)
        self.assertEqual(no_token.get('/api/integrations/ai/inbox').status_code,401)

    def test_role_restrictions_and_business_creation(self):
        staff=self.login('staff@luna.demo')
        self.assertEqual(staff.get('/api/ai').json()['token'],None)
        self.assertEqual(staff.post('/api/ai/rotate-token').status_code,403)
        self.assertEqual(staff.post('/api/services',json={'name':'Nope','duration':60,'price':10}).status_code,403)
        owner=self.login('luna@demo.local')
        new=owner.post('/api/businesses',json={'name':'Demo Pet Salon','industry':'Pet care','timezone':'America/New_York'})
        self.assertEqual(new.status_code,200,new.text)
        new_id=new.json()['id']
        self.assertEqual(owner.post('/api/auth/switch',json={'business_id':new_id}).status_code,200)
        self.assertEqual(owner.get('/api/contacts').json(),[])
        self.assertEqual(len(owner.get('/api/automations').json()['rules']),3)
        m=owner.post('/api/members',json={'name':'New Staff','email':'newstaff@demo.local','password':'staffpass123','role':'staff'})
        self.assertEqual(m.status_code,200,m.text)
        self.assertEqual(len(owner.get('/api/members').json()),2)


if __name__ == '__main__':
    unittest.main()
