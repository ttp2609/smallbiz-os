/* SmallBiz OS V0.2 — Provider settings, Voice Lab, and visual workflow editor.
   Uses core api(), esc(), header(), badge(), toast(), and modal() from app.js. */
const STUDIO_PROVIDERS = {
  none:['',''], openai:['https://api.openai.com/v1','gpt-4o-mini'],
  groq:['https://api.groq.com/openai/v1','llama-3.3-70b-versatile'],
  deepseek:['https://api.deepseek.com','deepseek-chat'],
  openrouter:['https://openrouter.ai/api/v1','openai/gpt-4o-mini'],
  gemini:['https://generativelanguage.googleapis.com/v1beta/openai','gemini-2.5-flash'],
  custom:['','']
};
const VOICES = {
  en:'en-US-AriaNeural',vi:'vi-VN-HoaiMyNeural',es:'es-ES-ElviraNeural',
  fr:'fr-FR-DeniseNeural',de:'de-DE-KatjaNeural',ja:'ja-JP-NanamiNeural',
  ko:'ko-KR-SunHiNeural','zh-CN':'zh-CN-XiaoxiaoNeural'
};
const LANGS = {en:'English',vi:'Tiếng Việt',es:'Español',fr:'Français',de:'Deutsch',ja:'日本語',ko:'한국어','zh-CN':'中文'};
const VOICE_TEST_TEXT = {
  en:'Hello! Welcome to our business. How can I help you?',
  vi:'Xin chào! Chào mừng bạn đến với cửa hàng. Tôi có thể giúp gì cho bạn?',
  es:'¡Hola! Bienvenido a nuestra tienda. ¿En qué puedo ayudarle?',
  fr:'Bonjour ! Bienvenue dans notre boutique. Comment puis-je vous aider ?',
  de:'Hallo! Willkommen in unserem Geschäft. Wie kann ich Ihnen helfen?',
  ja:'こんにちは！ご来店ありがとうございます。何かお手伝いできますか？',
  ko:'안녕하세요! 저희 매장에 오신 것을 환영합니다. 무엇을 도와드릴까요?',
  'zh-CN':'您好！欢迎光临。有什么可以帮您的吗？'
};
let studioConfig = {ai:null,sms:null,voice:null,whatsapp:null,calls:null};

function studioField(label,id,value='',type='text',placeholder=''){
  return `<label class="studio-field"><span>${esc(label)}</span><input id="${id}" type="${type}" value="${esc(value)}" placeholder="${esc(placeholder)}" autocomplete="off" /></label>`;
}
function studioSelect(label,id,opts,value){return `<label class="studio-field"><span>${esc(label)}</span><select id="${id}">${opts.map(([v,l])=>`<option value="${esc(v)}" ${v===value?'selected':''}>${esc(l)}</option>`).join('')}</select></label>`;}
function studioPill(name,active){return `<span class="studio-pill ${active?'ok':'off'}">${active?'●':'○'} ${esc(name)}</span>`;}
function studioCheck(id,label,enabled,checked){return `<label class="studio-checkbox"><input type="checkbox" id="${id}" ${checked?'checked':''} ${!enabled?'disabled':''} /><span>${esc(label)}</span></label>`;}

async function renderAIStudio(){
  const [info,ai,sms,voice,whatsapp,calls]=await Promise.all([api('/ai'),api('/ai/provider'),api('/sms/config'),api('/voice/config'),api('/whatsapp/config'),api('/calls/config')]);
  studioConfig={ai,sms,voice,whatsapp,calls};
  const owner=S.me.role==='owner';
  const aiOpts=[['none','Off / External agent only'],['openai','OpenAI'],['groq','Groq'],['deepseek','DeepSeek'],['openrouter','OpenRouter'],['gemini','Google Gemini (OpenAI-compatible)'],['custom','Custom / OpenAI-compatible']];
  E('content').innerHTML=`${header('AI, SMS & Voice','Connect services per workspace. All secrets stay on the backend.')}
  <div class="studio-headline"><div class="studio-orb">✳</div><div><strong>Your business. Your AI stack.</strong><p>Bring an API key, choose your voice and test the experience. Nothing is sent to a real phone by default.</p></div>
  ${studioPill('No billing',true)}</div>
  <div class="studio-stat-grid"><div>${studioPill('AI: '+(ai.provider==='none'?'not configured':ai.provider),ai.provider!=='none'&&ai.key_set)}</div><div>${studioPill('SMS: '+sms.mode,sms.mode==='twilio')}</div><div>${studioPill('TTS: '+voice.tts,true)}</div><div>${studioPill('Voice calls: '+(voice.enabled?'on':'off'),voice.enabled)}</div></div>
  <div class="studio-columns">
  <section data-studio-panel="assistant" class="card studio-card"><div class="studio-card-top"><span class="studio-num">01</span><div><h2>AI reply provider</h2><p>OpenAI-compatible Chat Completions API</p></div></div>
  <div class="studio-grid-2">
    ${studioSelect('Provider','ai-provider',aiOpts,ai.provider)}
    ${studioField('Model name','ai-model',ai.model,'text','e.g. gpt-4o-mini')}
  </div>
  <div class="studio-grid-2">
    ${studioField('Base URL','ai-base',ai.base_url,'url','https://api.example.com/v1')}
    ${studioField('API key'+(ai.key_set?' · saved':' · required'),'ai-key','','password',ai.key_set?'•••••••• saved — leave blank to keep':'sk-...')}
  </div>
  ${studioCheck('ai-auto','Automatically answer SMS conversations set to Built-in AI',owner,ai.auto_reply)}
  <label class="studio-field"><span>Business reply guidance</span><textarea id="ai-business-rules" rows="3" maxlength="1500" placeholder="Tone, approved wording, and when to hand off">${esc(ai.business_rules||'')}</textarea></label>
  <p class="studio-hint">Guidance can shape tone and workflow; it cannot override verified facts or safety rules. Unknown prices, hours, availability, and promises are handed to a person.</p>
  <p class="studio-hint">For Custom, specify the API Base URL and model. Keys are encrypted in this local demo and never returned through the API. Auto replies require contact SMS consent.</p>
  <div class="studio-actions"><button class="btn primary" onclick="studioSaveAI()" ${!owner?'disabled':''}>Save AI connection</button><button class="btn outline" onclick="studioTestAI()" ${!owner?'disabled':''}>Save & test connection</button></div>
  <div class="studio-divider"></div><h3>AI playground</h3><p class="studio-hint">Send a sample prompt. This test does not send an SMS or modify a conversation.</p>
  <div class="studio-inline"><input id="ai-prompt" placeholder="Ask a sample customer question..." value="What services do you offer?" /><button class="btn outline" onclick="studioChat()">Ask AI</button></div><div id="ai-result" class="studio-result" aria-live="polite">Response appears here after you test.</div>
  </section>
  <section data-studio-panel="sms" class="card studio-card"><div class="studio-card-top"><span class="studio-num">02</span><div><h2>SMS channel</h2><p>Twilio integration with safe Mock default</p></div></div>
  <div class="studio-grid-2">${studioSelect('Delivery mode','sms-mode',[['mock','Mock · Local demo'],['twilio','Twilio · Sends real messages']],sms.mode)}${studioField('Twilio Account SID','sms-sid',sms.account_sid,'text','AC...')}</div>
  <div class="studio-grid-2">${studioField('Twilio number (E.164)','sms-number',sms.phone_number,'tel','+15125550123')}${studioField('Twilio Auth Token'+(sms.token_set?' · saved':''),'sms-token','','password',sms.token_set?'Leave blank to keep':'Auth Token')}</div>
  <div class="studio-warning"><strong>Live SMS costs money.</strong> It is blocked until the server has SMALLBIZ_ENABLE_LIVE_SMS=1. Explicit contact consent, A2P registration, valid numbers and sender compliance are required.</div>
  <div class="studio-actions"><button class="btn primary" onclick="studioSaveSMS()" ${!owner?'disabled':''}>Save SMS settings</button></div>
  <div class="studio-divider"></div><h3>Provider webhooks</h3>
  <p class="studio-hint">To receive real messages/calls, expose the server over public HTTPS and set SMALLBIZ_PUBLIC_BASE_URL. Configure your Twilio phone number to POST to:</p>
  <div class="studio-code">${esc((sms.public_base_url||'https://YOUR-DOMAIN')+sms.sms_webhook)}<br>${esc((sms.public_base_url||'https://YOUR-DOMAIN')+sms.voice_webhook)}<br>${esc((sms.public_base_url||'https://YOUR-DOMAIN')+'/api/hooks/twilio/status')} (message status)</div>
  <p class="studio-hint">Webhook signatures are validated. An inbound SMS creates a contact and conversation. Reply routing uses the selected Inbox mode: Human, Built-in AI, or External agent.</p>
  </section>
  </div>
  <div class="studio-columns">
  <section data-studio-panel="whatsapp" class="card studio-card"><div class="studio-card-top"><span class="studio-num">03</span><div><h2>WhatsApp Business</h2><p>Meta Cloud API · replies within the 24-hour customer service window</p></div></div>
  <label class="studio-field"><span>Phone Number ID</span><input id="wa-phone-id" value="${esc(whatsapp.phone_number_id)}" placeholder="Meta Phone Number ID" autocomplete="off"></label>
  <label class="studio-field"><span>Access token${whatsapp.access_token_set?' · saved':''}</span><input id="wa-token" type="password" placeholder="${whatsapp.access_token_set?'Leave blank to keep saved token':'Paste access token'}" autocomplete="new-password"></label>
  <label class="studio-field"><span>App secret${whatsapp.app_secret_set?' · saved':''}</span><input id="wa-secret" type="password" placeholder="${whatsapp.app_secret_set?'Leave blank to keep saved secret':'Meta App Secret'}" autocomplete="new-password"></label>
  <label class="studio-field"><span>Webhook verify token${whatsapp.verify_token_set?' · saved':''}</span><input id="wa-verify-token" type="password" placeholder="${whatsapp.verify_token_set?'Leave blank to keep saved token':'Choose a private verify token'}" autocomplete="new-password"></label>
  ${studioCheck('wa-auto','Automatically reply to new WhatsApp conversations using Built-in AI',owner,whatsapp.auto_reply)}
  <p class="studio-hint">Credentials are encrypted. In Meta, set the callback URL below and subscribe to <b>messages</b>. Only text messages are supported; template messages are not sent.</p>
  <div class="studio-code">${esc((sms.public_base_url||'https://YOUR-DOMAIN')+whatsapp.webhook)}<br>Graph API ${esc(whatsapp.graph_api_version)}</div>
  <div class="studio-actions"><button class="btn primary" onclick="studioSaveWhatsApp()" ${!owner?'disabled':''}>Save WhatsApp settings</button></div>
  </section>
  <section data-studio-panel="calls" class="card studio-card"><div class="studio-card-top"><span class="studio-num">04</span><div><h2>Missed-call recovery</h2><p>Ring the team first, then use your selected fallback</p></div></div>
  <label class="studio-field"><span>Staff transfer number</span><input id="call-transfer" type="tel" value="${esc(calls.transfer_number)}" placeholder="+15125550123" autocomplete="off"></label>
  ${studioSelect('If the team is busy or does not answer','call-fallback',[['ai','Answer with Voice AI'],['sms','Send a consented SMS'],['none','End with a short message']],calls.fallback)}
  <p class="studio-hint">AI fallback requires Voice AI enabled. SMS fallback requires a contact with SMS consent. Set Twilio’s inbound voice webhook to the URL shown in SMS settings.</p>
  <div class="studio-actions"><button class="btn primary" onclick="studioSaveCallSettings()" ${!owner?'disabled':''}>Save call settings</button></div>
  </section></div>
  <section data-studio-panel="voice" class="card studio-card studio-voice"><div class="studio-card-top"><span class="studio-num">03</span><div><h2>Voice Lab · Multilingual TTS</h2><p>gTTS / Edge-TTS synthesis + optional AI conversation preview</p></div></div>
  <div class="studio-grid-4">
  ${studioSelect('Speech engine','tts-engine',[['gtts','gTTS (online)'],['edge','Edge-TTS (online)']],voice.tts)}
  ${studioSelect('Language','tts-lang',Object.entries(LANGS).map(([id,label])=>[id,label]),voice.language)}
  ${studioField('Edge voice','tts-voice',voice.voice,'text','en-US-AriaNeural')}
  ${studioField('Speech recognition locale','stt-lang',voice.stt_language,'text','en-US')}
  </div>
  ${studioField('Phone greeting','voice-greeting',voice.greeting,'text','Hello! How can I help?')}
  ${studioCheck('voice-enabled','Enable turn-based Twilio Voice AI (requires configured Twilio + AI provider)',owner,voice.enabled)}
  <div class="studio-actions"><button class="btn primary" onclick="studioSaveVoice()" ${!owner?'disabled':''}>Save voice settings</button></div>
  <div class="studio-lab"><div class="studio-lab-intro"><div class="studio-lab-icon">♫</div><div><h3>Test voice in browser</h3><p>Browser microphone → speech recognition (if supported) → your AI → gTTS / Edge-TTS audio.</p></div></div>
  <textarea id="voice-prompt" rows="3" placeholder="Type something to read or use the microphone...">${esc(VOICE_TEST_TEXT[voice.language]||VOICE_TEST_TEXT.en)}</textarea>
  <div class="studio-actions"><button class="btn outline" onclick="studioVoiceSpeak()">▶ Speak text</button><button class="btn outline" onclick="studioMicrophone()">🎙 Microphone</button><button class="btn primary" onclick="studioVoiceConversation()">✦ Ask AI & speak answer</button></div>
  <div id="voice-transcript" class="studio-result">Voice output and transcript appear here.</div><audio id="voice-audio" controls preload="none" class="studio-audio"></audio></div>
  <div class="studio-info">gTTS and Edge-TTS are online TTS tools, not speech recognition or LLMs. Phone AI uses Twilio Gather speech recognition (may be charged), an AI provider, and TTS playback; it is turn-by-turn, not low-latency streaming. Test phone calls only through a public HTTPS endpoint.</div>
  </section>
  <div class="studio-columns">
  <section data-studio-panel="external" class="card studio-card"><div class="studio-card-top"><span class="studio-num">04</span><div><h2>External agent API</h2><p>Keep using your own bot or OpenClaw</p></div></div>
  <div class="studio-code">GET  /api/integrations/ai/inbox<br>GET  /api/integrations/ai/context/{conversation_id}<br>POST /api/integrations/ai/reply<br>POST /api/integrations/ai/book<br>POST /api/integrations/ai/handoff</div>
  ${info.token?`<div class="studio-inline" style="margin-top:15px"><input type="password" id="ai-token" readonly value="${esc(info.token)}"/><button class="btn outline" onclick="revealToken()">Show</button><button class="btn outline" onclick="copyToken()">Copy</button></div><button class="btn mini outline" onclick="rotateToken()" style="margin-top:10px">Rotate integration token</button>`:'<div class="studio-hint">Owners can view and rotate integration tokens.</div>'}
  <p class="studio-hint">External AI is isolated per workspace and does not use the provider settings above. Set the corresponding conversation to External AI in Inbox.</p>
  </section>
  <section data-studio-panel="knowledge" class="card studio-card"><div class="studio-card-top"><span class="studio-num">05</span><div><h2>Knowledge base</h2><p>Verified facts provided to your AI</p></div></div>
  ${info.knowledge.map(x=>`<div class="studio-qa"><b>${esc(x.question)}</b>${owner?`<button class="row-actions" onclick="deleteFAQ(${x.id})">Remove</button>`:''}<p>${esc(x.answer)}</p></div>`).join('')||'<p class="studio-hint">No FAQ entries yet.</p>'}
  <button class="btn outline" onclick="addFAQ()" ${!owner?'disabled':''}>+ Add knowledge</button>
  </section>
  </div>`;
  E('ai-provider').addEventListener('change',studioProviderChanged);
  E('tts-lang').addEventListener('change',()=>{
    const l=E('tts-lang').value;
    E('tts-voice').value=VOICES[l]||VOICES.en;
    E('stt-lang').value=l==='zh-CN'?'zh-CN':l==='en'?'en-US':l==='vi'?'vi-VN':l==='es'?'es-ES':l==='fr'?'fr-FR':l==='de'?'de-DE':l==='ja'?'ja-JP':l==='ko'?'ko-KR':'en-US';
    const prompt=E('voice-prompt');
    if(!prompt.value.trim()||Object.values(VOICE_TEST_TEXT).includes(prompt.value.trim()))prompt.value=VOICE_TEST_TEXT[l]||VOICE_TEST_TEXT.en;
  });
  studioProviderChanged(false);
}
function studioProviderChanged(updateDefaults=true){
  const p=E('ai-provider').value,custom=p==='custom',none=p==='none';
  E('ai-base').readOnly=!custom;
  E('ai-base').classList.toggle('readonly',!custom);
  if(updateDefaults){E('ai-base').value=STUDIO_PROVIDERS[p][0];E('ai-model').value=STUDIO_PROVIDERS[p][1]}
  E('ai-auto').disabled=none||S.me.role!=='owner';
}
function studioAIForm(){return {
  provider:E('ai-provider').value,base_url:E('ai-base').value.trim(),
  model:E('ai-model').value.trim(),api_key:E('ai-key').value.trim(),
  auto_reply:E('ai-auto').checked,business_rules:E('ai-business-rules').value.trim()
}}
async function studioSaveAI(){await safe(async()=>{
  await api('/ai/provider','PUT',studioAIForm());
  toast('AI settings saved');await renderAIStudio()
})}
async function studioTestAI(){await safe(async()=>{
  const output=E('ai-result');output.textContent='Saving current settings and contacting the gateway...';
  try {
    await api('/ai/provider','PUT',studioAIForm());
    E('ai-key').value='';
    const r=await api('/ai/provider/test','POST');
    output.textContent=r.reply;toast('Provider responded successfully');
  } catch(err) {output.textContent=err.message||'AI connection failed';throw err}
})}
async function studioChat(){await safe(async()=>{
  const output=E('ai-result');output.textContent='Thinking using saved provider settings...';
  try {const r=await api('/ai/chat','POST',{message:E('ai-prompt').value.trim()});output.textContent=r.reply}
  catch(err){output.textContent=err.message||'AI request failed';throw err}
})}
async function studioSaveSMS(){await safe(async()=>{
  const mode=E('sms-mode').value;
  if(mode==='twilio'&&!confirm('This switches outbound SMS to LIVE Twilio if the server permits it. Twilio charges apply. Continue?'))return;
  await api('/sms/config','PUT',{mode,account_sid:E('sms-sid').value.trim(),auth_token:E('sms-token').value.trim(),phone_number:E('sms-number').value.trim()});
  toast('SMS settings saved');await renderAIStudio();
})}
async function studioSaveVoice(){await safe(async()=>{await api('/voice/config','PUT',{
  tts:E('tts-engine').value,language:E('tts-lang').value,voice:E('tts-voice').value.trim(),stt_language:E('stt-lang').value.trim(),greeting:E('voice-greeting').value.trim(),enabled:E('voice-enabled').checked
});toast('Voice settings saved');await renderAIStudio()})}
async function studioSaveWhatsApp(){await safe(async()=>{
  const enabled=E('wa-auto').checked;
  if(enabled&&!confirm('Enable real WhatsApp AI replies to customers who message this business? Continue?'))return;
  await api('/whatsapp/config','PUT',{phone_number_id:E('wa-phone-id').value.trim(),access_token:E('wa-token').value.trim(),app_secret:E('wa-secret').value.trim(),verify_token:E('wa-verify-token').value.trim(),auto_reply:enabled});
  toast('WhatsApp settings saved');await renderAIStudio()
})}
async function studioSaveCallSettings(){await safe(async()=>{
  const number=E('call-transfer').value.trim();
  if(number&&!confirm('Save live call forwarding? Calls reaching the configured Twilio webhook will ring this number first.'))return;
  await api('/calls/config','PUT',{transfer_number:number,fallback:E('call-fallback').value});
  toast('Call settings saved');await renderAIStudio()
})}
async function studioVoiceSpeak(){await safe(async()=>{
  const engine=await studioPlayText(E('voice-prompt').value.trim());
  E('voice-transcript').textContent=engine==='gtts-fallback'
    ? 'Edge-TTS did not return audio; Vietnamese speech was generated using gTTS fallback.'
    : 'TTS generated and played.';
})}
async function studioPlayText(text){
  if(!text)throw new Error('Enter some text first');
  const res=await fetch('/api/voice/speak',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:text.slice(0,500)})});
  if(!res.ok){const err=await res.json().catch(()=>({}));throw new Error(err.detail||'TTS failed')}
  const engine=res.headers.get('X-TTS-Engine')||'';
  const data=await res.blob();
  const audio=E('voice-audio');if(audio.dataset.objectUrl)URL.revokeObjectURL(audio.dataset.objectUrl);
  audio.dataset.objectUrl=URL.createObjectURL(data);audio.src=audio.dataset.objectUrl;
  await audio.play();
  return engine;
}
async function studioVoiceConversation(){await safe(async()=>{E('voice-transcript').textContent='Requesting AI response...';
  const r=await api('/voice/turn','POST',{text:E('voice-prompt').value.trim()});
  E('voice-transcript').textContent='AI: '+r.reply;
  const engine=await studioPlayText(r.reply.slice(0,500));
  if(engine==='gtts-fallback')E('voice-transcript').textContent+='\n(Used Vietnamese gTTS fallback: Edge-TTS returned no audio.)';
})}
function studioMicrophone(){
  const Speech=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!Speech){toast('Speech recognition is not available in this browser. Type text instead.',true);return}
  const r=new Speech();r.lang=E('stt-lang').value||'en-US';r.interimResults=false;r.maxAlternatives=1;
  E('voice-transcript').textContent='Listening...';
  r.onresult=e=>{const t=e.results[0][0].transcript;E('voice-prompt').value=t;E('voice-transcript').textContent='You said: '+t};
  r.onerror=e=>{E('voice-transcript').textContent='Microphone error: '+e.error};r.start();
}
async function setReplyMode(id,mode){await safe(async()=>{await api(`/conversations/${id}`,'PATCH',{ai_mode:mode});await renderInbox();toast('Reply mode updated')})}

/* Visual Workflow Studio */
const WF_TYPES={
  trigger_sms:{label:'Incoming SMS',group:'Trigger',description:'On inbound SMS',icon:'↳'},
  trigger_missed:{label:'Missed call',group:'Trigger',description:'On missed-call event',icon:'☎'},
  trigger_booking:{label:'Booking created',group:'Trigger',description:'On new confirmed appointment',icon:'◷'},
  condition_consent:{label:'SMS consent?',group:'Condition',description:'Branch based on consent',icon:'◇'},
  condition_keyword:{label:'Message contains?',group:'Condition',description:'Branch on a keyword',icon:'◇'},
  action_sms:{label:'Send SMS',group:'Action',description:'Send or queue a text',icon:'✉'},
  action_ai:{label:'AI reply',group:'Action',description:'Ask configured AI',icon:'✳'},
  action_tag:{label:'Add contact tag',group:'Action',description:'Update CRM tags',icon:'⌗'},
  action_handoff:{label:'Assign to team',group:'Action',description:'Switch to human mode',icon:'⇆'},
  action_log:{label:'Write activity log',group:'Action',description:'Record an event',icon:'▤'}
};
const WF = {items:[],logs:[],id:null,flow:null,selected:null,linkFrom:null,linkBranch:'next'};
const wfClone=obj=>JSON.parse(JSON.stringify(obj));
function wfBlank(){return {id:null,name:'New customer flow',enabled:false,nodes:[{id:'start',type:'trigger_sms',x:85,y:100,config:{}}],edges:[]};}
async function renderAutomationStudio(){
  const [data,legacy,contacts]=await Promise.all([api('/workflows'),api('/automations'),api('/contacts')]);
  WF.items=data.workflows;WF.logs=data.runs;
  if(!WF.flow||(WF.id!==null&&!WF.items.some(f=>f.id===WF.id))){
    WF.flow=wfClone(WF.items[0]||wfBlank());WF.id=WF.flow.id;WF.selected=WF.flow.nodes[0]?.id||null;
  }
  const canEdit=S.me.role==='owner';
  E('content').innerHTML=`${header('Workflow Studio','Build customer automations by dragging, connecting and configuring steps.',`<button class="btn outline" onclick="openDemoFlow()">${svg('phone')} Simulate an event</button>`)}
  <div class="studio-headline workflow-lead"><div class="studio-orb">⌘</div><div><strong>Visual automation builder</strong><p>Drag steps onto the canvas. Click Link and select the next node to connect them. Save to activate the workflow engine.</p></div>${studioPill('Dry-run test available',true)}</div>
  <div class="wf-toolbar"><select id="wf-picker" onchange="wfSelect(this.value)"><option value="new" ${!WF.id?'selected':''}>+ Unsaved workflow</option>${WF.items.map(x=>`<option value="${x.id}" ${x.id===WF.id?'selected':''}>${esc(x.name)}</option>`).join('')}</select>
  <input id="wf-name" value="${esc(WF.flow.name)}" placeholder="Workflow name" maxlength="120" />
  <label class="studio-checkbox"><input id="wf-enabled" type="checkbox" ${WF.flow.enabled?'checked':''} ${!canEdit?'disabled':''}/> Enabled</label>
  <button class="btn outline" onclick="wfNew()" ${!canEdit?'disabled':''}>+ New</button>
  <button class="btn primary" onclick="wfSave()" ${!canEdit?'disabled':''}>Save workflow</button>
  <button class="btn outline" onclick="wfDelete()" ${!canEdit||!WF.id?'disabled':''}>Delete</button></div>
  <div class="wf-studio-layout">
    <aside class="wf-palette card"><div class="wf-panel-head"><h3>Step library</h3><p>Drag onto the canvas</p></div>
      ${['Trigger','Condition','Action'].map(g=>`<div class="wf-group-label">${g.toUpperCase()}</div>${Object.entries(WF_TYPES).filter(([_,v])=>v.group===g).map(([k,v])=>`<div class="wf-tool" draggable="${canEdit}" ondragstart="wfStartDrag(event,'${k}')"><span>${v.icon}</span><div><b>${v.label}</b><small>${v.description}</small></div></div>`).join('')}`).join('')}
    </aside>
    <div class="wf-middle card"><div class="wf-canvas-top"><b>Flow canvas</b><span>Drag nodes • click to configure • Link nodes to define execution</span></div><div class="wf-viewport"><div class="wf-canvas" id="wf-canvas" ondragover="wfAllowDrop(event)" ondrop="wfDrop(event)"><svg id="wf-lines" class="wf-lines" viewBox="0 0 1100 650" preserveAspectRatio="none"></svg><div id="wf-nodes"></div></div></div><div class="wf-canvas-bottom">${WF.flow.nodes.length} nodes · ${WF.flow.edges.length} connections · Looping flows not supported</div></div>
    <aside class="wf-properties card" id="wf-properties"></aside>
  </div>
  <div class="studio-columns" style="margin-top:19px"><div class="card studio-card"><h3>Run a safe simulation</h3><p class="studio-hint">Test your SAVED workflow with a sample customer. No database updates, AI requests or real SMS are made during this dry-run.</p>
   <div class="studio-inline"><select id="wf-test-contact">${contacts.map(c=>`<option value="${c.id}">${esc(c.name)} · SMS ${c.consent_sms?'allowed':'not allowed'}</option>`).join('')}</select><input id="wf-test-text" value="Can I book an appointment?" /><button class="btn primary" onclick="wfTest()">Run test</button></div>
   <div class="studio-result" id="wf-test-output">Save a flow, then choose a contact and run the test.</div></div>
  <div class="card studio-card"><h3>Workflow run history</h3><p class="studio-hint">Actual events appear here when a flow is enabled.</p>
   <div class="wf-runs">${WF.logs.slice(0,8).map(x=>`<div><b>${esc(x.trigger)} · ${esc(x.result)}</b><small>${esc((x.detail||[]).join(' → ').slice(0,160))}</small></div>`).join('')||'<p class="studio-hint">No custom workflows have run yet.</p>'}</div></div></div>
  <div class="card studio-card" style="margin-top:19px"><h3>Built-in presets (from V0.1)</h3><div class="studio-grid-3">${legacy.rules.map(r=>`<div class="wf-legacy"><strong>${esc(r.name)}</strong><p>${esc(r.description)}</p><button class="switch ${r.enabled?'on':''}" onclick="toggleRule(${r.id},${r.enabled})" ${!canEdit?'disabled':''} aria-label="Toggle preset"></button></div>`).join('')}</div></div>`;
  wfPaint();
}
function wfNew(){WF.id=null;WF.flow=wfBlank();WF.selected='start';WF.linkFrom=null;renderAutomationStudio()}
function wfSelect(value){WF.id=value==='new'?null:Number(value);WF.flow=wfClone(WF.items.find(x=>x.id===WF.id)||wfBlank());WF.selected=WF.flow.nodes[0]?.id||null;WF.linkFrom=null;renderAutomationStudio()}
function wfStartDrag(event,type,id=null){event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain',JSON.stringify({type,id}))}
function wfAllowDrop(e){e.preventDefault();e.dataTransfer.dropEffect='move'}
function wfDrop(e){e.preventDefault();if(S.me.role!=='owner')return;let data;try{data=JSON.parse(e.dataTransfer.getData('text/plain'))}catch{return}
  const canvas=E('wf-canvas'),rect=canvas.getBoundingClientRect();
  const x=Math.max(10,Math.min(850,Math.round(e.clientX-rect.left-80)));
  const y=Math.max(10,Math.min(520,Math.round(e.clientY-rect.top-24)));
  if(data.id){const node=WF.flow.nodes.find(x=>x.id===data.id);if(node){node.x=x;node.y=y}}
  else if(WF_TYPES[data.type]){
    if(data.type.startsWith('trigger_')&&WF.flow.nodes.some(n=>n.type.startsWith('trigger_'))){toast('One trigger per flow. Remove the current trigger first.',true);return}
    if(WF.flow.nodes.length>=25){toast('Maximum 25 nodes per workflow',true);return}
    const id='n'+Date.now().toString(36)+Math.floor(Math.random()*1000).toString(36);
    WF.flow.nodes.push({id,type:data.type,x,y,config:{}});WF.selected=id;
  }
  wfPaint();
}
function wfNodeClick(id){if(WF.linkFrom){if(WF.linkFrom===id){toast('Connect to a different node',true);return}
  WF.flow.edges=WF.flow.edges.filter(e=>!(e.from===WF.linkFrom&&e.branch===WF.linkBranch));
  WF.flow.edges.push({from:WF.linkFrom,to:id,branch:WF.linkBranch});
  WF.linkFrom=null;toast('Nodes connected');
 }WF.selected=id;wfPaint()}
function wfLink(id,branch){WF.linkFrom=id;WF.linkBranch=branch;toast('Click the target node to connect')}
function wfRemoveNode(id){WF.flow.nodes=WF.flow.nodes.filter(n=>n.id!==id);WF.flow.edges=WF.flow.edges.filter(e=>e.from!==id&&e.to!==id);WF.selected=WF.flow.nodes[0]?.id||null;wfPaint()}
function wfRemoveEdge(from,branch){WF.flow.edges=WF.flow.edges.filter(e=>!(e.from===from&&e.branch===branch));wfPaint()}
function wfSetConfig(key,value){const n=WF.flow.nodes.find(n=>n.id===WF.selected);if(n)n.config[key]=value}
function wfPaint(){const host=E('wf-nodes');if(!host)return;
  host.innerHTML=WF.flow.nodes.map(n=>{const meta=WF_TYPES[n.type];const cls=meta.group.toLowerCase();return `<div class="wf-node ${cls} ${n.id===WF.selected?'selected':''}" style="left:${Number(n.x)||0}px;top:${Number(n.y)||0}px" draggable="${S.me.role==='owner'}" ondragstart="wfStartDrag(event,'${n.type}','${n.id}')" onclick="wfNodeClick('${n.id}')"><div class="wf-node-icon">${meta.icon}</div><div><strong>${meta.label}</strong><small>${meta.description}</small></div><span class="wf-node-dot"></span></div>`}).join('');
  const ns=Object.fromEntries(WF.flow.nodes.map(n=>[n.id,n]));
  E('wf-lines').innerHTML=`<defs><marker id="wf-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z" fill="#8176f1" /></marker></defs>`+
    WF.flow.edges.filter(e=>ns[e.from]&&ns[e.to]).map(e=>{let a=ns[e.from],b=ns[e.to],x1=(Number(a.x)||0)+202,y1=(Number(a.y)||0)+36,x2=Number(b.x)||0,y2=(Number(b.y)||0)+36;
      const c1=x1+Math.max(35,Math.abs(x2-x1)/2),c2=x2-Math.max(35,Math.abs(x2-x1)/2);
      const d=`M${x1} ${y1} C${c1} ${y1},${c2} ${y2},${x2-7} ${y2}`;
      return `<path d="${d}" fill="none" stroke="#8176f1" stroke-width="2.5" marker-end="url(#wf-arrow)"/><text x="${(x1+x2)/2}" y="${(y1+y2)/2-10}" class="wf-edge-label">${e.branch==='next'?'':e.branch.toUpperCase()}</text>`;
    }).join('');
  wfProperties();
}
function wfProperties(){const p=E('wf-properties'),n=WF.flow.nodes.find(x=>x.id===WF.selected);
  if(!n){p.innerHTML='<div class="wf-panel-head"><h3>Node inspector</h3><p>Click any node on the canvas.</p></div>';return}
  const meta=WF_TYPES[n.type],cfg=n.config||{},cond=n.type.startsWith('condition_');
  const edges=WF.flow.edges.filter(e=>e.from===n.id);
  const input=(label,key,placeholder='')=>`<label class="studio-field"><span>${label}</span><textarea rows="3" placeholder="${esc(placeholder)}" oninput="wfSetConfig('${key}',this.value)">${esc(cfg[key]||'')}</textarea></label>`;
  p.innerHTML=`<div class="wf-panel-head"><h3>Node inspector</h3><p>Configure the selected step</p></div>
   <div class="wf-inspector-head"><span>${meta.icon}</span><div><b>${meta.label}</b><small>${meta.group}</small></div></div>
   ${n.type==='action_sms'?input('SMS text','text','Hi {{first_name}}, we missed you!'):''}
   ${n.type==='action_log'?input('Log description','text','A new customer has contacted us'):''}
   ${n.type==='action_tag'?input('Tag name','tag','New lead'):''}
   ${n.type==='condition_keyword'?input('Match phrase (case-insensitive)','keyword','booking'):''}
   ${n.type==='condition_consent'?'<p class="studio-hint">Checks the SMS consent field in CRM. YES continues when the customer opted in.</p>':''}
   ${n.type==='action_ai'?'<p class="studio-hint">Uses your selected AI provider. If no API key or SMS consent, the flow skips the reply.</p>':''}
   ${n.type.startsWith('trigger_')?'<p class="studio-hint">This event launches the workflow when enabled. One trigger per workflow.</p>':''}
   <div class="wf-property-label">CONNECT TO NEXT STEP</div>
   <div class="wf-link-actions">${cond?`<button class="btn outline mini" onclick="wfLink('${n.id}','yes')">Link YES →</button><button class="btn outline mini" onclick="wfLink('${n.id}','no')">Link NO →</button>`:`<button class="btn outline mini" onclick="wfLink('${n.id}','next')">Link NEXT →</button>`}</div>
   ${WF.linkFrom===n.id?'<div class="studio-hint" style="color:#6557df">Now click another node to connect.</div>':''}
   ${edges.map(e=>`<div class="wf-connected">${esc(e.branch)} → ${esc(WF_TYPES[WF.flow.nodes.find(n=>n.id===e.to)?.type]?.label||e.to)} <button onclick="wfRemoveEdge('${n.id}','${e.branch}')" aria-label="Remove connection">×</button></div>`).join('')}
   <button class="btn danger" style="margin-top:20px;width:100%" onclick="wfRemoveNode('${n.id}')">Remove node</button>`;
}
async function wfSave(){await safe(async()=>{
  WF.flow.name=E('wf-name').value.trim();WF.flow.enabled=E('wf-enabled').checked;
  const data={name:WF.flow.name,enabled:WF.flow.enabled,nodes:WF.flow.nodes,edges:WF.flow.edges};
  if(WF.id)await api(`/workflows/${WF.id}`,'PUT',data);
  else WF.id=(await api('/workflows','POST',data)).id;
  WF.items=(await api('/workflows')).workflows;WF.flow=wfClone(WF.items.find(f=>f.id===WF.id));
  toast('Workflow saved');await renderAutomationStudio();
})}
async function wfDelete(){if(!WF.id||!confirm('Delete this workflow?'))return;await safe(async()=>{await api(`/workflows/${WF.id}`,'DELETE');WF.id=null;WF.flow=null;await renderAutomationStudio();toast('Workflow removed')})}
async function wfTest(){await safe(async()=>{if(!WF.id){toast('Save the workflow first',true);return}
  const result=await api(`/workflows/${WF.id}/test`,'POST',{contact_id:Number(E('wf-test-contact').value),text:E('wf-test-text').value});
  E('wf-test-output').textContent=result.trace.length?result.trace.join('\n→ '):'No nodes fired. Confirm trigger/edges.';
  toast('Dry-run completed. No SMS sent.')
})}

// Replace old V0.1 views with functioning provider/voice/visual-builder views.
renderAI = renderAIStudio;
renderAutomations = renderAutomationStudio;
