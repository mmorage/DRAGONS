#
#                                                                      caches.py
# ------------------------------------------------------------------------------
import os

# GLOBAL/CONSTANTS (could be exported to config file)
# [DEFAULT]
CALS = "calibrations"

# [caches]
caches = { 'reducecache'  : '.reducecache',
           'storedcals'   : os.path.join(CALS,"storedcals"),
           'retrievedcals': os.path.join(CALS,"retrievedcals"),
           'calibrations' : CALS
       }

CALDIR     =  caches["storedcals"]
adatadir   = "./recipedata/"                # ???
calindfile = os.path.join('.', caches['reducecache'], "calindex.pkl")
stkindfile = os.path.join('.', caches['reducecache'], "stkindex.pkl")

def set_caches():
    cachedict = {}
    for cachename, cachedir in caches.items():
        if not os.path.exists(cachedir):
            os.makedirs(cachedir)
        cachedict.update({cachename:cachedir})
    return cachedict
