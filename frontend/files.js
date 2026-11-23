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

function folderTree(container, path, current, includeHidden, onSelect, expandTo = current) {
    const ancestors = expandTo.split('/').filter(Boolean);
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
    // name === null asks only for a destination folder (used for several selected items).
    const content = '<label>Folder under public_html<input name="folder" placeholder="public_html" maxlength="2048" value="' +
        esc(folder) + '"></label><details><summary>Browse folders</summary><div class="file-picker"></div></details>' +
        (name === null ? '' : '<label>Name<input name="filename" required maxlength="255" value="' + esc(name) + '"></label>');
    const form = fileDialog(title, content, submitLabel, fields => {
        if (name === null) return run(fields.folder.split('/').filter(Boolean).join('/'));
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

// Original 16px line icons for the File Manager toolbars.
const FM_ICONS = {
    file: '<path d="M4 1.5h5l3 3v10H4z"/><path d="M8 7v5M5.5 9.5h5"/>',
    folder: '<path d="M1.5 4V2.5h5l1.5 2h6.5v9h-13z"/><path d="M8 7v4.5M5.8 9.2h4.4"/>',
    copy: '<rect x="5" y="5" width="9" height="9" rx="1"/><path d="M11 5V2H2v9h3"/>',
    move: '<path d="M8 1.5v13M1.5 8h13M8 1.5L6 3.5M8 1.5l2 2M8 14.5l-2-2M8 14.5l2-2M1.5 8l2-2M1.5 8l2 2M14.5 8l-2-2M14.5 8l-2 2"/>',
    upload: '<path d="M8 11V2M4.5 5.5L8 2l3.5 3.5M2 10v4h12v-4"/>',
    download: '<path d="M8 2v9M4.5 7.5L8 11l3.5-3.5M2 10v4h12v-4"/>',
    delete: '<path d="M2.5 4h11M6 4V2h4v2M4 4l.8 10h6.4L12 4M6.8 6.5v5M9.2 6.5v5"/>',
    rename: '<path d="M2 12.5h4M10.5 2.5l3 3L6 13H3v-3z"/>',
    edit: '<path d="M11 1.5l3.5 3.5L6 13.5H2.5V10z"/><path d="M9.5 3l3.5 3.5"/>',
    permissions: '<circle cx="5" cy="8" r="3"/><path d="M8 8h6.5M12 8v2.5M14.5 8v2"/>',
    view: '<path d="M1 8s2.6-4.5 7-4.5S15 8 15 8s-2.6 4.5-7 4.5S1 8 1 8z"/><circle cx="8" cy="8" r="2"/>',
    extract: '<path d="M9.5 6.5L14 2M10 2h4v4M6.5 9.5L2 14M2 10v4h4"/>',
    compress: '<path d="M14 2L9.5 6.5M9.5 3v3.5H13M2 14l4.5-4.5M3 9.5h3.5V13"/>',
    home: '<path d="M1.5 8L8 2l6.5 6M3.5 6.5V14h3.5v-4h2v4h3.5V6.5"/>',
    up: '<path d="M8 14V3M4 7l4-4 4 4M3 1.5h10"/>',
    back: '<path d="M14 8H2.5M7 3.5L2.5 8 7 12.5"/>',
    forward: '<path d="M2 8h11.5M9 3.5L13.5 8 9 12.5"/>',
    reload: '<path d="M13.5 8A5.5 5.5 0 1 1 11.6 3.8M12 1.5v3h-3"/>',
    selectAll: '<rect x="2" y="2" width="12" height="12" rx="1.5"/><path d="M5 8l2 2 4-4.5"/>',
    selectNone: '<rect x="2" y="2" width="12" height="12" rx="1.5"/>',
    trash: '<path d="M3 4.5h10M6 4.5V2.5h4v2M4.5 4.5l.7 9.5h5.6l.7-9.5"/>',
    emptyTrash: '<path d="M3 4.5h10M6 4.5V2.5h4v2M4.5 4.5l.7 9.5h5.6l.7-9.5M6.5 7.5l3 3M9.5 7.5l-3 3"/>',
    settings: '<circle cx="8" cy="8" r="2.2"/><path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M3.4 12.6l1.4-1.4M11.2 4.8l1.4-1.4"/>',
    dir: '<path d="M1.5 3.5h5l1.5 1.5h6.5v8.5h-13z" fill="currentColor" fill-opacity=".18"/>',
    doc: '<path d="M3.5 1.5h6l3 3v10h-9z"/><path d="M9.5 1.5v3h3"/>',
    link: '<path d="M6.5 9.5l3-3M5 7L3.5 8.5a2.1 2.1 0 0 0 3 3L8 10M8 6l1.5-1.5a2.1 2.1 0 0 1 3 3L11 9"/>'
};
const fmIcon = name => '<svg class="fm-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' + FM_ICONS[name] + '</svg>';

const fileTypeNames = {
    php: 'PHP script', html: 'HTML page', htm: 'HTML page', css: 'Stylesheet', js: 'JavaScript', mjs: 'JavaScript',
    json: 'JSON data', xml: 'XML document', txt: 'Text', md: 'Markdown', csv: 'CSV data', log: 'Log file',
    ini: 'Configuration', conf: 'Configuration', yml: 'YAML', yaml: 'YAML', sql: 'SQL script', sh: 'Shell script',
    py: 'Python script', svg: 'SVG image', png: 'PNG image', jpg: 'JPEG image', jpeg: 'JPEG image', gif: 'GIF image',
    webp: 'WebP image', ico: 'Icon', pdf: 'PDF document', zip: 'ZIP archive', gz: 'Gzip archive', tar: 'Tar archive',
    mp3: 'MP3 audio', wav: 'WAV audio', ogg: 'Ogg audio', mp4: 'MP4 video', webm: 'WebM video',
    woff: 'Web font', woff2: 'Web font', ttf: 'Font', htaccess: 'Server rules'
};

function fileTypeName(entry) {
    if (entry.directory) return 'Folder';
    if (entry.symlink) return 'Symbolic link';
    if (!entry.regular) return 'Special file';
    const dot = entry.name.lastIndexOf('.');
    const extension = dot >= 0 ? entry.name.slice(dot + 1).toLowerCase() : '';
    return fileTypeNames[extension] || (extension ? extension.toUpperCase() + ' file' : 'File');
}

const fileSettingsKey = 'alma-file-manager';
function fileSettings() {
    try { return {showOwner: false, ...JSON.parse(localStorage.getItem(fileSettingsKey) || '{}')}; }
    catch { return {showOwner: false}; }
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
    const settings = fileSettings();
    if (typeof settings.showHidden === 'boolean') showHidden = settings.showHidden;
    let current = currentPath;
    let page = {entries: [], total: 0, next_offset: null};
    let rows = [];
    let offset = 0;
    let browseRequest = 0;
    let selected;
    let previewController;
    let isDirty = () => false;
    let batch;
    let downloading = false;
    let sortKey = 'name';
    let sortAscending = true;
    let anchor = null;
    let treeExpandTo = null;
    let mode = 'files';
    const chosen = new Set();
    const past = [];
    const ahead = [];
    fileViewHasUnsavedChanges = () => active() && isDirty();

    const tool = (cmd, label, iconName, extra = '') =>
        '<button type="button" class="fm-btn" data-cmd="' + cmd + '" title="' + label + '"' + extra + '>' + fmIcon(iconName) + '<span>' + label + '</span></button>';
    document.title = 'File Manager · ' + account.name + ' · almaPanel';
    $('#main').innerHTML = '<div class="fm fm-page">' +
        '<div class="fm-head"><div class="fm-brand"><img src="/logo.svg" alt=""><h1>File Manager</h1></div>' +
        '<span class="fm-account" title="Hosting account">' + esc(account.name) + '</span>' +
        '<p id="file-storage" role="status">Loading storage usage…</p>' +
        '<form id="file-search" class="fm-search" role="search"><label for="fm-scope">Search</label>' +
        '<select id="fm-scope" name="scope" aria-label="Search scope"><option value="all">All your files</option>' +
        '<option value="current">Current folder</option></select><label for="fm-query">for</label>' +
        '<input id="fm-query" name="query" type="search" maxlength="120" required aria-label="Search files">' +
        '<button type="submit">Go</button></form>' +
        '<button type="button" class="fm-btn fm-settings" data-cmd="settings" title="Settings">' + fmIcon('settings') + '<span>Settings</span></button>' +
        '</div>' +
        '<div class="fm-tools" role="toolbar" aria-label="File actions">' +
        tool('newfile', 'File', 'file', ' aria-label="New file"') + tool('newfolder', 'Folder', 'folder', ' aria-label="New folder"') +
        tool('copy', 'Copy', 'copy') + tool('move', 'Move', 'move') + tool('upload', 'Upload', 'upload') +
        tool('download', 'Download', 'download') + tool('delete', 'Delete', 'delete') +
        '<span class="fm-sep" aria-hidden="true"></span>' +
        tool('rename', 'Rename', 'rename') + tool('edit', 'Edit', 'edit') + tool('permissions', 'Permissions', 'permissions') +
        tool('view', 'View', 'view') + '<span class="fm-sep" aria-hidden="true"></span>' +
        tool('extract', 'Extract', 'extract') + tool('compress', 'Compress', 'compress') +
        '<input type="file" id="upload" multiple hidden></div>' +
        '<div class="fm-body"><aside class="fm-side" aria-label="Folders">' +
        '<form id="file-location" class="fm-path"><button type="button" class="fm-home" data-cmd="home" aria-label="Go to public_html">' +
        fmIcon('home') + '</button><input name="folder" maxlength="2048" placeholder="public_html" aria-label="Folder path">' +
        '<button type="submit" class="subtle">Go</button></form>' +
        '<button type="button" class="subtle fm-collapse" id="fm-collapse">Collapse All</button>' +
        '<nav id="file-tree" aria-label="Folder tree"></nav></aside>' +
        '<section class="fm-main" id="drop-files" aria-label="Folder contents">' +
        '<div class="fm-nav" role="toolbar" aria-label="Folder navigation">' +
        tool('home', 'Home', 'home') + tool('up', 'Up One Level', 'up') + tool('back', 'Back', 'back') +
        tool('forward', 'Forward', 'forward') + tool('reload', 'Reload', 'reload') +
        '<span class="fm-sep" aria-hidden="true"></span>' +
        tool('selectall', 'Select All', 'selectAll') + tool('selectnone', 'Unselect All', 'selectNone') +
        '<span class="fm-sep" aria-hidden="true"></span>' +
        tool('trash', 'View Trash', 'trash') +
        tool('emptytrash', 'Empty Trash', 'emptyTrash') + '</div>' +
        '<nav class="file-crumbs" id="file-crumbs" aria-label="Current folder"></nav>' +
        '<div id="file-results" aria-live="polite"></div><div id="file-transfers" aria-live="polite"></div>' +
        '<div class="fm-drop-hint" aria-hidden="true">Drop files to upload them here</div>' +
        '<div id="file-list" class="fm-list" tabindex="-1"></div>' +
        '<div class="fm-status"><p id="file-page-status" role="status"></p><div class="toolbar" id="file-pages"></div></div>' +
        '<section id="file-open" class="file-open" hidden><div class="file-open-head"><h2 id="file-open-title"></h2>' +
        '<button id="close-file" class="subtle">Close file</button></div><div id="file-preview-content"></div></section>' +
        '</section></div></div>';
    const folderForm = $('#file-location');
    const listing = $('#file-list');
    const pages = $('#file-pages');
    const status = $('#file-page-status');
    const popup = $('#file-open');
    const content = $('#file-preview-content');
    const searchResults = $('#file-results');
    const transferField = $('#file-transfers');
    const input = $('#upload');
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
        }, treeExpandTo ?? current);
        treeExpandTo = null;
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

    const selection = () => rows.filter(entry => chosen.has(entry.name));
    const locationOf = entry => joinFilePath(current, entry.name);
    const isZip = entry => entry.regular && /\.zip$/i.test(entry.name);
    const isEditable = entry => entry.regular && !isZip(entry) && entry.size <= 1048576 &&
        !Object.hasOwn(mediaFiles, entry.name.split('.').at(-1).toLowerCase());

    // Enable each command only when the current selection supports it.
    function updateTools() {
        const items = selection();
        const one = items.length === 1 ? items[0] : null;
        const real = items.length > 0 && items.every(entry => entry.regular || entry.directory);
        const state = {
            copy: real, move: items.length > 0, delete: items.length > 0, compress: real,
            download: Boolean(one?.regular), rename: Boolean(one), edit: Boolean(one && isEditable(one)),
            view: Boolean(one?.regular), permissions: real, extract: Boolean(one && isZip(one)),
            up: current !== '', back: past.length > 0, forward: ahead.length > 0,
            selectall: rows.length > 0 && items.length < rows.length, selectnone: items.length > 0
        };
        for (const button of $('#main').querySelectorAll('.fm [data-cmd]')) {
            if (Object.hasOwn(state, button.dataset.cmd)) button.disabled = !state[button.dataset.cmd];
        }
        const all = $('#fm-check-all');
        if (all) {
            all.checked = rows.length > 0 && items.length === rows.length;
            all.indeterminate = items.length > 0 && items.length < rows.length;
        }
        for (const row of listing.querySelectorAll('tr[data-index]')) {
            const isChosen = chosen.has(rows[Number(row.dataset.index)].name);
            row.classList.toggle('chosen', isChosen);
            row.setAttribute('aria-selected', String(isChosen));
            row.querySelector('input[type=checkbox]').checked = isChosen;
        }
        if (mode === 'trash') return;
        const range = page.total ? (offset + 1) + '–' + (offset + page.entries.length) + ' of ' + page.total + ' items' : 'This folder is empty.';
        status.textContent = range + (items.length ? ' · ' + items.length + ' selected' : '') +
            (page.next_offset !== null || offset ? ' · Sorting applies to this page' : '');
    }

    function sortRows() {
        const direction = sortAscending ? 1 : -1;
        const value = {
            name: entry => entry.name.toLowerCase(), size: entry => entry.regular ? entry.size : -1,
            modified: entry => entry.modified, type: entry => fileTypeName(entry).toLowerCase(),
            permissions: entry => entry.mode
        }[sortKey];
        rows = [...page.entries].sort((a, b) => {
            if (a.directory !== b.directory) return a.directory ? -1 : 1;  // Folders stay first.
            const left = value(a), right = value(b);
            return (left < right ? -1 : left > right ? 1 : a.name.localeCompare(b.name)) * direction;
        });
    }

    function renderListing() {
        const names = current.split('/').filter(Boolean);
        $('#file-crumbs').innerHTML = ['public_html', ...names].map((label, index) =>
            '<button type="button" class="subtle" data-level="' + index + '"' +
            (index === names.length ? ' aria-current="page"' : '') + '>' + esc(label) + '</button>').join('<span aria-hidden="true">/</span>');
        actionHandler($('#file-crumbs'), '[data-level]', async button =>
            openFolder(names.slice(0, Number(button.dataset.level)).join('/')));
        folderForm.elements.folder.value = current;
        sortRows();
        const columns = [['name', 'Name'], ['size', 'Size'], ['modified', 'Last Modified'], ['type', 'Type'], ['permissions', 'Permissions']];
        const header = columns.map(([key, label]) => '<th' + (key === sortKey ? ' aria-sort="' + (sortAscending ? 'ascending' : 'descending') + '"' : '') +
            ' class="fm-col-' + key + '"><button type="button" data-sort="' + key + '">' + label +
            (key === sortKey ? '<span aria-hidden="true">' + (sortAscending ? ' ▲' : ' ▼') + '</span>' : '') + '</button></th>').join('');
        const body = rows.length ? rows.map((entry, index) => {
            const kind = entry.directory ? 'dir' : entry.symlink ? 'link' : 'doc';
            const name = entry.regular || entry.directory
                ? '<button type="button" class="fm-open" data-open="' + index + '">' + esc(entry.name) + '</button>'
                : '<span>' + esc(entry.name) + '</span>';
            const owner = esc(entry.owner) + ' / ' + esc(entry.group);
            return '<tr data-index="' + index + '" aria-selected="false"><td class="fm-check"><input type="checkbox" aria-label="Select ' +
                esc(entry.name) + '"></td><td class="fm-name"><span class="fm-kind fm-' + kind + '">' + fmIcon(kind) + '</span>' + name + '</td>' +
                '<td class="fm-col-size">' + (entry.regular ? fileSize(entry.size) : entry.directory ? '—' : '') + '</td>' +
                '<td class="fm-col-modified">' + esc(new Date(entry.modified * 1000).toLocaleString()) + '</td>' +
                '<td class="fm-col-type">' + esc(fileTypeName(entry)) + '</td>' +
                '<td class="fm-col-permissions" title="Owner ' + owner + ' (UID ' + Number(entry.uid) + ', GID ' + Number(entry.gid) + ')">' +
                esc(entry.mode.replace(/^0o/, '').padStart(4, '0')) + '</td>' +
                (settings.showOwner ? '<td class="fm-col-owner">' + owner + '</td>' : '') + '</tr>';
        }).join('') : '<tr><td colspan="' + (settings.showOwner ? 7 : 6) + '" class="fm-empty">This folder is empty. Use Upload, File or Folder to add content.</td></tr>';
        listing.innerHTML = '<table class="fm-table"><thead><tr><th class="fm-check"><input type="checkbox" id="fm-check-all" aria-label="Select all items on this page"></th>' +
            header + (settings.showOwner ? '<th class="fm-col-owner">Owner / Group</th>' : '') + '</tr></thead><tbody>' + body + '</tbody></table>';
        pages.innerHTML = (offset ? '<button class="subtle" id="file-prev">Previous page</button>' : '') +
            (page.next_offset === null ? '' : '<button class="subtle" id="file-next">Next page</button>');
        actionHandler(pages, '#file-prev', async () => load(current, Math.max(0, offset - 100)));
        actionHandler(pages, '#file-next', async () => load(current, page.next_offset));
        updateTools();
    }

    listing.addEventListener('click', event => {
        const sort = event.target.closest('[data-sort]');
        if (sort) {
            sortAscending = sort.dataset.sort === sortKey ? !sortAscending : true;
            sortKey = sort.dataset.sort;
            renderListing();
            listing.querySelector('[data-sort="' + sortKey + '"]').focus();
            return;
        }
        if (event.target.id === 'fm-check-all') {
            if (event.target.checked) rows.forEach(entry => chosen.add(entry.name)); else chosen.clear();
            updateTools();
            return;
        }
        const open = event.target.closest('[data-open]');
        if (open) {
            const entry = rows[Number(open.dataset.open)];
            (entry.directory ? openFolder(locationOf(entry)) : openFile(locationOf(entry), entry.size)).catch(error => notice(error.message));
            return;
        }
        const row = event.target.closest('tr[data-index]');
        if (!row) return;
        const index = Number(row.dataset.index);
        const name = rows[index].name;
        if (event.target.matches('input[type=checkbox]')) {
            if (event.target.checked) chosen.add(name); else chosen.delete(name);
            anchor = index;
        } else if (event.shiftKey && anchor !== null) {
            // Shift-click selects a range; Ctrl/Cmd adds to it.
            if (!event.ctrlKey && !event.metaKey) chosen.clear();
            for (let i = Math.min(anchor, index); i <= Math.max(anchor, index); i += 1) chosen.add(rows[i].name);
        } else if (event.ctrlKey || event.metaKey) {
            if (chosen.has(name)) chosen.delete(name); else chosen.add(name);
            anchor = index;
        } else {
            chosen.clear();
            chosen.add(name);
            anchor = index;
        }
        updateTools();
    });
    listing.addEventListener('dblclick', event => {
        const row = event.target.closest('tr[data-index]');
        if (!row || event.target.closest('button, input')) return;
        const entry = rows[Number(row.dataset.index)];
        if (entry.directory) openFolder(locationOf(entry)).catch(error => notice(error.message));
        else if (entry.regular) openFile(locationOf(entry), entry.size).catch(error => notice(error.message));
    });
    listing.addEventListener('keydown', event => {
        if (event.target.closest('input:not([type=checkbox]), textarea')) return;
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a') {
            event.preventDefault();
            rows.forEach(entry => chosen.add(entry.name));
            updateTools();
        } else if (event.key === 'Delete' && chosen.size) {
            event.preventDefault();
            command('delete');
        }
    });

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
            mode = 'files';
            history.replaceState(null, '', fileManagerUrl(current));  // Reloading this tab keeps the folder.
            offset = nextOffset;
            if (changed) {
                closePreview();
                chosen.clear();
                anchor = null;
            } else {
                const present = new Set(result.entries.map(entry => entry.name));
                for (const name of [...chosen]) if (!present.has(name)) chosen.delete(name);
            }
            renderListing();
            return true;
        } catch (error) {
            if (active() && request === browseRequest) status.textContent = error.message;
            return false;
        }
    }

    // how: 'new' records history; 'back' and 'forward' move through it.
    async function openFolder(folder, how = 'new') {
        folder = String(folder).split('/').filter(Boolean).join('/');
        if (folder !== current && !await checkChanges()) return;
        const previous = current;
        if (!active() || !await load(folder)) return;
        if (current !== previous) {
            if (how === 'new') { past.push(previous); ahead.length = 0; }
            else if (how === 'back') { past.pop(); ahead.push(previous); }
            else { ahead.pop(); past.push(previous); }
            if (past.length > 50) past.shift();
        }
        mountTree();
        updateTools();
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

    // Apply one operation to several items, then report successes and failures together.
    async function runEach(items, label, operation) {
        const failed = [];
        for (const entry of items) {
            if (!active()) break;
            try { await operation(entry); }
            catch (error) { failed.push(entry.name + ': ' + error.message); }
        }
        const done = items.length - failed.length;
        notice(label + ' ' + done + ' of ' + items.length + (items.length === 1 ? ' item.' : ' items.') +
            (failed.length ? ' ' + failed.slice(0, 3).join(' ') + (failed.length > 3 ? ' …' : '') : ''));
        await refresh();
        if (failed.length) throw Error(failed.length + ' item' + (failed.length === 1 ? '' : 's') + ' could not be processed. ' + failed[0]);
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

    const previewable = location => {
        const extension = location.split('.').at(-1).toLowerCase();
        return extension === 'zip' || Object.hasOwn(mediaFiles, extension);
    };

    // Text files open in their own editor tab; images, audio, video and ZIPs preview here.
    // Runs synchronously up to window.open so the browser treats it as the user's click.
    function openFile(location, size) {
        if (previewable(location)) return previewFile(location);
        if (size > 1048576) return Promise.reject(Error('Files larger than 1 MiB are available through Download.'));
        openEditorTab(account.id, location);
        return Promise.resolve();
    }

    async function previewFile(location) {
        if (!await checkChanges() || !active()) return;
        closePreview();
        const preview = new AbortController();
        previewController = preview;
        selected = location;
        const stillOpen = () => active() && !preview.signal.aborted;
        popup.hidden = false;
        $('#file-open-title').textContent = location;
        content.textContent = 'Opening file…';
        popup.scrollIntoView({block: 'nearest'});
        const extension = location.split('.').at(-1).toLowerCase();
        const media = Object.hasOwn(mediaFiles, extension) ? mediaFiles[extension] : null;
        try {
            if (media) {
                const chunks = await readLargeFile(path, 'download', location,
                    {maxBytes: 24 * 1024 * 1024, active: stillOpen});
                if (!stillOpen()) return;
                await showFileMedia(content, leafFileName(location), media, chunks, preview.signal, async (blob, filename) => {
                    const dest = joinFilePath(parentFilePath(location), validateFileName(filename));
                    await sendFileUpload(path, dest, blob, stillOpen);
                    await refresh();
                });
            } else {
                await previewZip(location, stillOpen);
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

    // Trash is shown inside this tab; navigating to any folder leaves it.
    async function showTrash() {
        const items = await filePath(path, 'trash_list');
        if (!active()) return;
        mode = 'trash';
        closePreview();
        chosen.clear();
        rows = [];
        const back = leafFileName(current) || 'public_html';
        $('#file-crumbs').innerHTML = '<button type="button" class="subtle" data-exit-trash>← Back to ' + esc(back) + '</button>' +
            '<span aria-hidden="true">/</span><button type="button" class="subtle" aria-current="page">Trash</button>';
        actionHandler($('#file-crumbs'), '[data-exit-trash]', async () => openFolder(current));
        listing.innerHTML = '<table class="fm-table fm-trash"><thead><tr><th class="fm-trash-path">Original path</th><th>Actions</th></tr></thead><tbody>' +
            (items.length ? items.map((item, index) => '<tr><td class="fm-trash-path">' + esc(item.path) + '</td><td>' +
                '<button class="subtle" data-trash-restore="' + index + '">Restore</button> ' +
                '<button class="subtle" data-trash-delete="' + index + '">Delete permanently</button></td></tr>').join('')
                : '<tr><td colspan="2" class="fm-empty">Trash is empty.</td></tr>') + '</tbody></table>';
        pages.replaceChildren();
        updateTools();
        status.textContent = items.length + (items.length === 1 ? ' item' : ' items') + ' in Trash. Restore an item or delete it permanently.';
        actionHandler(listing, '[data-trash-restore]', async button => {
            const item = items[Number(button.dataset.trashRestore)];
            chooseFileTarget(path, 'Restore from Trash', parentFilePath(item.path), leafFileName(item.path),
                'Restore entry', async destination => {
                    notice((await filePath(path, 'trash_restore', {id: item.id, destination})).message);
                    if (active() && mode === 'trash') await showTrash();
                });
        });
        actionHandler(listing, '[data-trash-delete]', async button => {
            const item = items[Number(button.dataset.trashDelete)];
            if (!await confirmed('Permanently delete ' + item.path + '? This cannot be undone.')) return;
            notice((await filePath(path, 'trash_purge', {id: item.id})).message);
            if (active() && mode === 'trash') await showTrash();
        });
    }

    async function download(entry) {
        if (downloading) throw Error('Wait for the current download to finish.');
        downloading = true;
        try {
            const chunks = await readLargeFile(path, 'download', locationOf(entry), {maxBytes: fileTransferLimit, active,
                progress: (done, total) => { status.textContent = 'Downloading ' + fileSize(done) + ' of ' + fileSize(total); }});
            if (active()) {
                downloadBlob(new Blob(chunks, {type: 'application/octet-stream'}), entry.name);
                status.textContent = 'Download ready.';
            }
        } finally {
            downloading = false;
        }
    }

    function renameDialog(entry) {
        const location = locationOf(entry);
        fileDialog('Rename ' + entry.name, '<label>New name<input name="filename" required maxlength="255" value="' +
            esc(entry.name) + '"></label>', 'Rename', async fields => {
            await runFileAction('rename', {path: location, destination: joinFilePath(current, validateFileName(fields.filename))});
            if (location === selected) closePreview();
        });
    }

    function settingsDialog() {
        const form = fileDialog('File Manager settings',
            '<label class="file-check"><input type="checkbox" name="hidden"' + (showHidden ? ' checked' : '') + '> Show hidden files</label>' +
            '<p class="muted">Names that start with a dot, such as .htaccess, are hidden by default.</p>' +
            '<label class="file-check"><input type="checkbox" name="owner"' + (settings.showOwner ? ' checked' : '') + '> Show owner and group column</label>',
            'Save settings', async fields => {
                showHidden = fields.hidden === 'on';
                settings.showOwner = fields.owner === 'on';
                try { localStorage.setItem(fileSettingsKey, JSON.stringify({showHidden, showOwner: settings.showOwner})); } catch { /* Per-browser only. */ }
                if (await load(current, offset)) mountTree();
            });
        form.querySelector('input').focus();
    }

    async function emptyTrash() {
        const items = await filePath(path, 'trash_list');
        if (!items.length) { notice('Trash is already empty.'); return; }
        if (!await confirmed('Permanently delete all ' + items.length + ' item' + (items.length === 1 ? '' : 's') +
            ' in Trash? This cannot be undone.')) return;
        let removed = 0;
        for (const item of items) {
            if (!active()) break;
            try { await filePath(path, 'trash_purge', {id: item.id}); removed += 1; }
            catch (error) { notice(error.message); }
        }
        notice('Permanently deleted ' + removed + ' of ' + items.length + ' Trash items.');
    }

    async function command(cmd) {
        const items = selection();
        const one = items[0];
        if (cmd === 'newfile') {
            chooseFileTarget(path, 'New file', current, '', 'Open editor', destination => openEditorTab(account.id, destination, true));
        } else if (cmd === 'newfolder') {
            chooseFileTarget(path, 'New folder', current, '', 'Create folder', destination => runFileAction('mkdir', {path: destination}));
        } else if (cmd === 'upload') {
            input.click();
        } else if (cmd === 'copy') {
            if (items.length === 1) {
                chooseFileTarget(path, 'Copy ' + one.name, current, one.name + '.copy', 'Copy',
                    destination => runFileAction(one.directory ? 'copy_tree' : 'copy', {path: locationOf(one), destination}));
            } else {
                chooseFileTarget(path, 'Copy ' + items.length + ' items', current, null, 'Copy', folder =>
                    runEach(items, 'Copied', entry => filePath(path, entry.directory ? 'copy_tree' : 'copy',
                        {path: locationOf(entry), destination: joinFilePath(folder, entry.name)})));
            }
        } else if (cmd === 'move') {
            if (selected && items.some(entry => locationOf(entry) === selected) && !await checkChanges()) return;
            if (items.length === 1) {
                chooseFileTarget(path, 'Move ' + one.name, current, one.name, 'Move', async destination => {
                    await runFileAction('rename', {path: locationOf(one), destination});
                    if (locationOf(one) === selected) closePreview();
                });
            } else {
                chooseFileTarget(path, 'Move ' + items.length + ' items', current, null, 'Move', async folder => {
                    if (items.some(entry => locationOf(entry) === selected)) closePreview();
                    await runEach(items, 'Moved', entry => filePath(path, 'rename',
                        {path: locationOf(entry), destination: joinFilePath(folder, entry.name)}));
                });
            }
        } else if (cmd === 'download') {
            await download(one);
        } else if (cmd === 'delete') {
            const what = items.length === 1 ? one.name : items.length + ' items';
            if (!await confirmed('Move ' + what + ' to Trash? You can restore items from View Trash.')) return;
            if (selected && items.some(entry => locationOf(entry) === selected)) {
                if (!await checkChanges()) return;
                closePreview();
            }
            await runEach(items, 'Moved to Trash', entry => filePath(path, 'trash', {path: locationOf(entry)}));
        } else if (cmd === 'rename') {
            if (locationOf(one) === selected && !await checkChanges()) return;
            renameDialog(one);
        } else if (cmd === 'edit' || cmd === 'view') {
            await openFile(locationOf(one), one.size);
        } else if (cmd === 'permissions') {
            const label = items.length === 1 ? one : {...one, name: items.length + ' items'};
            editFileMode(label, mode => runEach(items, 'Updated permissions for', entry =>
                filePath(path, 'chmod', {path: locationOf(entry), mode})));
        } else if (cmd === 'extract') {
            chooseFileTarget(path, 'Extract ' + one.name, current, one.name.replace(/\.zip$/i, ''), 'Extract',
                destination => runFileAction('extract', {path: locationOf(one), destination}));
        } else if (cmd === 'compress') {
            const suggested = items.length === 1 ? one.name + '.zip' : (leafFileName(current) || 'website') + '-files.zip';
            chooseFileTarget(path, 'Compress ' + (items.length === 1 ? one.name : items.length + ' items'), current, suggested,
                'Create ZIP', destination => runFileAction('archive', {path: current, names: items.map(entry => entry.name), destination}));
        } else if (cmd === 'home') {
            await openFolder('');
        } else if (cmd === 'up') {
            await openFolder(parentFilePath(current));
        } else if (cmd === 'back') {
            if (past.length) await openFolder(past.at(-1), 'back');
        } else if (cmd === 'forward') {
            if (ahead.length) await openFolder(ahead.at(-1), 'forward');
        } else if (cmd === 'reload') {
            await refresh();
        } else if (cmd === 'selectall') {
            rows.forEach(entry => chosen.add(entry.name));
            updateTools();
        } else if (cmd === 'selectnone') {
            chosen.clear();
            updateTools();
        } else if (cmd === 'trash') {
            await showTrash();
        } else if (cmd === 'emptytrash') {
            await emptyTrash();
            if (active() && mode === 'trash') await showTrash();
        } else if (cmd === 'settings') {
            settingsDialog();
        }
    }

    $('#main').querySelector('.fm').addEventListener('click', async event => {
        const button = event.target.closest('button[data-cmd]');
        if (!button || button.disabled) return;
        event.preventDefault();
        button.disabled = true;
        try { await command(button.dataset.cmd); }
        catch (error) { notice(error.message); }
        finally {
            button.disabled = false;
            if (active()) updateTools();
        }
    });

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
        const rowsShown = files.map(file => {
            const item = document.createElement('li');
            item.textContent = file.name + ' · Waiting';
            list.append(item);
            return item;
        });
        try {
            for (const [index, file] of files.entries()) {
                const row = rowsShown[index];
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
            // Clear the finished transfer list unless another batch has started.
            setTimeout(() => { if (!batch && list.isConnected) transferField.replaceChildren(); }, 10000);
        }
    }

    folderForm.onsubmit = event => {
        event.preventDefault();
        openFolder(folderForm.elements.folder.value).catch(error => notice(error.message));
    };
    $('#fm-collapse').onclick = () => {
        treeExpandTo = '';
        mountTree();
    };
    actionHandler($('#main'), '#close-file', async () => { if (await checkChanges()) closePreview(); });
    form('#file-search', async fields => {
        const start = fields.scope === 'current' ? current : '';
        const hidden = showHidden;
        searchResults.textContent = 'Searching…';
        try {
            const found = await filePath(path, 'search', {path: start, query: fields.query, include_hidden: hidden});
            if (!active() || showHidden !== hidden) return;
            searchResults.innerHTML = '<div class="fm-results-head"><h2>Search results for “' + esc(fields.query) + '” in ' +
                esc(start ? 'public_html/' + start : 'all your files') + '</h2><button type="button" class="subtle" data-close-results>Close results</button></div>' +
                table(['Matching path', ''], found.matches.map((item, index) => [
                    esc(item.path), item.symlink ? 'Symlink' : '<button class="subtle" data-result="' + index + '">' + (item.directory ? 'Open folder' : 'Open') + '</button>'
                ])) + (found.truncated ? '<p>Search reached its scanning or display limit.</p>' : '');
            actionHandler(searchResults, '[data-result]', async button => {
                const item = found.matches[Number(button.dataset.result)];
                if (item.directory) await openFolder(item.path);
                else await openFile(item.path);
            });
            actionHandler(searchResults, '[data-close-results]', async () => searchResults.replaceChildren());
        } catch (error) {
            if (active()) searchResults.textContent = error.message;
        }
    });
    input.onchange = () => {
        const files = [...input.files];
        input.value = '';
        upload(files).catch(error => notice(error.message));
    };
    drop.ondragover = event => {
        if (![...(event.dataTransfer?.types || [])].includes('Files')) return;
        event.preventDefault();
        drop.classList.add('dropping');
    };
    drop.ondragleave = event => { if (!drop.contains(event.relatedTarget)) drop.classList.remove('dropping'); };
    drop.ondrop = event => {
        event.preventDefault();
        drop.classList.remove('dropping');
        upload([...event.dataTransfer.files]).catch(error => notice(error.message));
    };
    // Editor tabs announce saves; refresh when the saved file is in the folder shown here.
    fileChannel?.addEventListener('message', event => {
        if (active() && mode === 'files' && event.data?.account === account.id && event.data.folder === current) refresh();
    }, {signal: controller.signal});
    await load(current);
    if (active()) {
        mountTree();
        updateUsage();
    }
}
