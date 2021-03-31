# -*- coding: utf-8 -*-
# Copyright (C) 2004-2021 Aaron Swartz
#                         Amir Yalon <105565+amiryal@users.noreply.github.com>
#                         Amir Yalon <git@please.nospammail.net>
#                         Anders Damsgaard <anders@adamsgaard.dk>
#                         Andrey Zelenchuk <azelenchuk@parallels.com>
#                         Andrey Zelenchuk <azelenchuk@plesk.com>
#                         Brian Lalor
#                         Dean Jackson
#                         Dennis Keitzel <github@pinshot.net>
#                         Emil Oppeln-Bronikowski <emil@fuse.pl>
#                         Erik Hetzner
#                         Etienne Millon <me@emillon.org>
#                         George Saunders <georgesaunders@gmail.com>
#                         Gregory Soutade <gregory@soutade.fr>
#                         J. Lewis Muir <jlmuir@imca-cat.org>
#                         Jakub Wilk <jwilk@jwilk.net>
#                         Joey Hess
#                         Jonathan Kamens <jik@kamens.us>
#                         Kaashif Hymabaccus <kaashif@kaashif.co.uk>
#                         Karthikeyan Singaravelan <tir.karthi@gmail.com>
#                         Lindsey Smith <lindsey.smith@gmail.com>
#                         Léo Gaspard <leo@gaspard.io>
#                         Marcel Ackermann
#                         Martin 'Joey' Schulze
#                         Martin Monperrus <monperrus@users.noreply.github.com>
#                         Martin Vietz <git@martin.vietz.eu>
#                         Matej Cepl
#                         Notkea <pacien@users.noreply.github.com>
#                         Profpatsch <mail@profpatsch.de>
#                         W. Trevor King <wking@tremily.us>
#                         auouymous <5005204+auouymous@users.noreply.github.com>
#                         auouymous <au@qzx.com>
#                         shan3141 <xpoh434@users.noreply.github.com>
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

"""Define the ``Feed`` class for handling a single feed
"""

import calendar as _calendar
import collections as _collections
import platform
from email.message import Message
from email.mime.message import MIMEMessage as _MIMEMessage
from email.mime.multipart import MIMEMultipart as _MIMEMultipart
from email.utils import formataddr as _formataddr
from email.utils import formatdate as _formatdate
from email.utils import parseaddr as _parseaddr
import hashlib as _hashlib
import html.parser as _html_parser
import re as _re
import socket as _socket
import time as _time
import urllib.request as _urllib_request
import uuid as _uuid
import xml.sax as _sax
import xml.sax.saxutils as _saxutils
from functools import lru_cache
from typing import Optional, Dict, Any, Tuple

import feedparser as _feedparser
import html2text as _html2text
import html as _html

from . import __url__
from . import __version__
from . import LOG as _LOG
from . import config as _config
from . import email as _email
from . import error as _error
from . import util as _util


_urllib_request.install_opener(_urllib_request.build_opener())
_SOCKET_ERRORS = []
for e in ['error', 'herror', 'gaierror']:
    if hasattr(_socket, e):
        _SOCKET_ERRORS.append(getattr(_socket, e))
del e  # cleanup namespace
_SOCKET_ERRORS = tuple(_SOCKET_ERRORS)

# drv_libxml2 raises:
#   TypeError: 'str' does not support the buffer interface
_feedparser.PREFERRED_XML_PARSERS = []


class Feed (object):
    """Utility class for feed manipulation and storage.

    >>> import pickle
    >>> import sys
    >>> from .config import CONFIG

    >>> feed = Feed(
    ...    name='test-feed', url='http://example.com/feed.atom', to='a@b.com')
    >>> print(feed)
    test-feed (http://example.com/feed.atom -> a@b.com)
    >>> feed.section
    'feed.test-feed'
    >>> feed.from_email
    'user@rss2email.invalid'

    >>> feed.from_email = 'a@b.com'
    >>> feed.save_to_config()
    >>> feed.config.write(sys.stdout)  # doctest: +REPORT_UDIFF, +ELLIPSIS
    [DEFAULT]
    from = user@rss2email.invalid
    ...
    verbose = warning
    <BLANKLINE>
    [feed.test-feed]
    url = http://example.com/feed.atom
    from = a@b.com
    to = a@b.com
    <BLANKLINE>

    >>> feed.etag = 'dummy etag'
    >>> string = pickle.dumps(feed)
    >>> feed = pickle.loads(string)
    >>> feed.load_from_config(config=CONFIG)
    >>> feed.etag
    'dummy etag'
    >>> feed.url
    'http://example.com/feed.atom'

    Names can only contain letters, digits, and '._-'.  Here the
    invalid space causes an exception:

    >>> Feed(name='invalid name')
    Traceback (most recent call last):
      ...
    rss2email.error.InvalidFeedName: invalid feed name 'invalid name'

    However, you aren't restricted to ASCII letters:

    >>> Feed(name='Αθήνα')
    <Feed Αθήνα (None -> )>

    You must define a URL:

    >>> Feed(name='feed-without-a-url', to='a@b.com').run(send=False)
    Traceback (most recent call last):
      ...
    rss2email.error.InvalidFeedConfig: invalid feed configuration {'url': None}


    Cleanup `CONFIG`.

    >>> CONFIG['DEFAULT']['to'] = ''
    >>> test_section = CONFIG.pop('feed.test-feed')

    """
    _name_regexp = _re.compile(r'^[\w\d.-]+$')

    # saved/loaded from feed.dat using __getstate__/__setstate__.
    _dynamic_attributes = [
        'name',
        'etag',
        'modified',
        'seen',
        ]

    ## saved/loaded from ConfigParser instance
    # attributes that aren't in DEFAULT
    _non_default_configured_attributes = [
        'url',
        ]
    # attributes that are in DEFAULT
    _default_configured_attributes = [
        key.replace('-', '_') for key in _config.CONFIG['DEFAULT'].keys()]
    _default_configured_attributes[
        _default_configured_attributes.index('from')
        ] = 'from_email'  # `from` is a Python keyword
    _default_configured_attributes[
        _default_configured_attributes.index('user_agent')
        ] = '_user_agent'  # `user_agent` is a getter that does substitution
    # all attributes that are saved/loaded from .config
    _configured_attributes = (
        _non_default_configured_attributes + _default_configured_attributes)
    # attribute name -> .config option
    _configured_attribute_translations = dict(
        (attr,attr) for attr in _non_default_configured_attributes)
    _configured_attribute_translations.update(dict(
            zip(_default_configured_attributes,
                _config.CONFIG['DEFAULT'].keys())))
    # .config option -> attribute name
    _configured_attribute_inverse_translations = dict(
        (v,k) for k,v in _configured_attribute_translations.items())

    # hints for value conversion
    _boolean_attributes = [
        'digest',
        'force_from',
        'use_publisher_email',
        'active',
        'date_header',
        'trust_guid',
        'trust_link',
        'reply_changes',
        'html_mail',
        'use_css',
        'unicode_snob',
        'links_after_each_paragraph',
        'use_smtp',
        'smtp_ssl',
        ]

    _integer_attributes = [
        'feed_timeout',
        'body_width',
        ]

    _list_attributes = [
        'date_header_order',
        'encodings',
        ]

    _function_attributes = [
        'post_process',
        'digest_post_process',
        ]

    @property
    def user_agent(self):
        return self._user_agent.\
            replace('__VERSION__', __version__).\
            replace('__URL__', __url__)

    def __init__(self, name=None, url=None, to=None, config=None):
        self._set_name(name=name)
        self.reset()
        self.__setstate__(dict(
                (attr, getattr(self, attr))
                for attr in self._dynamic_attributes))
        self.load_from_config(config=config)
        self._fix_user_agent() # Fix feeds broken by user agent change in 3.11
        if url:
            self.url = url
        if to:
            self.to = to

    def __str__(self):
        return '{} ({} -> {})'.format(self.name, self.url, self.to)

    def __repr__(self):
        return '<Feed {}>'.format(str(self))

    def __getstate__(self):
        "Save dynamic attributes"
        return dict(
            (key,getattr(self,key)) for key in self._dynamic_attributes)

    get_state = __getstate__  # make it publicly accessible

    def __setstate__(self, state):
        "Restore dynamic attributes"
        keys = sorted(state.keys())
        if keys != sorted(self._dynamic_attributes):
            raise ValueError(state)
        self._set_name(name=state['name'])
        self.__dict__.update(state)

    set_state = __setstate__  # make it publicly accessible

    def save_to_config(self):
        "Save configured attributes"
        data = _collections.OrderedDict()
        default = self.config['DEFAULT']
        for attr in self._configured_attributes:
            key = self._configured_attribute_translations[attr]
            value = getattr(self, attr)
            if value is not None:
                value = self._get_configured_option_value(
                    attribute=attr, value=value)
                if (attr in self._non_default_configured_attributes or
                    value != default[key]):
                    data[key] = value
        self.config[self.section] = data

    def load_from_config(self, config=None):
        "Restore configured attributes"
        if config is None:
            config = _config.CONFIG
        self.config = config
        if self.section in self.config:
            data = self.config[self.section]
        else:
            data = self.config['DEFAULT']
        keys = sorted(data.keys())
        expected = sorted(self._configured_attribute_translations.values())
        if keys != expected:
            for key in expected:
                if (key not in keys and
                    key not in self._non_default_configured_attributes):
                    raise _error.InvalidFeedConfig(
                        setting=key, feed=self,
                        message='missing configuration key: {}'.format(key))
            for key in keys:
                if key not in expected:
                    raise _error.InvalidFeedConfig(
                        setting=key, feed=self,
                        message='extra configuration key: {}'.format(key))
        data = dict(
            (self._configured_attribute_inverse_translations[k],
             self._get_configured_attribute_value(
                  attribute=self._configured_attribute_inverse_translations[k],
                  key=k, data=data))
            for k in data.keys())
        for attr in self._non_default_configured_attributes:
            if attr not in data:
                data[attr] = None
        self.__dict__.update(data)

    def _get_configured_option_value(self, attribute, value):
        if value is None:
            return ''
        elif attribute in self._list_attributes:
            return ', '.join(value)
        elif attribute in self._function_attributes:
            return _util.import_name(value)
        return str(value)

    def _get_configured_attribute_value(self, attribute, key, data):
        if attribute in self._boolean_attributes:
            return data.getboolean(key)
        elif attribute in self._integer_attributes:
            return data.getint(key)
        elif attribute in self._list_attributes:
            return [x.strip() for x in data[key].split(',')]
        elif attribute in self._function_attributes:
            if data[key]:
                return _util.import_function(data[key])
            return None
        return data[key]

    def reset(self):
        """Reset dynamic data
        """
        self.etag = None
        self.modified = None
        self.seen = {} # type: Dict[str, Dict[str, Any]]

    def _set_name(self, name):
        if not self._name_regexp.match(name):
            raise _error.InvalidFeedName(name=name, feed=self)
        self.name = name
        self.section = 'feed.{}'.format(self.name)

    def _fetch(self):
        """Fetch and parse a feed using feedparser.

        >>> feed = Feed(
        ...    name='test-feed',
        ...    url='http://feeds.feedburner.com/allthingsrss/hJBr')
        >>> parsed = feed._fetch()
        >>> parsed.status
        200
        """
        _LOG.info('fetch {}'.format(self))
        if not self.url:
            raise _error.InvalidFeedConfig(setting='url', feed=self)
        if self.section in self.config:
            config = self.config[self.section]
        else:
            config = self.config['DEFAULT']
        proxy = config['proxy']
        timeout = config.getint('feed-timeout')
        kwargs = {}
        if proxy:
            kwargs['handlers'] = [
                _urllib_request.ProxyHandler({ 'http': proxy, 'https': proxy })
            ]
        f = _util.TimeLimitedFunction('feed {}'.format(self.name), timeout, _feedparser.parse)
        return f(self.url, self.etag, modified=self.modified, **kwargs)

    def _process(self, parsed):
        _LOG.info('process {}'.format(self))
        self._check_for_errors(parsed)
        for entry in reversed(parsed.entries):
            _LOG.debug('processing {}'.format(entry.get('id', 'no-id')))
            processed = self._process_entry(parsed=parsed, entry=entry)
            if processed:
                guid, _, sender, message = processed
                if self.post_process:
                    message = self.post_process(
                        feed=self, parsed=parsed, entry=entry, guid=guid,
                        message=message)
                    if not message:
                        continue
                yield processed

    def _check_for_errors(self, parsed):
        warned = False
        status = getattr(parsed, 'status', 200)
        _LOG.debug('HTTP status {}'.format(status))
        if status == 301:
            _LOG.info('redirect {} from {} to {}'.format(
                    self.name, self.url, parsed['url']))
            self.url = parsed['url']
        elif status not in [200, 302, 304, 307]:
            raise _error.HTTPError(status=status, feed=self)

        http_headers = parsed.get('headers', {})
        if http_headers:
            _LOG.debug('HTTP headers: {}'.format(http_headers))
            http_headers = dict((k.lower(), v) for k, v in http_headers.items())
        if not http_headers:
            _LOG.warning('could not get HTTP headers: {}'.format(self))
            warned = True
        else:
            if 'html' in http_headers.get('content-type', 'rss'):
                _LOG.warning('looks like HTML: {}'.format(self))
                warned = True
            if http_headers.get('content-length', '1') == '0':
                _LOG.warning('empty page: {}'.format(self))
                warned = True

        version = parsed.get('version', None)
        if version:
            _LOG.debug('feed version {}'.format(version))
        else:
            _LOG.debug('unrecognized version: {}'.format(self))
            warned = True

        exc = parsed.get('bozo_exception', None)
        if isinstance(exc, _socket.timeout):
            _LOG.error('timed out: {}'.format(self))
            warned = True
        elif isinstance(exc, OSError):
            _LOG.error('{}: {}'.format(exc, self))
            warned = True
        elif isinstance(exc, _SOCKET_ERRORS):
            _LOG.error('{}: {}'.format(exc, self))
            warned = True
        elif isinstance(exc, _feedparser.http.zlib.error):
            _LOG.error('broken compression: {}'.format(self))
            warned = True
        elif isinstance(exc, (IOError, AttributeError)):
            _LOG.error('{}: {}'.format(exc, self))
            warned = True
        elif isinstance(exc, KeyboardInterrupt):
            raise exc
        elif isinstance(exc, _sax.SAXParseException):
            _LOG.error('sax parsing error: {}: {}'.format(exc, self))
            warned = True
        elif (parsed.bozo and
              isinstance(exc, _feedparser.CharacterEncodingOverride)):
            _LOG.warning(
                'incorrectly declared encoding: {}: {}'.format(exc, self))
            warned = True
        elif (parsed.bozo and isinstance(exc, _feedparser.NonXMLContentType)):
            _LOG.warning('non XML Content-Type: {}: {}'.format(exc, self))
            warned = True
        elif parsed.bozo or exc:
            if exc is None:
                exc = "can't process"
            _LOG.error('processing error: {}: {}'.format(exc, self))
            warned = True

        if (not warned and
            status in [200, 302] and
            not parsed.entries and
            not version):
            raise _error.ProcessingError(parsed=parsed, feed=self)

    def _html2text(self, html, baseurl='', default=None):
        self.config.setup_html2text(section=self.section)
        try:
            return _html2text.html2text(html=html, baseurl=baseurl)
        except _html_parser.HTMLParseError as e:
            if default is not None:
                return default
            raise

    def _process_entry(self, parsed, entry) -> Optional[Tuple[str, Dict[str, Any], str, Message]]:
        guid = self._get_uid_for_entry(entry)
        new_hash = self._get_entry_hash(entry)

        old_state = self.seen.get(guid)
        if old_state is None:
            _LOG.debug('not seen {}'.format(guid))
            new_state = {} # type: Dict[str, Any]
        else:
            _LOG.debug('already seen {}'.format(guid))
            if 'old' in old_state:
                del old_state['old']
            if self.reply_changes:
                if new_hash != old_state.get('hash'):
                    _LOG.debug('hash changed for {}'.format(guid))
                    new_state = old_state.copy()
                else:
                    return None
            else:
                return None

        new_state['hash'] = new_hash

        sender = self._get_entry_email(parsed=parsed, entry=entry)
        subject = self._get_entry_title(entry)

        message_id = '<{0}@{1}>'.format(_uuid.uuid4(), platform.node())
        in_reply_to = old_state.get('message_id') if old_state is not None else None
        extra_headers = _collections.OrderedDict((
                ('Date', self._get_entry_date(entry)),
                ('Message-ID', message_id),
                ('In-Reply-To', in_reply_to),
                ('User-Agent', self.user_agent),
                ('List-ID', '<{}.localhost>'.format(self.name)),
                ('List-Post', 'NO (posting not allowed on this list)'),
                ('X-RSS-Feed', self.url),
                ('X-RSS-ID', guid),
                ('X-RSS-URL', self._get_entry_link(entry)),
                ('X-RSS-TAGS', self._get_entry_tags(entry)),
                ))
        # remove empty tags, etc.
        keys = {k for k, v in extra_headers.items() if v is None}
        for key in keys:
            extra_headers.pop(key)
        if self.bonus_header:
            for header in self.bonus_header.splitlines():
                if ':' in header:
                    key,value = header.split(':', 1)
                    extra_headers[key.strip()] = value.strip()
                else:
                    _LOG.warning(
                        'malformed bonus-header: {}'.format(
                            self.bonus_header))

        content = self._get_entry_content(entry)
        try:
            content = self._process_entry_content(
                entry=entry, content=content, subject=subject)
        except _error.ProcessingError as e:
            e.parsed = parsed
            raise
        message = _email.get_message(
            sender=sender,
            recipient=self.to,
            subject=subject,
            body=content['value'],
            content_type=content['type'].split('/', 1)[1],
            extra_headers=extra_headers,
            config=self.config,
            section=self.section)

        return guid, new_state, sender, message

    def _get_uid_for_entry(self, entry) -> str:
        """Get the best UID (unique ID) for the entry."""
        if self.trust_link:
            uid = self._get_entry_link(entry)
            if uid:
                return uid
        if self.trust_guid:
            uid = self._get_entry_id(entry)
            if uid:
                return uid
        return self._get_entry_hash(entry)

    @lru_cache(1)
    def _get_entry_hash(self, entry) -> str:
        content = self._get_entry_content(entry)
        content_value = content['value'].strip()
        if content_value:
            text = content_value
        elif getattr(entry, 'link', None):
            text = entry.link
        elif getattr(entry, 'title', None):
            text = entry.title
        else:
            text = ""
        return _hashlib.sha1(text.encode('unicode-escape')).hexdigest()

    def _get_entry_id(self, entry) -> Optional[str]:
        id_ = getattr(entry, 'id', None)
        # Newer versions of feedparser could return a dictionary
        if isinstance(id_, dict):
            return next(iter(id_.values()), None)
        return id_

    def _get_entry_link(self, entry) -> Optional[str]:
        return entry.get('link', None)

    def _get_entry_title(self, entry):
        if hasattr(entry, 'title_detail') and entry.title_detail:
            title = entry.title_detail.value
            if 'html' in entry.title_detail.type:
                title = self._html2text(title, default=title)
        else:
            content = self._get_entry_content(entry)
            value = content['value']
            if content['type'] in ('text/html', 'application/xhtml+xml'):
                value = self._html2text(value, default=value)
            title = value[:70]
        title = title.replace('\n', ' ').strip()
        return title

    def _get_entry_date(self, entry):
        datetime = _time.gmtime()
        if self.date_header:
            for datetype in self.date_header_order:
                kind = datetype + '_parsed'
                if entry.get(kind, None):
                    datetime = entry[kind]
                    break
        return _formatdate(_calendar.timegm(datetime))

    def _get_entry_name(self, parsed, entry):
        """Get the best name

        >>> import feedparser
        >>> f = Feed(name='test-feed')
        >>> parsed = feedparser.parse(
        ...     '<feed xmlns="http://www.w3.org/2005/Atom">\\n'
        ...     '  <entry>\\n'
        ...     '    <author>\\n'
        ...     '      <name>Example author</name>\\n'
        ...     '      <email>me@example.com</email>\\n'
        ...     '      <url>http://example.com/</url>\\n'
        ...     '    </author>\\n'
        ...     '  </entry>\\n'
        ...     '</feed>\\n'
        ...     )
        >>> entry = parsed.entries[0]
        >>> f.name_format = ''
        >>> f._get_entry_name(parsed, entry)
        ''
        >>> f.name_format = '{author}'
        >>> f._get_entry_name(parsed, entry)
        'Example author'
        >>> f.name_format = '{feed-title}: {author}'
        >>> f._get_entry_name(parsed, entry)
        ': Example author'
        >>> f.name_format = '{author} ({feed.name})'
        >>> f._get_entry_name(parsed, entry)
        'Example author (test-feed)'
        """
        if not self.name_format:
            return ''
        data = {
            'feed': self,
            'feed-name': self.name,
            'feed-url': self.url,
            'feed-title': '<feed title>',
            'author': '<author>',
            'publisher': '<publisher>',
            }
        feed = parsed.feed
        data['feed-title'] = feed.get('title', '')
        for x in [entry, feed]:
            if 'name' in x.get('author_detail', []):
                if x.author_detail.name:
                    data['author'] = x.author_detail.name
                    break
        if 'name' in feed.get('publisher_detail', []):
            data['publisher'] = feed.publisher_detail.name
        name = self.name_format.format(**data)
        return _html.unescape(name)

    def _validate_email(self, email, default=None):
        """Do a basic quality check on email address

        Return `default` if the address doesn't appear to be
        well-formed.  If `default` is `None`, return
        `self.from_email`.

        >>> f = Feed(name='test-feed')
        >>> f._validate_email('valid@example.com', 'default@example.com')
        'valid@example.com'
        >>> f._validate_email('invalid@', 'default@example.com')
        'default@example.com'
        >>> f._validate_email('@invalid', 'default@example.com')
        'default@example.com'
        >>> f._validate_email('invalid', 'default@example.com')
        'default@example.com'
        """
        parts = email.split('@')
        if len(parts) != 2 or '' in parts:
            if default is None:
                return self.from_email
            return default
        return email

    def _get_entry_address(self, parsed, entry):
        """Get the best From email address ('<jdoe@a.com>')

        If the best guess isn't well-formed (something@something.com),
        use `self.from_email` instead.
        """
        if self.force_from:
            return self.from_email
        feed = parsed.feed
        if 'email' in entry.get('author_detail', []):
            return self._validate_email(entry.author_detail.email)
        elif 'email' in feed.get('author_detail', []):
            return self._validate_email(feed.author_detail.email)
        if self.use_publisher_email:
            if 'email' in feed.get('publisher_detail', []):
                return self._validate_email(feed.publisher_detail.email)
            if feed.get('errorreportsto', None):
                return self._validate_email(feed.errorreportsto)
        _LOG.debug('no sender address found, fallback to default')
        return self.from_email

    def _get_entry_email(self, parsed, entry):
        """Get the best From email address ('John <jdoe@a.com>')
        """
        name = self._get_entry_name(parsed=parsed, entry=entry)
        address = self._get_entry_address(parsed=parsed, entry=entry)
        return _formataddr((name, address))

    def _get_entry_tags(self, entry):
        """Add post tags, if available

        >>> f = Feed(name='test-feed')
        >>> f._get_entry_tags({
        ...         'tags': [{'term': 'tag1',
        ...                   'scheme': None,
        ...                   'label': None}]})
        'tag1'
        >>> f._get_entry_tags({
        ...         'tags': [{'term': 'tag1',
        ...                   'scheme': None,
        ...                   'label': None},
        ...                  {'term': 'tag2',
        ...                   'scheme': None,
        ...                   'label': None}]})
        'tag1,tag2'

        Test some troublesome cases.  No tags:

        >>> f._get_entry_tags({})

        Empty tags:

        >>> f._get_entry_tags({'tags': []})

        Tags without a ``term`` entry:

        >>> f._get_entry_tags({
        ...         'tags': [{'scheme': None,
        ...                   'label': None}]})

        Tags with an empty term:

        >>> f._get_entry_tags({
        ...         'tags': [{'term': '',
        ...                   'scheme': None,
        ...                   'label': None}]})
        """
        taglist = [tag['term'] for tag in entry.get('tags', [])
                   if tag.get('term', '')]
        if taglist:
            return ','.join(taglist)

    @lru_cache(1)
    def _get_entry_content(self, entry):
        """Select the best content from an entry.

        Returns a feedparser content dict.
        """
        # How this works:
        #  * We have a bunch of potential contents.
        #  * We go thru looking for our first choice.
        #    (HTML or text, depending on self.html_mail)
        #  * If that doesn't work, we go thru looking for our second choice.
        #  * If that still doesn't work, we just take the first one.
        #
        # Possible future improvement:
        #  * Instead of just taking the first one
        #    pick the one in the "best" language.
        #  * HACK: hardcoded .html_mail, should take a tuple of media types
        contents = list(entry.get('content', []))
        if entry.get('summary_detail', None):
            contents.append(entry.summary_detail)
        if self.html_mail:
            types = ['application/xhtml+xml', 'text/html', 'text/plain']
        else:
            types = ['text/plain', 'text/html', 'application/xhtml+xml']
        for content_type in types:
            for content in contents:
                if content['type'] == content_type:
                    return content
        if contents:
            return contents[0]
        return {'type': 'text/plain', 'value': ''}

    def _process_entry_content(self, entry, content, subject):
        "Convert entry content to the requested format."
        link = self._get_entry_link(entry)
        if self.html_mail:
            lines = [
                '<!DOCTYPE html>',
                '<html>',
                '  <head>',
                ]
            if self.use_css and self.css:
                lines.extend([
                        '    <style type="text/css">',
                        _saxutils.escape(self.css),
                        '    </style>',
                        ])
            lines.extend([
                    '</head>',
                    '<body dir="auto">',
                    '<div id="entry">',
                    '<h1 class="header"><a href="{}">{}</a></h1>'.format(
                        _saxutils.escape(link), _saxutils.escape(subject)),
                    '<div id="body">',
                    ])
            if content['type'] in ('text/html', 'application/xhtml+xml'):
                lines.append(content['value'].strip())
            else:
                lines.append(_saxutils.escape(content['value'].strip()))
            lines.append('</div>')
            lines.extend([
                    '<div class="footer">'
                    '<p>URL: <a href="{0}">{0}</a></p>'.format(_saxutils.escape(link)),
                    ])
            for enclosure in getattr(entry, 'enclosures', []):
                if getattr(enclosure, 'url', None):
                    lines.append(
                        '<p>Enclosure: <a href="{0}">{0}</a></p>'.format(
                            _saxutils.escape(enclosure.url)))
                if getattr(enclosure, 'src', None):
                    lines.append(
                        '<p>Enclosure: <a href="{0}">{0}</a></p>'.format(
                            _saxutils.escape(enclosure.src)))
                    lines.append(
                        '<p><img src="{}" /></p>'.format(_saxutils.escape(enclosure.src)))
            for elink in getattr(entry, 'links', []):
                if elink.get('rel', None) == 'via':
                    url = elink['href']
                    title = elink.get('title', url)
                    lines.append('<p>Via <a href="{}">{}</a></p>'.format(
                            _saxutils.escape(url), _saxutils.escape(title)))
            lines.extend([
                    '</div>',  # /footer
                    '</div>',  # /entry
                    '</body>',
                    '</html>',
                    ''])
            content['type'] = 'text/html'
            content['value'] = '\n'.join(lines)
            return content
        else:  # not self.html_mail
            if content['type'] in ('text/html', 'application/xhtml+xml'):
                try:
                    lines = [self._html2text(content['value'])]
                except _html_parser.HTMLParseError as e:
                    raise _error.ProcessingError(parsed=None, feed=self)
            else:
                lines = [content['value']]
            lines.append('')
            lines.append('URL: {}'.format(link))
            for enclosure in getattr(entry, 'enclosures', []):
                if getattr(enclosure, 'url', None):
                    lines.append('Enclosure: {}'.format(enclosure.url))
                if getattr(enclosure, 'src', None):
                    lines.append('Enclosure: {}'.format(enclosure.src))
            for elink in getattr(entry, 'links', []):
                if elink.get('rel', None) == 'via':
                    url = elink['href']
                    title = elink.get('title', url)
                    lines.append('Via: {} {}'.format(title, url))
            content['type'] = 'text/plain'
            content['value'] = '\n'.join(lines)
            return content

    def _send(self, sender, message):
        _LOG.info('send message for {}'.format(self))
        section = self.section
        if section not in self.config:
            section = 'DEFAULT'
        _email.send(recipient=self.to, message=message,
                    config=self.config, section=section)

    def run(self, send=True, clean=False):
        """Fetch and process the feed, mailing entry emails.

        >>> feed = Feed(
        ...    name='test-feed',
        ...    url='http://feeds.feedburner.com/allthingsrss/hJBr')
        >>> def send(sender, message):
        ...    print('send from {}:'.format(sender))
        ...    print(message.as_string())
        >>> feed._send = send
        >>> feed.to = 'jdoe@dummy.invalid'
        >>> #parsed = feed.run()  # enable for debugging
        """
        if not self.to:
            raise _error.NoToEmailAddress(feed=self)
        if clean:
            self.etag = None
            self.modified = None
        parsed = self._fetch()

        if clean and len(parsed.entries) > 0:
            for guid in self.seen:
                self.seen[guid]['old'] = True

        if self.digest:
            digest = self._new_digest()
            seen = []
            for (guid, state, sender, message) in self._process(parsed):
                _LOG.debug('new message: {}'.format(message['Subject']))
                seen.append((guid, state))
                self._append_to_digest(digest=digest, message=message)
            if seen:
                if self.digest_post_process:
                    digest = self.digest_post_process(feed=self, parsed=parsed, seen=seen, message=digest)
                    if not digest:
                        return
                _LOG.debug('new digest for {}'.format(self))
                if send:
                    self._send_digest(digest=digest, sender=sender)
                for (guid, state) in seen:
                    self.seen[guid] = state
        else:
            for (guid, state, sender, message) in self._process(parsed):
                _LOG.debug('new message: {}'.format(message['Subject']))
                if send:
                    self._send(sender=sender, message=message)
                    state['message_id'] = str(message["Message-ID"])
                self.seen[guid] = state

        self.etag = parsed.get('etag', None)
        self.modified = parsed.get('modified', None)

        if clean and len(parsed.entries) > 0:
            # A feed might only show the newest N entries, but if the feed
            # author deletes a new entry, an older entry will reappear. Deleting
            # all entries not in the feed could cause an old entry to be resent.
            # To avoid this, the three newest entries no longer in the feed are
            # kept, allowing up to three new entries to be deleted from the feed
            # before anything would be resent.

            # Entries from new feeds are added oldest to newest, and new entries
            # are always inserted at the end. Entries no longer in the feed will
            # have an 'old' key added above. This iterates over the entry keys
            # (guid) from last to first, ignoring entries still in the feed. The
            # three newest 'old' entries are skipped and all others are deleting.

            # Python 3.7 guarantees Dict insertion order and CPython has done so
            # since 3.5. It is unlikely older and other implementations would
            # have stored the entries out-of-order, but if they did, the three
            # entries kept won't be correct. And in the unlikely event the feed
            # author deletes an entry, an old entry could be resent.

            old = 3
            for guid in reversed(list(self.seen)):
                if 'old' in self.seen[guid]:
                    if old > 0:
                        del self.seen[guid]['old']
                    else:
                        del self.seen[guid]
                    old = old - 1

    def _new_digest(self):
        digest = _MIMEMultipart('digest')
        digest['To'] = _formataddr(_parseaddr(self.to))  # Encodes with utf-8 as necessary
        digest['Subject'] = 'digest for {}'.format(self.name)
        digest['Message-ID'] = '<{0}@{1}>'.format(_uuid.uuid4(), platform.node())
        digest['User-Agent'] = self.user_agent
        digest['List-ID'] = '<{}.localhost>'.format(self.name)
        digest['List-Post'] = 'NO (posting not allowed on this list)'
        digest['X-RSS-Feed'] = self.url
        return digest

    def _append_to_digest(self, digest, message):
        part = _MIMEMessage(message)
        part.add_header('Content-Disposition', 'attachment')
        digest.attach(part)

    def _send_digest(self, digest, sender):
        """Send a digest message

        The date is extracted from the last message in the digest
        payload.  We assume that this part exists.  If you don't have
        any messages in the digest, don't call this function.
        """
        digest['From'] = sender
        last_part = digest.get_payload()[-1]
        last_message = last_part.get_payload()[0]
        digest['Date'] = last_message['Date']
        self._send(sender=sender, message=digest)

    def _fix_user_agent(self):
        """Fix feed user agent settings broken in 3.11

        Release 3.11 added code to allow the user agent string to be
        configured globally and on a per-feed basis. It was supposed
        to allow __VERSION__ and __URL__ in configuration setting to
        be substituted dynamically with the current version and URL of
        rss2email, but a bug in the implementation caused them to be
        substituted statically in the settings for any newly added
        feed. We've fixed that problem, but we want to go back now and
        repair feeds that got the wrong user agent value in the
        interim.
        """
        if self._user_agent == \
           'rss2email/3.11 (https://github.com/rss2email/rss2email)':
            self._user_agent = 'rss2email/__VERSION__ (__URL__)'
            self.save_to_config()
