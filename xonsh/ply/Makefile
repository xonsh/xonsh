PYTHON ?= python

test:
	cd test && $(PYTHON) testlex.py
	cd test && $(PYTHON) testyacc.py

wheel:
	$(PYTHON) setup.py bdist_wheel

sdist:
	$(PYTHON) setup.py sdist

upload: wheel sdist
	$(PYTHON) setup.py bdist_wheel upload
	$(PYTHON) setup.py sdist upload

.PHONY: test wheel sdist upload
