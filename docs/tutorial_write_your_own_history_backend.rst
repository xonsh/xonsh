.. _tutorial_write_your_own_history_backend:

****************************************
Tutorial: Write Your Own History Backend
****************************************

One of best thing you can do with xonsh is that you could customize
a lot of stuff. In this tutorial, let's write our own history backend
base on CouchDB.

Start with a minimal history template
=====================================

Here is a minimal *working* history backend we can have:

.. code-block:: python

    import collections
    from xonsh.history.base import History

    class CouchDBHistory(History):
        def append(self, cmd):
            pass

        def items(self):
            yield {'inp': 'couchdb in action', 'ts': 1464652800, 'ind': 0}

        def all_items(self):
            return self.items()

        def info(self):
            data = collections.OrderedDict()
            data['backend'] = 'couchdb'
            data['sessionid'] = str(self.sessionid)
            return data

Go ahead and create the file ``~/.xonsh/history_couchdb.py`` out and put the
content above into it.

Now we need to set xonsh to use it as the history backend. To do this
we need xonsh able to find our file and use this ``CouchDBHistory`` class.
Put the following code into your ``~/.xonshrc`` file can achieve it.

.. code-block:: python

    import os
    import sys
    xonsh_ext_dir = os.path.expanduser('~/.xonsh')
    if os.path.isdir(xonsh_ext_dir):
        sys.path.append(xonsh_ext_dir)

    from history_couchdb import CouchDBHistory
    from xonsh.history.main import HISTORY_BACKENDS
    HISTORY_BACKENDS['couchdb'] = CouchDBHistory
    $XONSH_HISTORY_BACKEND = 'couchdb'

After you starting a new xonsh session. Try the following commands:

.. code-block::

    $ history info
    backend: couchdb
    sessionid: 4198d678-1f0a-4ce3-aeb3-6d5517d7fc61

    $ history -n
    0: couchdb in action

Woho! We just wrote a working history backend!!

Setup CouchDB
=============

For real, we need a CouchDB running. Go to
`CouchDB website <http://couchdb.apache.org/>`_ and get a copy and
spend some time to install it. we will wait for you. Take your time.

After installing it, we could check it with ``curl``:


.. code-block::

    $ curl -i 'http://127.0.0.1:5984/'
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

Open ``http://127.0.0.1:5984/_utils/`` with your browser, and create a new
database called ``xonsh-history``.


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

``_save_to_db()`` takes a dict, which contains the information about
a command that use input, as the input, and save it into CouchDB.

As ``self.sessionid``, here we also use timestamps to build the doc KEY
so that we don't need any views. Just with bare ``_all_docs`` API, we can
fetch history items back in order.

Now that we have helper functions, we can update our ``append()`` method
to do the real job - save history into DB.

This method will be called by xonsh core every time it reveives new commands
from user.

.. code-block:: python

    def append(self, cmd):
        self.inps.append(cmd['inp'])
        self.rtns.append(cmd['rtn'])
        self.outs.append(None)
        self.tss.append(cmd.get('ts', (None, None)))
        self._save_to_db(cmd)


Retrieve History Items
======================

.. code-block:: python

    def items(self):
        yield from self._get_db_items(self.sessionid)

    def all_items(self):
        yield from self._get_db_items()

These two methods are responsible for get history items for current xonsh
session and all historical sessions respectively.

And here is our helper methods to get docs from DB:

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


History GC
==========

todo

Other History Options
=====================

todo
