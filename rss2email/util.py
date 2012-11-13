# Copyright

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
