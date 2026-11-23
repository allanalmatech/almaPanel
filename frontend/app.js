// Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
'use strict';
const $=s=>document.querySelector(s);
let me=null, accounts=[], account=null, csrf='', setup=false, currentPath='', showHidden=false, routeEpoch=0;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function notice(text){$('#notice').textContent=text;$('#notice').classList.add('visible');clearTimeout(notice.timer);notice.timer=setTimeout(()=>$('#notice').classList.remove('visible'),9000);}
async function api(path,body){const res=await fetch('/api'+path,{method:body?'POST':'GET',credentials:'same-origin',headers:body?{'Content-Type':'application/json','X-CSRF-Token':csrf}:{},body:body?JSON.stringify(body):undefined});const data=await res.json();if(!res.ok){if(res.status===401&&me){me=null;$('#shell').hidden=true;$('#auth').hidden=false;}throw Object.assign(Error(data.error||'Request failed'),{status:res.status});}return data;}
function form(id,handler){$(id).addEventListener('submit',async e=>{e.preventDefault();const button=e.target.querySelector('[type=submit]');button.disabled=true;try{await handler(Object.fromEntries(new FormData(e.target)),e.target);}catch(err){notice(err.message);}finally{button.disabled=false;}});}
async function confirmed(text){$('#confirm-text').textContent=text;$('#confirm').returnValue='cancel';$('#confirm').showModal();return new Promise(resolve=>$('#confirm').addEventListener('close',()=>resolve($('#confirm').returnValue==='confirm'),{once:true}));}
// Original line icons. Index: 0 folder, 1 database, 2 globe, 3 lock, 4 bars, 5 terminal, 6 dashboard,
// 7 people, 8 document, 9 sliders, 10 envelope, 11 shield, 12 help, 13 server, 14 clock, 15 package.
const ICONS=['<path d="M3 10V7h10l3 4h13v15H3z"/><path d="M3 14h26"/>','<ellipse cx="16" cy="7" rx="11" ry="4"/><path d="M5 7v18c0 5 22 5 22 0V7M5 16c0 5 22 5 22 0"/>','<circle cx="16" cy="16" r="12"/><ellipse cx="16" cy="16" rx="5" ry="12"/><path d="M4 16h24M7 8h18M7 24h18"/>','<rect x="4" y="10" width="24" height="18" rx="3"/><path d="M10 10V7a6 6 0 0112 0v3M16 17v5"/>','<path d="M5 26V15h5v11M14 26V6h5v20M23 26V11h5v15"/>','<path d="M4 7h24v19H4zM8 12l5 4-5 4M17 21h7"/>',
    '<rect x="4" y="4" width="10" height="12" rx="2"/><rect x="18" y="4" width="10" height="7" rx="2"/><rect x="4" y="20" width="10" height="8" rx="2"/><rect x="18" y="15" width="10" height="13" rx="2"/>',
    '<circle cx="12" cy="11" r="5"/><path d="M3 27c1-6 5-9 9-9s8 3 9 9"/><circle cx="23" cy="9" r="4"/><path d="M22 17c4 0 7 3 7 8"/>',
    '<path d="M8 3h11l6 6v20H8z"/><path d="M19 3v6h6M12 16h9M12 21h9"/>',
    '<path d="M5 9h22M5 16h22M5 23h22"/><circle cx="11" cy="9" r="2.5"/><circle cx="21" cy="16" r="2.5"/><circle cx="14" cy="23" r="2.5"/>',
    '<rect x="3" y="7" width="26" height="18" rx="2"/><path d="M4 9l12 9 12-9"/>',
    '<path d="M16 3l11 4v8c0 7-5 12-11 14C10 27 5 22 5 15V7z"/><path d="M11 16l4 4 6-8"/>',
    '<circle cx="16" cy="16" r="12"/><path d="M12 12a4 4 0 118 0c0 3-4 3-4 6M16 23v.5"/>',
    '<rect x="5" y="4" width="22" height="10" rx="2"/><rect x="5" y="18" width="22" height="10" rx="2"/><path d="M10 9h1M10 23h1M16 9h6M16 23h6"/>',
    '<circle cx="16" cy="16" r="12"/><path d="M16 9v7l5 3"/>',
    '<path d="M4 10l12-6 12 6v12l-12 6-12-6z"/><path d="M4 10l12 6 12-6M16 16v12"/>'];
const icon=(kind=0)=>`<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${ICONS[kind]||ICONS[0]}</svg>`;
// Shared tool catalog: drives the dashboard groups, search, breadcrumbs and role filtering.
// roles omitted = every signed-in role. The server still enforces every permission.
const MANAGERS=['admin','reseller'],ADMINS=['admin'];
// Tools marked with a fifth element true are planned: their tiles open a status page, not a tool.
const SOON=true;
const catalog=[
    {label:'Hosting Management',roles:MANAGERS,tools:[['Hosting Accounts','accounts',7,'Create, suspend and retry hosting accounts'],['Hosting Packages','packages',15,'Enforce domain-count allocations']]},
    {label:'Email',tools:[['Email Accounts','mail',10,'Create mailboxes, passwords and quotas'],['Forwarders','forwarders',10,'Forward addresses to other mailboxes'],
        ['Email Routing','soon-email-routing',10,'Choose local or remote mail delivery for a domain',SOON],['Autoresponders','autoresponders',10,'Send automatic replies while away'],
        ['Default Address','default-address',10,'Catch mail sent to unknown addresses'],['Mailing Lists','soon-mailing-lists',7,'Run discussion and announcement lists',SOON],
        ['Track Delivery','track-delivery',4,'Follow messages through the mail server'],['Global Email Filters','global-email-filters',11,'Filter mail for every address in the account'],
        ['Email Filters','email-filters',11,'Sort or discard mail for one address'],['Email Deliverability','email-deliverability',11,'Check MX, SPF and DMARC records'],
        ['Address Importer','soon-address-importer',8,'Create many addresses or forwarders from a file',SOON],['Spam Filters','soon-spam-filters',11,'Score and filter unwanted mail',SOON],
        ['Encryption','soon-encryption',3,'Manage keys for encrypted mail',SOON],['Challenge-Response Filter','soon-challenge-response',11,'Hold mail from unknown senders until they confirm',SOON],
        ['Configure Greylisting','soon-greylisting',14,'Delay first-time senders to reduce spam',SOON],['Email Disk Usage','email-disk-usage',4,'See storage used by each mailbox']]},
    {label:'Files',tools:[['File Manager','files',0,'Browse, upload and edit website files'],['Images','files',0,'Resize and convert pictures from the file list'],
        ['Directory Privacy','directory-privacy',3,'Password-protect website folders'],['Disk Usage','usage',4,'Measure actual account storage'],
        ['Website Backups','backups',0,'Back up and restore website files'],['Trash','trash',0,'Recover files and folders'],['SFTP Access','sftp',3,'Manage keys for file transfer'],
        ['Git Deployment','git',5,'Stage a public repository in a new site folder'],['Web Disk','soon-web-disk',0,'Open your files as a network drive',SOON],
        ['FTP Accounts','soon-ftp-accounts',7,'Create FTP logins limited to a folder',SOON],['Backup Wizard','soon-backup-wizard',0,'Step-by-step full backup and restore',SOON],
        ['Git Version Control','soon-git-version-control',5,'Create, clone and deploy private repositories',SOON]]},
    {label:'Databases',tools:[['Databases','databases',1,'Create MariaDB and PostgreSQL databases'],
        ['Database Manager','soon-database-manager',1,'Browse tables and run SQL in the browser',SOON],['Database Wizard','soon-database-wizard',1,'Create a database, user and privileges step by step',SOON],
        ['Remote Database Access','soon-remote-database',2,'Allow chosen hosts to connect to your databases',SOON]]},
    {label:'Domains',tools:[['Domains','domains',2,'Manage websites, aliases and document roots'],['Redirects','redirects',2,'Send a domain to another address'],
        ['WordPress Management','wordpress',15,'Install WordPress on an HTTPS website'],['Zone Editor','soon-zone-editor',2,'Edit DNS records for your domains',SOON],
        ['Site Publisher','soon-site-publisher',8,'Publish a simple starter page quickly',SOON],['Website Builder','soon-website-builder',6,'Design pages with a drag-and-drop editor',SOON],
        ['Dynamic DNS','soon-dynamic-dns',2,'Keep a hostname pointed at a changing IP address',SOON]]},
    {label:'Metrics',tools:[['Metrics','metrics',4,'Review recent requests and account processes'],
        ['Visitors','soon-visitors',4,'Browse recent visitors to each website',SOON],['Errors','soon-errors',8,'Read recent website error messages',SOON],
        ['Bandwidth','soon-bandwidth',4,'See data transferred by each website',SOON],['Raw Access Logs','soon-raw-access',8,'Download website access logs',SOON],
        ['Visitor Statistics','soon-visitor-statistics',4,'Charts of visits, pages and referrers',SOON],['Resource Usage','soon-resource-usage',13,'CPU, memory and process limits over time',SOON]]},
    {label:'Security',tools:[['SSL/TLS','tls',3,'Issue or install website certificates'],['SSL/TLS Status','ssl-status',3,'Check certificate expiry for each website'],
        ['IP Blocker','ip-blocker',11,'Block website visitors by IP address or network'],['Hotlink Protection','hotlink',11,'Stop other websites embedding your media'],
        ['Two-Factor Authentication','two-factor',3,'Require an authenticator code to sign in'],['API Tokens','tokens',3,'Manage read-only access to hosting data'],
        ['SSH Access','soon-ssh-access',5,'Manage keys for secure shell access',SOON],['Leech Protection','soon-leech-protection',11,'Lock shared passwords for protected folders',SOON],
        ['ModSecurity','soon-modsecurity',11,'Web application firewall rules for your websites',SOON],['Malware Scanner','soon-malware-scanner',11,'Scan website files for known malware',SOON]]},
    {label:'Software',tools:[['PHP Settings','php',5,'Manage resource settings and errors for your PHP-FPM pool'],['Optimize Website','optimize',4,'Compress text content so pages load faster'],
        ['PHP Version Manager','soon-php-versions',5,'Choose a PHP version for each website',SOON],['App Installer','soon-app-installer',15,'Install popular web applications in a few steps',SOON],
        ['Setup Node.js App','soon-nodejs',5,'Run a Node.js application behind your domain',SOON],['Setup Python App','soon-python',5,'Run a Python application behind your domain',SOON],
        ['Application Manager','soon-application-manager',15,'Start, stop and monitor your applications',SOON],['PHP PEAR Packages','soon-pear',15,'Install PHP extension packages for your account',SOON],
        ['Perl Modules','soon-perl',15,'Install Perl modules for your account',SOON]]},
    {label:'Advanced',tools:[['Cron Jobs','cron',14,'Schedule account PHP scripts'],['Track DNS','dns-lookup',2,'Look up public DNS records'],
        ['Indexes','indexes',0,'Choose folders that show a file listing'],['Error Pages','error-pages',8,'Show your own pages for HTTP errors'],
        ['MIME Types','mime-types',8,'Tell browsers how to handle file extensions']]},
    {label:'Preferences',tools:[['Preferences','preferences',9,'Contact details, password and two-factor sign-in'],['Operation History','jobs',5,'Track queued and completed operations'],
        ['Notifications','notifications',4,'Review completed or failed jobs'],['Change Language','soon-language',2,'Use the panel in another language',SOON]]},
    {label:'Billing & Support',tools:[['Support & About','about',12,'Alma Tech Labs Inc. contact and product information'],['Feature Availability','availability',12,'Implemented features and remaining work'],
        ['Billing','soon-billing',15,'Invoices, payments and plan changes',SOON]]},
    {label:'Server Administration',roles:ADMINS,tools:[['Server Information','system',13,'Live Linux resource and service status'],['Off-site Backups','offsite-backups',0,'Run encrypted backups and check progress'],['Zone Editor (server)','dns',2,'Manage authoritative DNS records'],['Resellers','resellers',7,'Create resellers with account limits'],['Audit Log','audit',5,'Review administrative activity']]}];
// Tiles that open an existing tool under a familiar name.
const ALIASES={'forwarders':'mail','directory-privacy':'site-security','ip-blocker':'site-security','redirects':'domains','ssl-status':'tls','two-factor':'preferences'};
// Short sidebar: everything else is reached from the dashboard groups.
const sidebar=[['dashboard','Dashboard',6],['accounts','Hosting Accounts',7,MANAGERS],['files','File Manager',8],['domains','Domains',2],['preferences','Preferences',9]];
const allowed=roles=>!roles||roles.includes(me?.role);
const visibleGroups=()=>catalog.filter(g=>allowed(g.roles));
// File Manager and the file editor open in their own browser tabs, without the panel shell.
const STANDALONE=['filemanager','editor'];
function fileManagerUrl(folder=''){return account?`#filemanager?account=${account.id}`+(folder?`&path=${encodeURIComponent(folder)}`:''):'#files';}
function syncFileManagerLinks(){document.querySelectorAll('a[data-file-manager]').forEach(a=>{a.setAttribute('href',fileManagerUrl());if(account)a.target='alma-files-'+account.id;else a.removeAttribute('target');});}
function findTool(page){for(const g of catalog)for(const t of g.tools)if(t[1]===page)return {group:g.label,title:t[0]};return null;}
function view(title,desc,html){$('#main').innerHTML=`<div class="intro"><div class="eyebrow">almaPanel / ${esc(me.role)}</div><h1>${esc(title)}</h1><p class="muted">${esc(desc)}</p></div>${html}`;}
function table(headers,items){return `<div class="table-wrap"><table><thead><tr>${headers.map(x=>`<th>${esc(x)}</th>`).join('')}</tr></thead><tbody>${items.length?items.map(row=>`<tr>${row.map(x=>`<td>${x}</td>`).join('')}</tr>`).join(''):`<tr><td colspan="${headers.length}">No records yet.</td></tr>`}</tbody></table></div>`;}
const field=(name,label,type='text',extra='')=>`<label>${label}<input name="${name}" type="${type}" required ${extra}></label>`;
function accountPath(s){if(!account)throw Error('Create or select a hosting account first.');return `/accounts/${account.id}/${s}`;}
async function refreshAccounts(){accounts=await api('/accounts');const previous=account?.id;account=accounts.find(a=>a.id===previous)||accounts[0]||null;$('#account-select').innerHTML=accounts.length?accounts.map(a=>`<option value="${a.id}">${esc(a.name)} · ${esc(a.state)}</option>`).join(''):'<option>No hosting accounts</option>';if(account)$('#account-select').value=account.id;await stats();}
async function stats(){let data={};if(account?.state==='active'){try{data=await api(accountPath('stats'));}catch(e){data.error=e.message;}}$('#statistics').innerHTML=`<h2>General information</h2><dl><dt>Current user</dt><dd>${esc(me.username)}</dd><dt>Account</dt><dd>${esc(account?.name||'None selected')}</dd><dt>Hosting package</dt><dd>${esc(account?.package||'—')}</dd><dt>Primary domain</dt><dd>${esc(data.primary_domain||'—')}</dd><dt>Databases</dt><dd>${esc(data.databases??'—')}</dd><dt>Email accounts</dt><dd>${esc(data.mailboxes??'—')}</dd><dt>Inodes</dt><dd>${esc(data.inodes??'—')}</dd><dt>Processes</dt><dd>${esc(data.processes??'—')}</dd><dt>Home directory</dt><dd>${esc(data.home||'—')}</dd><dt>Last login IP</dt><dd>${esc(me.last_ip||'—')}</dd></dl><div class="stat-separator"></div><h2>Statistics</h2><dl><dt>Disk usage</dt><dd>${data.disk_bytes!==undefined?(data.disk_bytes/1048576).toFixed(2)+' MiB':'Unavailable'}</dd><dt>Domains</dt><dd>${esc(data.domains??'Unavailable')}</dd><dt>CPU / RAM / bandwidth</dt><dd>Not metered in this release</dd></dl><p class="note">${esc(data.error||data.quota_note||'Usage is loaded from the server. No sample data.')}</p>`;}
function dashboard(){
    const raw=$('#search').value.trim(),terms=raw.toLowerCase().split(/\s+/).filter(Boolean);
    const groupsForRole=visibleGroups(),total=groupsForRole.reduce((n,g)=>n+g.tools.length,0);
    // Every search term must appear in the tool name, its description or its category name.
    const shown=groupsForRole.map(g=>({...g,tools:g.tools.filter(t=>{const text=`${g.label} ${t[0]} ${t[3]}`.toLowerCase();return terms.every(term=>text.includes(term));})})).filter(g=>g.tools.length);
    const matches=shown.reduce((n,g)=>n+g.tools.length,0);
    const planned=groupsForRole.reduce((n,g)=>n+g.tools.filter(t=>t[4]).length,0);
    const summary=terms.length?`${matches} of ${total} tools match “${esc(raw)}”`:`${total} tools in ${groupsForRole.length} groups · ${total-planned} available, ${planned} planned`;
    // Folded groups are remembered per browser; a search shows every group with matches unfolded.
    const folded=terms.length?new Set():foldedGroups();
    // Large groups span a row. The last small group stretches over any empty columns left in its row.
    const narrow=shown.filter(g=>g.tools.length<4),lastNarrow=narrow[narrow.length-1],fill=lastNarrow?[narrow.length%2?' fill-2':'',narrow.length%3===1?' fill-3':narrow.length%3===2?' fill-3-half':''].join(''):'';
    const chevron='<svg class="chevron" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true" focusable="false"><path d="M4 6l4 4 4-4"/></svg>';
    const body=shown.length?`<div class="tool-groups">${shown.map((g,n)=>{const closed=folded.has(g.label);return `<section class="section${g.tools.length>=4?' wide':g===lastNarrow?fill:''}${closed?' folded':''}" aria-labelledby="group-${n}"><h2 id="group-${n}"><button type="button" class="group-toggle" data-group="${esc(g.label)}" aria-expanded="${!closed}" aria-controls="group-body-${n}"><span class="group-name">${esc(g.label)}</span><span class="count">${g.tools.length}</span>${chevron}</button></h2><div class="tool-grid" id="group-body-${n}"${closed?' hidden':''}>${g.tools.map(([title,href,i,help,soon])=>`<a class="tool${soon?' soon':''}" href="#${href}"${href==='files'?' data-file-manager':''}>${icon(i)}<span>${esc(title)}${soon?'<em class="badge">Planned</em>':''}<small>${esc(help)}</small></span></a>`).join('')}</div></section>`;}).join('')}</div>`
        :`<section class="panel empty-state"><h2>No tools match “${esc(raw)}”</h2><p>Try a tool name, a task such as “backup”, or a category such as “Email”.</p><button id="clear-search" type="button">Clear search</button></section>`;
    const foldButtons=terms.length||!shown.length?'':'<span class="fold-all"><button type="button" class="subtle" data-fold-all="open">Expand all</button><button type="button" class="subtle" data-fold-all="close">Collapse all</button></span>';
    view('Dashboard','Manage your websites and hosting resources. Search or choose a tool below.',`<div class="toolbar dashboard-bar"><p id="tool-count" role="status">${summary}</p>${terms.length&&shown.length?'<button id="clear-search" type="button" class="subtle">Clear search</button>':''}${foldButtons}</div>${body}<p class="note">Tools marked Planned are on the roadmap. Feature Availability under Billing &amp; Support lists what this release includes.</p>`);
    syncFileManagerLinks();
    const setFolded=(section,closed)=>{section.classList.toggle('folded',closed);section.querySelector('.tool-grid').hidden=closed;section.querySelector('.group-toggle').setAttribute('aria-expanded',String(!closed));};
    $('#main').querySelectorAll('.group-toggle').forEach(button=>button.onclick=()=>{
        const section=button.closest('.section'),closed=!section.classList.contains('folded');
        setFolded(section,closed);
        if(!terms.length){const stored=foldedGroups();closed?stored.add(button.dataset.group):stored.delete(button.dataset.group);saveFolded(stored);}
    });
    $('#main').querySelectorAll('[data-fold-all]').forEach(button=>button.onclick=()=>{
        const closed=button.dataset.foldAll==='close';
        $('#main').querySelectorAll('.tool-groups .section').forEach(section=>setFolded(section,closed));
        saveFolded(closed?new Set(shown.map(g=>g.label)):new Set());
    });
    const clear=$('#clear-search');if(clear)clear.onclick=()=>{$('#search').value='';dashboard();$('#search').focus();};
}
const FOLD_KEY='alma-folded-groups';
function foldedGroups(){try{return new Set(JSON.parse(localStorage.getItem(FOLD_KEY)||'[]'));}catch{return new Set();}}
function saveFolded(groups){try{localStorage.setItem(FOLD_KEY,JSON.stringify([...groups]));}catch{/* Per-browser preference only. */}}
function breadcrumb(page){
    const tool=page==='dashboard'?null:findTool(page),title=page==='dashboard'?'Dashboard':tool?.title||'Page unavailable';
    const parts=[`<li><a href="#dashboard">Home</a></li>`];if(tool)parts.push(`<li>${esc(tool.group)}</li>`);parts.push(`<li aria-current="page">${esc(title)}</li>`);
    $('#breadcrumb').innerHTML=`<ol>${parts.join('')}</ol>`;document.title=`${title} · almaPanel`;
}
function markActive(page){
    const links=[...document.querySelectorAll('#nav a')],exact=links.some(a=>a.hash==='#'+page);
    // Tools opened from dashboard groups keep Dashboard highlighted as their parent.
    links.forEach(a=>{const current=a.hash==='#'+page,parent=!exact&&a.hash==='#dashboard';a.classList.toggle('active',current||parent);if(current)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
}
const mobileQuery=matchMedia('(max-width:760px)');
function setMenuState(){
    const mobile=mobileQuery.matches,open=document.body.classList.contains('mobile-open'),collapsed=document.body.classList.contains('collapsed');
    $('#menu').setAttribute('aria-expanded',String(mobile?open:!collapsed));
    $('#menu').setAttribute('aria-label',mobile?(open?'Close navigation':'Open navigation'):(collapsed?'Expand navigation':'Collapse navigation'));
}
function openMobileNav(){document.body.classList.add('mobile-open');setMenuState();$('#nav a')?.focus();}
function closeMobileNav(returnFocus){if(!document.body.classList.contains('mobile-open'))return;document.body.classList.remove('mobile-open');setMenuState();if(returnFocus)$('#menu').focus();}
function toggleMenu(){
    if(mobileQuery.matches){document.body.classList.contains('mobile-open')?closeMobileNav(true):openMobileNav();return;}
    document.body.classList.add('animate-nav');clearTimeout(toggleMenu.timer);toggleMenu.timer=setTimeout(()=>document.body.classList.remove('animate-nav'),250);document.body.classList.toggle('collapsed');try{localStorage.setItem('alma-sidebar',document.body.classList.contains('collapsed')?'collapsed':'expanded');}catch(e){}setMenuState();
}
async function route(){closeFileView();closeFileView=()=>{};const epoch=++routeEpoch;let [page,query='']=(location.hash.slice(1)||'dashboard').split('?');const params=new URLSearchParams(query);const standalone=STANDALONE.includes(page);document.body.classList.toggle('standalone',standalone);const fromDrawer=document.body.classList.contains('mobile-open');closeMobileNav(false);if(fromDrawer)$('#main').focus();if(page!=='dashboard')$('#search').value='';breadcrumb(page);markActive(page);const requested=page;page=ALIASES[page]||page;document.body.classList.toggle('page-files',page==='files');$('#main').innerHTML='<p role="status">Loading…</p>';try{
if(standalone){const id=Number(params.get('account')),target=accounts.find(a=>a.id===id);if(!target)throw Error('This hosting account is not available to you. Close this tab and choose an account in almaPanel.');if(account?.id!==id){account=target;currentPath='';$('#account-select').value=id;}
if(page==='filemanager'){if(params.has('path'))currentPath=params.get('path');await fileManagerView(epoch);}else await fileEditorPage(epoch,params);return;}
if(page==='dashboard'){dashboard();return;}
if(page.startsWith('soon-')){const tool=findTool(requested);if(!tool)throw Error('Tool not found.');const entry=catalog.flatMap(g=>g.tools).find(t=>t[1]===requested);view(tool.title,entry[3],`<section class="panel"><p><span class="badge">Planned</span> This tool is not available in this release yet.</p><p>It is on the almaPanel roadmap in the ${esc(tool.group)} group. Feature Availability lists what each release includes.</p><a href="#availability">Open Feature Availability</a> · <a href="#dashboard">Back to the dashboard</a></section>`);return;}
if(['default-address','autoresponders','email-filters','global-email-filters','email-disk-usage','track-delivery','email-deliverability'].includes(page)){await mailToolsView(epoch,page);return;}
if(page==='indexes'||page==='error-pages'||page==='mime-types'||page==='hotlink'||page==='optimize'){await siteOptionsView(epoch,{'indexes':'indexes','error-pages':'error_pages','mime-types':'mime','hotlink':'hotlink','optimize':'optimize'}[page]);return;}
if(page==='about'){view('About almaPanel','Powerful Hosting. Simple Management.',`<section class="panel"><h2>Developed and owned by Alma Tech Labs Inc.</h2><p>Linux hosting control panel · Linux edition</p><p><a href="https://almatechconsults.com">almatechconsults.com</a><br><a href="mailto:almatechuganda@gmail.com">almatechuganda@gmail.com</a><br><a href="tel:+256700868939">+256 700 868 939</a></p><p>Original branding, artwork and implementation. Not affiliated with cPanel.</p><p>Licensing is pending owner approval. © 2026 Alma Tech Labs Inc. All Rights Reserved.</p></section>`);return;}
if(page==='availability'){
    view('Feature availability', 'Check which tools are available on this installation.', table(['Module','Available tools','Requirements or limits'], [
        ['Files', 'File Manager tab, editor tab, search, previews, copying, ZIP, Trash, upload and download', '256 MiB per upload or download; 64 MiB archive content'],
        ['Website options', 'Indexes, Error Pages, MIME Types, Hotlink Protection and Optimize Website (compression)', 'Applied to Nginx after a configuration test'],
        ['Domains', 'Document roots, aliases, redirects and DNS verification', 'Tenant additions require a TXT record'],
        ['Databases', 'MariaDB and PostgreSQL provisioning, import and export', 'Enable each engine on the server'],
        ['SSL/TLS and DNS', 'Certificate upload, ACME, renewal and forward zones', 'Public DNS and optional Certbot/BIND setup'],
        ['Email', 'Mailboxes, mail quotas and forwarders', 'Requires optional Postfix and Dovecot setup'],
        ['Transfer', 'Key-only SFTP', 'Enable the separate SFTP listener first'],
        ['Software', 'WordPress, public Git staging, PHP settings and PHP jobs', 'WordPress needs a site certificate and empty MariaDB database'],
        ['Security', 'TOTP, API tokens, directory passwords and website IP rules', 'Directory passwords require HTTPS and a dedicated document root'],
        ['Backups', 'Manual and scheduled website ZIPs with restore', 'SQL exports are separate'],
        ['Planned', 'Tiles marked Planned on the dashboard, including FTP, Web Disk, mail filters and autoresponders, Node.js and Python apps, PHP versions and an app installer', 'See the repository feature matrix and roadmap']
    ].map(row=>row.map(esc))));
    return;
}
if(page==='preferences'){await preferencesView(epoch);return;}
if(page==='tokens'){await tokensView(epoch);return;}
if(page==='notifications'){await notificationsView(epoch);return;}
if(page==='jobs'||page==='audit'){const data=await api('/'+page);if(epoch!==routeEpoch)return;view(page==='jobs'?'Operation history':'Security audit log','Reload to retrieve the latest server state.',`<div class="toolbar"><button id="reload">Refresh</button></div>`+table(page==='jobs'?['ID','Operation','State','Details']:['Time','Actor','Action','Target'],data.map(x=>page==='jobs'?[esc(x.id),esc(x.operation),`<span class="badge">${esc(x.state)}</span>`,esc(x.result||'Waiting for worker')]:[esc(new Date(x.created*1000).toLocaleString()),esc(x.actor_id),esc(x.action),esc(x.target)])));$('#reload').onclick=route;return;}
if(page==='system'){const s=await api('/system');if(epoch!==routeEpoch)return;view('Server information','Live information from the privileged Linux agent.',`<section class="panel"><h2>${esc(s.hostname)}</h2><p>Memory used: ${((s.memory_total-s.memory_available)/1048576).toFixed(0)} / ${(s.memory_total/1048576).toFixed(0)} MiB</p><progress value="${s.memory_total-s.memory_available}" max="${s.memory_total}"></progress><p>Filesystem: ${(s.disk_used/1073741824).toFixed(1)} / ${(s.disk_total/1073741824).toFixed(1)} GiB</p><p>Load average: ${s.load_average.map(v=>v.toFixed(2)).join(' / ')}</p>${table(['Service','Status'],Object.entries(s.services).map(r=>r.map(esc)))}<form id="service-form"><label>Service<select name="service">${Object.keys(s.services).map(unit=>`<option>${esc(unit)}</option>`).join('')}</select></label>${field('confirm','Type RESTART to authorize disruption')}<button type="submit">Queue restart</button></form></section>`);const updates = await api('/updates');
if(epoch!==routeEpoch)return;
$('#main').insertAdjacentHTML('beforeend', `<section class="panel"><h2>Software updates</h2>
<p>Installed version ${esc(updates.version)}</p><p>${esc(updates.state)} · ${esc(updates.message)}</p>
${updates.checked_at ? `<p>Last checked ${esc(new Date(updates.checked_at*1000).toLocaleString())}</p>` : ''}
<button id="update-check">Check and apply updates</button>
<button id="update-refresh" class="subtle">Refresh status</button></section>`);
$('#update-refresh').onclick=route;
$('#update-check').onclick=async()=>{try{notice((await api('/updates',{})).message);}catch(e){notice(e.message);}};
form('#service-form',async b=>{if(await confirmed('Restart this service? Active requests may be interrupted.')){await api('/services',b);location.hash='jobs';}});return;}
if(page==='packages'){const data=await api('/packages');if(epoch!==routeEpoch)return;view('Hosting packages','This release enforces domain counts only.',`<section class="panel">${table(['Name','Domain limit'],data.map(x=>[esc(x.name),esc(x.max_domains)]))}<h2>Create package</h2><form id="package-form">${field('name','Package name')}${field('max_domains','Maximum domains','number','min="1" max="100" value="3"')}<button type="submit">Create package</button></form></section>`);form('#package-form',async b=>{b.max_domains=Number(b.max_domains);notice((await api('/packages',b)).message);await route();});return;}
if(page==='resellers'){const data=await api('/resellers');if(epoch!==routeEpoch)return;view('Resellers','Each reseller can access only their assigned hosting accounts.',`<section class="panel">${table(['Username','Account limit'],data.map(x=>[esc(x.username),esc(x.max_accounts)]))}<form id="reseller-form">${field('username','Username')}${field('password','Password','password','minlength="14" autocomplete="new-password"')}${field('max_accounts','Account allocation','number','min="1" max="100"')}<button type="submit">Create reseller</button></form></section>`);form('#reseller-form',async b=>{b.max_accounts=Number(b.max_accounts);notice((await api('/resellers',b)).message);await route();});return;}
if(page==='accounts'){await hostingAccountsView(epoch);return;}
if(page==='domains'){await domainsView(epoch);return;}
if(page==='tls'){await tlsView(epoch);return;}
if(page==='databases'){await databaseView(epoch);return;}
if(page==='dns'){await dnsView(epoch);return;}
if(page==='offsite-backups'){await offsiteBackupsView(epoch);return;}
if(page==='backups'){await backupsView(epoch);return;}
if(page==='metrics'){await metricsView(epoch);return;}
if(page==='mail'){await mailView(epoch);return;}
if(page==='sftp'){await sftpView(epoch);return;}
if(page==='site-security'){await siteSecurityView(epoch);return;}
if(page==='dns-lookup'){dnsLookupView(epoch);return;}
if(page==='cron'){await cronView(epoch);return;}
if(page==='php'){await phpView(epoch);return;}
if(page==='wordpress'){await wordpressView(epoch);return;}
if(page==='git'){gitView(epoch);return;}
if(page==='trash'){await trashView(epoch);return;}
if(page==='usage'){await stats();view('Disk usage','Actual account directory size; disk quotas are not enforced.',`<section class="panel"><p>Current measurements appear in the Statistics panel.</p><button id="reload">Refresh measurements</button></section>`);$('#reload').onclick=route;return;}
if(page==='files'){view('File Manager','File Manager opens in its own browser tab, so the panel stays open here.',account?`<section class="panel"><p>Hosting account <strong>${esc(account.name)}</strong></p><a class="button-link" data-file-manager href="#files">Open File Manager</a></section>`:'<section class="panel"><p>Create or select a hosting account first.</p></section>');syncFileManagerLinks();return;}
view('Page unavailable','Choose an available tool from the dashboard.','<a href="#dashboard">Return to tools</a>');
}catch(e){if(epoch===routeEpoch)view('Unable to load tool',e.message,'<a href="#dashboard">Return to tools</a>');}}
async function boot(){try{me=await api('/me');csrf=me.csrf;$('#boot').hidden=true;$('#auth').hidden=true;$('#shell').hidden=false;$('#username').textContent=me.username;$('#role-label').textContent=me.role+' control panel';$('#nav').innerHTML=sidebar.filter(([,,,roles])=>allowed(roles)).map(([id,name,i])=>`<a href="#${id}" title="${esc(name)}"${id==='files'?' data-file-manager':''}>${icon(i)}<span class="nav-label">${esc(name)}</span></a>`).join('');setMenuState();await refreshAccounts();syncFileManagerLinks();await route();}catch(e){$('#boot').hidden=true;$('#auth').hidden=false;$('#shell').hidden=true;if(!e.message.includes('sign in'))notice(e.message);}}
form('#login-form',async body=>{const data=await api(setup?'/setup':'/login',body);if(setup){notice(data.message);$('#setup-toggle').click();}else await boot();});$('#setup-toggle').onclick=()=>{setup=!setup;$('#token-label').hidden=!setup;$('#login-code').hidden=setup;$('#auth-title').textContent=setup?'Create initial administrator':'Sign in to your account';$('#login-form button').textContent=setup?'Create administrator':'Sign in';$('#setup-toggle').textContent=setup?'Back to sign in':'First installation? Set up administrator';};$('#logout').onclick=async()=>{try{await api('/logout',{});closeFileView();me=null;closeMobileNav(false);$('#search').value='';history.replaceState(null,'','#dashboard');document.title='almaPanel — Alma Tech Labs Inc.';$('#shell').hidden=true;$('#auth').hidden=false;$('#login-form').reset();}catch(e){notice(e.message);}};$('#search').oninput=()=>{if(location.hash!=='#dashboard')location.hash='dashboard';else dashboard();};$('#account-select').onchange=async e=>{account=accounts.find(a=>a.id===Number(e.target.value));currentPath='';syncFileManagerLinks();await stats();await route();};$('#theme').onclick=()=>{document.body.classList.toggle('dark');localStorage.setItem('alma-theme',document.body.classList.contains('dark')?'dark':'light');};if(localStorage.getItem('alma-theme')==='dark')document.body.classList.add('dark');try{if(localStorage.getItem('alma-sidebar')==='collapsed')document.body.classList.add('collapsed');}catch(e){}$('#menu').onclick=toggleMenu;$('#nav-close').onclick=()=>closeMobileNav(true);$('#scrim').onclick=()=>closeMobileNav(true);mobileQuery.addEventListener('change',()=>{closeMobileNav(false);setMenuState();});document.addEventListener('keydown',e=>{if(!document.body.classList.contains('mobile-open'))return;if(e.key==='Escape'){e.preventDefault();closeMobileNav(true);return;}if(e.key==='Tab'){const items=[...$('#sidebar').querySelectorAll('a[href],button')].filter(x=>x.offsetParent);if(!items.length)return;const first=items[0],last=items[items.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}else if(!$('#sidebar').contains(document.activeElement)){e.preventDefault();first.focus();}}});$('#search').onkeydown=e=>{if(e.key==='Escape'&&e.target.value){e.preventDefault();e.target.value='';dashboard();}};$('#jobs-top').onclick=()=>location.hash='jobs';window.addEventListener('hashchange',()=>{if(me)route();});document.body.classList.toggle('standalone',STANDALONE.includes(location.hash.slice(1).split('?')[0]));boot();
