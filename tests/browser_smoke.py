"""Optional browser QA (requires playwright + local Chromium)."""
import os
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
tmp=tempfile.TemporaryDirectory(prefix='smallbiz-browser-')
env=os.environ.copy()
env['SMALLBIZ_DB']=str(Path(tmp.name)/'qa.sqlite3')
server=subprocess.Popen(['python','-m','uvicorn','server:app','--host','127.0.0.1','--port','8765'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
try:
    for _ in range(80):
        try:
            urllib.request.urlopen('http://127.0.0.1:8765/').read(); break
        except Exception: time.sleep(.2)
    else: raise RuntimeError(server.stderr.read().decode())
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':900},device_scale_factor=1)
        errors=[]
        page.on('pageerror',lambda ex:errors.append(str(ex)))
        page.goto('http://127.0.0.1:8765/')
        page.get_by_text('Sign in to dashboard').click()
        page.locator('.nav-item[data-page="ai"]').click()
        page.get_by_text('Your business. Your AI stack.').wait_for()
        assert page.locator('#ai-provider').count()==1
        page.select_option('#ai-provider','custom')
        page.fill('#ai-base','https://api.example.com/v1')
        page.fill('#ai-model','custom-model')
        # Avoid saving external URL if network validation unavailable in QA.
        page.select_option('#ai-provider','openai')
        page.fill('#ai-key','fake-local-test-key')
        page.get_by_text('Save AI connection').click()
        page.get_by_text('AI settings saved').first.wait_for()
        page.screenshot(path=str(ROOT/'qa_ai_screen.png'),full_page=True)
        page.locator('.nav-item[data-page="automations"]').click()
        page.get_by_text('Visual automation builder').wait_for()
        page.locator('.wf-tool').filter(has_text='Add contact tag').drag_to(page.locator('#wf-canvas'),target_position={'x':690,'y':350})
        assert page.locator('.wf-node').count()>=5,page.locator('#wf-nodes').inner_text()
        page.locator('.wf-node').last.click()
        page.get_by_text('Tag name').wait_for()
        page.locator('.wf-properties textarea').fill('VIP')
        page.locator('#wf-name').fill('QA flow')
        page.get_by_text('Save workflow',exact=True).click()
        page.get_by_text('Workflow saved').first.wait_for()
        page.get_by_text('Run test',exact=True).click()
        page.get_by_text('Dry-run completed').first.wait_for()
        page.screenshot(path=str(ROOT/'qa_workflow_screen.png'),full_page=True)
        page.locator('.nav-item[data-page="inbox"]').click()
        page.locator('.mode-select').first.wait_for()
        page.locator('.mode-select').select_option('builtin')
        page.get_by_text('Reply mode updated').first.wait_for()
        if errors: raise RuntimeError('Browser JS errors: '+str(errors))
        print('Browser smoke passed: AI settings, workflow canvas, drag/drop, save, dry run, reply mode. Screenshots saved.')
        browser.close()
finally:
    server.terminate()
    try: server.wait(timeout=7)
    except subprocess.TimeoutExpired: server.kill()
    tmp.cleanup()
