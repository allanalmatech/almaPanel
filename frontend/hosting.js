// Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
'use strict';

const filePath = (path, action, fields = {}) => api(path, {action, ...fields});

function boundAccount() {
    return accountPath('');
}

function activeView(epoch, base) {
    return routeEpoch === epoch && account?.id && accountPath('') === base;
}

function actionHandler(scope, selector, handler) {
    scope.querySelectorAll(selector).forEach(button => {
        button.onclick = async () => {
            button.disabled = true;
            try { await handler(button); }
            catch (error) { notice(error.message); }
            finally { button.disabled = false; }
        };
    });
}

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function readLargeFile(path, action, name, options = {}) {
    let offset = 0;
    let revision = '';
    const chunks = [];
    const maxSize = options.maxBytes ?? (action === 'backup_read' ? 130 : 66) * 1024 * 1024;
    while (true) {
        if (options.active && !options.active()) throw Error('Transfer stopped.');
        const result = await filePath(path, action, {path: name, offset, revision});
        if (result.size > maxSize) throw Error('File exceeds the transfer or preview limit.');
        const chunk = Uint8Array.from(atob(result.content), char => char.charCodeAt(0));
        chunks.push(chunk);
        offset += chunk.length;
        revision = result.revision;
        options.progress?.(offset, result.size);
        if (result.done) {
            if (offset !== result.size) throw Error('Incomplete download.');
            break;
        }
        if (!chunk.length || offset > maxSize) throw Error('Download exceeds the size limit.');
    }
    return chunks;
}

async function backupsView(epoch) {
    const base = boundAccount();
    const path = base + 'files';
    const [backups, schedule] = await Promise.all([filePath(path, 'backups'), api(base + 'backup-schedule')]);
    if (!activeView(epoch, base)) return;
    view('Website backups', 'Create a private ZIP of public_html. Restore into a new folder to review before changing the live site.',
        '<section class="panel"><div class="toolbar"><button id="make-backup">Create website backup</button></div>' +
        table(['Archive', 'Size', 'Created', 'Actions'], backups.map((item, index) => [
            esc(item.name), esc((item.size / 1024).toFixed(1) + ' KiB'), esc(new Date(item.created * 1000).toLocaleString()),
            `<button class="subtle" data-backup-browse="${index}">Browse files</button>
             <button class="subtle" data-backup-download="${index}">Download</button>
             <button class="subtle" data-backup-restore="${index}">Restore into folder</button>
             <button class="subtle" data-backup-delete="${index}">Delete</button>`
        ])) + `</section><section id="backup-browser" class="panel" hidden></section>
        <section class="panel"><h2>Scheduled backups</h2><form id="backup-schedule">
        <label>Frequency<select name="interval_hours">
        <option value="0">Off</option><option value="24">Daily</option><option value="168">Weekly</option></select></label>
        ${field('retain', 'Keep this many scheduled backups', 'number', 'min="1" max="10" value="' + esc(schedule.retain) + '"')}
        <button type="submit">Save schedule</button></form>
        ${schedule.next_run ? `<p>Next check after ${esc(new Date(schedule.next_run * 1000).toLocaleString())}</p>` : ''}</section>`);
    const scope = $('#main');
    $('#backup-schedule').elements.interval_hours.value = schedule.interval_hours;
    form('#backup-schedule', async fields => {
        notice((await api(base + 'backup-schedule', {
            interval_hours: Number(fields.interval_hours), retain: Number(fields.retain)
        })).message);
        if (activeView(epoch, base)) await route();
    });
    actionHandler(scope, '#make-backup', async () => {
        const result = await filePath(path, 'backup_create');
        notice(result.message);
        if (activeView(epoch, base)) await route();
    });
    let sequence = 0;
    actionHandler(scope, '[data-backup-browse]', async button => {
        const name = backups[Number(button.dataset.backupBrowse)].name;
        const browser = $('#backup-browser');
        const selected = ++sequence;
        const stillOpen = () => activeView(epoch, base) && selected === sequence;
        browser.hidden = false;
        await browseBackup(path, name, browser, stillOpen);
    });
    actionHandler(scope, '[data-backup-download]', async button => {
        const name = backups[Number(button.dataset.backupDownload)].name;
        downloadBlob(new Blob(await readLargeFile(path, 'backup_read', name), {type: 'application/zip'}), name);
    });
    actionHandler(scope, '[data-backup-restore]', async button => {
        const name = backups[Number(button.dataset.backupRestore)].name;
        const destination = prompt('New restore folder relative to public_html', 'restored-site');
        if (destination) notice((await filePath(path, 'backup_restore', {path: name, destination})).message);
    });
    actionHandler(scope, '[data-backup-delete]', async button => {
        const name = backups[Number(button.dataset.backupDelete)].name;
        if (!await confirmed(`Permanently delete ${name}?`)) return;
        notice((await filePath(path, 'backup_delete', {path: name})).message);
        if (activeView(epoch, base)) await route();
    });
}

async function browseBackup(path, name, panel, stillOpen) {
    panel.innerHTML = `<h2>Backup contents</h2><p><code>${esc(name)}</code></p>
        <form id="backup-search"><label>Find a file<input type="search" name="query" maxlength="120"></label>
        <button type="submit">Search</button></form>
        <button id="backup-verify" class="subtle" disabled>Verify archive</button>
        <p id="backup-status" role="status"></p><div id="backup-files"></div><div id="backup-destination"></div>`;
    const status = $('#backup-status');
    let revision = '';
    let query = '';
    let offset = 0;
    let generation = 0;
    async function load() {
        const request = ++generation;
        const verify = $('#backup-verify');
        const listing = $('#backup-files');
        const restore = $('#backup-destination');
        listing.innerHTML = '';
        restore.innerHTML = '';
        verify.disabled = true;
        status.textContent = 'Loading files…';
        let data;
        try {
            data = await filePath(path, 'backup_contents', {path: name, query, offset, revision});
        } catch (error) {
            if (stillOpen() && request === generation) status.textContent = error.message;
            return;
        }
        if (!stillOpen() || request !== generation) return;
        revision = data.revision;
        verify.disabled = false;
        const end = offset + data.entries.length;
        status.textContent = data.entries.length ? `Files ${offset + 1}–${end} of ${data.total}` : 'No matching files.';
        listing.innerHTML = table(['File', 'Size', 'Action'], data.entries.map((item, index) => [
            esc(item.path), esc((item.size / 1024).toFixed(1) + ' KiB'),
            `<button class="subtle" data-restore-member="${index}">Restore file</button>`
        ])) + `<div class="toolbar">
            ${offset ? '<button id="backup-first" class="subtle">First page</button>' : ''}
            ${data.next_offset === null ? '' : '<button id="backup-next" class="subtle">Next page</button>'}</div>`;
        actionHandler(listing, '#backup-first', async () => { offset = 0; await load(); });
        actionHandler(listing, '#backup-next', async () => { offset = data.next_offset; await load(); });
        actionHandler(listing, '[data-restore-member]', async button => {
            const item = data.entries[Number(button.dataset.restoreMember)];
            const label = item.path.split('/').at(-1);
            restore.innerHTML = `<form id="backup-file-restore"><h3>Restore ${esc(item.path)}</h3>
                ${field('destination', 'New path under public_html', 'text', 'maxlength="2048"')}
                <p>Choose an existing destination folder and an unused file name.</p>
                <button type="submit">Restore to path</button></form>`;
            const input = $('#backup-file-restore').elements.destination;
            input.value = 'restored-' + label;
            form('#backup-file-restore', async fields => {
                const result = await filePath(path, 'backup_restore_file', {
                    path: name, member: item.path, destination: fields.destination, revision
                });
                if (stillOpen() && request === generation) {
                    status.textContent = `Restored to ${result.path}.`;
                    restore.innerHTML = '';
                }
            });
            input.focus();
        });
    }
    form('#backup-search', async fields => { query = fields.query.trim(); offset = 0; await load(); });
    actionHandler(panel, '#backup-verify', async () => {
        const request = generation;
        status.textContent = 'Checking ZIP integrity…';
        try {
            const result = await filePath(path, 'backup_verify', {path: name, revision});
            if (stillOpen() && request === generation) {
                const noun = result.files === 1 ? 'file' : 'files';
                status.textContent = `${result.message} ${result.files} ${noun} checked.`;
            }
        } catch (error) {
            if (stillOpen() && request === generation) status.textContent = error.message;
        }
    });
    await load();
    if (stillOpen()) $('#backup-search').elements.query.focus();
}

async function offsiteBackupsView(epoch) {
    const backup = await api('/offsite-backups');
    if (routeEpoch !== epoch) return;
    view('Off-site backups', 'Back up website files, managed DNS zones and enrolled databases to the encrypted repository.',
        `<section class="panel"><h2>Latest snapshot</h2><p>${esc(backup.message)}</p>
        ${backup.updated_at ? `<p>Updated ${esc(new Date(backup.updated_at * 1000).toLocaleString())}</p>` : ''}
        ${backup.state === 'running' && backup.total > 0 ? `<progress aria-label="Backup items prepared"
            value="${esc(backup.completed)}" max="${esc(backup.total)}"></progress>` : ''}
        <button id="offsite-run" ${backup.state === 'running' ? 'disabled' : ''}>Run backup</button>
        <button id="offsite-refresh" class="subtle">Refresh status</button></section>`);
    actionHandler($('#main'), '#offsite-run', async () => {
        notice((await api('/offsite-backups', {})).message);
        if (routeEpoch === epoch) await route();
    });
    $('#offsite-refresh').onclick = route;
}

async function trashView(epoch) {
    const base = boundAccount();
    const path = base + 'files';
    const items = await filePath(path, 'trash_list');
    if (!activeView(epoch, base)) return;
    view('Trash', 'Restore files and folders to a free path, or permanently delete them.',
        '<section class="panel">' + table(['Original path', 'Actions'], items.map((item, index) => [
            esc(item.path), `<button class="subtle" data-trash-restore="${index}">Restore</button>
             <button class="subtle" data-trash-delete="${index}">Delete permanently</button>`
        ])) + '</section>');
    const scope = $('#main');
    actionHandler(scope, '[data-trash-restore]', async button => {
        const item = items[Number(button.dataset.trashRestore)];
        chooseFileTarget(path, 'Restore from Trash', parentFilePath(item.path), leafFileName(item.path),
            'Restore entry', async destination => {
                notice((await filePath(path, 'trash_restore', {id: item.id, destination})).message);
                if (activeView(epoch, base)) await route();
            });
    });
    actionHandler(scope, '[data-trash-delete]', async button => {
        const item = items[Number(button.dataset.trashDelete)];
        if (!await confirmed(`Permanently delete ${item.path}?`)) return;
        notice((await filePath(path, 'trash_purge', {id: item.id})).message);
        if (activeView(epoch, base)) await route();
    });
}

async function databaseView(epoch) {
    const base = boundAccount();
    const path = base + 'databases';
    const data = await api(path);
    if (!activeView(epoch, base)) return;
    const engines = data.engines.map(engine => `<option value="${esc(engine)}">${esc(engine)}</option>`).join('');
    view('Databases', 'Each database has its own login. Use the displayed connection details in apps on this server.',
        '<section class="panel">' +
        (data.databases.length ? table(['Label', 'Engine', 'Database and user', 'Host', 'Actions'],
            data.databases.map((item, index) => [esc(item.label), esc(item.engine),
                `<code>${esc(item.database)}</code>`, esc(`${item.host}:${item.database_port}`),
                `<button class="subtle" data-db-size="${index}">Size</button>
                 <button class="subtle" data-db-reset="${index}">Reset password</button>
                 <button class="subtle" data-db-transfer="${index}">Import / Export</button>
                 <button class="subtle" data-db-drop="${index}">Delete</button>`])) : '<p>No databases yet.</p>') +
        (engines ? `<form id="database-form"><h2>Create database</h2>
          <label>Engine<select name="engine">${engines}</select></label>
          ${field('label', 'Label', 'text', 'maxlength="24" pattern="[a-z][a-z0-9]{0,23}"')}
          <p class="muted">${data.databases.length} of ${data.limit} databases. The password is generated when you create it.</p>
          <button type="submit">Create database</button></form>`
            : '<p>A server administrator needs to enable a database engine.</p>') +
        '<div id="database-credential" role="status" hidden></div><div id="database-transfer"></div></section>');
    const scope = $('#main');
    function credential(item) {
        const output = $('#database-credential');
        output.hidden = false;
        output.innerHTML = `<h2>Save these connection details</h2>
            <p><strong>Database and user</strong> <code>${esc(item.database)}</code></p>
            <p><strong>Host</strong> <code>${esc(`${item.host}:${item.database_port}`)}</code></p>
            <label>Password<input readonly id="database-secret" autocomplete="off"></label>
            <button id="database-done" class="subtle">Done</button>`;
        $('#database-secret').value = item.password;
        $('#database-done').onclick = route;
    }
    if (engines) form('#database-form', async fields => {
        const result = await api(path, {action: 'create', ...fields});
        if (activeView(epoch, base)) credential(result);
    });
    actionHandler(scope, '[data-db-size]', async button => {
        const label = data.databases[Number(button.dataset.dbSize)].label;
        const usage = await api(path, {action: 'usage', label});
        notice(`${label} uses ${(usage.bytes / 1024).toFixed(1)} KiB.`);
    });
    actionHandler(scope, '[data-db-reset]', async button => {
        const label = data.databases[Number(button.dataset.dbReset)].label;
        if (!await confirmed(`Reset the password for ${label}? Apps must use the new password.`)) return;
        const result = await api(path, {action: 'password', label});
        if (activeView(epoch, base)) credential(result);
    });
    actionHandler(scope, '[data-db-transfer]', async button => {
        const item = data.databases[Number(button.dataset.dbTransfer)];
        const container = $('#database-transfer');
        const extension = item.engine === 'mariadb' ? '.sql' : '.pgdump';
        container.innerHTML = `<h2>Transfer ${esc(item.label)}</h2><form id="sql-transfer">
            ${field('password', 'Database password', 'password', 'autocomplete="off"')}
            <label>Import file (up to 1 MiB)<input type="file" name="dump" accept="${extension}"></label>
            <button type="submit">Download export</button><button type="button" id="sql-import" class="subtle">Import into database</button></form>`;
        const editor = $('#sql-transfer');
        form('#sql-transfer', async fields => {
            const result = await api(path, {action: 'export', label: item.label, password: fields.password});
            editor.elements.password.value = '';
            const chunks = [];
            let offset = 0;
            let revision = '';
            try {
                while (true) {
                    const chunk = await api(path, {action: 'download', file: result.file, offset, revision});
                    const bytes = Uint8Array.from(atob(chunk.content), char => char.charCodeAt(0));
                    chunks.push(bytes);
                    offset += bytes.length;
                    revision = chunk.revision;
                    if (chunk.done) break;
                    if (!bytes.length || offset > 64 * 1024 * 1024) throw Error('Export exceeded the download limit.');
                }
                downloadBlob(new Blob(chunks), item.label + extension);
            } finally {
                await api(path, {action: 'export_delete', file: result.file});
            }
        });
        actionHandler(container, '#sql-import', async () => {
            const file = editor.elements.dump.files[0];
            if (!file || file.size > 1048576) throw Error('Choose a dump of up to 1 MiB.');
            const confirm = prompt(`Import statements into ${item.label}. Type the label to confirm.`);
            if (confirm !== item.label) return;
            const password = editor.elements.password.value;
            if (!password) throw Error('Supply the database password.');
            editor.elements.password.value = '';
            const content = bytesToBase64(new Uint8Array(await file.arrayBuffer()));
            notice((await api(path, {action: 'import', label: item.label, password, confirm, content})).message);
        });
        editor.elements.password.focus();
    });
    actionHandler(scope, '[data-db-drop]', async button => {
        const label = data.databases[Number(button.dataset.dbDrop)].label;
        const confirmation = prompt(`Type ${label} to delete its database and login permanently.`);
        if (confirmation !== label) return;
        notice((await api(path, {action: 'delete', label, confirm: confirmation})).message);
        if (activeView(epoch, base)) await route();
    });
}

async function domainsView(epoch) {
    const base = boundAccount();
    const [inventory, managed] = await Promise.all([api(base + 'domains'), api(base + 'tls')]);
    if (!activeView(epoch, base)) return;
    const sites = new Map(managed.sites.map(item => [item.name, item]));
    const rows = inventory.map((item, index) => {
        const site = sites.get(item.name);
        const kind = site?.kind || 'site';
        const canEdit = item.state === 'active' && site;
        const target = kind === 'site' ? 'public_html' + (site?.root ? '/' + site.root : '') : site?.target;
        return [esc(item.name) + (item.name === managed.primary ? ' · Primary' : ''), esc(item.state) + (item.dns_verified ? ' · DNS verified' : ''),
            esc(target || '—'), (canEdit ? `<button class="subtle" data-site-edit="${index}">Edit</button>
                ${kind === 'site' && managed.primary !== item.name ? `<button class="subtle" data-site-primary="${index}">Set primary</button>` : ''}` : '') +
                (['active', 'failed'].includes(item.state) ? `<button class="subtle" data-site-remove="${index}">Remove</button>` : '')];
    });
    view('Domains', 'Create a website, alias, or redirect. Create a document root folder in File Manager first.',
        '<section class="panel">' + table(['Domain', 'State', 'Document root or target', 'Actions'], rows) +
        `<form id="site-form"><h2 id="site-form-title">Add domain</h2>
        ${field('domain', 'Domain name')}
        <label>Type<select name="kind"><option value="site">Website</option><option value="alias">Alias to this account’s website</option><option value="redirect">Redirect</option></select></label>
        <label id="site-root">Document root inside public_html<input name="root" placeholder="Leave blank for public_html"></label>
        <label id="site-target" hidden>Target hostname or redirect URL<input name="target"></label>
        <button type="submit">Save domain</button><button type="button" id="new-site" class="subtle">Add another domain</button>
        <div class="toolbar"><button id="domain-challenge" type="button" class="subtle">Get DNS verification record</button>
        <button id="domain-verify" type="button" class="subtle">Verify DNS</button></div><div id="domain-proof" role="status"></div>
        </form></section>`);
    const scope = $('#main');
    const editor = $('#site-form');
    const fields = editor.elements;
    const showFields = () => {
        $('#site-root').hidden = fields.kind.value !== 'site';
        $('#site-target').hidden = fields.kind.value === 'site';
        fields.target.required = fields.kind.value !== 'site';
    };
    fields.kind.onchange = showFields;
    $('#new-site').onclick = () => {
        editor.reset();
        fields.domain.readOnly = false;
        $('#site-form-title').textContent = 'Add domain';
        showFields();
        fields.domain.focus();
    };
    actionHandler(scope, '#domain-challenge', async () => {
        const proof = await api(base + 'domains', {action: 'challenge', domain: fields.domain.value});
        if (!activeView(epoch, base)) return;
        const box = $('#domain-proof');
        box.textContent = `Add TXT record ${proof.name} with value ${proof.value}. Then click Verify DNS.`;
    });
    actionHandler(scope, '#domain-verify', async () => {
        const result = await api(base + 'domains', {action: 'verify', domain: fields.domain.value});
        if (activeView(epoch, base)) $('#domain-proof').textContent = result.message;
    });
    actionHandler(scope, '[data-site-edit]', async button => {
        const item = inventory[Number(button.dataset.siteEdit)];
        const site = sites.get(item.name);
        fields.domain.value = item.name;
        fields.domain.readOnly = true;
        fields.kind.value = site.kind || 'site';
        fields.root.value = site.root || '';
        fields.target.value = site.target || '';
        $('#site-form-title').textContent = 'Edit ' + item.name;
        showFields();
        fields.kind.focus();
    });
    form('#site-form', async body => {
        await api(base + 'domains', {action: fields.domain.readOnly ? 'edit' : 'create', ...body});
        if (activeView(epoch, base)) location.hash = 'jobs';
    });
    actionHandler(scope, '[data-site-primary]', async button => {
        await api(base + 'domains', {action: 'primary', domain: inventory[Number(button.dataset.sitePrimary)].name});
        if (activeView(epoch, base)) location.hash = 'jobs';
    });
    actionHandler(scope, '[data-site-remove]', async button => {
        const domain = inventory[Number(button.dataset.siteRemove)].name;
        const confirm = prompt(`Type ${domain} to remove its website configuration. Files remain in File Manager.`);
        if (confirm !== domain) return;
        await api(base + 'domains', {action: 'remove', domain, confirm});
        if (activeView(epoch, base)) location.hash = 'jobs';
    });
}

async function tlsView(epoch) {
    const base = boundAccount();
    const path = base + 'tls';
    const data = await api(path);
    if (!activeView(epoch, base)) return;
    const options = data.sites.map(item => `<option>${esc(item.name)}</option>`).join('');
    const status = data.sites.map((item, index) => [
        esc(item.name), esc(item.certificate.state),
        esc(item.certificate.days_remaining === undefined ? '—' : item.certificate.days_remaining),
        item.tls ? `<button class="subtle" data-https="${index}">${item.force_https ? 'Disable' : 'Enable'} HTTPS redirect</button>` : '—'
    ]);
    view('SSL/TLS', 'Manage public website certificates. HTTP validation needs a reachable domain pointing at this server.',
        '<section class="panel">' + table(['Domain', 'Certificate', 'Days left', 'Redirect'], status) +
        (!options ? '<p>Create a domain first.</p>' :
            (data.acme_available ? `<form id="acme-form"><h2>Issue a Let’s Encrypt certificate</h2>
              <label>Domain<select name="domain">${options}</select></label>${field('email', 'Contact email', 'email')}
              <label><input name="agree" type="checkbox" required>I agree to the Let’s Encrypt Subscriber Agreement.</label>
              <p><a href="https://letsencrypt.org/repository/" target="_blank" rel="noopener">Subscriber Agreement</a></p>
              <button type="submit">Queue issuance</button></form>`
                : '<p>Install Certbot on the server to enable Let’s Encrypt issuance.</p>') +
            `<form id="custom-tls"><h2>Install a certificate</h2><label>Domain<select name="domain">${options}</select></label>
            <label>PEM certificate chain<textarea name="certificate" maxlength="60000" required></textarea></label>
            <label>Unencrypted PEM private key<textarea name="key" maxlength="12000" required autocomplete="off" spellcheck="false"></textarea></label>
            <button type="submit">Install certificate</button></form>`) + '</section>');
    if ($('#acme-form')) form('#acme-form', async fields => {
        await api(path, {action: 'issue', domain: fields.domain, email: fields.email, agree: fields.agree === 'on'});
        if (activeView(epoch, base)) location.hash = 'jobs';
    });
    if ($('#custom-tls')) form('#custom-tls', async fields => {
        notice((await api(path, {action: 'upload', ...fields})).message);
        if (activeView(epoch, base)) await route();
    });
    actionHandler($('#main'), '[data-https]', async button => {
        const item = data.sites[Number(button.dataset.https)];
        notice((await api(path, {action: 'redirect', domain: item.name, enabled: !item.force_https})).message);
        if (activeView(epoch, base)) await route();
    });
}

const recordTypes = ['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'SRV', 'CAA'];

async function dnsView(epoch) {
    const base = boundAccount();
    const domains = (await api(base + 'domains')).filter(item => item.state === 'active');
    if (!activeView(epoch, base)) return;
    view('Zone Editor', 'Manage authoritative forward DNS for hosted domains.',
        '<section class="panel">' + (domains.length ?
            `<label>Domain<select id="zone-domain">${domains.map(item => `<option>${esc(item.name)}</option>`).join('')}</select></label><div id="zone-content"></div>`
            : '<p>Create a domain first.</p>') + '</section>');
    if (!domains.length) return;
    const select = $('#zone-domain');
    async function load() {
        const host = select.value;
        const path = base + 'dns';
        const value = await api(path + '?domain=' + encodeURIComponent(host));
        if (!activeView(epoch, base) || select.value !== host) return;
        const content = $('#zone-content');
        if (!value.available) {
            content.textContent = 'Managed DNS must first be enabled on the server.';
            return;
        }
        let records = value.records;
        function render() {
            content.innerHTML = `<p>Nameservers ${esc(value.nameservers.join(', '))}</p>
                <p class="muted">Record names are relative to this zone. Use @ for the domain itself.</p>` +
                table(['Name', 'Type', 'TTL', 'Data', ''], records.map((record, index) => [
                    esc(record.name), esc(record.type), esc(record.ttl), esc([
                        record.priority, record.weight, record.port, record.flag, record.tag, record.value
                    ].filter(x => x !== undefined).join(' ')),
                    `<button class="subtle" data-zone-remove="${index}">Remove</button>`
                ])) + `<form id="zone-record"><label>Type<select name="type">${recordTypes.map(type => `<option>${type}</option>`).join('')}</select></label>
                ${field('name', 'Name', 'text', 'value="@"')}${field('ttl', 'TTL', 'number', 'value="3600" min="60" max="604800"')}
                ${field('value', 'Record value')}
                <div id="zone-extras"></div><button type="submit">Add record to draft</button></form>
                <div class="toolbar"><button id="zone-save">Validate and publish</button>
                <button id="zone-export" class="subtle">Export JSON</button>
                <label>Import JSON<input type="file" id="zone-import" accept=".json,application/json"></label>
                ${value.active ? '<button id="zone-drop" class="subtle">Delete zone</button>' : ''}</div>`;
            function extras() {
                const kind = $('#zone-record').elements.type.value;
                $('#zone-extras').innerHTML = (['MX', 'SRV'].includes(kind) ? field('priority', 'Priority', 'number', 'value="10" min="0" max="65535"') : '') +
                    (kind === 'SRV' ? field('weight', 'Weight', 'number', 'value="0" min="0" max="65535"') +
                        field('port', 'Port', 'number', 'value="443" min="0" max="65535"') : '') +
                    (kind === 'CAA' ? field('flag', 'Flags', 'number', 'value="0" min="0" max="255"') +
                        '<label>Tag<select name="tag"><option>issue</option><option>issuewild</option><option>iodef</option></select></label>' : '');
            }
            $('#zone-record').elements.type.onchange = extras;
            extras();
            form('#zone-record', async fields => {
                for (const key of ['ttl', 'weight', 'priority', 'port', 'flag']) {
                    if (key in fields) fields[key] = Number(fields[key]);
                }
                if (records.length >= 100) throw Error('A zone can contain up to 100 managed records.');
                records.push(fields);
                render();
            });
            actionHandler(content, '[data-zone-remove]', async button => {
                records.splice(Number(button.dataset.zoneRemove), 1);
                render();
            });
            actionHandler(content, '#zone-save', async () => {
                notice((await api(path, {action: 'save', domain: host, records})).message);
                await load();
            });
            actionHandler(content, '#zone-export', async () => {
                downloadBlob(new Blob([JSON.stringify(records, null, 2)], {type: 'application/json'}), host + '.json');
            });
            $('#zone-import').onchange = async event => {
                try {
                    const file = event.target.files[0];
                    if (!file || file.size > 100000) throw Error('Choose a JSON file below 100 KB.');
                    const input = JSON.parse(await file.text());
                    let draft = input;
                    if (!Array.isArray(input)) {
                        if (!input || input.format !== 1 || input.domain !== host) {
                            throw Error('Select the domain named in this DNS backup.');
                        }
                        draft = input.records;
                    }
                    if (!Array.isArray(draft) || draft.length > 100 || draft.some(item => !item || typeof item !== 'object')) {
                        throw Error('Choose a JSON export with up to 100 records.');
                    }
                    records = draft;
                    render();
                    notice('Records loaded into the draft. Review them before publishing.');
                } catch (error) { notice(error.message); }
            };
            actionHandler(content, '#zone-drop', async () => {
                const confirm = prompt(`Type ${host} to remove its DNS zone.`);
                if (confirm !== host) return;
                notice((await api(path, {action: 'remove', domain: host, confirm})).message);
                await load();
            });
        }
        render();
    }
    select.onchange = () => load().catch(error => notice(error.message));
    await load();
}

function bytesToBase64(bytes) {
    let binary = '';
    for (let offset = 0; offset < bytes.length; offset += 4096) {
        binary += String.fromCharCode(...bytes.subarray(offset, offset + 4096));
    }
    return btoa(binary);
}

function gitView(epoch) {
    const base = boundAccount();
    view('Git Deployment', 'Fetch a public GitHub, GitLab or Bitbucket branch into a new folder. Point a domain to that folder when you are ready.',
        `<section class="panel"><form id="git-release-form">
        ${field('repository', 'Public HTTPS repository URL', 'url', 'maxlength="350"')}
        ${field('branch', 'Branch', 'text', 'value="main" maxlength="128"')}
        ${field('destination', 'New folder under public_html', 'text', 'placeholder="releases/site-v1"')}
        <button type="submit">Stage source</button></form></section>`);
    form('#git-release-form', async fields => {
        await api(base + 'git', fields);
        if (activeView(epoch, base)) location.hash = 'jobs';
    });
}

async function metricsView(epoch) {
    const base = boundAccount();
    const path = base + 'metrics';
    const [processes, domains] = await Promise.all([api(path), api(base + 'domains')]);
    if (!activeView(epoch, base)) return;
    view('Metrics', 'View account processes and activity from managed Nginx site logs.',
        `<section class="panel"><h2>Account processes</h2><p>${esc(processes.process_count)} running processes ·
          ${esc((processes.process_rss / 1048576).toFixed(1))} MiB total RSS</p>` +
        table(['PID', 'Process', 'Lifetime CPU', 'Resident memory'], processes.processes.map(process => [
            esc(process.pid), esc(process.name), esc(process.cpu_lifetime_percent + '%'), esc((process.rss / 1048576).toFixed(1) + ' MiB')
        ])) + '</section>' +
        `<section class="panel"><h2>Website activity</h2><label>Website<select id="metrics-domain">
        <option value="">Choose a domain</option>${domains.filter(item => item.state === 'active').map(item => `<option>${esc(item.name)}</option>`).join('')}
        </select></label><div id="site-activity"></div></section>`);
    const select = $('#metrics-domain');
    select.onchange = async () => {
        const domain = select.value;
        if (!domain) { $('#site-activity').replaceChildren(); return; }
        try {
            const sample = await api(path + '?domain=' + encodeURIComponent(domain));
            if (!activeView(epoch, base) || select.value !== domain) return;
            $('#site-activity').innerHTML = `<p>${esc(sample.requests)} requests · ${esc(sample.errors)} error responses ·
                ${esc((sample.bytes / 1024).toFixed(1))} KiB transferred in the available log sample</p>` +
                table(['Time', 'Method', 'Path', 'Status', 'Bytes', 'Client'], sample.latest.map(item =>
                    [item.time, item.method, item.path, item.status, item.bytes, item.client].map(esc))) +
                (sample.truncated ? '<p>Only the newest 512 KiB of the current log were scanned.</p>' : '');
        } catch (error) { notice(error.message); }
    };
}

async function wordpressView(epoch) {
    const base = boundAccount();
    const [domains, databases] = await Promise.all([api(base + 'tls'), api(base + 'databases')]);
    if (!activeView(epoch, base)) return;
    const sites = domains.sites.filter(site => (!site.kind || site.kind === 'site') &&
        ['active', 'expiring'].includes(site.certificate.state));
    const sql = databases.databases.filter(item => item.engine === 'mariadb');
    view('WordPress', 'Install WordPress into a new folder using an empty MariaDB database and an HTTPS domain.',
        '<section class="panel">' + (sites.length && sql.length ? `<form id="wordpress-form">
            <label>Website<select name="domain">${sites.map(site => `<option>${esc(site.name)}</option>`).join('')}</select></label>
            <label>Database<select name="label">${sql.map(item => `<option>${esc(item.label)}</option>`).join('')}</select></label>
            ${field('db_password', 'Database password', 'password', 'autocomplete="off"')}
            ${field('destination', 'New folder under public_html', 'text', 'placeholder="wordpress"')}
            ${field('title', 'Site title', 'text', 'maxlength="120"')}
            ${field('username', 'WordPress administrator username', 'text', 'maxlength="40"')}
            ${field('email', 'WordPress administrator email', 'email')}
            ${field('password', 'WordPress administrator password', 'password', 'autocomplete="new-password" minlength="16" maxlength="128"')}
            <label><input type="checkbox" required>Switch the domain to the new WordPress folder after installation.</label>
            <button type="submit">Install WordPress</button></form><p id="wordpress-result" role="status"></p>`
            : '<p>Add a certificate under <a href="#tls">SSL/TLS</a> and create an empty MariaDB database under <a href="#databases">Databases</a> to install WordPress.</p>') + '</section>');
    if ($('#wordpress-form')) form('#wordpress-form', async fields => {
        const result = await api(base + 'wordpress', fields);
        if (!activeView(epoch, base)) return;
        $('#wordpress-form').reset();
        const resultBox = $('#wordpress-result');
        const link = document.createElement('a');
        link.href = result.url;
        link.textContent = 'Open WordPress administration';
        link.target = '_blank';
        link.rel = 'noopener';
        resultBox.append(result.message + ' ', link);
    });
}

async function preferencesView(epoch) {
    const [mfa, profile] = await Promise.all([api('/mfa'), api('/profile')]);
    if (routeEpoch !== epoch) return;
    view('Preferences', 'Manage your profile and account security.',
        `<section class="panel"><h2>Contact information</h2><form id="profile-form">
        <label>Display name<input name="display_name" maxlength="80" value="${esc(profile.display_name)}"></label>
        <label>Email<input name="email" type="email" maxlength="254" value="${esc(profile.email)}"></label>
        <button type="submit">Save contact information</button></form></section>
        <section class="panel"><h2>Change password</h2><form id="password-form">
        ${field('current', 'Current password', 'password', 'autocomplete="current-password"')}
        ${field('password', 'New password', 'password', 'minlength="14" maxlength="128" autocomplete="new-password"')}
        <button type="submit">Change password</button></form></section>
        <section class="panel"><h2>Two-factor authentication</h2>
        <p>${mfa.enabled ? 'Enabled · ' + esc(mfa.recovery_codes_left) + ' unused recovery codes' : 'Disabled'}</p>
        <form id="mfa-form">${field('password', 'Current password', 'password', 'autocomplete="current-password"')}
        ${mfa.enabled ? field('code', 'Authenticator or recovery code', 'text', 'maxlength="16" autocomplete="one-time-code"') : ''}
        <button type="submit">${mfa.enabled ? 'Disable two-factor authentication' : 'Set up authenticator'}</button></form>
        <div id="mfa-enroll"></div></section>`);
    form('#profile-form', async fields => notice((await api('/profile', fields)).message));
    form('#password-form', async fields => {
        notice((await api('/password', fields)).message);
        await boot();
    });
    form('#mfa-form', async fields => {
        if (mfa.enabled) {
            if (!await confirmed('Disable two-factor authentication and revoke all sessions and API tokens?')) return;
            notice((await api('/mfa', {action: 'disable', ...fields})).message);
            await boot();
            return;
        }
        const setup = await api('/mfa', {action: 'begin', password: fields.password});
        if (routeEpoch !== epoch) return;
        $('#mfa-form').reset();
        $('#mfa-enroll').innerHTML = `<p>In your authenticator, add a time-based account with this setup key.</p>
            <p><code>${esc(setup.secret)}</code></p><form id="mfa-confirm">
            ${field('password', 'Current password', 'password', 'autocomplete="current-password"')}
            ${field('code', 'Six-digit code', 'text', 'pattern="[0-9]{6}" inputmode="numeric" autocomplete="one-time-code"')}
            <button type="submit">Enable and show recovery codes</button></form>`;
        form('#mfa-confirm', async confirmation => {
            const enabled = await api('/mfa', {action: 'confirm', ...confirmation});
            if (routeEpoch !== epoch) return;
            $('#mfa-form').remove();
            $('#mfa-enroll').innerHTML = '<p>Save these single-use codes before signing in again.</p><pre></pre><button id="mfa-done">Sign in again</button>';
            $('#mfa-enroll pre').textContent = enabled.recovery_codes.join('\n');
            $('#mfa-done').onclick = boot;
        });
    });
}

async function tokensView(epoch) {
    const [tokens, mfa] = await Promise.all([api('/tokens'), api('/mfa')]);
    if (routeEpoch !== epoch) return;
    view('API Tokens', 'Tokens can read your authorized account inventory, domains and metrics. Tokens expire after 90 days.',
        '<section class="panel">' + table(['Label', 'Expires', ''], tokens.map((token, index) => [
            esc(token.label), esc(new Date(token.expires * 1000).toLocaleDateString()),
            `<button class="subtle" data-token-revoke="${index}">Revoke</button>`
        ])) + `<form id="token-form"><h2>Create read-only token</h2>
        ${field('label', 'Label', 'text', 'maxlength="60"')}${field('password', 'Current password', 'password', 'autocomplete="current-password"')}
        ${mfa.enabled ? field('code', 'Authenticator code', 'text', 'maxlength="16" autocomplete="one-time-code"') : ''}
        <button type="submit">Create token</button></form><div id="token-confirmation" hidden></div></section>`);
    form('#token-form', async fields => {
        const result = await api('/tokens', {action: 'create', ...fields});
        if (routeEpoch !== epoch) return;
        $('#token-form').reset();
        $('#token-confirmation').hidden = false;
        $('#token-confirmation').innerHTML = '<label>Save this token now<input readonly autocomplete="off"></label><button id="token-done" class="subtle">Done</button>';
        $('#token-confirmation input').value = result.token;
        $('#token-done').onclick = route;
    });
    actionHandler($('#main'), '[data-token-revoke]', async button => {
        const token = tokens[Number(button.dataset.tokenRevoke)];
        if (!await confirmed(`Revoke ${token.label}?`)) return;
        notice((await api('/tokens', {action: 'revoke', id: token.id})).message);
        if (routeEpoch === epoch) await route();
    });
}

async function phpView(epoch) {
    const base = boundAccount();
    const path = base + 'php';
    const data = await api(path);
    if (!activeView(epoch, base)) return;
    const settings = data.settings;
    view('PHP Settings', 'These settings apply to all sites using this account’s PHP-FPM pool.',
        `<section class="panel"><p>PHP ${esc(data.version)}</p><form id="php-settings">
        ${field('memory_mib', 'Memory limit (MiB)', 'number', 'min="32" max="192" value="' + esc(settings.memory_mib) + '"')}
        ${field('upload_mib', 'Upload limit (MiB)', 'number', 'min="1" max="32" value="' + esc(settings.upload_mib) + '"')}
        ${field('execution_seconds', 'Execution time (seconds)', 'number', 'min="5" max="60" value="' + esc(settings.execution_seconds) + '"')}
        <label><input type="checkbox" name="show_errors" ${settings.show_errors ? 'checked' : ''}> Show PHP errors to site visitors</label>
        <button type="submit">Save PHP settings</button></form></section>
        <section class="panel"><h2>PHP error log</h2><button class="subtle" id="php-log">Load recent errors</button><pre id="php-log-output" class="hosting-log"></pre></section>`);
    form('#php-settings', async fields => {
        const body = {
            memory_mib: Number(fields.memory_mib), upload_mib: Number(fields.upload_mib),
            execution_seconds: Number(fields.execution_seconds), show_errors: fields.show_errors === 'on'
        };
        notice((await api(path, body)).message);
        if (activeView(epoch, base)) await route();
    });
    actionHandler($('#main'), '#php-log', async () => {
        const log = await api(path + '?view=log');
        if (activeView(epoch, base)) $('#php-log-output').textContent = log.lines.join('\n') || 'No recent PHP errors.';
    });
}

async function cronView(epoch) {
    const base = boundAccount();
    const path = base + 'cron';
    const jobs = await api(path);
    if (!activeView(epoch, base)) return;
    view('Cron Jobs', 'Run a PHP script from public_html at a scheduled interval. Review outcomes in Operation History.',
        '<section class="panel">' + table(['Script', 'Interval', 'Next due', ''], jobs.map((job, index) => [
            esc(job.path), esc(job.interval_minutes + ' min'), esc(new Date(job.next_run * 1000).toLocaleString()),
            `<button class="subtle" data-cron-remove="${index}">Remove schedule</button>`
        ])) + `<form id="cron-form"><h2>Schedule a PHP script</h2>
        ${field('path', 'Script path inside public_html', 'text', 'placeholder="tasks/report.php"')}
        <label>Interval<select name="interval_minutes"><option value="15">15 minutes</option>
        <option value="30">30 minutes</option><option value="60">Hourly</option><option value="360">6 hours</option>
        <option value="1440">Daily</option></select></label><button type="submit">Schedule script</button></form></section>`);
    form('#cron-form', async fields => {
        notice((await api(path, {action: 'save', path: fields.path, interval_minutes: Number(fields.interval_minutes)})).message);
        if (activeView(epoch, base)) await route();
    });
    actionHandler($('#main'), '[data-cron-remove]', async button => {
        const item = jobs[Number(button.dataset.cronRemove)];
        if (!await confirmed(`Remove the schedule for ${item.path}?`)) return;
        notice((await api(path, {action: 'delete', id: item.id})).message);
        if (activeView(epoch, base)) await route();
    });
}

async function siteSecurityView(epoch) {
    const base = boundAccount();
    const domains = (await api(base + 'tls')).sites.filter(site => !site.kind || site.kind === 'site');
    if (!activeView(epoch, base)) return;
    view('Website Security', 'Manage HTTPS directory passwords and site-level visitor IP rules.',
        '<section class="panel">' + (domains.length ?
            `<label>Website<select id="protected-site">${domains.map(item => `<option>${esc(item.name)}</option>`).join('')}</select></label>
            <div id="site-controls"></div>` : '<p>Create a website first.</p>') + '</section>');
    if (!domains.length) return;
    const select = $('#protected-site');
    const endpoint = base + 'site-security';
    async function load() {
        const domain = select.value;
        const data = await api(endpoint + '?domain=' + encodeURIComponent(domain));
        if (!activeView(epoch, base) || select.value !== domain) return;
        const controls = $('#site-controls');
        controls.innerHTML = `<h2>Directory Privacy</h2>` +
            table(['Directory', 'Username', ''], data.privacy.map((item, index) => [
                esc(item.path), esc(item.username), `<button class="subtle" data-remove-privacy="${index}">Remove protection</button>`
            ])) + (data.tls ? `<form id="privacy-form">${field('path', 'URL directory (/ for entire site)', 'text', 'placeholder="/private"')}
            ${field('username', 'Directory username', 'text', 'maxlength="32"')}
            ${field('password', 'Directory password', 'password', 'minlength="16" maxlength="128" autocomplete="new-password"')}
            <button type="submit">Save protection</button></form>` : '<p>Install a website certificate to enable directory passwords.</p>') +
            `<form id="site-ips"><h2>IP Blocker</h2><label>One IP or CIDR network per line<textarea name="addresses" rows="5">${esc(data.blocked.join('\n'))}</textarea></label>
            <button type="submit">Save IP blocklist</button></form>`;
        if (data.tls) form('#privacy-form', async fields => {
            notice((await api(endpoint, {action: 'set', domain, ...fields})).message);
            await load();
        });
        form('#site-ips', async fields => {
            const addresses = fields.addresses.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
            notice((await api(endpoint, {action: 'blocklist', domain, addresses})).message);
            await load();
        });
        actionHandler(controls, '[data-remove-privacy]', async button => {
            const item = data.privacy[Number(button.dataset.removePrivacy)];
            if (!await confirmed(`Remove password protection from ${item.path}?`)) return;
            notice((await api(endpoint, {action: 'remove', domain, path: item.path})).message);
            await load();
        });
    }
    select.onchange = () => load().catch(error => notice(error.message));
    await load();
}

async function sftpView(epoch) {
    const base = boundAccount();
    const endpoint = base + 'sftp';
    const info = await api(endpoint);
    if (!activeView(epoch, base)) return;
    const rows = info.keys.map((key, index) => [
        esc(key.label), `<code>${esc(key.fingerprint)}</code>`,
        `<button class="subtle" data-sftp-revoke="${index}">Remove key</button>`
    ]);
    view('SFTP Access', 'Use a separate key-only SFTP connection to transfer files.',
        '<section class="panel">' + (info.available ?
            `<p>Username <code>${esc(info.username)}</code> · Port ${esc(info.port)}</p>
             <p>${info.listen === '127.0.0.1' ? 'The listener is local to the server. Reach it through an SSH tunnel.' : 'Connect using this server’s hostname or IP address.'}</p>` +
            table(['Key', 'Fingerprint', ''], rows) +
            `<form id="sftp-key">
             ${field('label', 'Key label', 'text', 'maxlength="64"')}
             <label>OpenSSH Ed25519 public key<textarea name="public_key" rows="3" maxlength="1024" required placeholder="ssh-ed25519 …"></textarea></label>
             <button type="submit">Add public key</button></form>`
            : '<p>A server administrator needs to enable the separate SFTP listener.</p>') + '</section>');
    if (!info.available) return;
    form('#sftp-key', async fields => {
        notice((await api(endpoint, {action: 'add', label: fields.label, public_key: fields.public_key.trim()})).message);
        if (activeView(epoch, base)) await route();
    });
    actionHandler($('#main'), '[data-sftp-revoke]', async button => {
        const key = info.keys[Number(button.dataset.sftpRevoke)];
        if (!await confirmed(`Remove SFTP key ${key.label}?`)) return;
        notice((await api(endpoint, {action: 'remove', fingerprint: key.fingerprint})).message);
        if (activeView(epoch, base)) await route();
    });
}

async function notificationsView(epoch) {
    const notifications = await api('/notifications');
    if (routeEpoch !== epoch) return;
    view('Notifications', 'Review up to 40 recent job outcomes and dismiss those you have handled.',
        '<section class="panel">' + table(['Operation', 'Account', 'Outcome', 'Time', ''], notifications.map((item, index) => [
            esc(item.operation), esc(item.account || 'Server'), esc(item.state),
            esc(new Date((item.finished || item.created) * 1000).toLocaleString()),
            `<button class="subtle" data-dismiss-notification="${index}">Dismiss</button>`
        ])) + '<p><a href="#jobs">Open operation history</a></p></section>');
    actionHandler($('#main'), '[data-dismiss-notification]', async button => {
        const item = notifications[Number(button.dataset.dismissNotification)];
        await api('/notifications', {id: item.id});
        if (routeEpoch === epoch) await route();
    });
}

function dnsLookupView(epoch) {
    view('DNS Track', 'Check records visible to the server’s DNS resolver.',
        `<section class="panel"><form id="dns-lookup">
            ${field('domain', 'Hostname', 'text', 'placeholder="example.com" maxlength="253"')}
            <label>Record type<select name="type">${['A','AAAA','MX','NS','TXT','CAA','CNAME','SOA'].map(item => `<option>${item}</option>`).join('')}</select></label>
            <button type="submit">Look up records</button>
        </form><pre id="dns-answer" class="hosting-log" aria-live="polite"></pre></section>`);
    form('#dns-lookup', async fields => {
        const result = await api('/dns-lookup?' + new URLSearchParams(fields));
        if (routeEpoch === epoch) {
            $('#dns-answer').textContent = result.answer.join('\n') || 'No records in the answer section.';
        }
    });
}

async function mailView(epoch) {
    const base = boundAccount();
    const path = base + 'mail';
    const info = await api(path);
    if (!activeView(epoch, base)) return;
    const help = 'Manage email addresses for the selected hosting account.';
    if (!info.available) {
        view('Email Accounts', help, '<section class="panel"><p>Ask your server administrator to enable Postfix and Dovecot.</p></section>');
        return;
    }
    const domains = await api(base + 'domains');
    if (!activeView(epoch, base)) return;
    const inactive = domains.filter(item => item.state === 'active' && item.name !== info.hostname &&
        !info.domains.includes(item.name) && (me.role === 'admin' || item.dns_verified)).map(item => item.name);
    const options = hosts => hosts.map(host => `<option value="${esc(host)}">${esc(host)}</option>`).join('');
    const addressFields = `${field('local', 'Address name', 'text', 'maxlength="64" placeholder="hello"')}
        <label>Domain<select name="domain">${options(info.domains)}</select></label>`;
    const passwordField = field('password', 'Mailbox password', 'password', 'minlength="16" maxlength="128" autocomplete="new-password"');
    const quotaField = value => field('quota_mib', 'Mailbox quota (MiB)', 'number', `min="1" max="512" value="${esc(value)}"`);
    const mailboxRows = info.mailboxes.map((item, index) => {
        const actions = item.retired
            ? `<button class="subtle" data-mail-edit="restore" data-mailbox="${index}">Restore</button>`
            : `<button class="subtle" data-mail-edit="password" data-mailbox="${index}">Change password</button>
               <button class="subtle" data-mail-edit="quota" data-mailbox="${index}">Change quota</button>
               <button class="subtle" data-mail-toggle="${index}">${item.enabled ? 'Disable' : 'Enable'}</button>
               <button class="subtle" data-mail-archive="${index}">Archive</button>`;
        const state = item.retired ? 'Archived' : item.enabled ? 'Enabled' : 'Disabled';
        return [esc(item.address), esc(item.quota_mib + ' MiB'), state, actions];
    });
    view('Email Accounts', help, `<section class="panel"><h2>Mail client settings</h2>
        <dl><dt>Server</dt><dd><code>${esc(info.hostname)}</code></dd>
        <dt>Incoming</dt><dd>IMAP over TLS, port 993</dd>
        <dt>Outgoing</dt><dd>SMTP with STARTTLS, port 587</dd>
        <dt>Username</dt><dd>Full mailbox address</dd></dl>
        ${info.listen === 'loopback' ? '<p>Mail listeners accept only local connections. An administrator can enable external access.</p>' : ''}
        </section>
        <section class="panel"><h2>Local mail routing</h2>
        ${table(['Domain', 'Action'], info.domains.map((host, index) => [
            esc(host), `<button class="subtle" data-mail-domain="${index}">Disable local mail</button>`
        ]))}
        ${inactive.length ? `<form id="mail-domain"><label>Website domain<select name="domain">
            ${options(inactive)}</select></label><button type="submit">Enable local mail</button></form>`
            : '<p>Provision and verify a website domain in Domains to enable mail for it.</p>'}</section>
        <section class="panel"><h2>Mailboxes</h2>${table(['Address', 'Quota', 'State', 'Actions'], mailboxRows)}
        <div id="mail-edit"></div>
        ${info.domains.length ? `<form id="mail-create"><h3>New mailbox</h3>${addressFields}${passwordField}
            ${quotaField(128)}<button type="submit">Create mailbox</button></form>` : ''}</section>
        <section class="panel"><h2>Forwarders</h2>
        ${table(['Address', 'Destination', 'Action'], info.forwarders.map((item, index) => [
            esc(item.source), esc(item.target), `<button class="subtle" data-mail-forward="${index}">Remove</button>`
        ]))}
        ${info.domains.length ? `<form id="mail-forward"><h3>New or existing forwarder</h3>${addressFields}
            ${field('target', 'Destination address', 'email', 'maxlength="254"')}
            <button type="submit">Save forwarder</button></form>` : ''}</section>`);

    async function update(fields) {
        const result = await api(path, fields);
        if (!activeView(epoch, base)) return;
        notice(result.message);
        await stats();
        if (activeView(epoch, base)) await route();
    }
    if (inactive.length) form('#mail-domain', fields => update({action: 'domain', domain: fields.domain, enabled: true}));
    if (info.domains.length) {
        form('#mail-create', fields => update({action: 'create', address: fields.local + '@' + fields.domain,
            password: fields.password, quota_mib: Number(fields.quota_mib)}));
        form('#mail-forward', fields => update({action: 'forward', address: fields.local + '@' + fields.domain,
            target: fields.target}));
    }
    const scope = $('#main');
    actionHandler(scope, '[data-mail-domain]', async button => {
        const domain = info.domains[Number(button.dataset.mailDomain)];
        if (await confirmed(`Disable local mail for ${domain}?`)) await update({action: 'domain', domain, enabled: false});
    });
    actionHandler(scope, '[data-mail-edit]', button => {
        const item = info.mailboxes[Number(button.dataset.mailbox)];
        const action = button.dataset.mailEdit;
        const editingQuota = action === 'quota';
        const label = {password: 'Change password for', quota: 'Change quota for', restore: 'Restore'};
        $('#mail-edit').innerHTML = `<form id="mail-edit-form"><h3>${label[action]} ${esc(item.address)}</h3>
            ${editingQuota ? quotaField(item.quota_mib) : passwordField}<button type="submit">Save</button></form>`;
        form('#mail-edit-form', fields => update({action, address: item.address,
            ...(editingQuota ? {quota_mib: Number(fields.quota_mib)} : {password: fields.password})}));
        $('#mail-edit-form input').focus();
    });
    actionHandler(scope, '[data-mail-toggle]', async button => {
        const item = info.mailboxes[Number(button.dataset.mailToggle)];
        if (await confirmed(`${item.enabled ? 'Disable' : 'Enable'} login and delivery for ${item.address}?`)) {
            await update({action: 'state', address: item.address, enabled: !item.enabled});
        }
    });
    actionHandler(scope, '[data-mail-archive]', async button => {
        const item = info.mailboxes[Number(button.dataset.mailArchive)];
        if (await confirmed(`Archive ${item.address}? Existing messages stay on disk. New mail and logins will be denied.`)) {
            await update({action: 'retire', address: item.address, confirm: item.address});
        }
    });
    actionHandler(scope, '[data-mail-forward]', async button => {
        const item = info.forwarders[Number(button.dataset.mailForward)];
        if (await confirmed(`Remove the forwarder for ${item.source}?`)) {
            await update({action: 'unforward', address: item.source});
        }
    });
}

async function hostingAccountsView(epoch) {
    await refreshAccounts();
    const packages = await api('/packages');
    if (epoch !== routeEpoch) return;
    const canManage = me.role === 'admin' || me.role === 'reseller';
    view('Hosting accounts', 'Provision isolated Linux users and PHP-FPM pools.',
        `<section class="panel">${table(['Account', 'Package', 'State', 'Action'], accounts.map(item => {
            const stateAction = item.state === 'active' ? 'Suspend' : 'Unsuspend';
            let action = '<a href="#jobs">Review jobs</a>';
            if (canManage && item.can_retry) action = `<button data-retry-account="${item.id}">Retry setup</button>`;
            else if (canManage && ['active', 'suspended'].includes(item.state)) {
                action = `<button data-state="${item.id}">${stateAction}</button>`;
            }
            return [esc(item.name), esc(item.package), esc(item.state), action];
        }))}</section><section class="panel"><h2>Create hosting account</h2>
        ${packages.length ? `<form id="account-form">
        ${field('username', 'Username', 'text', 'pattern="[a-z][a-z0-9]{2,15}"')}
        ${field('password', 'Panel password', 'password', 'minlength="14" autocomplete="new-password"')}
        <label>Package<select name="package_id">${packages.map(item =>
            `<option value="${item.id}">${esc(item.name)}</option>`).join('')}</select></label>
        <button type="submit">Create account</button></form>` : 'Create a hosting package first.'}</section>`);
    if (packages.length) form('#account-form', async fields => {
        await api('/accounts', {...fields, package_id: Number(fields.package_id)});
        location.hash = 'jobs';
    });
    const scope = $('#main');
    actionHandler(scope, '[data-retry-account]', async button => {
        const item = accounts.find(entry => entry.id === Number(button.dataset.retryAccount));
        if (!await confirmed(`Retry setup for ${item.name}?`)) return;
        await api(`/accounts/${item.id}/retry-create`, {});
        location.hash = 'jobs';
    });
    actionHandler(scope, '[data-state]', async button => {
        const item = accounts.find(entry => entry.id === Number(button.dataset.state));
        const suspending = item.state === 'active';
        const message = suspending
            ? `Suspend ${item.name}? Existing requests and sessions may finish.`
            : `Unsuspend ${item.name}?`;
        if (!await confirmed(message)) return;
        await api(`/accounts/${item.id}/state`, {state: suspending ? 'suspended' : 'active'});
        location.hash = 'jobs';
    });
}
