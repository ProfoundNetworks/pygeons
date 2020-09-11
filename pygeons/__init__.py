#
# -*- coding: utf-8 -*-
# (C) Copyright: Profound Networks, LLC 2016
#

"""Top-level package for pygeons."""

import logging

__author__ = """Michael Penkov"""
__email__ = 'misha.penkov@gmail.com'
__version__ = '0.1.1'

_LOGGER = logging.getLogger(__name__)
#
# Prevent stderr message about "no handlers found".
# It is possible that somebody is using Pygeon without logging.
# https://docs.python.org/2/howto/logging.html#configuring-logging-for-a-library
#
_LOGGER.addHandler(logging.NullHandler())
