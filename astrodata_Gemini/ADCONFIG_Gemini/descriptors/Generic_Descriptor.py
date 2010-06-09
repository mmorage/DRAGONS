from astrodata import Lookups
from astrodata import Descriptors

from astrodata.Calculator import Calculator

import GemCalcUtil
import re

from StandardDescriptorKeyDict import globalStdkeyDict
from StandardGenericKeyDict import stdkeyDictGeneric

class Generic_DescriptorCalc(Calculator):
    
    def ut_date(self, dataset, **args):
        """
        Return the ut_date value for generic data
        @param dataset: the data set
        @type dataset: AstroData
        @rtype: string
        @return: the UT date of the observation (YYYY-MM-DD)
        """
        try:
            hdu = dataset.hdulist
            ut_date = hdu[0].header[globalStdkeyDict['key_ut_date']]
            
            # Validate the result. The definition is taken from the FITS
            # standard document v3.0. Must be YYYY-MM-DD or
            # YYYY-MM-DDThh:mm:ss[.sss]. Here I also do some very basic checks
            # like ensuring the first digit of the month is 0 or 1, but I
            # don't do cleverer checks like 01<=M<=12. nb. seconds ss > 59 is
            # valid when leap seconds occur.
            
            if (re.match('\d\d\d\d-[01]\d-[0123]\d', ut_date)):
                ret_ut_date = ut_date
            
            m = re.match('(\d\d\d\d-[01]\d-[0123]\d)(T)([012]\d:[012345]\d:\d\d.*\d*)', ut_date)
            
            if (m):
                ret_ut_date = m.group(1)
                return str(ret_ut_date)
            else:
                return None
        except KeyError:
            return None
        
