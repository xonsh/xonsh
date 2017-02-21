#!/usr/bin/env xonsh
import os
x = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'printfile.xsh')
source @(x)
