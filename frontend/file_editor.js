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

function mountFileEditor(panel, location, source, save) {
    const extension = location.split('.').at(-1).toLowerCase();
    const language = Object.hasOwn(codeExtensions, extension) ? codeExtensions[extension] : 'text';
    const bom = source.charCodeAt(0) === 0xfeff ? '\ufeff' : '';
    const original = bom ? source.slice(1) : source;
    const eol = original.includes('\r\n') && !original.replaceAll('\r\n', '').includes('\n') ? '\r\n' : '\n';
    panel.innerHTML = '<form class="file-editor-form"><div class="toolbar">' +
        '<button type="submit">Save file</button><label>Language<select name="language">' +
        Object.entries(codeLanguages).map(([key, label]) =>
            '<option value="' + key + '">' + label + '</option>').join('') +
        '</select></label><span class="muted" data-cursor></span></div>' +
        '<div class="source-editor"><pre aria-hidden="true"><code></code></pre>' +
        '<textarea aria-label="File contents" name="content" spellcheck="false" autocapitalize="off" autocomplete="off" wrap="off"></textarea></div>' +
        '<p data-editor-status role="status" class="muted"></p></form>';
    const form = panel.querySelector('form');
    const input = form.elements.content;
    const frame = input.parentElement;
    const preview = frame.querySelector('pre');
    const button = form.querySelector('[type=submit]');
    const message = form.querySelector('[data-editor-status]');
    input.value = original;
    form.elements.language.value = language;
    let saved = input.value;
    let scheduled = false;
    const syncScroll = () => {
        preview.scrollTop = input.scrollTop;
        preview.scrollLeft = input.scrollLeft;
    };
    function update() {
        if (scheduled) return;
        scheduled = true;
        requestAnimationFrame(() => {
            scheduled = false;
            if (!frame.isConnected) return;
            frame.classList.toggle('highlighted', paintSource(input.value, form.elements.language.value, preview.firstElementChild));
            syncScroll();
            const prefix = input.value.slice(0, input.selectionStart);
            form.querySelector('[data-cursor]').textContent =
                'Line ' + prefix.split('\n').length + ', column ' + (prefix.length - prefix.lastIndexOf('\n'));
        });
    }
    input.oninput = input.onkeyup = input.onpointerup = input.onselect = update;
    input.onscroll = syncScroll;
    form.elements.language.onchange = update;
    input.onkeydown = event => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
            event.preventDefault();
            if (!button.disabled) form.requestSubmit();
        }
    };
    form.onsubmit = async event => {
        event.preventDefault();
        if (button.disabled) return;
        button.disabled = true;
        message.textContent = 'Saving…';
        try {
            const value = input.value;
            const bytes = new TextEncoder().encode(bom + value.replaceAll('\n', eol));
            if (bytes.length > 1048576) throw Error('The text editor supports files up to 1 MiB.');
            const result = await save(bytes);
            saved = value;
            message.textContent = result.message;
        } catch (error) {
            message.textContent = error.message;
        } finally {
            button.disabled = false;
        }
    };
    update();
    requestAnimationFrame(() => { if (input.isConnected) input.focus(); });
    return () => input.value !== saved;
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
