**Added:**

* New ``free_cwd`` xontrib for Windows, which prevent the current directory from beeing locked when the prompt is shown. 
  This allows the other programs or Windows explorer to delete the current or parent directory. This is accomplished by 
  reseting the CWD to the users home directory temporarily while the prompt is displayed. The directory is still locked 
  while any commands are processed so xonsh still can't remove it own working directory. 

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:** None

**Security:** None
