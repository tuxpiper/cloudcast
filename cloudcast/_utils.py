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