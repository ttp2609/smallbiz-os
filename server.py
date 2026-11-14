"""Small Business OS demo: multi-tenant CRM, inbox, bookings, automation, external AI adapter.

Run: python server.py   (after pip install -r requirements.txt)
This is a LOCAL DEMO, not a production deployment.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get('SMALLBIZ_DB', str(ROOT / 'demo.sqlite3')))
NOW = lambda: datetime.now(timezone.utc).isoformat(timespec='seconds')
app = FastAPI(title='Small Business OS Demo', version='0.2.0', docs_url='/api/docs', openapi_url='/api/openapi.json')


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB), timeout=10, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys = ON')
    c.execute('PRAGMA busy_timeout = 5000')
    return c


@contextmanager
def database():
    c = connect()
    try:
        yield c
    finally:
        c.close()


def rows(cursor):
    return [dict(x) for x in cursor.fetchall()]


def one(c, sql, args=()):
    r = c.execute(sql, args).fetchone()
    return dict(r) if r is not None else None


def require(record, message='Not found'):
    if record is None:
        raise HTTPException(404, message)
    return record


def password_hash(password: str, salt: str | None = None):
    salt = salt or secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 220000).hex()
    return f'{salt}${hashed}'


def password_ok(password: str, saved: str):
    try:
        salt, digest = saved.split('$')
        return hmac.compare_digest(password_hash(password, salt).split('$')[1], digest)
    except (ValueError, TypeError):
        return False


def local_iso_date(days=0, tz='America/Chicago'):
    return (datetime.now(ZoneInfo(tz)) + timedelta(days=days)).date().isoformat()


def local_to_utc(date: str, hour: int, minute: int, tz: str):
    dt = datetime.fromisoformat(f'{date}T{hour:02}:{minute:02}:00').replace(tzinfo=ZoneInfo(tz))
    return dt.astimezone(timezone.utc).isoformat(timespec='seconds')


def parse_dt(value: str):
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            raise ValueError('Timezone is required')
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        raise HTTPException(400, 'Invalid datetime; send an ISO-8601 timestamp with timezone')


def init_db():
    with database() as c:
        c.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS businesses (id INTEGER PRIMARY KEY, name TEXT NOT NULL, industry TEXT NOT NULL, timezone TEXT NOT NULL, phone TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '', hours TEXT NOT NULL DEFAULT 'Mon–Sat · 9:00 AM–6:00 PM', ai_token TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS memberships (user_id INTEGER NOT NULL, business_id INTEGER NOT NULL, role TEXT NOT NULL, PRIMARY KEY(user_id,business_id));
        CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, business_id INTEGER NOT NULL, expires_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY, business_id INTEGER NOT NULL, name TEXT NOT NULL, phone TEXT NOT NULL, email TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'Lead', source TEXT NOT NULL DEFAULT 'Website', tags TEXT NOT NULL DEFAULT '', consent_sms INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_contacts_business ON contacts(business_id, name);
        CREATE TABLE IF NOT EXISTS contact_notes (id INTEGER PRIMARY KEY, business_id INTEGER NOT NULL, contact_id INTEGER NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS conversations (id INTEGER PRIMARY KEY, business_id INTEGER NOT NULL, contact_id INTEGER NOT NULL, channel TEXT NOT NULL DEFAULT 'SMS', status TEXT NOT NULL DEFAULT 'open', ai_mode TEXT NOT NULL DEFAULT 'human', last_message_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_conversations_business ON conversations(business_id,last_message_at);
        CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, business_id INTEGER NOT NULL, conversation_id INTEGER NOT NULL, direction TEXT NOT NULL, author TEXT NOT NULL, body TEXT NOT NULL, status TEXT NOT NULL, ai_handled INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS calls (id INTEGER PRIMARY KEY, business_id INTEGER NOT NULL, contact_id INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS services (id INTEGER PRIMARY KEY, business_id INTEGER NOT NULL, name TEXT NOT NULL, duration INTEGER NOT NULL, price REAL NOT NULL DEFAULT 0, color TEXT NOT NULL DEFAULT '#6c5ce7');
        CREATE TABLE IF NOT EXISTS staff (id INTEGER PRIMARY KEY, business_id INTEGER NOT NULL, name TEXT NOT NULL, title TEXT NOT NULL DEFAULT 'Team member', color TEXT NOT NULL DEFAULT '#667eea');
        CREATE TABLE IF NOT EXISTS appointments (id INTEGER PRIMARY KEY, business_id INTEGER NOT NULL, contact_id INTEGER NOT NULL, service_id INTEGER NOT NULL, staff_id INTEGER NOT NULL, starts_at TEXT NOT NULL, ends_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'confirmed', notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_appts_overlap ON appointments(business_id,staff_id,starts_at,ends_at,status);
        CREATE TABLE IF NOT EXISTS automation_rules (id INTEGER PRIMARY KEY, business_id INTEGER NOT NULL, key TEXT NOT NULL, name TEXT NOT NULL, description TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, UNIQUE(business_id,key));
        CREATE TABLE IF NOT EXISTS automation_logs (id INTEGER PRIMARY KEY, business_id INTEGER NOT NULL, rule_key TEXT NOT NULL, detail TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS knowledge_entries (id INTEGER PRIMARY KEY, business_id INTEGER NOT NULL, question TEXT NOT NULL, answer TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS inbound_events (id INTEGER PRIMARY KEY, business_id INTEGER NOT NULL, event_key TEXT NOT NULL, kind TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(business_id,event_key));
        CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY, business_id INTEGER NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL);
        ''')
        if one(c, 'SELECT id FROM businesses LIMIT 1'):
            return
        for name,email in [('Alex Morgan','demo@smallbiz.local'),('Mia Nguyen','luna@demo.local'),('Daniel Brooks','bright@demo.local'),('Sofia Rivera','staff@luna.demo')]:
            c.execute('INSERT INTO users(name,email,password_hash) VALUES(?,?,?)',(name,email,password_hash('demo123')))
        biz = [
            ('Luna Nail Studio','Beauty & wellness','America/Chicago','+1 (512) 555-0198','1208 South Lamar Blvd, Austin, TX',secrets.token_urlsafe(30)),
            ('BrightHome Services','Home services','America/Los_Angeles','+1 (206) 555-0144','472 Pine Street, Seattle, WA',secrets.token_urlsafe(30))
        ]
        c.executemany('INSERT INTO businesses(name,industry,timezone,phone,address,ai_token) VALUES(?,?,?,?,?,?)',biz)
        c.executemany('INSERT INTO memberships(user_id,business_id,role) VALUES(?,?,?)',[(1,1,'owner'),(1,2,'owner'),(2,1,'owner'),(3,2,'owner'),(4,1,'staff')])
        for b_id, contacts in [(1,[
            ('Olivia Martinez','+15125550141','olivia@example.com','Customer','Instagram','VIP,Regular',1),
            ('Sophia Chen','+15125550142','sophia@example.com','Lead','Google','New lead',1),
            ('Emma Williams','+15125550143','emma@example.com','Customer','Referral','Gel manicure',1),
            ('Ava Thompson','+15125550144','ava@example.com','Lead','Phone','Follow up',0),
            ('Isabella Garcia','+15125550145','isabella@example.com','Customer','Walk-in','Loyal',1),
        ]),(2,[
            ('Noah Peterson','+12065550171','noah@example.com','Lead','Google','New lead',1),
            ('Liam Baker','+12065550172','liam@example.com','Customer','Referral','Maintenance',1),
            ('Charlotte Lee','+12065550173','charlotte@example.com','Lead','Phone','Urgent',0),
        ])]:
            for x in contacts:
                c.execute('INSERT INTO contacts(business_id,name,phone,email,status,source,tags,consent_sms,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(b_id,*x,NOW()))
        for b_id, data in [(1,[('Gel Manicure',60,45,'#7c6ef6'),('Classic Pedicure',45,35,'#ff9b88'),('Nail Art',90,80,'#65c6bb')]),(2,[('Home Cleaning',120,140,'#7c6ef6'),('Deep Cleaning',180,240,'#ff9b88'),('Maintenance Visit',60,85,'#65c6bb')])]:
            for x in data:
                c.execute('INSERT INTO services(business_id,name,duration,price,color) VALUES(?,?,?,?,?)',(b_id,*x))
        for b_id,data in [(1,[('Mia','Nail technician','#806ff5'),('Jessica','Nail artist','#ff9e8c'),('Rachel','Nail technician','#58bcb0')]),(2,[('Daniel','Field specialist','#806ff5'),('Chris','Cleaning specialist','#ff9e8c')])]:
            for x in data:
                c.execute('INSERT INTO staff(business_id,name,title,color) VALUES(?,?,?,?)',(b_id,*x))
        for b_id,rules in [(1,[('missed_call','Missed-call text back','Send a mock SMS when a consented customer misses a call.'),('booking_confirm','Booking confirmations','Create a confirmation in the mock outbox after appointments.'),('new_lead','New lead alerts','Log a notification when a new inbound message arrives.')]),(2,[('missed_call','Missed-call text back','Send a mock SMS when a consented customer misses a call.'),('booking_confirm','Booking confirmations','Create a confirmation in the mock outbox after appointments.'),('new_lead','New lead alerts','Log a notification when a new inbound message arrives.')])]:
            for k,n,d in rules:
                c.execute('INSERT INTO automation_rules(business_id,key,name,description,enabled) VALUES(?,?,?,?,?)',(b_id,k,n,d,1))
        for b_id,qs in [(1,[('What are your hours?','Open Monday to Saturday, 9 AM to 6 PM.'),('Do you accept walk-ins?','Walk-ins are welcome subject to availability; appointments are recommended.'),('How much is a gel manicure?','A gel manicure starts at $45 and usually takes 60 minutes.'),('Where are you located?','1208 South Lamar Blvd, Austin, Texas.')]),(2,[('What areas do you serve?','We serve the Seattle metro area.'),('What is your availability?','Ask our team for a current slot; do not promise a time without booking.'),('What is included in home cleaning?','Kitchen, bath, bedrooms and general living areas. Deep cleaning is separately priced.')])]:
            for q,a in qs:
                c.execute('INSERT INTO knowledge_entries(business_id,question,answer) VALUES(?,?,?)',(b_id,q,a))
        for b_id,ct_id,content in [(1,1,[('inbound','customer','Hi! Can I book a gel manicure for this week?'),('outbound','staff','Of course! What day works best for you?'),('inbound','customer','Friday afternoon would be perfect.')]),(1,2,[('inbound','customer','How much is a classic pedicure?')]),(1,3,[('inbound','customer','Thanks for the beautiful nails last time!'),('outbound','staff','You are so welcome! 💜')]),(1,4,[('inbound','customer','Can somebody call me back?')]),(2,6,[('inbound','customer','Hi, I need a home cleaning quote for next week.')]),(2,7,[('inbound','customer','When is my next maintenance visit?')])]:
            c.execute('INSERT INTO conversations(business_id,contact_id,channel,status,ai_mode,last_message_at) VALUES(?,?,?,?,?,?)',(b_id,ct_id,'SMS','open','human',NOW()))
            conv_id=c.execute('SELECT last_insert_rowid()').fetchone()[0]
            for offset,(direction,author,body) in enumerate(content):
                ts=(datetime.now(timezone.utc)-timedelta(minutes=27-offset*8)).isoformat(timespec='seconds')
                c.execute('INSERT INTO messages(business_id,conversation_id,direction,author,body,status,ai_handled,created_at) VALUES(?,?,?,?,?,?,?,?)',(b_id,conv_id,direction,author,body,'delivered',1,ts))
            c.execute('UPDATE conversations SET last_message_at=? WHERE id=?',(ts,conv_id))
        for b_id,ct,sv,st,day,hour in [(1,1,1,1,0,13),(1,3,2,2,0,15),(1,5,3,3,1,11),(1,2,1,1,2,10),(1,1,2,2,3,14),(2,6,4,4,0,14),(2,7,6,5,1,10)]:
            tz='America/Chicago' if b_id==1 else 'America/Los_Angeles'
            start=datetime.fromisoformat(local_to_utc(local_iso_date(day,tz),hour,0,tz))
            duration=one(c,'SELECT duration FROM services WHERE id=?',(sv,))['duration']
            c.execute('INSERT INTO appointments(business_id,contact_id,service_id,staff_id,starts_at,ends_at,status,notes,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(b_id,ct,sv,st,start.isoformat(timespec='seconds'),(start+timedelta(minutes=duration)).isoformat(timespec='seconds'),'confirmed','',NOW()))
        c.execute('INSERT INTO contact_notes(business_id,contact_id,text,created_at) VALUES(?,?,?,?)',(1,1,'Prefers neutral nail colors. Regular Friday bookings.',NOW()))
        for b_id in [1,2]:
            c.execute('INSERT INTO audit_logs(business_id,action,detail,created_at) VALUES(?,?,?,?)',(b_id,'demo.initialized','Sample workspace created',NOW()))


init_db()


class LoginIn(BaseModel):
    email: str
    password: str


class SwitchIn(BaseModel):
    business_id: int


class ContactIn(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    phone: str = Field(min_length=5,max_length=35)
    email: str = ''
    status: str = 'Lead'
    source: str = 'Manual'
    tags: str = ''
    consent_sms: bool = False


class NoteIn(BaseModel):
    text: str = Field(min_length=1,max_length=2000)


class MessageIn(BaseModel):
    body: str = Field(min_length=1,max_length=2500)


class ConversationUpdate(BaseModel):
    status: str | None = None
    ai_mode: str | None = None


class EventIn(BaseModel):
    contact_id: int
    text: str = ''
    event_key: str | None = None


class AppointmentIn(BaseModel):
    contact_id: int
    service_id: int
    staff_id: int
    starts_at: str
    notes: str = ''


class StatusIn(BaseModel):
    status: str


class ToggleIn(BaseModel):
    enabled: bool


class KnowledgeIn(BaseModel):
    question: str = Field(min_length=1,max_length=200)
    answer: str = Field(min_length=1,max_length=2000)


class BusinessIn(BaseModel):
    name: str = Field(min_length=2,max_length=120)
    phone: str = ''
    address: str = ''
    hours: str = ''


class StaffIn(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    title: str = 'Team member'


class ServiceIn(BaseModel):
    name: str = Field(min_length=1,max_length=120)
    duration: int = Field(ge=15,le=480)
    price: float = Field(ge=0)


class NewBusinessIn(BaseModel):
    name: str = Field(min_length=2,max_length=120)
    industry: str = 'General services'
    timezone: str = 'America/Chicago'
    phone: str = ''
    address: str = ''


class MemberIn(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    email: str = Field(min_length=5,max_length=160)
    password: str = Field(min_length=8,max_length=150)
    role: str = 'staff'


class AIReplyIn(BaseModel):
    conversation_id: int
    reply: str = Field(min_length=1,max_length=2500)
    inbound_message_id: int


class AIHandoffIn(BaseModel):
    conversation_id: int


def auth(request: Request):
    tok=request.cookies.get('sb_session')
    if not tok:
        raise HTTPException(401,'Please sign in')
    with database() as c:
        data=one(c, '''SELECT s.user_id, s.business_id, u.name AS user_name,u.email,m.role,
            b.name AS business_name,b.timezone FROM sessions s JOIN users u ON u.id=s.user_id
            JOIN memberships m ON m.user_id=s.user_id AND m.business_id=s.business_id
            JOIN businesses b ON b.id=s.business_id WHERE s.token=? AND s.expires_at>?''',(tok,NOW()))
        if not data:
            raise HTTPException(401,'Session expired')
        return data


def is_owner(ctx):
    if ctx['role']!='owner':
        raise HTTPException(403,'Owner permission required')


def log(c,biz,action,detail):
    c.execute('INSERT INTO audit_logs(business_id,action,detail,created_at) VALUES(?,?,?,?)',(biz,action,detail,NOW()))


def get_contact(c,biz,contact_id):
    return require(one(c,'SELECT * FROM contacts WHERE id=? AND business_id=?',(contact_id,biz)),'Contact not found')


def get_conv(c,biz,conv_id):
    return require(one(c,'SELECT * FROM conversations WHERE id=? AND business_id=?',(conv_id,biz)),'Conversation not found')


def ensure_conv(c,biz,contact_id,channel='SMS'):
    conv=one(c,'SELECT * FROM conversations WHERE business_id=? AND contact_id=? AND channel=? ORDER BY id DESC LIMIT 1',(biz,contact_id,channel))
    if conv:
        return conv['id']
    c.execute('INSERT INTO conversations(business_id,contact_id,channel,status,ai_mode,last_message_at) VALUES(?,?,?,?,?,?)',(biz,contact_id,channel,'open','human',NOW()))
    return c.execute('SELECT last_insert_rowid()').fetchone()[0]


def append_message(c,biz,conv_id,direction,author,body,status='delivered',ai_handled=0):
    stamp=NOW()
    c.execute('INSERT INTO messages(business_id,conversation_id,direction,author,body,status,ai_handled,created_at) VALUES(?,?,?,?,?,?,?,?)',(biz,conv_id,direction,author,body,status,ai_handled,stamp))
    mid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    c.execute('UPDATE conversations SET last_message_at=?,status=? WHERE id=? AND business_id=?',(stamp,'open',conv_id,biz))
    return mid


def rule_on(c,biz,key):
    r=one(c,'SELECT enabled FROM automation_rules WHERE business_id=? AND key=?',(biz,key))
    return bool(r and r['enabled'])


def autom_log(c,biz,key,detail,result='completed'):
    c.execute('INSERT INTO automation_logs(business_id,rule_key,detail,result,created_at) VALUES(?,?,?,?,?)',(biz,key,detail,result,NOW()))


def dedup_event(c,biz,key,kind):
    if key:
        try:
            c.execute('INSERT INTO inbound_events(business_id,event_key,kind,created_at) VALUES(?,?,?,?)',(biz,key,kind,NOW()))
        except sqlite3.IntegrityError:
            return True
    return False


@app.post('/api/auth/login')
def login(data:LoginIn,response:Response):
    with database() as c:
        user=one(c,'SELECT * FROM users WHERE lower(email)=lower(?)',(data.email.strip(),))
        if not user or not password_ok(data.password,user['password_hash']):
            raise HTTPException(401,'Invalid email or password')
        membership=one(c,'SELECT business_id FROM memberships WHERE user_id=? ORDER BY business_id LIMIT 1',(user['id'],))
        if not membership:
            raise HTTPException(403,'No workspace access')
        token=secrets.token_urlsafe(32)
        expires=(datetime.now(timezone.utc)+timedelta(days=7)).isoformat(timespec='seconds')
        c.execute('INSERT INTO sessions(token,user_id,business_id,expires_at) VALUES(?,?,?,?)',(token,user['id'],membership['business_id'],expires))
        response.set_cookie('sb_session',token,httponly=True,samesite='lax',secure=False,max_age=7*24*3600,path='/')
        return {'ok':True}


@app.post('/api/auth/logout')
def logout(request:Request,response:Response):
    tok=request.cookies.get('sb_session')
    with database() as c:
        c.execute('DELETE FROM sessions WHERE token=?',(tok,))
    response.delete_cookie('sb_session',path='/')
    return {'ok':True}


@app.get('/api/auth/me')
def me(ctx=Depends(auth)):
    with database() as c:
        businesses=rows(c.execute('SELECT b.id,b.name,b.industry,b.timezone,m.role FROM businesses b JOIN memberships m ON m.business_id=b.id WHERE m.user_id=? ORDER BY b.id',(ctx['user_id'],)))
    return {'user':{'id':ctx['user_id'],'name':ctx['user_name'],'email':ctx['email']},'business_id':ctx['business_id'],'role':ctx['role'],'businesses':businesses}


@app.post('/api/auth/switch')
def switch(data:SwitchIn, request:Request,ctx=Depends(auth)):
    with database() as c:
        require(one(c,'SELECT role FROM memberships WHERE user_id=? AND business_id=?',(ctx['user_id'],data.business_id)),'Workspace not found')
        c.execute('UPDATE sessions SET business_id=? WHERE token=?',(data.business_id,request.cookies.get('sb_session')))
    return {'ok':True}


@app.get('/api/dashboard')
def dashboard(ctx=Depends(auth)):
    biz=ctx['business_id']
    with database() as c:
        counts={
            'contacts':one(c,'SELECT COUNT(*) AS n FROM contacts WHERE business_id=?',(biz,))['n'],
            'leads':one(c,"SELECT COUNT(*) AS n FROM contacts WHERE business_id=? AND status='Lead'",(biz,))['n'],
            'open_conversations':one(c,"SELECT COUNT(*) AS n FROM conversations WHERE business_id=? AND status='open'",(biz,))['n'],
            'appointments':one(c,"SELECT COUNT(*) AS n FROM appointments WHERE business_id=? AND status!='cancelled'",(biz,))['n'],
            'unhandled':one(c,"SELECT COUNT(*) AS n FROM messages m JOIN conversations co ON co.id=m.conversation_id WHERE m.business_id=? AND m.direction='inbound' AND m.ai_handled=0 AND co.ai_mode='external'",(biz,))['n']
        }
        activity=rows(c.execute('''SELECT 'message' AS type, m.body AS title,ct.name AS person,m.created_at AS at
          FROM messages m JOIN conversations co ON co.id=m.conversation_id JOIN contacts ct ON ct.id=co.contact_id
          WHERE m.business_id=? UNION ALL SELECT 'booking',s.name,ct.name,a.created_at
          FROM appointments a JOIN contacts ct ON ct.id=a.contact_id JOIN services s ON s.id=a.service_id
          WHERE a.business_id=? ORDER BY at DESC LIMIT 7''',(biz,biz)))
        upcoming=rows(c.execute('''SELECT a.id,a.starts_at,a.status,ct.name AS contact,s.name AS service,st.name AS staff
          FROM appointments a JOIN contacts ct ON ct.id=a.contact_id JOIN services s ON s.id=a.service_id
          JOIN staff st ON st.id=a.staff_id WHERE a.business_id=? AND a.status='confirmed' AND a.starts_at >=? ORDER BY a.starts_at LIMIT 5''',(biz,NOW())))
        last7=[]
        for i in range(6,-1,-1):
            d=(datetime.now(timezone.utc)-timedelta(days=i)).date().isoformat()
            n=one(c,'SELECT COUNT(*) AS n FROM messages WHERE business_id=? AND direction=? AND substr(created_at,1,10)=?',(biz,'inbound',d))['n']
            last7.append({'day':d,'count':n})
        return {'counts':counts,'activity':activity,'upcoming':upcoming,'volume':last7}


@app.get('/api/contacts')
def contacts(q:str='',ctx=Depends(auth)):
    with database() as c:
        return rows(c.execute('''SELECT ct.*, (SELECT COUNT(*) FROM appointments a WHERE a.contact_id=ct.id AND a.business_id=ct.business_id) AS bookings,
          (SELECT MAX(co.last_message_at) FROM conversations co WHERE co.contact_id=ct.id AND co.business_id=ct.business_id) AS last_message
          FROM contacts ct WHERE ct.business_id=? AND (ct.name LIKE ? OR ct.phone LIKE ? OR ct.email LIKE ?) ORDER BY ct.id DESC''',(ctx['business_id'],*(f'%{q.strip()}%',)*3)))


@app.post('/api/contacts')
def create_contact(data:ContactIn,ctx=Depends(auth)):
    with database() as c:
        c.execute('''INSERT INTO contacts(business_id,name,phone,email,status,source,tags,consent_sms,created_at) VALUES(?,?,?,?,?,?,?,?,?)''',(ctx['business_id'],data.name.strip(),data.phone.strip(),data.email.strip(),data.status,data.source,data.tags,int(data.consent_sms),NOW()))
        ident=c.execute('SELECT last_insert_rowid()').fetchone()[0]
        log(c,ctx['business_id'],'contact.created',f'Contact #{ident}')
        return {'id':ident}


@app.patch('/api/contacts/{ident}')
def edit_contact(ident:int,data:ContactIn,ctx=Depends(auth)):
    with database() as c:
        get_contact(c,ctx['business_id'],ident)
        c.execute('''UPDATE contacts SET name=?,phone=?,email=?,status=?,source=?,tags=?,consent_sms=? WHERE id=? AND business_id=?''',(data.name.strip(),data.phone.strip(),data.email.strip(),data.status,data.source,data.tags,int(data.consent_sms),ident,ctx['business_id']))
        log(c,ctx['business_id'],'contact.updated',f'Contact #{ident}')
    return {'ok':True}


@app.get('/api/contacts/{ident}/timeline')
def contact_timeline(ident:int,ctx=Depends(auth)):
    with database() as c:
        get_contact(c,ctx['business_id'],ident)
        notes=rows(c.execute('SELECT * FROM contact_notes WHERE business_id=? AND contact_id=? ORDER BY id DESC',(ctx['business_id'],ident)))
        messages=rows(c.execute('''SELECT m.* FROM messages m JOIN conversations co ON m.conversation_id=co.id WHERE m.business_id=? AND co.contact_id=? ORDER BY m.id DESC LIMIT 30''',(ctx['business_id'],ident)))
        return {'notes':notes,'messages':messages}


@app.post('/api/contacts/{ident}/notes')
def add_note(ident:int,data:NoteIn,ctx=Depends(auth)):
    with database() as c:
        get_contact(c,ctx['business_id'],ident)
        c.execute('INSERT INTO contact_notes(business_id,contact_id,text,created_at) VALUES(?,?,?,?)',(ctx['business_id'],ident,data.text,NOW()))
        return {'ok':True}


@app.get('/api/conversations')
def conversations(ctx=Depends(auth)):
    with database() as c:
        return rows(c.execute('''SELECT co.*,ct.name AS contact_name,ct.phone AS contact_phone,ct.email AS contact_email,ct.tags AS contact_tags,ct.consent_sms,
          (SELECT m.body FROM messages m WHERE m.conversation_id=co.id ORDER BY m.id DESC LIMIT 1) AS last_message,
          (SELECT COUNT(*) FROM messages m WHERE m.conversation_id=co.id AND m.direction='inbound' AND m.ai_handled=0) AS pending
          FROM conversations co JOIN contacts ct ON ct.id=co.contact_id
          WHERE co.business_id=? ORDER BY co.last_message_at DESC,co.id DESC''',(ctx['business_id'],)))


@app.get('/api/conversations/{ident}/messages')
def conversation_messages(ident:int,ctx=Depends(auth)):
    with database() as c:
        get_conv(c,ctx['business_id'],ident)
        return rows(c.execute('SELECT * FROM messages WHERE business_id=? AND conversation_id=? ORDER BY id ASC',(ctx['business_id'],ident)))


@app.post('/api/conversations/{ident}/messages')
def send_message(ident:int,data:MessageIn,ctx=Depends(auth)):
    with database() as c:
        co=get_conv(c,ctx['business_id'],ident)
        get_contact(c,ctx['business_id'],co['contact_id'])
        mid=append_message(c,ctx['business_id'],ident,'outbound','staff',data.body,'mock_sent')
        log(c,ctx['business_id'],'message.created',f'Message #{mid} created')
    result=dispatch_outbound(ctx['business_id'],mid)
    return {'id':mid,**result}


@app.patch('/api/conversations/{ident}')
def update_conversation(ident:int,data:ConversationUpdate,ctx=Depends(auth)):
    if data.status is not None and data.status not in ('open','closed'):
        raise HTTPException(400,'Invalid status')
    if data.ai_mode is not None and data.ai_mode not in ('human','external','builtin'):
        raise HTTPException(400,'Invalid mode')
    with database() as c:
        co=get_conv(c,ctx['business_id'],ident)
        c.execute('UPDATE conversations SET status=?,ai_mode=? WHERE id=? AND business_id=?',(data.status or co['status'],data.ai_mode or co['ai_mode'],ident,ctx['business_id']))
        log(c,ctx['business_id'],'conversation.updated',f'Conversation #{ident}')
    return {'ok':True}


@app.post('/api/demo/inbound-sms')
def inbound_sms(data:EventIn,background:BackgroundTasks,ctx=Depends(auth)):
    if not data.text.strip():
        raise HTTPException(400,'Message text required')
    with database() as c:
        c.execute('BEGIN IMMEDIATE')
        ct=get_contact(c,ctx['business_id'],data.contact_id)
        if dedup_event(c,ctx['business_id'],data.event_key,'inbound-sms'):
            c.commit(); return {'duplicate':True}
        conv=ensure_conv(c,ctx['business_id'],data.contact_id)
        mid=append_message(c,ctx['business_id'],conv,'inbound','customer',data.text.strip(),ai_handled=0)
        if data.text.strip().upper() in ('STOP','UNSUBSCRIBE','CANCEL','END','QUIT'):
            c.execute('UPDATE contacts SET consent_sms=0 WHERE business_id=? AND id=?',(ctx['business_id'],ct['id']))
        if rule_on(c,ctx['business_id'],'new_lead') and ct['status']=='Lead':
            autom_log(c,ctx['business_id'],'new_lead',f'Inbound message from lead {ct["name"]}')
        c.commit()
        is_external=one(c,'SELECT ai_mode FROM conversations WHERE id=? AND business_id=?',(conv,ctx['business_id']))['ai_mode']=='external'
        background.add_task(handle_workflow_event,ctx['business_id'],'sms_received',ct['id'],data.text.strip(),True)
        if data.text.strip().upper() not in ('STOP','UNSUBSCRIBE','CANCEL','END','QUIT'):
            background.add_task(auto_reply,ctx['business_id'],conv,mid,True)
        return {'conversation_id':conv,'message_id':mid,'provider':'mock','ai_queued':is_external}


@app.post('/api/demo/missed-call')
def missed_call(data:EventIn,background:BackgroundTasks,ctx=Depends(auth)):
    with database() as c:
        c.execute('BEGIN IMMEDIATE')
        ct=get_contact(c,ctx['business_id'],data.contact_id)
        if dedup_event(c,ctx['business_id'],data.event_key,'missed-call'):
            c.commit(); return {'duplicate':True}
        c.execute('INSERT INTO calls(business_id,contact_id,status,created_at) VALUES(?,?,?,?)',(ctx['business_id'],ct['id'],'missed',NOW()))
        conv=ensure_conv(c,ctx['business_id'],ct['id'])
        textback=False
        recent=one(c,"SELECT m.id FROM messages m WHERE m.business_id=? AND m.conversation_id=? AND m.author='automation' AND m.created_at>? LIMIT 1",(ctx['business_id'],conv,(datetime.now(timezone.utc)-timedelta(minutes=15)).isoformat(timespec='seconds')))
        if rule_on(c,ctx['business_id'],'missed_call') and ct['consent_sms'] and not recent:
            # LOCAL MOCK ONLY: never transmitted to SMS provider.
            append_message(c,ctx['business_id'],conv,'outbound','automation',f'Hi {ct["name"].split()[0]}, sorry we missed your call! How can we help you? Reply here.','mock_sent')
            autom_log(c,ctx['business_id'],'missed_call',f'Mock SMS text-back for {ct["name"]}')
            textback=True
        else:
            autom_log(c,ctx['business_id'],'missed_call',f'{ct["name"]}: SMS skipped (no consent, cooldown or disabled rule)','skipped')
        c.commit()
        background.add_task(handle_workflow_event,ctx['business_id'],'missed_call',ct['id'],'',True)
        return {'conversation_id':conv,'mock_textback_sent':textback,'provider':'mock'}


@app.get('/api/services')
def services(ctx=Depends(auth)):
    with database() as c:
        return rows(c.execute('SELECT * FROM services WHERE business_id=? ORDER BY id',(ctx['business_id'],)))


@app.post('/api/services')
def service_create(data:ServiceIn,ctx=Depends(auth)):
    is_owner(ctx)
    with database() as c:
        c.execute('INSERT INTO services(business_id,name,duration,price) VALUES(?,?,?,?)',(ctx['business_id'],data.name,data.duration,data.price))
        return {'id':c.execute('SELECT last_insert_rowid()').fetchone()[0]}


@app.get('/api/staff')
def staff(ctx=Depends(auth)):
    with database() as c:
        return rows(c.execute('SELECT * FROM staff WHERE business_id=? ORDER BY id',(ctx['business_id'],)))


@app.post('/api/staff')
def staff_create(data:StaffIn,ctx=Depends(auth)):
    is_owner(ctx)
    with database() as c:
        c.execute('INSERT INTO staff(business_id,name,title) VALUES(?,?,?)',(ctx['business_id'],data.name,data.title))
        return {'id':c.execute('SELECT last_insert_rowid()').fetchone()[0]}


def create_booking(c,biz,data:AppointmentIn,action='booking.created'):
    get_contact(c,biz,data.contact_id)
    service=require(one(c,'SELECT * FROM services WHERE business_id=? AND id=?',(biz,data.service_id)),'Service not found')
    require(one(c,'SELECT * FROM staff WHERE business_id=? AND id=?',(biz,data.staff_id)),'Staff member not found')
    start=parse_dt(data.starts_at)
    end=start+timedelta(minutes=service['duration'])
    if start < datetime.now(timezone.utc)-timedelta(minutes=3):
        raise HTTPException(400,'Appointment must be in the future')
    conflict=one(c,"""SELECT id FROM appointments WHERE business_id=? AND staff_id=? AND status='confirmed' AND starts_at<? AND ends_at>? LIMIT 1""",(biz,data.staff_id,end.isoformat(timespec='seconds'),start.isoformat(timespec='seconds')))
    if conflict:
        raise HTTPException(409,'Time slot unavailable: this staff member has another booking')
    c.execute('''INSERT INTO appointments(business_id,contact_id,service_id,staff_id,starts_at,ends_at,status,notes,created_at) VALUES(?,?,?,?,?,?,?,?,?)''',(biz,data.contact_id,data.service_id,data.staff_id,start.isoformat(timespec='seconds'),end.isoformat(timespec='seconds'),'confirmed',data.notes,NOW()))
    ident=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    log(c,biz,action,f'Appointment #{ident}')
    if rule_on(c,biz,'booking_confirm'):
        ct=get_contact(c,biz,data.contact_id)
        if ct['consent_sms']:
            conv=ensure_conv(c,biz,data.contact_id)
            biz_tz=one(c,'SELECT timezone FROM businesses WHERE id=?',(biz,))['timezone']
            slot_label=start.astimezone(ZoneInfo(biz_tz)).strftime('%b %d at %I:%M %p')
            append_message(c,biz,conv,'outbound','automation',f'Booking confirmed! {service["name"]} on {slot_label} ({biz_tz}). Demo notification only.','mock_sent')
            autom_log(c,biz,'booking_confirm',f'Mock booking confirmation for {ct["name"]}')
        else:
            autom_log(c,biz,'booking_confirm','Skipped: contact has not opted in to SMS','skipped')
    return ident


@app.get('/api/appointments')
def appointments(ctx=Depends(auth)):
    with database() as c:
        return rows(c.execute('''SELECT a.*,ct.name AS contact_name,ct.phone AS contact_phone,s.name AS service_name,s.color AS service_color, st.name AS staff_name,st.color AS staff_color
          FROM appointments a JOIN contacts ct ON ct.id=a.contact_id JOIN services s ON s.id=a.service_id JOIN staff st ON st.id=a.staff_id
          WHERE a.business_id=? ORDER BY a.starts_at ASC''',(ctx['business_id'],)))


@app.post('/api/appointments')
def appointment_create(data:AppointmentIn,background:BackgroundTasks,ctx=Depends(auth)):
    with database() as c:
        c.execute('BEGIN IMMEDIATE')
        ident=create_booking(c,ctx['business_id'],data)
        c.commit()
    background.add_task(handle_workflow_event,ctx['business_id'],'booking_created',data.contact_id,'',False)
    return {'id':ident,'status':'confirmed'}


@app.patch('/api/appointments/{ident}')
def appointment_status(ident:int,data:StatusIn,ctx=Depends(auth)):
    if data.status not in ('cancelled','confirmed','completed'):
        raise HTTPException(400,'Invalid appointment status')
    with database() as c:
        existing=require(one(c,'SELECT * FROM appointments WHERE id=? AND business_id=?',(ident,ctx['business_id'])),'Appointment not found')
        if data.status=='confirmed' and existing['status']!='confirmed':
            c.execute('BEGIN IMMEDIATE')
            conflict=one(c,"SELECT id FROM appointments WHERE id!=? AND business_id=? AND staff_id=? AND status='confirmed' AND starts_at<? AND ends_at>?",(ident,ctx['business_id'],existing['staff_id'],existing['ends_at'],existing['starts_at']))
            if conflict:
                raise HTTPException(409,'Cannot reconfirm: slot already taken')
        c.execute('UPDATE appointments SET status=? WHERE id=? AND business_id=?',(data.status,ident,ctx['business_id']))
        log(c,ctx['business_id'],'booking.updated',f'Appointment #{ident}: {data.status}')
        return {'ok':True}


@app.get('/api/availability')
def availability(date:str,staff_id:int,service_id:int,ctx=Depends(auth)):
    with database() as c:
        business=require(one(c,'SELECT timezone FROM businesses WHERE id=?',(ctx['business_id'],)))
        service=require(one(c,'SELECT * FROM services WHERE id=? AND business_id=?',(service_id,ctx['business_id'])),'Service not found')
        require(one(c,'SELECT id FROM staff WHERE id=? AND business_id=?',(staff_id,ctx['business_id'])),'Staff member not found')
        try:
            d=datetime.strptime(date,'%Y-%m-%d').date()
            tz=ZoneInfo(business['timezone'])
        except ValueError:
            raise HTTPException(400,'Invalid date')
        slots=[]
        for hour in range(9,18):
            for minute in (0,30):
                local=datetime(d.year,d.month,d.day,hour,minute,tzinfo=tz)
                start=local.astimezone(timezone.utc)
                end=start+timedelta(minutes=service['duration'])
                if end.astimezone(tz).date()!=d or end.astimezone(tz).time()>time(18,0) or start<datetime.now(timezone.utc):
                    continue
                busy=one(c,"SELECT id FROM appointments WHERE business_id=? AND staff_id=? AND status='confirmed' AND starts_at<? AND ends_at>?",(ctx['business_id'],staff_id,end.isoformat(timespec='seconds'),start.isoformat(timespec='seconds')))
                if not busy:
                    slots.append({'starts_at':start.isoformat(timespec='seconds'),'label':local.strftime('%I:%M %p')})
        return {'timezone':business['timezone'],'slots':slots}


@app.get('/api/automations')
def automations(ctx=Depends(auth)):
    with database() as c:
        return {'rules':rows(c.execute('SELECT * FROM automation_rules WHERE business_id=? ORDER BY id',(ctx['business_id'],))),
                'logs':rows(c.execute('SELECT * FROM automation_logs WHERE business_id=? ORDER BY id DESC LIMIT 30',(ctx['business_id'],)))}


@app.patch('/api/automations/{ident}')
def toggle_automation(ident:int,data:ToggleIn,ctx=Depends(auth)):
    is_owner(ctx)
    with database() as c:
        require(one(c,'SELECT id FROM automation_rules WHERE id=? AND business_id=?',(ident,ctx['business_id'])),'Rule not found')
        c.execute('UPDATE automation_rules SET enabled=? WHERE id=? AND business_id=?',(int(data.enabled),ident,ctx['business_id']))
        log(c,ctx['business_id'],'rule.updated',f'Rule #{ident}: {data.enabled}')
        return {'ok':True}


@app.get('/api/ai')
def ai_info(ctx=Depends(auth)):
    with database() as c:
        return {'mode':'external-only','connected':False,'knowledge':rows(c.execute('SELECT * FROM knowledge_entries WHERE business_id=? ORDER BY id',(ctx['business_id'],))),
                'pending':one(c,"SELECT COUNT(*) AS n FROM messages m JOIN conversations co ON co.id=m.conversation_id WHERE m.business_id=? AND m.direction='inbound' AND m.ai_handled=0 AND co.ai_mode='external'",(ctx['business_id'],))['n'],
                'token':one(c,'SELECT ai_token FROM businesses WHERE id=?',(ctx['business_id'],))['ai_token'] if ctx['role']=='owner' else None}


@app.post('/api/ai/knowledge')
def add_knowledge(data:KnowledgeIn,ctx=Depends(auth)):
    is_owner(ctx)
    with database() as c:
        c.execute('INSERT INTO knowledge_entries(business_id,question,answer) VALUES(?,?,?)',(ctx['business_id'],data.question,data.answer))
        return {'id':c.execute('SELECT last_insert_rowid()').fetchone()[0]}


@app.delete('/api/ai/knowledge/{ident}')
def remove_knowledge(ident:int,ctx=Depends(auth)):
    is_owner(ctx)
    with database() as c:
        c.execute('DELETE FROM knowledge_entries WHERE business_id=? AND id=?',(ctx['business_id'],ident))
        return {'ok':True}


@app.post('/api/ai/rotate-token')
def rotate_token(ctx=Depends(auth)):
    is_owner(ctx)
    token=secrets.token_urlsafe(32)
    with database() as c:
        c.execute('UPDATE businesses SET ai_token=? WHERE id=?',(token,ctx['business_id']))
        log(c,ctx['business_id'],'ai.token_rotated','External AI integration token rotated')
    return {'token':token}


def ai_auth(request:Request):
    header=request.headers.get('authorization','')
    if not header.startswith('Bearer '):
        raise HTTPException(401,'Bearer token required')
    token=header[7:]
    with database() as c:
        # Tokens are high-entropy, per-business demo credentials; use a secure secret vault in production.
        for item in rows(c.execute('SELECT id,ai_token FROM businesses')):
            if hmac.compare_digest(token,item['ai_token']):
                return item['id']
        raise HTTPException(401,'Invalid integration token')


@app.get('/api/integrations/ai/inbox')
def integration_inbox(biz:int=Depends(ai_auth)):
    with database() as c:
        return rows(c.execute('''SELECT m.id AS message_id,m.conversation_id,m.body,m.created_at,ct.name AS contact_name,ct.phone AS contact_phone
          FROM messages m JOIN conversations co ON co.id=m.conversation_id JOIN contacts ct ON ct.id=co.contact_id
          WHERE m.business_id=? AND m.direction='inbound' AND m.ai_handled=0 AND co.ai_mode='external' AND co.status='open'
          ORDER BY m.id LIMIT 50''',(biz,)))


@app.get('/api/integrations/ai/context/{ident}')
def integration_context(ident:int,biz:int=Depends(ai_auth)):
    with database() as c:
        co=get_conv(c,biz,ident)
        return {'business':one(c,'SELECT id,name,industry,timezone,phone,address,hours FROM businesses WHERE id=?',(biz,)),
                'contact':get_contact(c,biz,co['contact_id']),
                'conversation':co,
                'messages':rows(c.execute('SELECT id,direction,author,body,created_at FROM messages WHERE business_id=? AND conversation_id=? ORDER BY id DESC LIMIT 25',(biz,ident))),
                'knowledge':rows(c.execute('SELECT question,answer FROM knowledge_entries WHERE business_id=?',(biz,))),
                'services':rows(c.execute('SELECT id,name,duration,price FROM services WHERE business_id=?',(biz,))),
                'staff':rows(c.execute('SELECT id,name,title FROM staff WHERE business_id=?',(biz,)))}


@app.post('/api/integrations/ai/reply')
def integration_reply(data:AIReplyIn,biz:int=Depends(ai_auth)):
    with database() as c:
        c.execute('BEGIN IMMEDIATE')
        co=get_conv(c,biz,data.conversation_id)
        if co['ai_mode']!='external' or co['status']!='open':
            raise HTTPException(409,'Conversation is not assigned to external AI')
        if data.inbound_message_id is not None:
            msg=require(one(c,'SELECT * FROM messages WHERE id=? AND business_id=? AND conversation_id=? AND direction=?',(data.inbound_message_id,biz,data.conversation_id,'inbound')),'Inbound message not found')
            if msg['ai_handled']:
                c.commit()
                return {'duplicate':True,'status':'already_handled'}
            c.execute('UPDATE messages SET ai_handled=1 WHERE id=? AND business_id=?',(msg['id'],biz))
        mid=append_message(c,biz,data.conversation_id,'outbound','external_ai',data.reply,'mock_sent')
        log(c,biz,'ai.reply.created',f'External AI message #{mid}')
        c.commit()
    result=dispatch_outbound(biz,mid)
    return {'id':mid,**result}


@app.post('/api/integrations/ai/handoff')
def integration_handoff(data:AIHandoffIn,biz:int=Depends(ai_auth)):
    with database() as c:
        get_conv(c,biz,data.conversation_id)
        c.execute("UPDATE conversations SET ai_mode='human' WHERE id=? AND business_id=?",(data.conversation_id,biz))
        log(c,biz,'ai.handoff',f'Conversation #{data.conversation_id} transferred to human')
    return {'ok':True}


@app.get('/api/integrations/ai/availability')
def integration_availability(date:str,staff_id:int,service_id:int,biz:int=Depends(ai_auth)):
    return availability(date,staff_id,service_id,ctx={'business_id':biz})


@app.post('/api/integrations/ai/book')
def integration_book(data:AppointmentIn,background:BackgroundTasks,biz:int=Depends(ai_auth)):
    with database() as c:
        c.execute('BEGIN IMMEDIATE')
        ident=create_booking(c,biz,data,'ai.booking.created')
        c.commit()
    background.add_task(handle_workflow_event,biz,'booking_created',data.contact_id,'',False)
    return {'id':ident,'status':'confirmed'}


@app.get('/api/business')
def business(ctx=Depends(auth)):
    with database() as c:
        return require(one(c,'SELECT id,name,industry,timezone,phone,address,hours FROM businesses WHERE id=?',(ctx['business_id'],)))


@app.patch('/api/business')
def update_business(data:BusinessIn,ctx=Depends(auth)):
    is_owner(ctx)
    with database() as c:
        c.execute('UPDATE businesses SET name=?,phone=?,address=?,hours=? WHERE id=?',(data.name,data.phone,data.address,data.hours,ctx['business_id']))
        log(c,ctx['business_id'],'business.updated','Business profile updated')
    return {'ok':True}


@app.get('/api/members')
def members(ctx=Depends(auth)):
    with database() as c:
        return rows(c.execute('SELECT u.id,u.name,u.email,m.role FROM memberships m JOIN users u ON u.id=m.user_id WHERE m.business_id=? ORDER BY m.role,u.name',(ctx['business_id'],)))


@app.post('/api/members')
def add_member(data:MemberIn,ctx=Depends(auth)):
    is_owner(ctx)
    if data.role not in ('owner','staff'):
        raise HTTPException(400,'Invalid role')
    email=data.email.strip().lower()
    if '@' not in email:
        raise HTTPException(400,'Invalid email')
    with database() as c:
        c.execute('BEGIN IMMEDIATE')
        user=one(c,'SELECT * FROM users WHERE lower(email)=?',(email,))
        if user:
            # A member who already has an account can join without changing their password.
            user_id=user['id']
        else:
            c.execute('INSERT INTO users(name,email,password_hash) VALUES(?,?,?)',(data.name.strip(),email,password_hash(data.password)))
            user_id=c.execute('SELECT last_insert_rowid()').fetchone()[0]
        if one(c,'SELECT 1 AS present FROM memberships WHERE user_id=? AND business_id=?',(user_id,ctx['business_id'])):
            raise HTTPException(409,'User already belongs to this workspace')
        c.execute('INSERT INTO memberships(user_id,business_id,role) VALUES(?,?,?)',(user_id,ctx['business_id'],data.role))
        log(c,ctx['business_id'],'member.added',f'{email}: {data.role}')
        c.commit()
        return {'id':user_id,'role':data.role}


@app.post('/api/businesses')
def create_business(data:NewBusinessIn,ctx=Depends(auth)):
    is_owner(ctx)
    try:
        ZoneInfo(data.timezone)
    except Exception:
        raise HTTPException(400,'Unknown timezone')
    with database() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('INSERT INTO businesses(name,industry,timezone,phone,address,ai_token) VALUES(?,?,?,?,?,?)',(data.name.strip(),data.industry.strip(),data.timezone,data.phone,data.address,secrets.token_urlsafe(30)))
        bid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
        c.execute('INSERT INTO memberships(user_id,business_id,role) VALUES(?,?,?)',(ctx['user_id'],bid,'owner'))
        for k,n,d in [('missed_call','Missed-call text back','Mock SMS after missed calls when explicit consent exists.'),('booking_confirm','Booking confirmations','Mock booking confirmation.'),('new_lead','New lead alerts','Log new inbound lead activity.')]:
            c.execute('INSERT INTO automation_rules(business_id,key,name,description,enabled) VALUES(?,?,?,?,1)',(bid,k,n,d))
        log(c,bid,'business.created','New empty workspace initialized')
        c.commit()
        return {'id':bid}


@app.get('/api/audit')
def audit(ctx=Depends(auth)):
    with database() as c:
        return rows(c.execute('SELECT * FROM audit_logs WHERE business_id=? ORDER BY id DESC LIMIT 30',(ctx['business_id'],)))


@app.get('/')
def homepage():
    return FileResponse(ROOT/'static'/'index.html')


app.mount('/static',StaticFiles(directory=str(ROOT/'static')),name='static')

# Optional integrations and visual workflow engine use the same database and tenant checks.
import sys
import enhancements
enhancements.install(sys.modules[__name__])


if __name__=='__main__':
    import uvicorn
    print('Small Business OS demo: http://127.0.0.1:8000  |  demo@smallbiz.local / demo123')
    uvicorn.run(app,host='127.0.0.1',port=int(os.environ.get('PORT','8000')))
