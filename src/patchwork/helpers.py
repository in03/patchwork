import os
from copy import deepcopy


def blacklist_filter_dict(d: dict[str, str], fpl: list[str]) -> dict[str, str]:
    """
    Remove all items from `d` prefixed with a string matching a str in `fpl`

    Args:
        d (dict[str, str]): dictionary to operate on
        fpl (list[str]): list of forbidden prefixes used for blacklist

    Returns:
        dict[str, str]: return modified dictionary
    """

    d = deepcopy(d)

    for k in list(d.keys()):
        for fp in fpl:
            if k.startswith(fp):
                d.pop(k)
                break
    return d


def next_path(path_pattern):
    """
    Finds the next free path in an sequentially named list of files

    e.g. path_pattern = 'file-%s.txt':

    file-1.txt
    file-2.txt
    file-3.txt

    Runs in log(n) time where n is the number of existing files in sequence
    """
    i = 1

    # First do an exponential search
    while os.path.exists(path_pattern % i):
        i = i * 2

    # Result lies somewhere in the interval (i/2..i]
    # We call this interval (a..b] and narrow it down until a + 1 = b
    a, b = (i // 2, i)
    while a + 1 < b:
        c = (a + b) // 2 # interval midpoint
        a, b = (c, b) if os.path.exists(path_pattern % c) else (a, c)

    return path_pattern % b
