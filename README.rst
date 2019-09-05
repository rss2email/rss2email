.. -*- coding: utf-8 -*-

.. image:: https://pypip.in/download/rss2email/badge.png
    :target: https://pypi.python.org/pypi/rss2email/
    :alt: Downloads

.. image:: https://pypip.in/version/rss2email/badge.png
    :target: https://pypi.python.org/pypi/rss2email/
    :alt: Latest Version

.. image:: https://pypip.in/license/rss2email/badge.png
    :target: https://pypi.python.org/pypi/rss2email/
    :alt: License

==============================
Getting Started With rss2email
==============================

We highly recommend that you watch the rss2email project on GitHub
so you can keep up to date with the latest version, bugfixes and
features:

  https://github.com/rss2email/rss2email

.. contents::

Installing rss2email
====================

Packages
--------

A quick way to get rss2email going is using pre-made packages. There
are releases for Debian__, Ubuntu__, Fedora__, openSUSE__, Gentoo__,
NetBSD__, and OpenBSD__.

__ `Debian package`_
__ `Ubuntu package`_
__ `Fedora package`_
__ `openSUSE package`_
__ `Gentoo package`_
__ `NetBSD package`_
__ `OpenBSD package`_

Installing by hand
------------------

Requirements
~~~~~~~~~~~~

Before you install rss2email, you'll need to make sure that a few
things are in place.

1. Ensure that a version of Python_ ≥3.4 is installed.
2. Install the required Python packages.

   * feedparser_
   * html2text_

3. Figure out how you are going to send outgoing email.  You have two
   options here: either use an SMTP server or a local sendmail
   program.  So,

   * determine your outgoing email server's SMTP address, or
   * install sendmail (or a compatible replacement like postfix).

Download
~~~~~~~~

Download the latest rss2email source and unpack it.  You can choose
from several equivalent formats.

1. A ``.zip`` file (suggested for Microsoft Windows users)
   or ``.tar.gz`` file (suggested for everyone else)::

    * Navigate to https://github.com/rss2email/rss2email/releases
    * Click either the ``zip`` or ``tar.gz`` icon for the latest release
    * Download and extract the archive

3. A Git_ checkout (suggested for developers)::

    $ git clone git://github.com/rss2email/rss2email.git

Install
~~~~~~~

From the unpacked directory, run::

  $ python setup.py install

You can pass all the usual options to the ``install`` command,
including ``--user``.  If you don't want to install rss2email, you can
also run ``r2e`` directly from the source directory.

Upgrading to a new version
~~~~~~~~~~~~~~~~~~~~~~~~~~

Just repeat the installation procedure for the new source package.  If
your config file and data file were in the old source directory, move
them over to the new source directory.  If the config and data files
were in another directory (e.g. ``~/.config`` and ``~/.local/share``),
there is no need to move them.

Using rss2email
===============

Create a new feed database to send updates to your email address::

  $ r2e new you@yourdomain.com

This command will create a configuration file
(``$XDG_CONFIG_HOME/rss2email.cfg`` by default) and a feed database
(``$XDG_DATA_HOME/rss2email.json`` by default).  If you'd rather those
files were stored in other locations, use the ``--config`` and
``--data`` options.  ``XDG_CONFIG_HOME`` defaults to ``$HOME/.config``
and ``XDG_DATA_HOME`` defaults to ``$HOME/.local/share``.

You should edit the default configuration file now to adjust rss2email
for your local system.  Unless you've installed a local
sendmail-equivalent, you'll need to edit the SMTP_ options.

Subscribe to some feeds::

  $ r2e add eff https://www.eff.org/rss/updates.xml

That will cause rss2email to notify you when there is a new announcement from
the Electronic Frontier Foundation. Repeat this for each feed you want to
subscribe to.

When you run rss2email, it emails you about every story it hasn't seen
before. But the first time you run it, that will be every story. To
avoid this, you can ask rss2email not to send you any stories the
first time you run it::

  r2e run --no-send

Then later, you can ask it to email you new stories::

  r2e run

When a run is made, rss2email stores the list of already seen items for each feed in `$HOME/.local/share/rss2email.json`.

Customizing rss2email
=====================

There are a number of options, described in full in
``rss2email/config.py``, to customize the way rss2email behaves. If
you want to change something, edit the configuration file that was
created by ``r2e new``.

For example, if you want to receive HTML mail, instead of having
entries converted to plain text::

  html-mail = True

To be notified every time a post changes, instead of just when it's
first posted (see also ``trust-link``, described in
``rss2email/config.py``)::

  trust-guid = True

And to make the emails look as if they were sent when the item was
posted::

  date-header = True

If you get an error message ``Sender domain must exist``, add the
following to your configuration file::

  from = rss2email@yoursite.com
  force-from = True

You can make the email address whatever you want, but your mail server
requires that the ``yoursite.com`` part actually exists.


SMTP
----

By default, rss2email uses sendmail (or an equivalent) to send
outgoing email.  If you don't have such a program installed, or simply
prefer to use SMTP__ directly, edit the configuration file and fill in
your outgoing email server's details::

  [DEFAULT]
  ...
  email-protocol = smtp
  smtp-server = smtp.example.net:587
  smtp-auth = False
  ...

If your server requires you to login, change ``smtp-auth = False`` to
``smtp-auth = True`` and enter your email username and password::

  smtp-auth = True
  smtp-username = username
  smtp-password = password

If your server requires an `TLS/SSL`_ connection (SMTPS), change
``smtp-ssl = False`` to ``smtp-ssl = True``.  If your server does
not require a SMTPS connection but you request authentication,
rss2email will use STARTTLS_ to encrypt the connection before sending
your login credentials to the server.

__ `Simple Mail Transport Protocol`_

Post-processing
---------------

rss2email has a mechanism to post-process entries. A post-processor can be used to change the content of each entry
before rss2email sends the email out. A hook is added by defining the variable ``post-process`` in the
config file. It takes two arguments, the module and the function to call. For example:

  post-process = rss2email.post_process.prettify process

Examples of built-in post-processors:

* ``prettify.py`` prettifies the HTML content with BeautifulSoup.
* ``redirect.py`` remove redirects on the post URL for privacy or durability.


Automating rss2email
====================

More than likely you will want rss2email to run automatically at a
regular interval. Under Windows this is can be easily accomplished
using the Windows Task Scheduler. This site has a
nice tutorial__ on it. Just select ``r2e.bat`` as the program to run. Once
you've created the task, double click on it in the task list and
change the Run entry so that ``run`` comes
after ``r2e.bat``. For example, if you installed rss2email in
the ``C:\rss2email`` directory, then you would change the Run
entry from ``C:\rss2email\r2e.bat``
to ``C:\rss2email\r2e.bat run``.

__ `windows scheduler`_

On Unix/Linux systems, you should add a cron_ job that runs ``r2e``.
For example, run ``r2e`` every night (at 1:23 am) with::

  23 1 * * * r2e run

Development
===========

User discussion and development take place on GitHub. Please feel free
to post bug reports, feature requests, comments, and patches. If you
do not have a GitHub account and do not wish to acquire one, you may
e-mail Jeff:

  jeff@jsbackus.com

There is a developer chat on the `freenode IRC server`_, in the
``rss2email`` channel. Feel free to idle.

.. _Debian package:
  http://packages.qa.debian.org/r/rss2email.html
.. _Ubuntu package:
  https://launchpad.net/ubuntu/+source/rss2email
.. _Fedora package:
  https://src.fedoraproject.org/rpms/rss2email
.. _openSUSE package:
  https://build.opensuse.org/package/show/openSUSE:Factory/rss2email
.. _NetBSD package:
  http://ftp.netbsd.org/pub/pkgsrc/current/pkgsrc/mail/rss2email/README.html
.. _Gentoo package:
  http://gpo.zugaina.org/net-mail/rss2email
.. _OpenBSD package:
  http://openports.se/mail/rss2email
.. _Python: http://www.python.org
.. _feedparser: http://pypi.python.org/pypi/feedparser
.. _html2text: http://pypi.python.org/pypi/html2text
.. _Git: http://git-scm.com/
.. _Simple Mail Transport Protocol: http://en.wikipedia.org/wiki/Simple_Mail_Transport_Protocol
.. _TLS/SSL: http://en.wikipedia.org/wiki/Transport_Layer_Security
.. _STARTTLS: http://en.wikipedia.org/wiki/STARTTLS
.. _windows scheduler: http://www.iopus.com/guides/winscheduler.htm
.. _cron: http://en.wikipedia.org/wiki/Cron
.. _freenode IRC server: https://freenode.net
