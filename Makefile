SHELL = /bin/sh

which = edited # which tests to run

all:
	@echo "You must specifiy a make target."
	@echo "Targets are:"
	@echo "  clean"
	@echo "  lint"
	@echo "  lint-all"
	@echo "  test"
	@echo "  test-all"
	@echo "  build-tables"

clean:
	rm -f xonsh/lexer_table.py xonsh/parser_table.py
	rm -f xonsh/lexer_test_table.py xonsh/parser_test_table.py
	rm -f xonsh/*.pyc tests/*.pyc
	rm -f xonsh/*.rej tests/*.rej
	rm -fr build

# Line just the changed python files. It doesn't matter if "git add" has
# already been done but obviously if you've already done "git commit" then
# they're no longer consider changed. This should be run (along with "make
# test") before commiting a set of changes.
lint:
	pylint $$(git status -s | awk '/\.py$$/ { print $$2 }' | sort)

# Lint all the python files.
lint-all:
	make clean
	pylint $$(find tests xonsh -name \*.py | sort)

# Test just the changed python files. It doesn't matter if "git add" has
# already been done but obviously if you've already done "git commit" then
# they're no longer consider changed. This should be run (along with "make
# lint") before commiting a set of changes. You can also pass a list of test
# names via a "which=name1 name2..." argument.
test:
	scripts/run_tests.xsh $(which)

# Test all the python files.
test-all:
	scripts/run_tests.xsh all

# Build the parser_table.py module. This is normally done by setup.py at
# install time. This just makes it easy to create the parser module on the fly
# to facilitate development.
build-tables:
	python3 -c 'import setup; setup.build_tables()'
