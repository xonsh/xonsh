**Added:** None

**Changed:**

* All ansicolor names used in styles have ben updated to the color names used by prompt_toolkit 2. 
  The new names are are much easier to understand 
  (e.g. ``ansicyan``/``ansibrightcyan`` vs. the old ``#ansiteal``/``#ansiturquoise``). The names are automatically 
  translated back when using prompt_toolkit 1.

**Deprecated:** None

**Removed:**

* Removed support for pygments < 2.2.

**Fixed:**

* New ansi-color names fixes the problem with darker colors using prompt_toolkit 2 on windows. 

**Security:** None
