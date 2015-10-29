# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""
Package reads in DCIMG files and integrates them as first class citizens
into the ULTRACAM pipeline.
"""

# Affiliated packages may add whatever they like to this file, but
# should keep this content at the top.
# ----------------------------------------------------------------------------
from ._astropy_init import *
# ----------------------------------------------------------------------------

# For egg_info test builds to pass, put package imports here.
if not _ASTROPY_SETUP_:
    #from utils import *
    pass