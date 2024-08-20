"""
 * @file timestamp.py
 * @author Remy Nguyen (rnguyen@nrao.edu)
 * @brief Prepends a timestamp to print function. Use _print to print without timestamp.
 * 
 * @date Last Modified: 2024-08-20
 * 
 * @copyright Copyright (c) 2024
 * 
 """

import time

_print = print
def print(*args, **kw):
    _print("[%s]" % (time.strftime("%Y-%m-%d %H:%M:%S")),*args, **kw)
