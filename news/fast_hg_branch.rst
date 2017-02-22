**Added:** None

**Changed:**

* ``prompt.vc.get_hg_branch`` now uses ``os.scandir`` to walk up the filetree
  looking for a ``.hg`` directory. This results in (generally) faster branch
  resolution compared to the subprocess call to ``hg root``.

**Deprecated:** None

**Removed:** None

**Fixed:** None

**Security:** None
