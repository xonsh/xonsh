# Maintained, No Package Releases

PLY is maintained software, but no longer produces package releases.
There is no `setup.py` file.  It is not something that you install
with `pip` or a similar tool. You must COPY the necessary code from
PLY into your project and take ownership of it.

Why this policy? PLY is a highly specialized tool for expert-level
programmers who are writing parsers and compilers.  If you are writing
a compiler, there's a good chance that it's part of a substantially
larger project.  Managing external dependencies (such as PLY) in such
projects is an ongoing challenge.  However, the truth of the matter is
that PLY just isn't that big.  All of the core functionality is
contained in just two files.  PLY has no external dependencies of its
own.  It changes very rarely.  Plus, there are various customizations
that you might want to apply to how it works.  So, all things equal,
it's probably better for you to copy it.  

But what about getting all of the latest improvements and bug fixes?
What improvements? PLY is implementing a 1970s-era parsing algorithm.
It's not cutting edge.  As for bug fixes, you'll know pretty rapidly
if PLY works for your project or not.  If it's working, there's
literally no reason to ever upgrade it. Keep using the version of code
that you copied.  If you think you've found a bug, check back with the
repository to see if it's been fixed. Or submit it as an issue so that
it can be looked at.














