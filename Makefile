# Make GNU Make xonshy
SHELL=xonsh
.SHELLFLAGS=-c
.ONESHELL:

xonsh/ply:
	git subtree pull --prefix xonsh/ply https://github.com/dabeaz/ply.git master --squash


.PHONY: clean
clean:
	find xonsh -name __amalgam__.py -delete -print

.PHONY: amalgamate
amalgamate:
	python3 amalgamate.py xonsh