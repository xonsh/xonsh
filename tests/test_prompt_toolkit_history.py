# -*- coding: utf-8 -*-
"""Tests for the LimitedFileHistory class."""
import os
from tempfile import NamedTemporaryFile

import nose
from nose.tools import assert_equal


def is_prompt_toolkit_available():
    try:
        import prompt_toolkit
        return True
    except ImportError:
        return False

if not is_prompt_toolkit_available():
    from nose.plugins.skip import SkipTest
    raise SkipTest('prompt_toolkit is not available')


from xonsh.prompt_toolkit_history import LimitedFileHistory


def create_file(content):
    with NamedTemporaryFile(delete=False) as tfile:
        tfile.write(content.encode('utf-8'))
        file_name = tfile.name
    return file_name


def check_op_sequence(op_sequence, start_file_content, desired_file_content):
    file_name = create_file(start_file_content)
    try:
        op_sequence(file_name)
        with open(file_name) as tfile:
            content = tfile.read()
            assert_equal(content, desired_file_content)
    finally:
        os.unlink(file_name)


def create_file_content(start_line, stop_line):
    content = []
    for num in range(start_line, stop_line):
        content.append('line{}'.format(num))
    return '\n'.join(content) + '\n'


def test_without_limit():
    start_content = create_file_content(0, 10)
    desired_content = start_content + 'line10\n'
    def operation_sequence(history_file):
        history_obj = LimitedFileHistory()
        history_obj.read_history_file(history_file)
        history_obj.append('line10')
        history_obj.save_history_to_file(history_file)
    yield check_op_sequence, operation_sequence, start_content, desired_content


def test_smaller_limit():
    start_content = create_file_content(0, 10)
    desired_content = create_file_content(5, 10)
    def operation_sequence(history_file):
        history_obj = LimitedFileHistory()
        history_obj.read_history_file(history_file)
        history_obj.save_history_to_file(history_file, limit=5)
    yield check_op_sequence, operation_sequence, start_content, desired_content


def test_empty_initial_file():
    start_content = ''
    desired_content = create_file_content(0, 4)
    def operation_sequence(history_file):
        history_obj = LimitedFileHistory()
        history_obj.read_history_file(history_file)
        history_obj.append('line0')
        history_obj.append('line1')
        history_obj.append('line2')
        history_obj.append('line3')
        history_obj.save_history_to_file(history_file)
    yield check_op_sequence, operation_sequence, start_content, desired_content


def test_exact_limit():
    start_content = create_file_content(0, 4)
    desired_content = create_file_content(0, 4)
    def operation_sequence(history_file):
        history_obj = LimitedFileHistory()
        history_obj.read_history_file(history_file)
        history_obj.save_history_to_file(history_file, limit=4)
    yield check_op_sequence, operation_sequence, start_content, desired_content


def test_two_shells():
    start_content = create_file_content(0, 4)
    desired_content = create_file_content(0, 6)
    def operation_sequence(history_file):
        history1 = LimitedFileHistory()
        history2 = LimitedFileHistory()
        history1.append('line4')
        history2.append('line5')
        history1.save_history_to_file(history_file)
        history2.save_history_to_file(history_file)
    yield check_op_sequence, operation_sequence, start_content, desired_content


if __name__ == '__main__':
    nose.runmodule()
