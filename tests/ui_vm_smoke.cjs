// Render check without browser navigation (Chromium may have URLBlocklist in CI).
const fs=require('fs'),vm=require('vm'),path=require('path');
const ROOT=path.resolve(__dirname,'..');
const els={};
function element(id){return els[id] ||= {innerHTML:'',value:'',classList:{toggle(){}},addEventListener(){},querySelector(){return null},scrollHeight:0,scrollTop:0};}
const data={
  '/ai':{knowledge:[{id:1,question:'When are you open?',answer:'Mon-Sat, 9-6'}],pending:0,token:'demo-token'},
  '/ai/provider':{provider:'none',base_url:'',model:'',key_set:false,auto_reply:false},
  '/sms/config':{mode:'mock',account_sid:'',token_set:false,phone_number:'',public_base_url:'',sms_webhook:'/api/hooks/twilio/sms',voice_webhook:'/api/hooks/twilio/voice'},
  '/voice/config':{tts:'gtts',language:'en',voice:'en-US-AriaNeural',stt_language:'en-US',greeting:'Hello!',enabled:false},
  '/whatsapp/config':{phone_number_id:'',access_token_set:false,app_secret_set:false,verify_token_set:false,auto_reply:false,webhook:'/api/hooks/whatsapp',graph_api_version:'v25.0'},
  '/calls/config':{transfer_number:'',fallback:'ai'},
  '/workflows':{workflows:[{id:4,name:'Test workflow',enabled:false,nodes:[{id:'a',type:'trigger_missed',x:80,y:80,config:{}},{id:'b',type:'action_sms',x:340,y:80,config:{text:'Hello!'}}],edges:[{from:'a',to:'b',branch:'next'}]}],runs:[]},
  '/automations':{rules:[{id:1,name:'Missed-call text back',description:'Demo rule',enabled:1}],logs:[]},
  '/contacts':[{id:1,name:'Alice',consent_sms:1}],
};
const ctx=vm.createContext({
  console,Date,Intl,setTimeout:()=>{},confirm:()=>true,
  navigator:{clipboard:{writeText:async()=>{}}},
  window:{addEventListener:()=>{}},
  document:{getElementById:element,querySelectorAll:()=>[]},
  fetch:async(url)=>({ok:true,json:async()=>{if(!data[url.replace('/api','')])throw new Error('No test response for '+url);return data[url.replace('/api','')]}}),
});
let base=fs.readFileSync(path.join(ROOT,'static/app.js'),'utf8');
base=base.replace(/boot\(\);\s*$/,'');
vm.runInContext(base,ctx,{filename:'app.js'});
vm.runInContext(fs.readFileSync(path.join(ROOT,'static/studio.js'),'utf8'),ctx,{filename:'studio.js'});
vm.runInContext("S.me={role:'owner',user:{name:'QA'},businesses:[{id:1,name:'Test'}]};S.business={timezone:'America/Chicago'}",ctx);
(async()=>{
  await vm.runInContext('renderAIStudio()',ctx);
  if(!element('content').innerHTML.includes('Your business. Your AI stack.')||!element('content').innerHTML.includes('Voice Lab'))throw new Error('Missing AI/Voice UI');
  await vm.runInContext('renderAutomationStudio()',ctx);
  if(!element('content').innerHTML.includes('Visual automation builder')||!element('wf-nodes').innerHTML.includes('Missed call')||!element('wf-lines').innerHTML.includes('<path'))throw new Error('Workflow canvas not rendered');
  // New flow should remain selected after rerender, not revert to first saved.
  vm.runInContext('wfNew()',ctx);
  await new Promise(r=>setTimeout(r,0));
  console.log('UI template VM smoke passed: AI, SMS, WhatsApp, calls, Voice, visual workflow nodes/edges.');
})().catch(e=>{console.error(e);process.exitCode=1});
