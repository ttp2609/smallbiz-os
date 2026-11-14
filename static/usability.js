/* Native controls and existing API flows; no additional runtime dependencies. */
let channelTab = 'assistant';
let inboxThread = false;
let inboxQuery = '';
let modalTrigger = null;
const pendingButtons = new WeakSet();

const originalToast = toast;
toast = function(message, isError = false) {
  E('toast-root').querySelectorAll('.toast').forEach(item => item.remove());
  originalToast(message, isError);
};

const originalSafe = safe;
safe = async function(job) {
  const button = document.activeElement?.closest('button');
  if (button && pendingButtons.has(button)) return;
  const disabled = button?.disabled;
  if (button) { pendingButtons.add(button); button.disabled = true; button.setAttribute('aria-busy', 'true'); }
  try { return await originalSafe(job); }
  finally { if (button) { pendingButtons.delete(button); button.disabled = disabled; button.removeAttribute('aria-busy'); } }
};

const originalShell = appShell;
appShell = function() {
  originalShell();
  const skip = document.createElement('a');
  skip.className = 'skip-link'; skip.href = '#content'; skip.textContent = 'Skip to content';
  E('app').prepend(skip);
  E('content').tabIndex = -1;
  document.querySelector('.bread').replaceChildren(E('crumb'));
  E('nav-list').setAttribute('aria-label', 'Daily work');
  E('nav-settings').setAttribute('aria-label', 'Business settings');
  const groups = document.querySelectorAll('.sidebar-group');
  groups[0].textContent = 'Daily work'; groups[1].textContent = 'Manage';
  E('nav-settings').prepend(document.querySelector('[data-page="automations"]'));
  document.querySelector('[data-page="ai"] span').textContent = 'AI & channels';
  const demo = document.querySelector('.sidebar-card');
  demo.innerHTML = '<details><summary>Explore the demo</summary><p>Try a sample message or missed call.</p><button onclick="openDemoFlow()">Simulate an event</button></details>';
  const logout = document.createElement('button');
  logout.className = 'circle-ico'; logout.setAttribute('aria-label', 'Sign out'); logout.title = 'Sign out';
  logout.innerHTML = svg('logout', 18); logout.onclick = signOut;
  document.querySelector('.top-actions').append(logout);
};

const originalNavigate = navigate;
navigate = async function(page) {
  E('content').dataset.page = page;
  await originalNavigate(page);
  if (page === 'ai') E('crumb').textContent = 'AI & channels';
  document.querySelectorAll('.nav-item').forEach(item => item.setAttribute('aria-current', item.dataset.page === page ? 'page' : 'false'));
  if (E('content').textContent.trim() === 'Loading data...') {
    E('content').innerHTML = '<div class="page-error" role="alert"><h1>Unable to load this page</h1><p>Check the connection and try again.</p><button class="btn primary" onclick="reload()">Try again</button></div>';
  }
  const heading = E('content').querySelector('h1');
  if (heading) { heading.tabIndex = -1; heading.focus({preventScroll: true}); }
};

const originalDashboard = renderDashboard;
renderDashboard = async function() {
  await originalDashboard();
  document.querySelector('.page-title').textContent = 'Your work, at a glance';
  document.querySelector('.page-sub').textContent = 'Messages, customers and appointments at ' + S.business.name + '.';
  const hero = document.querySelector('.hero');
  hero.className = 'daily-actions';
  hero.setAttribute('aria-label', 'Quick actions');
  hero.innerHTML = '<button data-action="inbox">' + svg('chat',22) + '<span><strong>Reply to customers</strong><small>Open your inbox</small></span>' + svg('arrow') + '</button><button data-action="customer">' + svg('users',22) + '<span><strong>Add a customer</strong><small>Save details and SMS consent</small></span>' + svg('plus') + '</button><button data-action="calendar">' + svg('calendar',22) + '<span><strong>Check the schedule</strong><small>See appointments and availability</small></span>' + svg('arrow') + '</button>';
  hero.querySelectorAll('button').forEach(button => button.onclick = () => button.dataset.action === 'customer' ? openContact() : navigate(button.dataset.action));
  const appointments = document.querySelector('.table-card');
  document.querySelector('.stats').after(appointments);
  document.querySelector('.mini-chart')?.closest('.card').remove();
  document.querySelector('.grid-2').classList.add('activity-only');
  document.querySelector('.page-head .btn.outline')?.remove();
};

const originalInbox = renderInbox;
renderInbox = async function() {
  await originalInbox();
  const shell = document.querySelector('.inbox-shell');
  shell.classList.toggle('thread-open', inboxThread);
  const back = document.createElement('button');
  back.className = 'inbox-back btn outline'; back.textContent = '← All conversations';
  back.onclick = () => { inboxThread = false; shell.classList.remove('thread-open'); E('inbox-query').focus(); };
  document.querySelector('.thread').prepend(back);
  E('inbox-query').value = inboxQuery;
  E('inbox-query').setAttribute('aria-label', 'Search conversations');
  E('inbox-query').placeholder = 'Search customers or messages';
  filterInbox();
  const reply = document.querySelector('.compose textarea');
  reply?.setAttribute('aria-label', 'Reply to customer');
  const contact = document.querySelector('.contact-sidebar');
  if (contact) {
    const details = document.createElement('details'); details.className = 'conversation-details';
    const summary = document.createElement('summary'); summary.textContent = 'Customer details & reply mode';
    details.append(summary); contact.before(details); details.append(contact);
  }
};
const originalFilterInbox = filterInbox;
filterInbox = function() {
  inboxQuery = E('inbox-query').value;
  originalFilterInbox();
  document.querySelectorAll('.conv-row').forEach(row => {
    row.tabIndex = 0; row.setAttribute('role', 'button');
    row.setAttribute('aria-pressed', String(row.classList.contains('selected')));
    row.onkeydown = event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); row.click(); } };
  });
};
selectConversation = function(id) {
  S.convId = id; inboxThread = true;
  safe(async () => {
    await renderInbox();
    if (matchMedia('(max-width:740px)').matches) document.querySelector('.inbox-back').focus({preventScroll: true});
  });
};

const originalSwitchBusiness = switchBusiness;
switchBusiness = async function(id) {
  inboxThread = false; inboxQuery = ''; WF.id = null; WF.flow = null;
  await originalSwitchBusiness(id);
};

function showChannel(id, focus = false) {
  channelTab = id;
  document.querySelectorAll('.channel-tabs [role="tab"]').forEach(tab => {
    const selected = tab.dataset.channel === id;
    tab.setAttribute('aria-selected', String(selected)); tab.tabIndex = selected ? 0 : -1;
    if (selected && focus) tab.focus();
  });
  document.querySelectorAll('.channel-panel').forEach(panel => panel.hidden = panel.id !== 'channel-' + id);
}

const originalStudio = renderAIStudio;
renderAIStudio = async function() {
  await originalStudio();
  document.querySelector('.page-title').textContent = 'AI & channels';
  document.querySelector('.page-sub').textContent = 'Choose a service. Save its settings, then try it below.';
  document.querySelector('.studio-headline').remove();
  const tabs = document.createElement('div'); tabs.className = 'channel-tabs';
  tabs.setAttribute('role', 'tablist'); tabs.setAttribute('aria-label', 'AI and channel settings');
  const names = [['assistant','AI assistant'],['knowledge','Business knowledge'],['voice','Voice Lab'],['sms','SMS delivery'],['whatsapp','WhatsApp'],['calls','Phone calls'],['external','External agent']];
  const panels = {};
  for (const [id] of names) panels[id] = E('content').querySelector('[data-studio-panel="' + id + '"]');
  for (const [id, label] of names) {
    const tab = document.createElement('button'); tab.id = 'channel-tab-' + id; tab.dataset.channel = id;
    tab.setAttribute('role', 'tab'); tab.setAttribute('aria-controls', 'channel-' + id); tab.textContent = label;
    tab.onclick = () => showChannel(id);
    tab.onkeydown = event => {
      let index = names.findIndex(item => item[0] === id);
      if (event.key === 'ArrowRight') index = (index + 1) % names.length;
      else if (event.key === 'ArrowLeft') index = (index + names.length - 1) % names.length;
      else if (event.key === 'Home') index = 0;
      else if (event.key === 'End') index = names.length - 1; else return;
      event.preventDefault(); showChannel(names[index][0], true);
    };
    tabs.append(tab);
    const panel = panels[id]; panel.id = 'channel-' + id; panel.classList.add('channel-panel');
    panel.setAttribute('role', 'tabpanel'); panel.setAttribute('aria-labelledby', tab.id);
    panel.querySelector('.studio-num')?.remove();
  }
  document.querySelector('.studio-stat-grid').after(tabs);
  names.forEach(([id]) => E('content').append(panels[id]));
  E('content').querySelectorAll('.studio-columns').forEach(column => column.remove());
  panels.assistant.querySelector('h2').textContent = 'Connect your AI assistant';
  panels.assistant.querySelector('.studio-card-top p').textContent = 'Choose a provider, add its key, then save and test the connection.';
  const base = E('ai-base').closest('label');
  const updateBase = () => { base.hidden = E('ai-provider').value !== 'custom'; };
  E('ai-provider').addEventListener('change', updateBase); updateBase();
  const advanced = document.createElement('details'); advanced.className = 'advanced-settings';
  const summary = document.createElement('summary'); summary.textContent = 'Advanced: receive SMS and phone calls'; advanced.append(summary);
  const divider = panels.sms.querySelector('.studio-divider');
  while (divider.nextSibling) advanced.append(divider.nextSibling);
  divider.replaceWith(advanced);
  const phone = document.createElement('details'); phone.className = 'advanced-settings';
  phone.innerHTML = '<summary>Phone call settings</summary>';
  const greeting = E('voice-greeting').closest('label'); greeting.before(phone);
  phone.append(greeting, E('voice-enabled').closest('label'));
  E('ai-prompt').setAttribute('aria-label', 'Sample customer question');
  E('voice-prompt').setAttribute('aria-label', 'Text to read aloud');
  E('voice-transcript').setAttribute('aria-live', 'polite');
  if (S.me.role !== 'owner') {
    for (const panel of [panels.assistant, panels.sms, panels.voice, panels.whatsapp, panels.calls]) {
      panel.querySelectorAll('.studio-grid-2 input,.studio-grid-2 select,.studio-grid-4 input,.studio-grid-4 select,#ai-auto,#voice-greeting,#voice-enabled').forEach(field => field.disabled = true);
    }
    for (const panel of [panels.whatsapp, panels.calls]) panel.querySelectorAll('input,select').forEach(field => field.disabled = true);
    E('ai-business-rules').disabled = true;
    const note = document.createElement('p'); note.className = 'info-note'; note.textContent = 'A business owner manages these connections. You can still try the saved AI and voice settings.'; tabs.before(note);
  }
  showChannel(channelTab);
};
renderAI = renderAIStudio;

const originalWorkflow = renderAutomationStudio;
renderAutomationStudio = async function() {
  await originalWorkflow();
  E('wf-name').setAttribute('aria-label', 'Workflow name');
  E('wf-picker').setAttribute('aria-label', 'Choose workflow');
  E('wf-test-contact').setAttribute('aria-label', 'Test customer');
  E('wf-test-text').setAttribute('aria-label', 'Test message');
  document.querySelector('.wf-panel-head p').textContent = 'Click to add a step, or drag it onto the canvas.';
  document.querySelector('.workflow-lead p').textContent = 'Add steps, connect them, then save. Check Enabled only when you want the workflow to run automatically.';
  document.querySelectorAll('.wf-tool').forEach((tool, index) => {
    const type = Object.entries(WF_TYPES).filter(([,value]) => value.group === 'Trigger').concat(Object.entries(WF_TYPES).filter(([,value]) => value.group === 'Condition'), Object.entries(WF_TYPES).filter(([,value]) => value.group === 'Action'))[index][0];
    tool.tabIndex = S.me.role === 'owner' ? 0 : -1; tool.setAttribute('role', 'button');
    tool.setAttribute('aria-disabled', String(S.me.role !== 'owner'));
    tool.onclick = () => {
      const rect = E('wf-canvas').getBoundingClientRect(), index = WF.flow.nodes.length;
      wfDrop({preventDefault(){}, clientX: rect.left + 150 + (index % 4) * 250, clientY: rect.top + 104 + Math.floor(index / 4) * 120, dataTransfer: {getData: () => JSON.stringify({type})}});
      E('wf-nodes').lastElementChild?.scrollIntoView({block: 'nearest', inline: 'nearest'});
    };
    tool.onkeydown = event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); tool.click(); } };
  });
};
renderAutomations = renderAutomationStudio;

const originalCalendar = renderCalendar;
renderCalendar = async function() {
  await originalCalendar();
  const week = document.querySelector('.week-grid');
  const scroller = document.createElement('div'); scroller.className = 'calendar-scroll'; scroller.tabIndex = 0;
  scroller.setAttribute('aria-label', 'Weekly schedule. Scroll to see all days.'); week.before(scroller); scroller.append(week);
  document.querySelectorAll('.appt-card').forEach(card => {
    card.tabIndex = 0; card.setAttribute('role', 'button');
    card.onkeydown = event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); card.click(); } };
  });
};

const originalModal = modal;
modal = function(...args) {
  if (!E('modal-root').firstElementChild) modalTrigger = document.activeElement;
  originalModal(...args);
  const dialog = E('modal-root').querySelector('.modal');
  dialog.tabIndex = -1; dialog.querySelector('h3').id = 'dialog-title'; dialog.setAttribute('aria-labelledby', 'dialog-title');
  E('app').inert = true; document.body.classList.add('dialog-open');
  (dialog.querySelector('input:not([type="hidden"]),select,textarea') || dialog).focus();
};
const originalClose = closeModal;
closeModal = function() {
  originalClose(); E('app').inert = false; document.body.classList.remove('dialog-open');
  if (modalTrigger?.isConnected) modalTrigger.focus(); modalTrigger = null;
};
window.addEventListener('keydown', event => {
  const dialog = E('modal-root').querySelector('.modal');
  if (!dialog || event.key !== 'Tab') return;
  const items = [...dialog.querySelectorAll('button,input,select,textarea,a[href],[tabindex="0"]')].filter(item => !item.disabled && item.getClientRects().length);
  const first = items[0], last = items.at(-1);
  if (!first) { event.preventDefault(); dialog.focus(); }
  else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
});

const originalLogin = showLogin;
showLogin = function() {
  originalLogin();
  document.querySelectorAll('#login-form .field').forEach(field => {
    const input = field.querySelector('input'); input.id = 'login-' + input.name;
    field.querySelector('label').htmlFor = input.id; input.autocomplete = input.name === 'email' ? 'username' : 'current-password';
  });
  const credentials = document.querySelector('.demo-credentials');
  const details = document.createElement('details'); details.className = 'demo-credentials';
  details.innerHTML = '<summary>Other demo accounts</summary>'; details.append(credentials.querySelector('p')); credentials.replaceWith(details);
};
