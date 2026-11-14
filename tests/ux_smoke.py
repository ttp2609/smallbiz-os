"""Run: python tests/ux_smoke.py (Playwright + installed Edge on Windows).

Uses a temporary database/key. Does not contact AI, SMS or TTS providers.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(os.environ.get('SMALLBIZ_QA_OUTPUT', tempfile.gettempdir()))
OUTPUT.mkdir(parents=True, exist_ok=True)


def check_width(page):
    if page.evaluate('document.documentElement.scrollWidth > window.innerWidth'):
        page.screenshot(path=str(OUTPUT / 'smallbiz-overflow.png'), full_page=True)
        details = page.evaluate('Array.from(document.querySelectorAll("body *")).filter(e=>e.getBoundingClientRect().right>innerWidth+1 && getComputedStyle(e).position!=="absolute").slice(0,16).map(e=>[e.tagName,e.className,Math.round(e.getBoundingClientRect().width)])')
        raise AssertionError('Page overflows: ' + str(page.viewport_size) + ' ' + page.locator('#content').get_attribute('data-page') + ' ' + str(details))


with tempfile.TemporaryDirectory(prefix='smallbiz-ux-') as temporary:
    env = os.environ.copy()
    env.update(SMALLBIZ_DB=str(Path(temporary) / 'qa.sqlite3'),
               SMALLBIZ_KEY_FILE=str(Path(temporary) / 'key'),
               SMALLBIZ_ENABLE_LIVE_SMS='0')
    with open(Path(temporary) / 'server.log', 'w+', encoding='utf-8') as log:
        server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'server:app', '--host', '127.0.0.1', '--port', '8766'], cwd=ROOT, env=env, stdout=log, stderr=log)
        try:
            for _ in range(100):
                try:
                    urllib.request.urlopen('http://127.0.0.1:8766/', timeout=1).close()
                    break
                except OSError:
                    if server.poll() is not None:
                        log.seek(0)
                        raise RuntimeError(log.read())
                    time.sleep(.1)
            else:
                raise RuntimeError('QA server did not start')
            with sync_playwright() as playwright:
                options = {'headless': True}
                if sys.platform == 'win32':
                    options['channel'] = os.environ.get('SMALLBIZ_BROWSER_CHANNEL', 'msedge')
                browser = playwright.chromium.launch(**options)
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto('http://127.0.0.1:8766/')
                page.wait_for_load_state('networkidle')
                page.get_by_role('button', name='Sign in to dashboard').click()
                expect(page.locator('.daily-actions')).to_be_visible()
                check_width(page)
                page.screenshot(path=str(OUTPUT / 'smallbiz-overview.png'), full_page=True)
                page.get_by_role('button', name='Add a customer').click()
                expect(page.get_by_role('dialog')).to_be_visible()
                assert page.evaluate('document.querySelector("#app").inert')
                page.locator('.modal-footer button').last.focus()
                page.keyboard.press('Tab')
                expect(page.locator('.modal-close')).to_be_focused()
                page.keyboard.press('Escape')
                expect(page.get_by_role('dialog')).to_have_count(0)
                expect(page.get_by_role('button', name='Add a customer')).to_be_focused()
                page.locator('[data-page="ai"]').click()
                expect(page.get_by_role('tabpanel', include_hidden=True)).to_have_count(7)
                expect(page.locator('#channel-assistant')).to_be_visible()
                expect(page.locator('#channel-voice')).to_be_hidden()
                page.get_by_role('tab', name='AI assistant', exact=True).focus()
                page.keyboard.press('ArrowRight')
                expect(page.locator('#channel-knowledge')).to_be_visible()
                page.get_by_role('tab', name='AI assistant', exact=True).click()
                page.locator('#ai-provider').select_option('custom')
                expect(page.locator('#ai-base')).to_be_visible()
                page.locator('#ai-provider').select_option('openai')
                expect(page.locator('#ai-base')).to_be_hidden()
                page.locator('#ai-key').fill('local-qa-key')
                page.locator('#ai-business-rules').fill('Answer briefly; refer unusual requests to the owner.')
                page.get_by_role('button', name='Save AI connection', exact=True).click()
                expect(page.get_by_text('AI settings saved', exact=True)).to_be_visible()
                expect(page.locator('.toast')).to_have_count(1)
                expect(page.locator('#ai-business-rules')).to_have_value('Answer briefly; refer unusual requests to the owner.')
                page.get_by_role('tab', name='WhatsApp', exact=True).click()
                expect(page.locator('#channel-whatsapp')).to_be_visible()
                page.locator('#wa-phone-id').fill('123456789')
                page.locator('#wa-token').fill('local-qa-token')
                page.locator('#wa-secret').fill('local-qa-secret')
                page.locator('#wa-verify-token').fill('local-qa-verify')
                page.get_by_role('button', name='Save WhatsApp settings', exact=True).click()
                expect(page.get_by_text('WhatsApp settings saved', exact=True)).to_be_visible()
                expect(page.locator('#channel-whatsapp')).to_be_visible()
                expect(page.locator('#wa-phone-id')).to_have_value('123456789')
                expect(page.locator('#wa-token')).to_have_value('')
                expect(page.locator('#wa-token')).to_have_attribute('placeholder', 'Leave blank to keep saved token')
                page.screenshot(path=str(OUTPUT / 'smallbiz-whatsapp.png'), full_page=True)
                page.get_by_role('tab', name='Phone calls', exact=True).click()
                expect(page.locator('#channel-calls')).to_be_visible()
                page.locator('#call-fallback').select_option('sms')
                page.get_by_role('button', name='Save call settings', exact=True).click()
                expect(page.get_by_text('Call settings saved', exact=True)).to_be_visible()
                expect(page.locator('#channel-calls')).to_be_visible()
                expect(page.locator('#call-fallback')).to_have_value('sms')
                page.screenshot(path=str(OUTPUT / 'smallbiz-calls.png'), full_page=True)
                page.get_by_role('tab', name='Voice Lab', exact=True).click()
                expect(page.locator('#channel-voice')).to_be_visible()
                page.locator('#tts-lang').select_option('vi')
                page.get_by_role('button', name='Save voice settings', exact=True).click()
                expect(page.locator('#channel-voice')).to_be_visible()
                expect(page.locator('#tts-lang')).to_have_value('vi')
                expect(page.locator('.toast')).to_have_count(1)
                page.screenshot(path=str(OUTPUT / 'smallbiz-voice.png'), full_page=True)
                page.locator('[data-page="automations"]').click()
                page.locator('.wf-tool').filter(has_text='Add contact tag').click()
                expect(page.locator('.wf-properties textarea')).to_be_visible()
                page.locator('.wf-properties textarea').fill('VIP')
                page.locator('#wf-name').fill('UX test flow')
                page.get_by_role('button', name='Save workflow', exact=True).click()
                expect(page.get_by_text('Workflow saved', exact=True)).to_be_visible()
                page.get_by_role('button', name='Run test', exact=True).click()
                expect(page.locator('#wf-test-output')).not_to_have_text('Save a flow, then choose a contact and run the test.')
                for width in [390, 740, 1024, 1440]:
                    page.set_viewport_size({'width': width, 'height': 900})
                    for name in ['dashboard', 'contacts', 'calendar', 'ai', 'automations', 'settings', 'inbox']:
                        page.locator('[data-page="' + name + '"]').click()
                        expect(page.locator('.page-title')).to_be_visible()
                        check_width(page)
                        if name == 'ai':
                            for tab in ['WhatsApp', 'Phone calls']:
                                page.get_by_role('tab', name=tab, exact=True).click()
                                check_width(page)
                            if width == 390:
                                page.screenshot(path=str(OUTPUT / 'smallbiz-mobile-calls.png'), full_page=True)
                    if width == 390:
                        assert page.locator('.sidebar').bounding_box()['height'] < 100
                        assert page.locator('.sidebar .nav-item').first.bounding_box()['width'] < 120
                        expect(page.locator('.inbox-list')).to_be_visible()
                        expect(page.locator('.thread')).to_be_hidden()
                        page.locator('.conv-row').first.focus()
                        page.keyboard.press('Enter')
                        expect(page.locator('.thread')).to_be_visible()
                        expect(page.locator('.inbox-list')).to_be_hidden()
                        expect(page.get_by_role('button', name='All conversations')).to_be_focused()
                        expect(page.locator('.toast')).to_have_count(0, timeout=5000)
                        page.screenshot(path=str(OUTPUT / 'smallbiz-mobile-inbox.png'), full_page=True)
                        page.get_by_text('Customer details & reply mode', exact=True).click()
                        expect(page.locator('.mode-select')).to_be_visible()
                        page.get_by_role('button', name='All conversations').click()
                        expect(page.locator('.inbox-list')).to_be_visible()
                        E = page.locator('#inbox-query')
                        E.fill('no-such-customer')
                        expect(page.locator('.conv-row')).to_have_count(0)
                        E.fill('')
                page.route('**/api/contacts', lambda route: route.fulfill(status=503, content_type='application/json', body='{"detail":"Temporary service error"}'))
                page.locator('[data-page="contacts"]').click()
                expect(page.get_by_role('button', name='Try again', exact=True)).to_be_visible()
                page.unroute('**/api/contacts')
                page.get_by_role('button', name='Try again', exact=True).click()
                expect(page.locator('#contacts-table')).to_be_visible()
                page.locator('#workspace-picker').select_option('2')
                expect(page.locator('.daily-actions')).to_be_visible()
                page.locator('[data-page="automations"]').click()
                expect(page.locator('#wf-name')).not_to_have_value('UX test flow')
                assert page.evaluate('WF.flow.name !== "UX test flow"')
                page.locator('.top-actions button[aria-label="Sign out"]').click()
                expect(page.locator('#login-email')).to_be_visible()
                page.locator('#login-email').fill('staff@luna.demo')
                page.get_by_role('button', name='Sign in to dashboard').click()
                expect(page.locator('.daily-actions')).to_be_visible()
                page.locator('[data-page="ai"]').click()
                page.get_by_role('tab', name='AI assistant', exact=True).click()
                expect(page.locator('#ai-provider')).to_be_disabled()
                expect(page.get_by_role('button', name='Save AI connection', exact=True)).to_be_disabled()
                expect(page.get_by_role('button', name='Ask AI', exact=True)).to_be_enabled()
                page.get_by_role('tab', name='Voice Lab', exact=True).click()
                expect(page.locator('#tts-lang')).to_be_disabled()
                expect(page.get_by_role('button', name='Save voice settings', exact=True)).to_be_disabled()
                expect(page.get_by_role('button', name='Speak text')).to_be_enabled()
                page.get_by_role('tab', name='WhatsApp', exact=True).click()
                expect(page.locator('#wa-phone-id')).to_be_disabled()
                expect(page.get_by_role('button', name='Save WhatsApp settings', exact=True)).to_be_disabled()
                page.get_by_role('tab', name='Phone calls', exact=True).click()
                expect(page.locator('#call-fallback')).to_be_disabled()
                expect(page.get_by_role('button', name='Save call settings', exact=True)).to_be_disabled()
                assert not errors, errors
                print('UX smoke passed: dashboard, tabs, saves, modal keyboard, workflow click/save, 7 pages at 4 widths, mobile inbox, error recovery, business switch and staff controls.')
                print('Screenshots:', OUTPUT)
                browser.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
