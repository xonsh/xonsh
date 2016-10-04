#!/usr/bin/env python3
import subprocess
import os
import argparse

program_description = """Build and run Xonsh in a fresh, controlled
    environment using docker """

parser = argparse.ArgumentParser(description=program_description)

parser.add_argument('env', nargs='*', default=[], metavar='ENV=value')
parser.add_argument('--python', '-p', default='3.4', metavar='python_version')
parser.add_argument('--ptk', '-t', default='1.00', metavar='ptk_version')
parser.add_argument('--keep', action='store_true')
parser.add_argument('--build', action='store_true')
parser.add_argument('--command', '-c', default='xonsh',
                    metavar='command')

args = parser.parse_args()

docker_script = """
from python:{python_version}
RUN pip install --upgrade pip && pip install \\
  ply \\
  prompt-toolkit=={ptk_version} \\
  pygments
RUN mkdir /xonsh
WORKDIR /xonsh
ADD ./ ./
RUN python setup.py install
""".format(
    python_version=args.python,
    ptk_version=args.ptk)

print('Building and running Xonsh')
print('Using python ', args.python)
print('Using prompt-toolkit ', args.ptk)

with open('./Dockerfile', 'w+') as f:
    f.write(docker_script)

env_string = ' '.join(args.env)

subprocess.call(['docker', 'build', '-t', 'xonsh', '.'])
os.remove('./Dockerfile')

if not args.build:
    run_args = ['docker', 'run', '-ti']
    for e in args.env:
        run_args += ['-e', e]
    if not args.keep:
        run_args.append('--rm')
    run_args += ['xonsh', args.command]
    subprocess.call(run_args)
