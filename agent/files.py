# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Run only after dropping supplementary groups and UID to the hosting user.
Every traversal uses directory descriptors and O_NOFOLLOW; no resolve/check/use race.
"""
import base64
import json
import os
from pathlib import PurePosixPath
import secrets
import stat
import sys

MAX_FILE = 1024*1024

def components(path):
    if not isinstance(path,str) or len(path)>2048 or '\x00' in path:
        raise ValueError('Invalid path.')
    p=PurePosixPath(path)
    if p.is_absolute() or any(x in ('.','..') for x in path.split('/')):
        raise ValueError('Path must stay inside public_html.')
    return [x for x in path.split('/') if x]

def directory(root, parts):
    fd=os.dup(root)
    try:
        for part in parts:
            next_fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=next_fd
        return fd
    except BaseException:
        os.close(fd);raise

def regular(fd):
    s=os.fstat(fd)
    if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1:
        raise ValueError('Only regular, non-hardlinked files are supported.')
    return s

def operate(root, request):
    parts=components(request.get('path',''))
    action=request.get('action')
    if action=='list':
        fd=directory(root,parts)
        try:
            result=[]
            names=sorted(os.listdir(fd))
            if len(names)>5000:
                raise ValueError('Directory exceeds 5000-entry browsing limit.')
            for item in names:
                s=os.stat(item,dir_fd=fd,follow_symlinks=False)
                result.append({'name':item,'size':s.st_size,'mode':oct(stat.S_IMODE(s.st_mode)),
                               'uid':s.st_uid,'directory':stat.S_ISDIR(s.st_mode),'symlink':stat.S_ISLNK(s.st_mode)})
            return result
        finally: os.close(fd)
    if not parts:
        raise ValueError('Select a file or folder.')
    parent=directory(root,parts[:-1]);leaf=parts[-1]
    try:
        if action=='read':
            fd=os.open(leaf,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
            with os.fdopen(fd,'rb') as f:
                if regular(f.fileno()).st_size>MAX_FILE: raise ValueError('File exceeds 1 MB.')
                data=f.read(MAX_FILE+1)
                if len(data)>MAX_FILE: raise ValueError('File exceeds 1 MB.')
                return {'content':base64.b64encode(data).decode()}
        if action=='write':
            data=base64.b64decode(request.get('content',''),validate=True)
            if len(data)>MAX_FILE: raise ValueError('File exceeds 1 MB.')
            # Atomic replacement does not follow a symlink at the destination.
            try:
                s=os.stat(leaf,dir_fd=parent,follow_symlinks=False)
                if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1: raise ValueError('Unsafe destination.')
            except FileNotFoundError: pass
            tmp='.alma-'+secrets.token_hex(16)
            fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o640,dir_fd=parent)
            try:
                with os.fdopen(fd,'wb') as f: f.write(data);f.flush();os.fsync(f.fileno())
                os.rename(tmp,leaf,src_dir_fd=parent,dst_dir_fd=parent)
            finally:
                try: os.unlink(tmp,dir_fd=parent)
                except FileNotFoundError: pass
            return {'message':'File saved.'}
        if action=='mkdir':
            os.mkdir(leaf,0o750,dir_fd=parent);return {'message':'Folder created.'}
        if action=='rename':
            dest=components(request.get('destination',''))
            if not dest: raise ValueError('Destination required.')
            other=directory(root,dest[:-1])
            try:
                # No replacement of existing objects; Linux renameat2 NOREPLACE.
                import ctypes
                libc=ctypes.CDLL(None,use_errno=True)
                if libc.renameat2(parent,os.fsencode(leaf),other,os.fsencode(dest[-1]),1)!=0:
                    err=ctypes.get_errno();raise OSError(err,os.strerror(err))
            finally: os.close(other)
            return {'message':'Renamed.'}
        if action == 'copy':
            destination = components(request.get('destination', ''))
            if not destination:
                raise ValueError('Destination required.')
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            with os.fdopen(fd, 'rb') as source:
                if regular(source.fileno()).st_size > MAX_FILE:
                    raise ValueError('File exceeds 1 MB.')
                content = source.read(MAX_FILE + 1)
                if len(content) > MAX_FILE:
                    raise ValueError('File exceeds 1 MB.')
            target = directory(root, destination[:-1])
            try:
                output = os.open(destination[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o640, dir_fd=target)
                try:
                    with os.fdopen(output, 'wb') as file:
                        file.write(content)
                        file.flush()
                        os.fsync(file.fileno())
                except OSError:
                    os.unlink(destination[-1], dir_fd=target)
                    raise
            finally:
                os.close(target)
            return {'message': 'File copied.'}
        if action=='delete':
            s=os.stat(leaf,dir_fd=parent,follow_symlinks=False)
            if stat.S_ISDIR(s.st_mode): os.rmdir(leaf,dir_fd=parent)
            else: os.unlink(leaf,dir_fd=parent)
            return {'message':'Deleted permanently.'}
        raise ValueError('Unsupported file operation.')
    finally: os.close(parent)

if __name__=='__main__':
    try:
        root=os.open(sys.argv[1],os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try: result=operate(root,json.loads(sys.stdin.buffer.read(1_500_001)))
        finally: os.close(root)
        print(json.dumps({'ok':True,'data':result}))
    except (OSError,ValueError,TypeError) as e:
        print(json.dumps({'ok':False,'error':str(e)}));sys.exit(1)
