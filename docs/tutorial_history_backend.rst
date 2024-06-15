.. _tutorial_history_backend:

****************************************
Tutorial: Write Your Own History Backend
****************************************

One of the great things about xonsh is how easy it is to customize. In
this tutorial, let's write our own history backend based on CouchDB.


Start with a Minimal History Template
=====================================

Here is a minimal history backend to start with:

.. code-block:: python

    import collections
    from xonsh.history.base import History

    class CouchDBHistory(History):
        def append(self, cmd):
            pass

        def items(self, newest_first=False):
            yield {'inp': 'couchdb in action', 'ts': 1464652800, 'ind': 0}

        def all_items(self, newest_first=False):
            return self.items()

        def info(self):
            data = collections.OrderedDict()
            data['backend'] = 'couchdb'
            data['sessionid'] = str(self.sessionid)
            return data

Go ahead and create the file ``~/.xonsh/history_couchdb.py`` and put the
content above into it.

Now we need to tell xonsh to use it as the history backend. To do this
we need xonsh to be able to find our file and this ``CouchDBHistory`` class.
Putting the following code into `xonshrc <xonshrc.rst>`_ file can achieve this.

.. code-block:: none

    import os.path
    import sys
    xonsh_ext_dir = os.path.expanduser('~/.xonsh')
    if os.path.isdir(xonsh_ext_dir):
        sys.path.append(xonsh_ext_dir)

    from history_couchdb import CouchDBHistory
    $XONSH_HISTORY_BACKEND = CouchDBHistory

After starting a new xonsh session, try the following commands:

.. code-block:: none

    @ history info
    backend: couchdb
    sessionid: 4198d678-1f0a-4ce3-aeb3-6d5517d7fc61

    @ history -n
    0: couchdb in action

Woohoo! We just wrote a working history backend!


Setup CouchDB
=============

For this to work, we need CouchDB up and running. Go to
`CouchDB website <http://couchdb.apache.org/>`_ and spend some time to
install it. we will wait for you. Take your time.

After installing, check that it's configured correctly with ``curl``:

.. code-block:: none

    @ curl -i 'http://127.0.0.1:5984/'
    HTTP/1.1 200 OK
    Cache-Control: must-revalidate
    Content-Length: 91
    Content-Type: application/json
    Date: Wed, 01 Feb 2017 13:54:14 GMT
    Server: CouchDB/2.0.0 (Erlang OTP/19)
    X-Couch-Request-ID: 025a195bcb
    X-CouchDB-Body-Time: 0

    {
        "couchdb": "Welcome",
        "version": "2.0.0",
        "vendor": {
            "name": "The Apache Software Foundation"
        }
    }

Okay, CouchDB is working. Now open `<http://127.0.0.1:5984/_utils/>`_ with
your browser, and create a new database called ``xonsh-history``.


Initialize History Backend
==========================

.. code-block:: python

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.gc = None
        self.sessionid = self._build_session_id()
        self.inps = []
        self.rtns = []
        self.outs = []
        self.tss = []

    def _build_session_id(self):
        ts = int(time.time() * 1000)
        return '{}-{}'.format(ts, str(uuid.uuid4())[:18])

In the ``__init__()`` method, let's initialize
`Some Public Attributes <api/history/base.html#xonsh.history.base.History>`_
which xonsh uses in various places. Note that we use Unix timestamp and
some random char to make ``self.sessionid`` unique and to keep the entries
ordered in time. We will cover it with a bit more detail in the next section.


Save History to CouchDB
=======================

First, we need some helper functions to write docs to CouchDB.

.. code-block:: python

    def _save_to_db(self, cmd):
        data = cmd.copy()
        data['inp'] = cmd['inp'].rstrip()
        if 'out' in data:
            data.pop('out')
        data['_id'] = self._build_doc_id()
        try:
            self._request_db_data('/xonsh-history', data=data)
        except Exception as e:
            msg = 'failed to save history: {}: {}'.format(e.__class__.__name__, e)
            print(msg, file=sys.stderr)

    def _build_doc_id(self):
        ts = int(time.time() * 1000)
        return '{}-{}-{}'.format(self.sessionid, ts, str(uuid.uuid4())[:18])

    def _request_db_data(self, path, data=None):
        url = 'http://127.0.0.1:5984' + path
        headers = {'Content-Type': 'application/json'}
        if data is not None:
            resp = requests.post(url, json.dumps(data), headers=headers)
        else:
            headers = {'Content-Type': 'text/plain'}
            resp = requests.get(url, headers=headers)
        return resp

``_save_to_db()`` takes a dict as the input, which contains the information
about a command that user input, and saves it into CouchDB.

Instead of letting CouchDB provide us a random Document ID (i.e. the
``data['_id']`` in our code), we build it for ourselves.  We use the Unix
timestamp and UUID string for a second time. Prefixing this with
``self.sessionid``, we make history entries in order inside a single xonsh
session too. So that we don't need any extra CouchDB's
`Design Documents and Views <http://docs.couchdb.org/en/2.0.0/couchapp/ddocs.html>`_
feature. Just with a bare ``_all_docs`` API, we can fetch history items back
in order.

Now that we have helper functions, let's update our ``append()`` method
to do the real job - save history into DB.

.. code-block:: python

    def append(self, cmd):
        self.inps.append(cmd['inp'])
        self.rtns.append(cmd['rtn'])
        self.outs.append(None)
        self.tss.append(cmd.get('ts', (None, None)))
        self._save_to_db(cmd)

This method will be called by xonsh every time it runs a new command from user.


Retrieve History Items
======================

.. code-block:: python

    def items(self, newest_first=False):
        yield from self._get_db_items(self.sessionid)

    def all_items(self, newest_first=False):
        yield from self._get_db_items()

These two methods are responsible for getting history items for the current
xonsh session and all historical sessions respectively.

And here is our helper method to get docs from DB:

.. code-block:: python

    def _get_db_items(self, sessionid=None):
        path = '/xonsh-history/_all_docs?include_docs=true'
        if sessionid is not None:
            path += '&start_key="{0}"&end_key="{0}-z"'.format(sessionid)
        try:
            r = self._request_db_data(path)
        except Exception as e:
            msg = 'error when query db: {}: {}'.format(e.__class__.__name__, e)
            print(msg, file=sys.stderr)
            return
        data = json.loads(r.text)
        for item in data['rows']:
            cmd = item['doc'].copy()
            cmd['ts'] = cmd['ts'][0]
            yield cmd

The `try-except` is here so that we're safe when something bad happens, like
CouchDB is not running properly, etc.


Try Out Our New History Backend
===============================

That's it. We've finished our new history backend. The ``import`` part is
skipped, but I think you can figure it out though. Note that in our code
an extra Python library is used: ``requests``. You could easily install it
with ``pip`` or other library managers. You can find the full code here:
`<https://gist.github.com/mitnk/2d08dc60aab33d8b8b758c544b37d570>`_

Let's start a new xonsh session:

.. code-block:: none

    @ history info
    backend: couchdb
    sessionid: 1486035364166-3bb78606-dd59-4679

    @ ls
    Applications   Desktop    Documents    Downloads

    @ echo hi
    hi

Start a second xonsh session:

.. code-block:: none

    @ history info
    backend: couchdb
    sessionid: 1486035430658-6f81cd5d-b6d4-4f6a

    @ echo new
    new

    @ history show all -nt
    0:(2017-02-02 19:36) history info
    1:(2017-02-02 19:36) ls
    2:(2017-02-02 19:37) echo hi
    3:(2017-02-02 19:37) history info
    4:(2017-02-02 19:37) echo new

    @ history -nt
    0:(2017-02-02 19:37) history info
    1:(2017-02-02 19:37) echo new
    2:(2017-02-02 19:37) history show all -nt

We're not missing any history, so it looks like we're good to go!


History Garbage Collection
==========================

For the built-in history backends ``json`` and ``sqlite``, garbage collection
is triggered when xonsh is started or when the user runs ``history gc``.
History items outside of the range defined by
`$XONSH_HISTORY_SIZE <envvars.html#xonsh-history-size>`_ are deleted.

.. code-block:: python

    class History:
        def run_gc(self, size=None, blocking=True):
            """Run the garbage collector.

            Parameters
            ----------
            size: None or tuple of a int and a string
                Determines the size and units of what would be allowed to remain.
            blocking: bool
                If set blocking, then wait until gc action finished.
            """
            pass

The History public method ``run_gc()`` is for this purpose. Our
``CouchDBHistory`` doesn't define this method, thus it inherits from its
parent ``History``, which does nothing. We will leave the GC implementation
as an exercise.


Other History Options
=====================

There are some environment variables that can change the behavior of the
history backend. Such as `$HISTCONTROL <envvars.html#histcontrol>`_,
`$XONSH_HISTORY_SIZE <envvars.html#xonsh-history-size>`_,
`$XONSH_STORE_STDOUT <envvars.html#xonsh-store-stdout>`_, etc.

We should implement these ENVs in our CouchDB backend. Luckily, it's not a
hard thing. We'll leave the implementation of those features to you,
but you can see how it's handled for
`the sqlite backend <_modules/xonsh/history/sqlite.html#SqliteHistory>`_.


Wrap Up
=======

This is a barebones implementation but hopefully it will give you a sense
of how you can customize xonsh's history backend for your own needs!
