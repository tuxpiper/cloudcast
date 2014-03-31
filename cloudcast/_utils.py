import os.path

def caller_folder():
    """
    Returns the folder where the code of the caller's caller lives
    """
    import inspect
    caller_file = inspect.stack()[2][1]
    if os.path.exists(caller_file):
        return os.path.abspath(os.path.dirname(caller_file))
    else:
        return os.path.abspath(os.getcwd())

def search_file(filepath, *where):
    if not os.path.isabs(filepath):
        # Search relative to the caller, the stack and cwd
        search_paths = map(lambda x: os.path.join(x, filepath), where)
        for p in search_paths:
            if os.path.isfile(p):
                return p
        return None
    else:
        return filepath

def walk_values(obj):
    if type(obj) == dict:
        for v in obj.values():
            for vv in walk_values(v): yield vv
    elif type(obj) in [ list, tuple, set ]:
        for v in obj:
            for vv in walk_values(v): yield vv
    else:
        yield obj

from contextlib import contextmanager
@contextmanager
def in_mem_gzip_file(src_path, basename, mtime=0.0):
    from gzip import GzipFile
    from StringIO import StringIO
    stringbuf = StringIO()
    with open(src_path, "rb") as source:
        with GzipFile(filename=basename, mode="w", compresslevel=9, fileobj=stringbuf, mtime=mtime) as gz:
            gz.write(source.read())
    yield stringbuf
    stringbuf.close()

@contextmanager
def in_mem_gzip(contents, basename, mtime=0.0):
    from gzip import GzipFile
    from StringIO import StringIO
    stringbuf = StringIO()
    with GzipFile(filename=basename, mode="w", compresslevel=9, fileobj=stringbuf, mtime=mtime) as gz:
        gz.write(contents)
    yield stringbuf
    stringbuf.close()