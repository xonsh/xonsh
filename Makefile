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
	""")

.PHONY: clean
clean:
	find xonsh -name __amalgam__.py -delete -print

.PHONY: amalgamate
amalgamate:
	sys.path.insert(0, '.')
	import setup
	setup.amalgamate_source()
	_ = sys.path.pop(0)
