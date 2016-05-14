#!/usr/bin/env python
import sys 
import subprocess
import os

pythonVersion = '3.5'
ptkVersion = '1.00'

if len(sys.argv) > 1:
    pythonVersion = sys.argv[1]
    if len(sys.argv) > 2:
        ptkVersion = sys.argv[2]

print('Building and runing Xonsh')
print('Using python ', pythonVersion)
print('Using prompt-toolkit ', ptkVersion)

dockerFile = 'from python:'+pythonVersion + '\n'
dockerFile += 'RUN pip install --upgrade pip && pip install \\\n'
dockerFile += '  ply \\\n'
dockerFile += '  prompt-toolkit=='+ptkVersion+ ' \\\n'
dockerFile += '  pygments\n'
dockerFile += 'RUN mkdir /xonsh\n'
dockerFile += 'WORKDIR /xonsh\n'
dockerFile += 'CMD /usr/bin/env xonsh\n'
dockerFile += 'ENV XONSH_COLOR_STYLE "paraiso-dark\n'
dockerFile += 'ADD ./ ./\n'
dockerFile += 'RUN python setup.py install\n'

with open('./Dockerfile', 'w+') as f:
    f.write(dockerFile)

subprocess.call(['docker', 'build', '-t' , 'xonsh', '.'])
os.remove('./Dockerfile')
subprocess.call(['docker', 'run', '-ti' , 'xonsh'])


