#!/usr/bin/env python
"""The xonsh installer."""
from __future__ import print_function, unicode_literals
import os
import sys
try:
    from setuptools import setup
    HAVE_SETUPTOOLS = True
except ImportError:
    from distutils.core import setup
    HAVE_SETUPTOOLS = False

VERSION = '0.1.0'

TABLES = ['xonsh/lexer_table.py', 'xonsh/parser_table.py']

def clean_tables():
    for f in TABLES:
        if os.path.isfile(f):
            os.remove(f)
            print('Remove ' + f)

def build_tables():
    print('Building lexer and parser tables.')
    sys.path.insert(0, os.path.dirname(__file__))
    from xonsh.parser import Parser
    Parser(lexer_table='lexer_table', yacc_table='parser_table',
           outputdir='xonsh')
    sys.path.pop(0)

def main():
    print(logo)
    clean_tables()
    build_tables()
    with open('readme.rst', 'r') as f:
        readme = f.read()
    skw = dict(
        name='xonsh',
        description='an exotic, usable shell',
        long_description=readme,
        license='BSD',
        version=VERSION,
        author='Anthony Scopatz',
        maintainer='Anthony Scopatz',
        author_email='scopatz@gmail.com',
        url='https://github.com/scopatz/xonsh',
        platforms='Cross Platform',
        classifiers = ['Programming Language :: Python :: 3'],
        packages=['xonsh'],
        scripts=['scripts/xonsh'],
        )
    setup(**skw)

logo = """
                           ╓██▄                                              
                          ╙██▀██╕                                            
                         ▐██4Φ█▀█▌                                           
                       ²██▄███▀██^██                                         
                     -███╩▀ " ╒▄█████▀█                                      
                      ║██▀▀W╤▄▀ ▐║█╘ ╝█                                      
                 ▄m▀%Φ▀▀  ╝*"    ,α█████▓▄,▄▀Γ"▀╕                            
                 "▀██¼"     ▄═╦█╟║█▀ ╓ `^`   ,▄ ╢╕                           
                  ,▀╫M█▐j╓╟▀ ╔▓▄█▀  '║ ╔    ╣║▌  ▀▄                          
               ▄m▀▀███╬█╝▀  █▀^      "ÜM  j▐╟╫╨▒   ╙▀≡═╤═m▀╗                 
               █æsæ╓  ╕, ,▄Ä   ▐'╕H   LU  ║║╠╫Å^2=⌐         █                
            ▄æ%Å███╠█ª╙▄█▀      $1╙       ║║╟╫╩*T▄           ▌               
           ╙╗%▄,╦██▌█▌█╢M         ╕      M║║║║█═⌐ⁿ"^         ╫               
             ╙╣▀████@█░█    ▌╕╕   `      ▌║▐▐║█D═≈⌐¬ⁿ      s ║⌐              
               ╙╬███▓║█`     ▌╚     ╕   ╕▌║▐▐╣▌⌐*▒▒Dù`       ▐▌              
                ╙╬██╨U█      ╟      $ ▌ ▌▌▐▐▐M█▄═≤⌐%       ╓⌐ ▌              
                 ║║█▄▌║             ╟ ▌ ▌M▐▐▐M█▀▒▒▒22,       ▐▌              
                  ███╙^▌            ║ ▌ ⌐M▐▐▐M█≤⌐⌐¬──        ▐M              
                  ║██ ▌╙   ╓       H║ ▌╒ M║▐▐M█"^^^^^"ⁿ      ║               
                   ██╕╙@▓   ╕      ▌║ H'  ║▐▐▐█══=.,,,       █               
                   ╙█▓╔╚╚█     ╠   ▌└╒ ▌▐ ╚║║║▀****ⁿ -      ╓▌               
                    ╙█▌¼V╚▌   ▌  ╕ ▌ ║╒ ║ ▌▒╠█▀≤≤≤≤≤⌐       █                
                     ╙█▌╔█╚▌     ┘ M ▌║ ╫ UUM██J^^"        ▐▌                
                      ╙██╙█╙▌  ╕$j  ▐⌐▌ ▌║╝╟█Å%%%≈═        █                 
                       ╙╣█╣█^▌ ╠║▐  ║ ▌▐.DU██^[""ⁿ       -╒▌                 
                         ▀█▄█`▌ ░M▀ ▌▐ Å£╝╝█╜%≈═╓""w   ⁿ⌐ █                  
                          `▀▄▀`▌ ▌█▐⌐║▐UW╖██%≤═░*─    =z ▄Γ                  
                            ╙██╙▄▌█  ▌Å╛╣██╨%╤ƒⁿ=    -` ▄┘                   
                              █▌╢▓▌▌ W £6█╤,"ⁿ `   ▄≡▀▀▀                     
                               █"█▌▌╟Å╓█╓█▀%`    ▄▀                          
                               ╙▌██`▒U▓U█%╗*     █                           
                                ▌╫║ ▌ÅÅ║▀╛¬`      `"█                        
                                ▌╫  ╫╟ █▄     ~╦%▒╥4^                        
                                ▌▌  "M█ `▀╕ X╕"╗▄▀^                          
                                █▌   ╓M   ╙▀e▀▀^                             
                                ╙██▄▄▀                                       
                                  ^^                                         
"""

if __name__ == '__main__':
    main()

