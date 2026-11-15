// Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
'use strict';

const fileTransferLimit = 256 * 1024 * 1024;
let closeFileView = () => {};
let fileViewHasUnsavedChanges = () => false;
window.addEventListener('beforeunload', event => {
    if (fileViewHasUnsavedChanges()) {
        event.preventDefault();
        event.returnValue = '';
    }
});

const joinFilePath = (parent, name) => parent ? parent + '/' + name : name;
const parentFilePath = path => path.split('/').slice(0, -1).join('/');
const leafFileName = path => path.split('/').at(-1);
const browseFolder = (path, folder, hidden, offset = 0, foldersOnly = false) =>
    filePath(path, 'list_page', {path: folder, include_hidden: hidden, offset, folders_only: foldersOnly});

function fileSize(bytes) {
    const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
    let value = bytes;
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
        value /= 1024;
        unit += 1;
    }
    return value.toLocaleString(undefined, {maximumFractionDigits: unit ? 1 : 0}) + ' ' + units[unit];
}

function validateFileName(name) {
    if (!name.trim() || /^[.]{1,2}$/.test(name) || name.startsWith('.alma-') ||
        /[\u0000-\u001f/]/.test(name) || new TextEncoder().encode(name).length > 255) {
        throw Error('Enter a file or folder name without a path (up to 255 UTF-8 bytes).');
    }
    return name;
}

function folderTree(container, path, current, includeHidden, onSelect) {
    const ancestors = current.split('/').filter(Boolean);
    const expanded = new Set(['']);
    ancestors.reduce((parent, name) => {
        const next = joinFilePath(parent, name);
        expanded.add(next);
        return next;
    }, '');
    const list = document.createElement('ul');
    list.className = 'folder-tree';

    function node(parent, folder, name) {
        const item = document.createElement('li');
        item.innerHTML = '<div class="folder-node"><button type="button" class="subtle folder-toggle" aria-expanded="false">▸</button>' +
            '<button type="button" class="folder-name"></button></div><ul hidden></ul>';
        const [toggle, open] = item.querySelectorAll('button');
        const branch = item.lastElementChild;
        const label = folder ? name : 'public_html';
        open.textContent = label;
        open.title = folder || 'public_html';
        if (folder === current) open.setAttribute('aria-current', 'page');
        open.onclick = () => onSelect(folder);
        let loaded = false;

        async function load(offset = 0) {
            const progress = document.createElement('li');
            progress.textContent = 'Loading…';
            progress.setAttribute('role', 'status');
            branch.append(progress);
            try {
                const result = await browseFolder(path, folder, includeHidden, offset, true);
                progress.remove();
                if (!item.isConnected) return;
                for (const child of result.entries) node(branch, joinFilePath(folder, child.name), child.name);
                if (!result.total) {
                    const empty = document.createElement('li');
                    empty.className = 'muted';
                    empty.textContent = 'No subfolders';
                    branch.append(empty);
                }
                if (result.next_offset !== null) {
                    const more = document.createElement('li');
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.className = 'subtle';
                    button.textContent = 'More folders';
                    button.onclick = () => { more.remove(); load(result.next_offset); };
                    more.append(button);
                    branch.append(more);
                }
                loaded = true;
            } catch (error) {
                progress.textContent = error.message;
                loaded = false;
            }
        }

        function show(visible) {
            branch.hidden = !visible;
            toggle.setAttribute('aria-expanded', String(visible));
            toggle.setAttribute('aria-label', (visible ? 'Collapse ' : 'Expand ') + label);
            toggle.textContent = visible ? '▾' : '▸';
            if (visible && !loaded) {
                loaded = true;
                branch.replaceChildren();
                load();
            }
        }
        parent.append(item);
        toggle.onclick = () => show(branch.hidden);
        show(expanded.has(folder));
    }

    container.replaceChildren(list);
    node(list, '', 'public_html');
}

function fileDialog(title, content, submitLabel, run) {
    const dialog = document.createElement('dialog');
    dialog.className = 'file-dialog';
    dialog.setAttribute('aria-labelledby', 'file-dialog-title');
    dialog.innerHTML = '<form><h2 id="file-dialog-title">' + esc(title) + '</h2>' + content +
        '<p class="file-error" role="status" hidden></p><div class="actions">' +
        '<button type="button" class="subtle" data-cancel-file>Cancel</button>' +
        '<button type="submit">' + esc(submitLabel) + '</button></div></form>';
    const form = dialog.querySelector('form');
    const submit = form.querySelector('button[type=submit]');
    const cancel = form.querySelector('[data-cancel-file]');
    const error = form.querySelector('.file-error');
    cancel.onclick = () => dialog.close();
    dialog.addEventListener('close', () => dialog.remove(), {once: true});
    dialog.addEventListener('cancel', event => {
        if (submit.disabled) event.preventDefault();
    });
    form.onsubmit = async event => {
        event.preventDefault();
        if (submit.disabled) return;
        submit.disabled = cancel.disabled = true;
        error.hidden = false;
        error.textContent = 'Working…';
        try {
            await run(Object.fromEntries(new FormData(form)));
            if (dialog.open) dialog.close();
        } catch (problem) {
            error.textContent = problem.message;
        } finally {
            submit.disabled = cancel.disabled = false;
        }
    };
    $('#main').append(dialog);
    dialog.showModal();
    return form;
}

function chooseFileTarget(path, title, folder, name, submitLabel, run) {
    const content = '<label>Folder under public_html<input name="folder" placeholder="public_html" maxlength="2048" value="' +
        esc(folder) + '"></label><details><summary>Browse folders</summary><div class="file-picker"></div></details>' +
        '<label>Name<input name="filename" required maxlength="255" value="' + esc(name) + '"></label>';
    const form = fileDialog(title, content, submitLabel, fields => {
        const destination = joinFilePath(fields.folder, validateFileName(fields.filename));
        return run(destination);
    });
    form.querySelector('details').addEventListener('toggle', event => {
        if (!event.target.open) return;
        folderTree(form.querySelector('.file-picker'), path, form.elements.folder.value, true, selected => {
            form.elements.folder.value = selected;
            form.elements.folder.focus();
            event.target.open = false;
        });
    });
}

function editFileMode(entry, save) {
    const current = entry.mode.slice(-3).padStart(3, '0');
    const columns = ['Read', 'Write', 'Execute'];
    const content = '<p>' + esc(entry.name) + ' · ' + esc(entry.owner) + ' / ' + esc(entry.group) + '</p>' +
        '<p class="muted">Changing permissions can stop Nginx from reading a file or entering a folder.</p>' +
        ['Owner', 'Group', 'Others'].map((role, index) => '<fieldset class="file-mode"><legend>' + role + '</legend>' +
            columns.map((label, bit) => '<label class="file-check"><input name="permissions" type="checkbox" value="' +
                (4 >> bit) * 8 ** (2 - index) + '"' + (Number(current[index]) & (4 >> bit) ? ' checked' : '') +
                '> ' + label + '</label>').join('') + '</fieldset>').join('');
    const form = fileDialog('Change permissions', content, 'Save permissions', () => {
        const mask = new FormData(form).getAll('permissions').reduce((mode, bit) => mode + Number(bit), 0);
        return save(mask.toString(8).padStart(3, '0'));
    });
}

async function sendFileUpload(path, location, file, active, progress) {
    if (file.size > fileTransferLimit) throw Error('Files must be 256 MiB or smaller.');
    if (!active()) throw Error('Upload canceled.');
    const started = await filePath(path, 'upload_start', {path: location, size: file.size});
    const upload_id = started.upload_id;
    let published = false;
    async function retry(action, fields = {}) {
        for (let attempt = 0; ; attempt += 1) {
            if (!active()) throw Error('Upload canceled.');
            try { return await filePath(path, action, {upload_id, ...fields}); }
            catch (error) {
                if (attempt >= 2 || (error.status && ![503, 504].includes(error.status))) throw error;
                await new Promise(resolve => setTimeout(resolve, 350 * (attempt + 1)));
            }
        }
    }
    try {
        let offset = started.offset;
        if (!Number.isInteger(started.chunk_bytes) || started.chunk_bytes < 1 || started.chunk_bytes > 524288) {
            throw Error('Invalid upload settings.');
        }
        while (offset < file.size) {
            const end = Math.min(file.size, offset + started.chunk_bytes);
            const content = bytesToBase64(new Uint8Array(await file.slice(offset, end).arrayBuffer()));
            const reply = await retry('upload_chunk', {offset, content});
            if (reply.offset !== end) throw Error('The server reported an unexpected upload offset.');
            offset = reply.offset;
            progress?.(offset, file.size);
        }
        progress?.(file.size, file.size);
        const result = await retry('upload_finish');
        published = true;
        return result;
    } finally {
        if (!published) {
            try { await filePath(path, 'upload_cancel', {upload_id}); } catch { /* Stage expires server-side. */ }
        }
    }
}

async function fileManagerView(epoch) {
    const base = boundAccount();
    const path = base + 'files';
    const controller = new AbortController();
    closeFileView = () => {
        fileViewHasUnsavedChanges = () => false;
        controller.abort();
    };
    const active = () => Boolean(me && activeView(epoch, base) && !controller.signal.aborted);
    let current = currentPath;
    let page = {entries: [], total: 0, next_offset: null};
    let offset = 0;
    let browseRequest = 0;
    let selected;
    let previewController;
    let isDirty = () => false;
    let batch;
    let downloading = false;
    fileViewHasUnsavedChanges = () => active() && isDirty();

    view('File Manager', 'Browse, edit and transfer your website files in public_html.',
        '<div class="file-layout"><aside class="panel file-folders"><h2>Folders</h2><nav id="file-tree" aria-label="Folder tree"></nav>' +
        '<p id="file-storage" class="muted" role="status">Loading storage usage…</p><a href="#usage">Disk Usage</a></aside>' +
        '<section class="panel file-browser"><nav class="file-crumbs" id="file-crumbs" aria-label="Current folder"></nav>' +
        '<form id="file-location" class="file-location"><label>Folder path<input name="folder" maxlength="2048" placeholder="public_html"></label>' +
        '<button type="submit" class="subtle">Go</button></form>' +
        '<div class="toolbar file-tools"><button id="new-file">New file</button><button id="new-dir" class="subtle">New folder</button>' +
        '<button id="archive-folder" class="subtle">Zip folder</button><button id="reload-files" class="subtle">Reload</button>' +
        '<a href="#trash">Trash</a><a href="#backups">Website backups</a></div>' +
        '<form id="file-search" class="file-location"><label>Search this folder and its subfolders<input name="query" type="search" maxlength="120" required></label>' +
        '<button type="submit" class="subtle">Search</button></form><div id="file-results" aria-live="polite"></div>' +
        '<div class="drop-zone" id="drop-files"><label>Upload or drop files (256 MiB each)<input type="file" id="upload" multiple></label>' +
        '<div id="file-transfers" aria-live="polite"></div></div>' +
        '<div class="file-list-header"><label class="file-check"><input id="hidden-files" type="checkbox"' +
        (showHidden ? ' checked' : '') + '> Show hidden files</label><p id="file-page-status" role="status"></p></div>' +
        '<div id="file-list"></div><div class="toolbar" id="file-pages"></div>' +
        '<section id="file-open" class="file-open" hidden><div class="file-open-head"><h2 id="file-open-title"></h2>' +
        '<button id="close-file" class="subtle">Close file</button></div><div id="file-preview-content"></div></section></section></div>');
    const folderForm = $('#file-location');
    const listing = $('#file-list');
    const pages = $('#file-pages');
    const status = $('#file-page-status');
    const popup = $('#file-open');
    const content = $('#file-preview-content');
    const searchResults = $('#file-results');
    const transferField = $('#file-transfers');
    const input = $('#upload');
    const search = $('#file-search');
    const drop = $('#drop-files');

    function closePreview() {
        previewController?.abort();
        previewController = null;
        isDirty = () => false;
        selected = null;
        popup.hidden = true;
        content.replaceChildren();
    }

    async function checkChanges() {
        return !isDirty() || await confirmed('Discard unsaved file changes?');
    }

    function mountTree() {
        folderTree($('#file-tree'), path, current, showHidden, folder => {
            openFolder(folder).catch(error => notice(error.message));
        });
    }

    async function updateUsage() {
        const usage = $('#file-storage');
        usage.textContent = 'Loading storage usage…';
        try {
            const stats = await api(base + 'stats');
            if (active()) usage.textContent = Number.isFinite(stats.disk_bytes)
                ? fileSize(stats.disk_bytes) + ' used in this account' : 'Storage usage unavailable.';
        } catch (error) {
            if (active()) usage.textContent = 'Storage usage unavailable. ' + error.message;
        }
    }

    function fileOptions(item) {
        const choices = [];
        if (item.regular) {
            choices.push(['download', 'Download'], ['copy', 'Copy'], ['mode', 'Permissions'], ['archive', 'Create ZIP']);
            if (/\.zip$/i.test(item.name)) choices.push(['extract', 'Extract ZIP']);
        } else if (item.directory) {
            choices.push(['copy', 'Copy folder'], ['mode', 'Permissions'], ['archive', 'Create ZIP']);
        }
        return [...choices, ['rename', 'Move or rename'], ['trash', 'Move to Trash']];
    }

    function renderListing() {
        const names = current.split('/').filter(Boolean);
        $('#file-crumbs').innerHTML = ['public_html', ...names].map((label, index) =>
            '<button type="button" class="subtle" data-level="' + index + '"' +
            (index === names.length ? ' aria-current="page"' : '') + '>' + esc(label) + '</button>').join(' / ');
        actionHandler($('#file-crumbs'), '[data-level]', async button =>
            openFolder(names.slice(0, Number(button.dataset.level)).join('/')));
        folderForm.elements.folder.value = current;
        status.textContent = page.total
            ? (offset + 1) + '–' + (offset + page.entries.length) + ' of ' + page.total + ' entries'
            : 'This folder has no visible entries.';
        listing.innerHTML = table(['Name', 'Size', 'Modified', 'Owner / Group', 'Mode', 'Actions'],
            page.entries.map((entry, index) => {
                const label = esc(entry.name) + (entry.directory ? '/' : '');
                const name = entry.regular || entry.directory
                    ? '<button class="file-name subtle" data-open="' + index + '">' + label + '</button>'
                    : label + (entry.symlink ? ' (symlink)' : ' (special file)');
                const options = fileOptions(entry).map(([key, action]) =>
                    '<option value="' + key + '">' + action + '</option>').join('');
                return [name, entry.regular ? fileSize(entry.size) : '—',
                    esc(new Date(entry.modified * 1000).toLocaleString()),
                    '<span title="UID ' + Number(entry.uid) + ', GID ' + Number(entry.gid) + '">' +
                    esc(entry.owner) + ' / ' + esc(entry.group) + '</span>', esc(entry.mode.replace(/^0o/, '')),
                    '<select class="file-actions" data-action="' + index + '" aria-label="Action for ' + esc(entry.name) +
                    '"><option value="">Choose…</option>' + options + '</select>'];
            }));
        actionHandler(listing, '[data-open]', async button => {
            const entry = page.entries[Number(button.dataset.open)];
            const location = joinFilePath(current, entry.name);
            if (entry.directory) await openFolder(location);
            else await openFile(location, entry.size);
        });
        for (const select of listing.querySelectorAll('[data-action]')) {
            select.onchange = async () => {
                const entry = page.entries[Number(select.dataset.action)];
                const action = select.value;
                select.disabled = true;
                select.value = '';
                try { if (action) await fileAction(action, entry); }
                catch (error) { notice(error.message); }
                finally { select.disabled = false; }
            };
        }
        pages.innerHTML = (offset ? '<button class="subtle" id="file-prev">Previous page</button>' : '') +
            (page.next_offset === null ? '' : '<button class="subtle" id="file-next">Next page</button>');
        actionHandler(pages, '#file-prev', async () => load(current, Math.max(0, offset - 100)));
        actionHandler(pages, '#file-next', async () => load(current, page.next_offset));
    }

    async function load(folder, nextOffset = 0) {
        const request = ++browseRequest;
        status.textContent = 'Loading entries…';
        try {
            const result = await browseFolder(path, folder, showHidden, nextOffset);
            if (!active() || request !== browseRequest) return false;
            if (nextOffset && !result.entries.length) return load(folder, 0);
            const changed = result.path !== current;
            currentPath = current = result.path;
            page = result;
            offset = nextOffset;
            if (changed) {
                closePreview();
                searchResults.replaceChildren();
                search.reset();
            }
            renderListing();
            return true;
        } catch (error) {
            if (active() && request === browseRequest) status.textContent = error.message;
            return false;
        }
    }

    async function openFolder(folder) {
        if (folder !== current && !await checkChanges()) return;
        if (active() && await load(folder)) mountTree();
    }

    async function refresh() {
        if (active() && await load(current, offset)) {
            mountTree();
            updateUsage();
        }
    }

    async function runFileAction(action, fields) {
        const result = await filePath(path, action, fields);
        notice(result.message);
        await refresh();
    }

    async function previewZip(location, stillOpen) {
        async function listZip(zipOffset = 0, revision = '') {
            const result = await filePath(path, 'archive_contents', {path: location, offset: zipOffset, revision});
            if (!stillOpen()) return;
            content.innerHTML = '<p role="status">' + result.total + (result.total === 1 ? ' file' : ' files') + ' in this ZIP</p>' +
                table(['Path in archive', 'Size'], result.entries.map(entry => [esc(entry.path), fileSize(entry.size)])) +
                '<div class="toolbar">' + (zipOffset ? '<button class="subtle" data-prev-zip>Previous page</button>' : '') +
                (result.next_offset === null ? '' : '<button class="subtle" data-next-zip>Next page</button>') + '</div>';
            actionHandler(content, '[data-prev-zip]', () => listZip(Math.max(0, zipOffset - 75), result.revision));
            actionHandler(content, '[data-next-zip]', () => listZip(result.next_offset, result.revision));
        }
        await listZip();
    }

    async function openFile(location, size, create = false) {
        if (!await checkChanges() || !active()) return;
        closePreview();
        const preview = new AbortController();
        previewController = preview;
        selected = location;
        const stillOpen = () => active() && !preview.signal.aborted;
        popup.hidden = false;
        $('#file-open-title').textContent = location;
        content.textContent = 'Opening file…';
        const extension = location.split('.').at(-1).toLowerCase();
        const media = Object.hasOwn(mediaFiles, extension) ? mediaFiles[extension] : null;
        try {
            if (media && !create) {
                const chunks = await readLargeFile(path, 'download', location,
                    {maxBytes: 24 * 1024 * 1024, active: stillOpen});
                if (!stillOpen()) return;
                await showFileMedia(content, leafFileName(location), media, chunks, preview.signal, async (blob, filename) => {
                    const dest = joinFilePath(parentFilePath(location), validateFileName(filename));
                    await sendFileUpload(path, dest, blob, stillOpen);
                    await refresh();
                });
            } else if (extension === 'zip' && !create) {
                await previewZip(location, stillOpen);
            } else {
                if (!create && size > 1048576) throw Error('Files larger than 1 MiB are available through Download.');
                const result = create ? {content: ''} : await filePath(path, 'read', {path: location});
                if (!stillOpen()) return;
                let source;
                try {
                    source = new TextDecoder('utf-8', {fatal: true, ignoreBOM: true}).decode(
                        Uint8Array.from(atob(result.content), character => character.charCodeAt(0)));
                    if (/[\u0000-\u0008\u000e-\u001a]/.test(source)) throw Error('Binary data');
                } catch {
                    throw Error('This file is not UTF-8 text. Use Download.');
                }
                let revision = result.revision;
                isDirty = mountFileEditor(content, location, source, async bytes => {
                    if (!stillOpen()) throw Error('This editor was closed.');
                    const saved = await filePath(path, 'write', {path: location, content: bytesToBase64(bytes),
                        create_only: create, expected_revision: revision});
                    revision = saved.revision;
                    if (create) {
                        create = false;
                        await refresh();
                    }
                    return saved;
                });
            }
        } catch (error) {
            if (stillOpen()) {
                const message = document.createElement('p');
                message.textContent = error.message;
                message.setAttribute('role', 'status');
                content.replaceChildren(message);
            }
        }
    }

    async function fileAction(action, entry) {
        const location = joinFilePath(current, entry.name);
        const moveTarget = (title, folder, name, submit, operation) =>
            chooseFileTarget(path, title, folder, name, submit, async destination => {
                await runFileAction(operation, {path: location, destination});
                if (location === selected && operation === 'rename') closePreview();
            });
        if (action === 'download') {
            if (downloading) throw Error('Wait for the current download to finish.');
            downloading = true;
            try {
                const chunks = await readLargeFile(path, 'download', location, {maxBytes: fileTransferLimit, active,
                    progress: (done, total) => { status.textContent = 'Downloading ' + fileSize(done) + ' of ' + fileSize(total); }});
                if (active()) {
                    downloadBlob(new Blob(chunks, {type: 'application/octet-stream'}), entry.name);
                    status.textContent = 'Download ready.';
                }
            } catch (error) {
                status.textContent = error.message;
            } finally {
                downloading = false;
            }
        } else if (action === 'mode') {
            editFileMode(entry, mode => runFileAction('chmod', {path: location, mode}));
        } else if (action === 'trash') {
            if (!await confirmed('Move ' + entry.name + ' to Trash?')) return;
            if (location === selected && !await checkChanges()) return;
            await runFileAction('trash', {path: location});
            if (location === selected) closePreview();
        } else if (action === 'copy') {
            moveTarget('Copy ' + entry.name, current, entry.name + '.copy', 'Copy', entry.directory ? 'copy_tree' : 'copy');
        } else if (action === 'rename') {
            if (location === selected && !await checkChanges()) return;
            moveTarget('Move or rename ' + entry.name, current, entry.name, 'Move', 'rename');
        } else if (action === 'extract') {
            moveTarget('Extract ' + entry.name, current, entry.name.replace(/\.zip$/i, ''), 'Extract', 'extract');
        } else if (action === 'archive') {
            moveTarget('Create ZIP of ' + entry.name, current, entry.name + '.zip', 'Create ZIP', 'archive');
        }
    }

    async function upload(files) {
        if (!files.length) return;
        if (batch) throw Error('Wait for the current upload batch or cancel it.');
        if (files.length > 50) throw Error('Upload up to 50 files at a time.');
        const target = current;
        batch = new AbortController();
        const thisBatch = batch;
        const stillUploading = () => active() && !thisBatch.signal.aborted;
        const list = document.createElement('ul');
        const cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.className = 'subtle';
        cancel.textContent = 'Cancel uploads';
        cancel.onclick = () => thisBatch.abort();
        transferField.replaceChildren(cancel, list);
        const rows = files.map(file => {
            const item = document.createElement('li');
            item.textContent = file.name + ' · Waiting';
            list.append(item);
            return item;
        });
        try {
            for (const [index, file] of files.entries()) {
                const row = rows[index];
                if (!stillUploading()) {
                    row.textContent = file.name + ' · Canceled';
                    continue;
                }
                try {
                    await sendFileUpload(path, joinFilePath(target, validateFileName(file.name)), file,
                        stillUploading, (done, size) => {
                            row.textContent = file.name + ' · ' + (done === size ? 'Publishing…' : fileSize(done) + ' of ' + fileSize(size));
                        });
                    row.textContent = file.name + ' · Uploaded';
                } catch (error) {
                    row.textContent = file.name + ' · ' + error.message;
                }
            }
            await refresh();
        } finally {
            cancel.remove();
            batch = null;
        }
    }

    folderForm.onsubmit = event => {
        event.preventDefault();
        openFolder(folderForm.elements.folder.value).catch(error => notice(error.message));
    };
    $('#hidden-files').onchange = async event => {
        showHidden = event.target.checked;
        searchResults.replaceChildren();
        if (await load(current)) mountTree();
    };
    actionHandler($('#main'), '#reload-files', refresh);
    actionHandler($('#main'), '#close-file', async () => { if (await checkChanges()) closePreview(); });
    actionHandler($('#main'), '#new-file', async () =>
        chooseFileTarget(path, 'New file', current, '', 'Open editor', destination => openFile(destination, 0, true)));
    actionHandler($('#main'), '#new-dir', async () =>
        chooseFileTarget(path, 'New folder', current, '', 'Create folder', destination => runFileAction('mkdir', {path: destination})));
    actionHandler($('#main'), '#archive-folder', async () =>
        chooseFileTarget(path, 'Zip current folder', parentFilePath(current), (leafFileName(current) || 'website') + '.zip',
            'Create ZIP', destination => runFileAction('archive', {path: current, destination})));
    form('#file-search', async (fields, element) => {
        const start = current;
        const hidden = showHidden;
        searchResults.textContent = 'Searching…';
        try {
            const found = await filePath(path, 'search', {path: start, query: fields.query, include_hidden: hidden});
            if (!active() || current !== start || showHidden !== hidden) return;
            searchResults.innerHTML = table(['Matching path', ''], found.matches.map((item, index) => [
                esc(item.path), item.symlink ? 'Symlink' : '<button class="subtle" data-result="' + index + '">Open</button>'
            ])) + (found.truncated ? '<p>Search reached its scanning or display limit.</p>' : '');
            actionHandler(searchResults, '[data-result]', async button => {
                const item = found.matches[Number(button.dataset.result)];
                if (item.directory) await openFolder(item.path);
                else await openFile(item.path);
            });
        } catch (error) {
            if (element.isConnected && current === start) searchResults.textContent = error.message;
        }
    });
    input.onchange = () => {
        const files = [...input.files];
        input.value = '';
        upload(files).catch(error => notice(error.message));
    };
    drop.ondragover = event => { event.preventDefault(); drop.classList.add('dropping'); };
    drop.ondragleave = () => drop.classList.remove('dropping');
    drop.ondrop = event => {
        event.preventDefault();
        drop.classList.remove('dropping');
        upload([...event.dataTransfer.files]).catch(error => notice(error.message));
    };
    await load(current);
    if (active()) {
        mountTree();
        updateUsage();
    }
}
