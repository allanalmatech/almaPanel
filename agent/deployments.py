# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Read-only Git fetches and source releases, run only as the hosting UID."""
import os
from pathlib import Path
import re
import resource
import subprocess
import tempfile
from urllib.parse import urlsplit

if __package__:
    from . import file_tools as files
else:
    import file_tools as files

HOSTS = {'github.com', 'gitlab.com', 'bitbucket.org'}
SEGMENT = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z')
BRANCH = re.compile(r'[A-Za-z0-9][A-Za-z0-9_./-]{0,127}\Z')


def source_repository(value):
    if not isinstance(value, str) or len(value) > 350:
        raise ValueError('Invalid repository URL.')
    url = urlsplit(value)
    if url.scheme != 'https' or url.netloc not in HOSTS or url.query or url.fragment:
        raise ValueError('Use an HTTPS repository URL on GitHub, GitLab or Bitbucket.')
    parts = url.path.strip('/').split('/')
    if not 2 <= len(parts) <= 8 or not all(SEGMENT.fullmatch(part) for part in parts):
        raise ValueError('Invalid repository path.')
    if url.netloc in ('github.com', 'bitbucket.org') and len(parts) != 2:
        raise ValueError('Use the provider’s owner/repository URL.')
    repo = '/'.join(parts)
    return f'https://{url.netloc}/{repo}' + ('' if repo.endswith('.git') else '.git')


def branch_name(value):
    if (not isinstance(value, str) or not BRANCH.fullmatch(value) or
            '..' in value or '//' in value or value.endswith(('/', '.')) or
            any(part.startswith('.') or part.endswith('.lock') for part in value.split('/'))):
        raise ValueError('Invalid Git branch name.')
    return value


def git(*args, cwd, stdout=subprocess.PIPE):
    env = {
        'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8',
        'HOME': '/nonexistent', 'XDG_CONFIG_HOME': '/nonexistent',
        'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
        'GIT_TERMINAL_PROMPT': '0', 'GIT_ALLOW_PROTOCOL': 'https',
        'GIT_PROTOCOL_FROM_USER': '0',
    }
    command = ['/usr/bin/git', '-c', 'http.followRedirects=false',
               '-c', 'http.sslVerify=true', '-c', 'core.hooksPath=/dev/null',
               '-c', 'fetch.fsckObjects=true', *args]
    try:
        result = subprocess.run(command, cwd=cwd, stdout=stdout, stderr=subprocess.DEVNULL,
                                timeout=65, check=True, env=env)
    except (OSError, subprocess.SubprocessError):
        raise ValueError('Git could not read the chosen public repository and branch.') from None
    return (result.stdout or b'').decode('utf-8').strip()


def release(root, request):
    repo = source_repository(request.get('repository'))
    branch = branch_name(request.get('branch', 'main'))
    destination = files.components(request.get('destination'))
    if not destination or any(part.startswith('.') for part in destination):
        raise ValueError('Choose a new visible folder for the Git release.')
    # There is no persistent checkout or tenant-supplied Git config. Use a new
    # private directory and an isolated bare repository for each fetch.
    soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
    file_limit = files.MAX_BYTES + 2 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_FSIZE, (min(soft, file_limit) if soft >= 0 else file_limit, hard))
    with tempfile.TemporaryDirectory(prefix='.alma-git-') as folder:
        work = Path(folder)
        git('init', '--bare', '--template=', cwd=work)
        git('fetch', '--depth=1', '--no-tags', '--no-recurse-submodules',
            repo, 'refs/heads/' + branch, cwd=work)
        commit = git('rev-parse', '--verify', 'FETCH_HEAD^{commit}', cwd=work)
        if not re.fullmatch('[a-f0-9]{40,64}', commit):
            raise ValueError('Invalid fetched commit.')
        # Git's generated ZIP can contain symlinks. The unpacker refuses them.
        # A file-size resource limit protects the output while Git writes it.
        with (work / 'release.zip').open('xb') as archive:
            git('archive', '--format=zip', commit, cwd=work, stdout=archive)
        parent = os.open(work, files.NOFOLLOW_DIR)
        try:
            files.extract_zip(parent, ['release.zip'], root, destination)
        finally:
            os.close(parent)
    return {'message': 'Git source staged in a new folder.', 'commit': commit,
            'path': '/'.join(destination), 'repository': repo, 'branch': branch}
