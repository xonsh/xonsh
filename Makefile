# Make GNU Make xonshy
SHELL=xonsh
.SHELLFLAGS=-c
.ONESHELL:
.SILENT:

# Unlike normal makefiles: executes the entire body in one go under xonsh, and doesn't echo

.PHONY: help
help:
	print("""
	Utility file for xonsh project. Try these targets:
	* amalgamate: Generate __amalgam__.py files
	* clean: Remove generated files (namely, the amalgamations)
	* xonsh/ply: Pull down most recent ply
	""")

.PHONY: xonsh/ply
xonsh/ply:
	git remote add ply https://github.com/dabeaz/ply.git
	git fetch ply
	git branch ply-branch ply/master
	git rm -rf xonsh/ply
	git read-tree --prefix=xonsh/ply/ply -u ply-branch:ply
	git add xonsh/ply
	git commit -m "Merged changes from ply to sub-directory"
	git branch -D ply-branch


.PHONY: clean
clean:
	find xonsh -name __amalgam__.py -delete -print

.PHONY: amalgamate
amalgamate:
	sys.path.insert(0, '.')
	import setup
	setup.amalgamate_source()
	_ = sys.path.pop(0)
