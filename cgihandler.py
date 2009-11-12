#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import os
import sys
import logging
import wsgiref.handlers

sys.path.insert(0, '')
path = os.path.dirname(os.path.abspath(__file__))
if not path in sys.path:
    sys.path.append(path)
os.chdir(path)

import gluon.main

wsgiref.handlers.CGIHandler().run(gluon.main.wsgibase)
