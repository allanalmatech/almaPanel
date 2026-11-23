// Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
'use strict';

const codeLanguages = {
    text: 'Plain text', html: 'HTML / XML', javascript: 'JavaScript / TypeScript', css: 'CSS',
    php: 'PHP', python: 'Python', ruby: 'Ruby', json: 'JSON', sql: 'SQL', shell: 'Shell'
};
const codeExtensions = {
    htm: 'html', html: 'html', xml: 'html', svg: 'html', js: 'javascript', mjs: 'javascript',
    cjs: 'javascript', ts: 'javascript', jsx: 'javascript', tsx: 'javascript',
    css: 'css', php: 'php', phtml: 'php', py: 'python', rb: 'ruby', json: 'json', sql: 'sql',
    sh: 'shell', bash: 'shell'
};
const keywords = new Set(('abstract and as async await break case catch class const continue def default delete do echo elif ' +
    'else end except export extends false finally fn for foreach from function global if import in interface lambda let match ' +
    'new nil none not null or pass print private protected public raise require return static super switch this throw true ' +
    'try type use var void while with yield alter create database drop insert into select table update values where join ' +
    'limit order group union distinct left right on primary key grant revoke begin commit rollback').split(' '));

function paintSource(source, language, code) {
    if (language === 'text' || source.length > 180000) {
        code.replaceChildren();
        return false;
    }
    const fragment = document.createDocumentFragment();
    const pattern = /<!--|<[/]?[A-Za-z][\w:-]*|[\/]?>|\/\*|\/\/|--|#|["'\x60]|\b(?:\d+(?:\.\d+)?|[a-zA-Z_][a-zA-Z_\d]*)\b/g;
    let offset = 0;
    let count = 0;
    for (let match = pattern.exec(source); match; match = pattern.exec(source)) {
        const token = match[0];
        const start = match.index;
        let style;
        let ending = pattern.lastIndex;
        let closing;
        if (language === 'html') {
            if (token === '<!--') {
                style = 'comment';
                closing = '-->';
            } else if (token.startsWith('<') || token.endsWith('>')) {
                style = 'element';
            }
        }
        if (token === '/*' && ['css', 'sql', 'javascript', 'php'].includes(language)) {
            style = 'comment';
            closing = '*/';
        } else if ((token === '//' && ['javascript', 'php'].includes(language)) ||
                   (token === '--' && language === 'sql') ||
                   (token === '#' && ['python', 'ruby', 'php', 'shell'].includes(language))) {
            style = 'comment';
            const newline = source.indexOf('\n', ending);
            ending = newline === -1 ? source.length : newline;
        }
        if (closing) {
            const next = source.indexOf(closing, ending);
            ending = next === -1 ? source.length : next + closing.length;
        } else if (token === '"' || token === "'" || token === String.fromCharCode(96)) {
            style = 'string';
            while (ending < source.length) {
                const character = source[ending++];
                if (character === token || (character === '\n' && token !== String.fromCharCode(96))) break;
                if (character === '\\' && ending < source.length) ending += 1;
            }
        } else if (language !== 'html' && /^\d/.test(token)) {
            style = 'number';
        } else if (language !== 'html' && keywords.has(token.toLowerCase())) {
            style = 'keyword';
        }
        if (!style) continue;
        if (++count > 12000) {
            code.replaceChildren();
            return false;
        }
        fragment.append(document.createTextNode(source.slice(offset, start)));
        const span = document.createElement('span');
        span.className = 'code-' + style;
        span.textContent = source.slice(start, ending);
        fragment.append(span);
        pattern.lastIndex = offset = ending;
    }
    fragment.append(document.createTextNode(source.slice(offset) + '\n '));
    code.replaceChildren(fragment);
    return true;
}

const editorPrefsKey = 'alma-editor';
const editorFontSizes = [11, 12, 13, 14, 15, 16, 18, 20];
const editorUrl = (accountId, file, create = false) =>
    '#editor?account=' + accountId + '&file=' + encodeURIComponent(file) + (create ? '&new=1' : '');
const editorWindowName = (accountId, file) => 'alma-edit-' + accountId + '-' + file;
const fileChannel = 'BroadcastChannel' in window ? new BroadcastChannel('alma-files') : null;
const EDITOR_ICONS = {
    find: '<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/>',
    goto: '<path d="M2 4l4 4-4 4M8 13h6"/>',
    undo: '<path d="M5.5 3.5L2.5 6.5l3 3M2.5 6.5H10a3.5 3.5 0 0 1 0 7H7"/>',
    redo: '<path d="M10.5 3.5l3 3-3 3M13.5 6.5H6a3.5 3.5 0 0 0 0 7h3"/>',
    wrap: '<path d="M2 4h12M2 8h9a2 2 0 0 1 0 4H8M9.5 10.5L8 12l1.5 1.5M2 12h3"/>'
};
const editorIcon = name => '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" ' +
    'stroke-linejoin="round" aria-hidden="true" focusable="false">' + EDITOR_ICONS[name] + '</svg>';

function editorPrefs() {
    try { return {wrap: true, fontSize: 13, ...JSON.parse(localStorage.getItem(editorPrefsKey) || '{}')}; }
    catch { return {wrap: true, fontSize: 13}; }
}

// Open a file in its own editor tab; reopening the same file reuses that tab.
function openEditorTab(accountId, file, create = false) {
    const url = editorUrl(accountId, file, create);
    const tab = window.open(url, editorWindowName(accountId, file));
    if (!tab) location.hash = url;  // Pop-up blocked: open the editor here; Close returns to File Manager.
    else tab.focus();
}

async function fileEditorPage(epoch, params) {
    const base = boundAccount();
    const path = base + 'files';
    const location = String(params.get('file') || '').split('/').filter(Boolean).join('/');
    if (!location) throw Error('Choose a file to edit from File Manager.');
    let create = params.get('new') === '1';
    const active = () => Boolean(me && activeView(epoch, base));
    const prefs = editorPrefs();
    const name = leafFileName(location);
    const extension = name.includes('.') ? name.split('.').at(-1).toLowerCase() : '';
    const tool = (key, label) => '<button type="button" class="ed-icon" data-ed="' + key + '" aria-label="' + label +
        '" title="' + label + '">' + editorIcon(key) + '</button>';
    $('#main').innerHTML = '<div class="ed" id="editor-page">' +
        '<header class="ed-bar"><label class="ed-field">Editing:<input id="ed-path" readonly value="public_html/' + esc(location) + '"></label>' +
        '<label class="ed-field">Encoding:<select id="ed-encoding" title="almaPanel edits files as UTF-8 text"><option value="utf-8">utf-8</option></select></label>' +
        '<button type="button" class="subtle" id="ed-reopen">Re-open</button>' +
        '<p id="ed-status" class="ed-status" role="status" data-editor-status></p>' +
        '<button type="button" id="ed-save">Save Changes</button><button type="button" class="subtle" id="ed-close">Close</button></header>' +
        '<div class="ed-tools" role="toolbar" aria-label="Editor tools">' +
        '<button type="button" class="ed-link" id="ed-help">Keyboard shortcuts</button>' +
        '<div class="ed-group">' + tool('find', 'Find and replace (Ctrl+F)') + tool('goto', 'Go to line (Ctrl+G)') + '</div>' +
        '<div class="ed-group">' + tool('undo', 'Undo (Ctrl+Z)') + tool('redo', 'Redo (Ctrl+Y)') + '</div>' +
        tool('wrap', 'Wrap long lines (Alt+Z)') +
        '<select id="ed-font" aria-label="Font size">' + editorFontSizes.map(size => '<option value="' + size + '">' + size + 'px</option>').join('') + '</select>' +
        '<select id="ed-language" aria-label="Highlighting mode">' + Object.entries(codeLanguages).map(([key, label]) =>
            '<option value="' + key + '">' + label + '</option>').join('') + '</select>' +
        '<span id="ed-cursor" class="ed-cursor"></span></div>' +
        '<form class="ed-find" id="ed-find" role="search" hidden><input name="find" aria-label="Find" placeholder="Find" maxlength="1000">' +
        '<input name="replace" aria-label="Replace with" placeholder="Replace with" maxlength="1000">' +
        '<label class="file-check"><input type="checkbox" name="matchCase"> Match case</label>' +
        '<button type="submit">Next</button><button type="button" class="subtle" data-find="previous">Previous</button>' +
        '<button type="button" class="subtle" data-find="replace">Replace</button><button type="button" class="subtle" data-find="all">Replace all</button>' +
        '<span id="ed-matches" role="status"></span><button type="button" class="subtle" data-find="close" aria-label="Close find">×</button></form>' +
        '<div class="ed-body"><div class="ed-gutter" aria-hidden="true"><div class="ed-lines"></div></div>' +
        '<div class="source-editor ed-source"><pre aria-hidden="true"><code></code></pre>' +
        '<textarea aria-label="File contents" spellcheck="false" autocapitalize="off" autocomplete="off"></textarea>' +
        '<div class="ed-measure" aria-hidden="true"></div></div></div></div>';
    const page = $('#editor-page');
    const input = page.querySelector('textarea');
    const frame = input.parentElement;
    const preview = frame.querySelector('pre');
    const gutter = page.querySelector('.ed-gutter');
    const lines = page.querySelector('.ed-lines');
    const measure = page.querySelector('.ed-measure');
    const findForm = $('#ed-find');
    const saveButton = $('#ed-save');
    const languageField = $('#ed-language');
    const fontField = $('#ed-font');
    let bom = '';
    let eol = '\n';
    let revision = '';
    let saved = '';
    let editable = false;
    let saving = false;
    let scheduled = false;
    let lineCount = 0;
    let measuredFor = '';
    let currentLine = -1;
    let tabLeavesEditor = false;
    const dirty = () => editable && input.value !== saved;
    fileViewHasUnsavedChanges = () => active() && dirty();
    closeFileView = () => { fileViewHasUnsavedChanges = () => false; };
    languageField.value = Object.hasOwn(codeExtensions, extension) ? codeExtensions[extension] : 'text';
    fontField.value = editorFontSizes.includes(Number(prefs.fontSize)) ? prefs.fontSize : 13;

    const setStatus = text => { $('#ed-status').textContent = text; };
    const storePrefs = () => {
        try { localStorage.setItem(editorPrefsKey, JSON.stringify({wrap: prefs.wrap, fontSize: Number(fontField.value)})); }
        catch { /* Preferences are per browser only. */ }
    };

    function applyView() {
        page.classList.toggle('wrap', prefs.wrap);
        input.wrap = prefs.wrap ? 'soft' : 'off';
        page.style.setProperty('--ed-font', fontField.value + 'px');
        const wrap = page.querySelector('[data-ed=wrap]');
        wrap.setAttribute('aria-pressed', String(prefs.wrap));
        measuredFor = '';
        update();
    }

    // Line numbers: one row per source line; wrapped lines take their measured height.
    function renderGutter() {
        const value = input.value;
        let count = 1;
        for (let index = value.indexOf('\n'); index !== -1; index = value.indexOf('\n', index + 1)) count += 1;
        if (count !== lineCount) {
            const fragment = document.createDocumentFragment();
            for (let line = 1; line <= count; line += 1) {
                const row = document.createElement('div');
                row.textContent = line;
                fragment.append(row);
            }
            lines.replaceChildren(fragment);
            lineCount = count;
            currentLine = -1;
            measuredFor = '';
        }
        const key = prefs.wrap ? value + '\u0000' + input.clientWidth + '\u0000' + fontField.value : 'nowrap';
        if (key !== measuredFor) {
            measuredFor = key;
            if (prefs.wrap) {
                measure.style.width = input.clientWidth + 'px';
                const fragment = document.createDocumentFragment();
                for (const text of value.split('\n')) {
                    const row = document.createElement('div');
                    row.textContent = text || ' ';
                    fragment.append(row);
                }
                measure.replaceChildren(fragment);
                const heights = [...measure.children].map(row => row.getBoundingClientRect().height);
                measure.replaceChildren();
                [...lines.children].forEach((row, index) => { row.style.height = heights[index] + 'px'; });
            } else {
                for (const row of lines.children) row.style.height = '';
            }
        }
    }

    function syncScroll() {
        preview.scrollTop = input.scrollTop;
        preview.scrollLeft = input.scrollLeft;
        gutter.scrollTop = input.scrollTop;
    }

    function update() {
        if (scheduled) return;
        scheduled = true;
        requestAnimationFrame(() => {
            scheduled = false;
            if (!input.isConnected) return;
            // Keep the highlight layer the same size as the text area's visible text.
            preview.style.right = (input.offsetWidth - input.clientWidth) + 'px';
            preview.style.bottom = (input.offsetHeight - input.clientHeight) + 'px';
            frame.classList.toggle('highlighted', paintSource(input.value, languageField.value, preview.firstElementChild));
            renderGutter();
            const prefix = input.value.slice(0, input.selectionStart);
            const line = prefix.split('\n').length;
            if (line !== currentLine) {
                lines.children[currentLine - 1]?.classList.remove('current');
                lines.children[line - 1]?.classList.add('current');
                currentLine = line;
            }
            $('#ed-cursor').textContent = 'Line ' + line + ', column ' + (prefix.length - prefix.lastIndexOf('\n')) +
                ' · ' + lineCount + (lineCount === 1 ? ' line' : ' lines');
            document.title = (dirty() ? '● ' : '') + name + ' · Editor · almaPanel';
            saveButton.classList.toggle('pending', dirty());
            syncScroll();
        });
    }

    function scrollToCaret() {
        renderGutter();
        const line = input.value.slice(0, input.selectionStart).split('\n').length;
        const row = lines.children[line - 1];
        if (row) {
            const top = row.offsetTop;
            if (top < input.scrollTop || top + row.offsetHeight > input.scrollTop + input.clientHeight) {
                input.scrollTop = Math.max(0, top - input.clientHeight / 3);
            }
        }
        update();
    }

    function select(start, end) {
        input.focus();
        input.setSelectionRange(start, end);
        scrollToCaret();
    }

    // Replace text through the browser's editing commands so Undo still works.
    function insertText(text) {
        input.focus();
        if (!document.execCommand('insertText', false, text)) input.setRangeText(text, input.selectionStart, input.selectionEnd, 'end');
        update();
    }

    async function loadFile() {
        editable = false;
        input.readOnly = true;
        saveButton.disabled = true;
        if (create) {
            bom = '';
            eol = '\n';
            revision = '';
            input.value = saved = '';
            setStatus('New file. Save Changes creates it.');
        } else {
            setStatus('Opening file…');
            const result = await filePath(path, 'read', {path: location});
            if (!active()) return;
            let source;
            try {
                source = new TextDecoder('utf-8', {fatal: true, ignoreBOM: true}).decode(
                    Uint8Array.from(atob(result.content), character => character.charCodeAt(0)));
                if (/[\u0000-\u0008\u000e-\u001a]/.test(source)) throw Error('Binary data');
            } catch {
                throw Error('This file is not UTF-8 text. Download it from File Manager instead.');
            }
            bom = source.charCodeAt(0) === 0xfeff ? '﻿' : '';
            const original = bom ? source.slice(1) : source;
            eol = original.includes('\r\n') && !original.replaceAll('\r\n', '').includes('\n') ? '\r\n' : '\n';
            input.value = original;
            saved = input.value;
            revision = result.revision;
            setStatus('Opened.');
        }
        editable = true;
        input.readOnly = false;
        saveButton.disabled = false;
        input.setSelectionRange(0, 0);
        input.scrollTop = 0;
        input.focus();
        update();
    }

    async function save() {
        if (saving || !editable) return;
        saving = true;
        saveButton.disabled = true;
        setStatus('Saving…');
        try {
            const value = input.value;
            const bytes = new TextEncoder().encode(bom + value.replaceAll('\n', eol));
            if (bytes.length > 1048576) throw Error('The editor supports files up to 1 MiB.');
            const result = await filePath(path, 'write', {path: location, content: bytesToBase64(bytes),
                create_only: create, ...(create ? {} : {expected_revision: revision})});
            revision = result.revision;
            saved = value;
            if (create) {
                create = false;
                history.replaceState(null, '', editorUrl(account.id, location));
            }
            setStatus(result.message);
            fileChannel?.postMessage({account: account.id, folder: parentFilePath(location)});
        } catch (error) {
            setStatus(error.message);
        } finally {
            saving = false;
            saveButton.disabled = !editable;
            update();
        }
    }

    async function closeEditor() {
        if (dirty() && !await confirmed('Close without saving your changes?')) return;
        editable = false;
        fileViewHasUnsavedChanges = () => false;
        window.close();
        // Tabs the browser will not close (for example one opened by hand) return to File Manager.
        setTimeout(() => { if (!window.closed) location.hash = fileManagerUrl(parentFilePath(location)); }, 200);
    }

    function findNext(backwards = false) {
        const needle = findForm.elements.find.value;
        const counter = $('#ed-matches');
        if (!needle) { counter.textContent = ''; return false; }
        const matchCase = findForm.elements.matchCase.checked;
        const text = matchCase ? input.value : input.value.toLowerCase();
        const target = matchCase ? needle : needle.toLowerCase();
        let index = backwards ? text.lastIndexOf(target, input.selectionStart - 1) : text.indexOf(target, input.selectionEnd);
        if (index === -1) index = backwards ? text.lastIndexOf(target) : text.indexOf(target);  // Wrap around.
        let total = 0;
        for (let at = text.indexOf(target); at !== -1 && total < 10000; at = text.indexOf(target, at + target.length)) total += 1;
        if (index === -1) {
            counter.textContent = 'No matches';
            return false;
        }
        counter.textContent = total + (total === 1 ? ' match' : ' matches');
        select(index, index + needle.length);
        findForm.elements.find.focus();
        return true;
    }

    function selectionMatches() {
        const needle = findForm.elements.find.value;
        const chosen = input.value.slice(input.selectionStart, input.selectionEnd);
        return needle && (findForm.elements.matchCase.checked ? chosen === needle : chosen.toLowerCase() === needle.toLowerCase());
    }

    function openFind(focusReplace = false) {
        findForm.hidden = false;
        const chosen = input.value.slice(input.selectionStart, input.selectionEnd);
        if (chosen && !chosen.includes('\n')) findForm.elements.find.value = chosen;
        const field = focusReplace ? findForm.elements.replace : findForm.elements.find;
        field.focus();
        field.select();
    }

    function closeFind() {
        findForm.hidden = true;
        $('#ed-matches').textContent = '';
        input.focus();
    }

    function goToLine() {
        const form = fileDialog('Go to line', '<label>Line number (1–' + lineCount + ')<input name="line" type="number" required min="1" max="' +
            lineCount + '" value="' + Math.max(1, currentLine) + '"></label>', 'Go', fields => {
            const target = Math.min(lineCount, Math.max(1, Math.round(Number(fields.line))));
            let offset = 0;
            for (let line = 1; line < target; line += 1) offset = input.value.indexOf('\n', offset) + 1;
            select(offset, offset);
        });
        form.elements.line.select();
    }

    function showShortcuts() {
        const shortcuts = [['Ctrl+S', 'Save changes'], ['Ctrl+F', 'Find'], ['Ctrl+H', 'Find and replace'],
            ['Enter / Shift+Enter in Find', 'Next / previous match'], ['Ctrl+G', 'Go to line'], ['Ctrl+Z', 'Undo'],
            ['Ctrl+Y or Ctrl+Shift+Z', 'Redo'], ['Alt+Z', 'Turn line wrapping on or off'], ['Tab', 'Insert a tab'],
            ['Esc, then Tab', 'Move keyboard focus out of the editor'], ['Esc', 'Close Find']];
        const dialog = document.createElement('dialog');
        dialog.className = 'file-dialog';
        dialog.setAttribute('aria-labelledby', 'ed-shortcuts-title');
        dialog.innerHTML = '<form method="dialog"><h2 id="ed-shortcuts-title">Keyboard shortcuts</h2>' +
            '<p class="muted">On macOS, use Cmd instead of Ctrl.</p>' +
            table(['Keys', 'Action'], shortcuts.map(([keys, action]) => ['<kbd>' + esc(keys) + '</kbd>', esc(action)])) +
            '<div class="actions"><button>Close</button></div></form>';
        dialog.addEventListener('close', () => { dialog.remove(); input.focus(); }, {once: true});
        $('#main').append(dialog);
        dialog.showModal();
    }

    input.addEventListener('input', update);
    for (const type of ['keyup', 'pointerup', 'select']) input.addEventListener(type, update);
    input.addEventListener('scroll', syncScroll);
    new ResizeObserver(() => { measuredFor = ''; update(); }).observe(input);
    languageField.onchange = update;
    fontField.onchange = () => { storePrefs(); applyView(); };
    $('#ed-save').onclick = save;
    $('#ed-close').onclick = closeEditor;
    $('#ed-help').onclick = showShortcuts;
    $('#ed-reopen').onclick = async () => {
        if (dirty() && !await confirmed('Discard your changes and reload the file from the server?')) return;
        try { await loadFile(); } catch (error) { setStatus(error.message); }
    };
    page.querySelector('.ed-tools').addEventListener('click', event => {
        const button = event.target.closest('[data-ed]');
        if (!button) return;
        const action = button.dataset.ed;
        if (action === 'find') findForm.hidden ? openFind() : closeFind();
        else if (action === 'goto') goToLine();
        else if (action === 'undo' || action === 'redo') { input.focus(); document.execCommand(action); update(); }
        else if (action === 'wrap') { prefs.wrap = !prefs.wrap; storePrefs(); applyView(); }
    });
    findForm.onsubmit = event => { event.preventDefault(); findNext(); };
    findForm.addEventListener('click', event => {
        const action = event.target.closest('[data-find]')?.dataset.find;
        if (action === 'previous') findNext(true);
        else if (action === 'close') closeFind();
        else if (action === 'replace' && editable) {
            if (selectionMatches()) insertText(findForm.elements.replace.value);
            findNext();
        } else if (action === 'all' && editable) {
            const needle = findForm.elements.find.value;
            if (!needle) return;
            const flags = findForm.elements.matchCase.checked ? 'g' : 'gi';
            const pattern = new RegExp(needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), flags);
            const count = (input.value.match(pattern) || []).length;
            if (!count) { $('#ed-matches').textContent = 'No matches'; return; }
            const replaced = input.value.replace(pattern, () => findForm.elements.replace.value);
            input.focus();
            input.setSelectionRange(0, input.value.length);
            insertText(replaced);
            input.setSelectionRange(0, 0);
            $('#ed-matches').textContent = 'Replaced ' + count + (count === 1 ? ' match' : ' matches');
        }
    });
    findForm.addEventListener('keydown', event => {
        if (event.key === 'Escape') { event.preventDefault(); closeFind(); }
        else if (event.key === 'Enter' && event.shiftKey) { event.preventDefault(); findNext(true); }
    });
    input.addEventListener('keydown', event => {
        if (event.key === 'Escape') { tabLeavesEditor = true; return; }
        if (event.key === 'Tab' && !event.ctrlKey && !event.altKey && !event.metaKey) {
            if (tabLeavesEditor || event.shiftKey || !editable) { tabLeavesEditor = false; return; }
            event.preventDefault();
            insertText('\t');
        }
        tabLeavesEditor = false;
    });
    page.addEventListener('keydown', event => {
        const key = event.key.toLowerCase();
        const command = event.ctrlKey || event.metaKey;
        if (command && key === 's') { event.preventDefault(); save(); }
        else if (command && key === 'f') { event.preventDefault(); openFind(); }
        else if (command && key === 'h') { event.preventDefault(); openFind(true); }
        else if (command && key === 'g') { event.preventDefault(); goToLine(); }
        else if (event.altKey && key === 'z') { event.preventDefault(); prefs.wrap = !prefs.wrap; storePrefs(); applyView(); }
    });

    applyView();
    try {
        await loadFile();
    } catch (error) {
        if (!active()) return;
        setStatus(error.message);
        input.value = '';
        input.placeholder = error.message;
        update();
    }
}

const mediaFiles = {
    png: ['image/png', data => data[0] === 137 && mediaTag(data, 1, 'PNG')],
    jpg: ['image/jpeg', data => data[0] === 255 && data[1] === 216 && data[2] === 255],
    jpeg: ['image/jpeg', data => data[0] === 255 && data[1] === 216 && data[2] === 255],
    gif: ['image/gif', data => mediaTag(data, 0, 'GIF87a') || mediaTag(data, 0, 'GIF89a')],
    webp: ['image/webp', data => mediaTag(data, 0, 'RIFF') && mediaTag(data, 8, 'WEBP')],
    mp3: ['audio/mpeg', data => mediaTag(data, 0, 'ID3') || (data[0] === 255 && (data[1] & 224) === 224)],
    wav: ['audio/wav', data => mediaTag(data, 0, 'RIFF') && mediaTag(data, 8, 'WAVE')],
    ogg: ['audio/ogg', data => mediaTag(data, 0, 'OggS')],
    mp4: ['video/mp4', data => mediaTag(data, 4, 'ftyp')],
    webm: ['video/webm', data => data[0] === 26 && data[1] === 69 && data[2] === 223 && data[3] === 163]
};

function mediaTag(bytes, offset, tag) {
    return [...tag].every((letter, index) => bytes[offset + index] === letter.charCodeAt(0));
}

async function showFileMedia(panel, name, media, parts, signal, saveImage) {
    const [type, matches] = media;
    if (!matches(parts[0])) throw Error('The file header does not match this media format. Use Download.');
    const kind = type.split('/')[0];
    const player = document.createElement(kind === 'image' ? 'img' : kind);
    player.className = 'file-preview';
    if (kind === 'image') player.alt = name;
    else {
        player.controls = true;
        player.preload = 'metadata';
        player.setAttribute('aria-label', name);
    }
    const url = URL.createObjectURL(new Blob(parts, {type}));
    signal.addEventListener('abort', () => URL.revokeObjectURL(url), {once: true});
    const error = document.createElement('p');
    error.setAttribute('role', 'status');
    player.onerror = () => { error.textContent = 'This browser could not decode the file. Use Download.'; };
    player.src = url;
    panel.replaceChildren(player, error);
    if (kind === 'image') {
        try { await player.decode(); }
        catch { return; }
        if (!signal.aborted) imageOptions(panel, name, player, saveImage);
    }
}

function imageOptions(panel, name, image, save) {
    const form = document.createElement('form');
    form.className = 'image-tools';
    form.innerHTML = '<p>' + image.naturalWidth + ' × ' + image.naturalHeight + ' pixels</p>' +
        '<div class="compact">' +
        '<label>Width (pixels)<input name="width" type="number" required min="1" max="8192"></label>' +
        '<label>Height (pixels)<input name="height" type="number" required min="1" max="8192"></label>' +
        '<label>Output format<select name="format"><option value="png">PNG</option><option value="jpeg">JPEG</option>' +
        '<option value="webp">WebP</option></select></label>' +
        '<label>Save as<input name="filename" required maxlength="255"></label></div>' +
        '<label class="file-check"><input type="checkbox" name="ratio" checked> Keep aspect ratio</label>' +
        '<div><button type="submit">Save image copy</button></div><p data-image-status role="status"></p>';
    const fields = form.elements;
    const defaultName = name.replace(/\.[^.]+$/, '') + '-resized';
    const refreshName = () => {
        fields.filename.value = defaultName + '.' + (fields.format.value === 'jpeg' ? 'jpg' : fields.format.value);
    };
    fields.width.value = image.naturalWidth;
    fields.height.value = image.naturalHeight;
    fields.format.onchange = refreshName;
    fields.width.oninput = () => {
        if (fields.ratio.checked) fields.height.value = Math.round(fields.width.value * image.naturalHeight / image.naturalWidth);
    };
    fields.height.oninput = () => {
        if (fields.ratio.checked) fields.width.value = Math.round(fields.height.value * image.naturalWidth / image.naturalHeight);
    };
    refreshName();
    form.onsubmit = async event => {
        event.preventDefault();
        const width = fields.width.valueAsNumber;
        const height = fields.height.valueAsNumber;
        const status = form.querySelector('[data-image-status]');
        const button = form.querySelector('button');
        const filename = fields.filename.value;
        const mime = 'image/' + fields.format.value;
        if (width * height > 16000000) {
            status.textContent = 'Choose an output of 16 megapixels or less.';
            return;
        }
        button.disabled = true;
        status.textContent = 'Creating image…';
        const canvas = document.createElement('canvas');
        try {
            canvas.width = width;
            canvas.height = height;
            const context = canvas.getContext('2d');
            if (!context) throw Error('The browser could not allocate an image canvas.');
            if (mime === 'image/jpeg') {
                context.fillStyle = '#ffffff';
                context.fillRect(0, 0, width, height);
            }
            context.drawImage(image, 0, 0, width, height);
            const output = await new Promise(resolve => canvas.toBlob(resolve, mime, 0.92));
            if (!output || output.type !== mime) throw Error('This browser cannot encode the selected format.');
            await save(output, filename);
            status.textContent = 'Image saved.';
        } catch (error) {
            status.textContent = error.message;
        } finally {
            canvas.width = canvas.height = 0;
            button.disabled = false;
        }
    };
    panel.append(form);
}
