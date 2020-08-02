# Copyright (C) 2013-2020 Arun Persaud <apersaud@lbl.gov>
#                         Etienne Millon <me@emillon.org>
#                         Léo Gaspard <leo@gaspard.io>
#                         Profpatsch <mail@profpatsch.de>
#                         W. Trevor King <wking@tremily.us>
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

"""Simple example for a post-process filter in rss2email

A post-process call can be used to change the content of each entry
before rss2email sends the email out. Using this you can add filters to
rss2email that, for example, remove advertising or links to
Facebook/Google+ or other unwanted information. Or you could add those
links in case you want them. ;)

A hook is added by defining the variable ``post-process`` in the
config file. It takes two arguments, the module and the function to
call. For example::

  post-process = rss2email.post_process.prettify process

There's nothing special about the ``rss2email.post_process`` package.
If you write your own post-processing hooks, you can put them in any
package you like. If Python can run::

  from some.package import some_hook

then you can use::

  post-process = some.package some_hook

This means that your hook can live in any package in your
``PYTHONPATH``, in a package in your per-user site-packages
(:pep:`307`), etc

The hook function itself has 5 arguments: ``feed``, ``parsed``,
``entry``, ``guid``, ``message`` and needs to return a ``message`` or
``None`` to skip the feed item.

The post-process variable can be defined globally or on a per-feed basis.

Examples in this file:

pretty
  a filter that prettifies the html

process
  the actual post_process function that you need to call in
  the config file
"""


# import modules you need
from bs4 import BeautifulSoup
import rss2email.email


def pretty(feed, parsed, entry, guid, message):
    """Use BeautifulSoup to pretty-print the html

    A very simple function that decodes the entry into a unicode
    string and then calls BeautifulSoup on it and afterwards encodes
    the feed entry
    """
    # decode message
    encoding = message.get_charsets()[0]
    content = str(message.get_payload(decode=True), encoding)

    # modify content
    soup = BeautifulSoup(content)
    content = soup.prettify()

    # BeautifulSoup uses unicode, so we perhaps have to adjust the encoding.
    # It's easy to get into encoding problems and this step will prevent
    # them ;)
    encoding = rss2email.email.guess_encoding(content, encodings=feed.encodings)

    # clear CTE and set message. It can be important to clear the CTE
    # before setting the payload, since the payload is only re-encoded
    # if CTE is not already set.
    del message['Content-Transfer-Encoding']
    message.set_payload(content, charset=encoding)
    return message


def process(feed, parsed, entry, guid, message):
    message = pretty(feed, parsed, entry, guid, message)
    # you could add several filters in here if you want to

    # we need to return the message, if we return False,
    # the feed item will be skipped
    return message
