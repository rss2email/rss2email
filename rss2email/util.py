# Copyright (C) 2012-2013 W. Trevor King <wking@tremily.us>
#
# This file is part of rss2email.
#
# rss2email is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 2 of the License, or (at your option) version 3 of
# the License.
#
# rss2email is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# rss2email.  If not, see <http://www.gnu.org/licenses/>.

"""Odds and ends
"""

import sys as _sys
import threading as _threading

from . import error as _error


class TimeLimitedFunction (_threading.Thread):
    """Run `function` with a time limit of `timeout` seconds.

    >>> import time
    >>> def sleeping_return(sleep, x):
    ...     time.sleep(sleep)
    ...     return x
    >>> TimeLimitedFunction(0.5, sleeping_return)(0.1, 'x')
    'x'
    >>> TimeLimitedFunction(0.5, sleeping_return)(10, 'y')
    Traceback (most recent call last):
      ...
    rss2email.error.TimeoutError: 0.5 second timeout exceeded
    >>> TimeLimitedFunction(0.5, time.sleep)('x')
    Traceback (most recent call last):
      ...
    rss2email.error.TimeoutError: error while running time limited function: a float is required
    """
    def __init__(self, timeout, target, **kwargs):
        super(TimeLimitedFunction, self).__init__(target=target, **kwargs)
        self.setDaemon(True)  # daemon kwarg only added in Python 3.3.
        self.timeout = timeout
        self.result = None
        self.error = None

    def run(self):
        """Based on Thread.run().

        We add handling for self.result and self.error.
        """
        try:
            if self._target:
                self.result = self._target(*self._args, **self._kwargs)
        except:
            self.error = _sys.exc_info()
        finally:
            # Avoid a refcycle if the thread is running a function with
            # an argument that has a member that points to the thread.
            del self._target, self._args, self._kwargs

    def __call__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        self.start()
        self.join(self.timeout)
        if self.error:
            raise _error.TimeoutError(
                time_limited_function=self) from self.error[1]
        elif self.isAlive():
            raise _error.TimeoutError(time_limited_function=self)
        return self.result
