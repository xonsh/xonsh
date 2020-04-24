# calclextab.py. This file automatically created by PLY (version 3.11). Don't edit!
_tabversion   = '3.10'
_lextokens    = set(('DIVIDE', 'EQUALS', 'LPAREN', 'MINUS', 'NAME', 'NUMBER', 'PLUS', 'RPAREN', 'TIMES'))
_lexreflags   = 64
_lexliterals  = ''
_lexstateinfo = {'INITIAL': 'inclusive'}
_lexstatere   = {'INITIAL': [('(?P<t_NUMBER>\\d+)|(?P<t_newline>\\n+)|(?P<t_NAME>[a-zA-Z_][a-zA-Z0-9_]*)|(?P<t_PLUS>\\+)|(?P<t_TIMES>\\*)|(?P<t_LPAREN>\\()|(?P<t_RPAREN>\\))|(?P<t_MINUS>-)|(?P<t_DIVIDE>/)|(?P<t_EQUALS>=)', [None, ('t_NUMBER', 'NUMBER'), ('t_newline', 'newline'), (None, 'NAME'), (None, 'PLUS'), (None, 'TIMES'), (None, 'LPAREN'), (None, 'RPAREN'), (None, 'MINUS'), (None, 'DIVIDE'), (None, 'EQUALS')])]}
_lexstateignore = {'INITIAL': ' \t'}
_lexstateerrorf = {'INITIAL': 't_error'}
_lexstateeoff = {}
