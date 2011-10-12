# This module contains user level functions related to source detection
# and photometry of the input dataset

import os
import sys
import subprocess
from copy import deepcopy
import numpy as np
import pyfits as pf
import pywcs
from astrodata import AstroData
from astrodata import Errors
from astrodata import Lookups
from astrodata.ConfigSpace import lookup_path
from astrodata.adutils import gemLog
from gempy import geminiTools as gt
from gempy import astrotools as at

# Load the timestamp keyword dictionary that will be used to define the keyword
# to be used for the time stamp for the user level function
timestamp_keys = Lookups.get_lookup_table("Gemini/timestamp_keywords",
                                          "timestamp_keys")

def add_objcat(adinput=None, extver=1, replace=False,
               id=None, x=None, y=None, ra=None, dec=None, 
               fwhm_pix=None, fwhm_arcsec=None, ellipticity=None,
               flux=None, class_star=None, flags=None,
               refid=None, refmag=None):
    """
    Add OBJCAT table if it does not exist, update or replace it if it does.
    Lengths of all provided lists should be the same.
    
    :param adinput: AD object(s) to add table to
    :type adinput: AstroData objects, either a single instance or a list
    
    :param extver: Extension number for the table (should match the science
                   extension).
    :type extver: int
    
    :param replace: Flag to determine if an existing OBJCAT should be
                    replaced or updated in place. If replace=False, the
                    length of all lists provided must match the number
                    of entries currently in OBJCAT.
    :type replace: boolean
    
    :param id: List of ID numbers. If not provided, will be automatically
               assigned to the index (+1) of the list of x-values.
    :type id: Python list of ints
    
    :param x: List of x (pixel) coordinates. Required if creating new table.
    :type x: Python list of floats
    
    :param y: List of y (pixel) coordinates. Required if creating new table.
    :type y: Python list of floats
    
    :param ra: List of RA values. Required if creating new table.
    :type ra: Python list of floats
    
    :param dec: List of Dec values. Required if creating new table.
    :type dec: Python list of floats
    
    :param flux: List of flux values. Set to -999 if not provided.
    :type flux: Python list of floats
    
    :param fwhm_pix: List of fwhm values in pixels. Set to -999 if not provided.
    :type fwhm_pix: Python list of floats
    
    :param fwhm_arcsec: List of fwhm values in arcsec. Set to -999 if not provided.
    :type fwhm_arcsec: Python list of floats
    
    :param ellipticity: List of ellipticity values. Set to -999 if not provided.
    :type ellipticity: Python list of floats
    
    :param class_star: List of class_star values. Set to -999 if not provided.
    :type class_star: Python list of floats (value between 0 and 1)
    
    :param flags: List of flags values. Set to 0 (good) if not provided.
    :type flags: Python list of ints    

    :param refid: List of reference ids. Set to '' if not provided.
    :type refid: Python list of strings
    
    :param refmag: List of reference magnitude values. Set to -999 if 
                   not provided.
    :type refmag: Python list of floats
    """
    
    # Instantiate the log. This needs to be done outside of the try block,
    # since the log object is used in the except block 
    log = gemLog.getGeminiLog()
    
    # The validate_input function ensures that adinput is not None and returns
    # a list containing one or more AstroData objects
    adinput = gt.validate_input(adinput=adinput)
    
    # Define the keyword to be used for the time stamp for this user level
    # function
    timestamp_key = timestamp_keys["add_objcat"]
    
    # Initialize the list of output AstroData objects
    adoutput_list = []
    try:
        
        # Loop over each input AstroData object in the input list
        for ad in adinput:
            
            # Check if OBJCAT already exists and just update if desired
            objcat = ad["OBJCAT",extver]
            if objcat and not replace:
                log.fullinfo("Table already exists; updating values.")
                if id is not None:
                    objcat.data.field("id")[:] = id
                if x is not None:
                    objcat.data.field("x")[:] = x
                if y is not None:
                    objcat.data.field("y")[:] = y
                if ra is not None:
                    objcat.data.field("ra")[:] = ra
                if dec is not None:
                    objcat.data.field("dec")[:] = dec
                if flux is not None:
                    objcat.data.field("flux")[:] = flux
                if fwhm_pix is not None:
                    objcat.data.field("fwhm_pix")[:] = fwhm_pix
                if fwhm_arcsec is not None:
                    objcat.data.field("fwhm_arcsec")[:] = fwhm_arcsec
                if ellipticity is not None:
                    objcat.data.field("ellipticity")[:] = ellipticity
                if class_star is not None:
                    objcat.data.field("class_star")[:] = class_star
                if flags is not None:
                    objcat.data.field("flags")[:] = flags
                if refid is not None:
                    objcat.data.field("refid")[:] = refid
                if refmag is not None:
                    objcat.data.field("refmag")[:] = refmag
                continue
            
            # Make new table: x, y, ra, dec required
            if x is None or y is None or ra is None or dec is None:
                raise Errors.InputError("Arguments x, y, ra, dec must " +
                                        "not be None.")
            # define sensible placeholders for missing information
            nlines = len(x)
            if id is None:
                id = range(1,nlines+1)
            if flux is None:
                flux = [-999]*nlines
            if fwhm_pix is None:
                fwhm_pix= [-999]*nlines
            if fwhm_arcsec is None:
                fwhm_arcsec = [-999]*nlines
            if ellipticity is None:
                ellipticity = [-999]*nlines
            if class_star is None:
                class_star = [-999]*nlines
            if flags is None:
                flags = [0]*nlines
            if refid is None:
                refid = [""]*nlines
            if refmag is None:
                refmag = [-999]*nlines
            
            # define pyfits columns
            c1 = pf.Column(name="id",format="J",array=id)
            c2 = pf.Column(name="x",format="E",array=x)
            c3 = pf.Column(name="y",format="E",array=y)
            c4 = pf.Column(name="ra",format="E",array=ra)
            c5 = pf.Column(name="dec",format="E",array=dec)
            c6 = pf.Column(name="flux",format="E",array=flux)
            c7 = pf.Column(name="fwhm_pix",format="E",array=fwhm_pix)
            c8 = pf.Column(name="fwhm_arcsec",format="E",array=fwhm_arcsec)
            c9 = pf.Column(name="ellipticity",format="E",array=ellipticity)
            c10 = pf.Column(name="class_star",format="E",array=class_star)
            c11 = pf.Column(name="flags",format="J",array=flags)
            c12 = pf.Column(name="refid",format="22A",array=refid)
            c13 = pf.Column(name="refmag",format="E",array=refmag)
            
            # make new pyfits table
            col_def = pf.ColDefs([c1,c2,c3,c4,c5,c6,c7,c8,c9,c10,c11,c12,c13])
            tb_hdu = pf.new_table(col_def)
            tb_ad = AstroData(tb_hdu)
            tb_ad.rename_ext("OBJCAT",extver)
            
            # replace old version or append new table to AD object
            if objcat:
                ad = _replace_ext(ad,"OBJCAT",extver,tb_hdu)
            else:
                ad.append(tb_ad)
            
            # Add the appropriate time stamps to the PHU
            gt.mark_history(adinput=ad, keyword=timestamp_key)
            
            # Append the output AstroData object to the list of output
            # AstroData objects
            adoutput_list.append(ad)
        
        # Return the list of output AstroData objects
        return adoutput_list
    except:
        # Log the message from the exception
        log.critical(repr(sys.exc_info()[1]))
        raise


def detect_sources(adinput=None, method="sextractor", 
                   sigma=None, threshold=3.0, fwhm=None,
                   max_sources=50, centroid_function="moffat"):
    """
    Find x,y positions of all the objects in the input image. Append 
    a FITS table extension with position information plus columns for
    standard objects to be updated with positions from addReferenceCatalogs
    (if any are found for the field).
    
    The appended FITS table with extension name 'OBJCAT' will contain
    these columns:
    - 'id'    : Unique ID. Simple running number.
    - 'x'     : x coordinate of the detected object.
    - 'y'     : y coordinate of the detected object.
                Both x and y are with respect to the lower left corner. 
                They are 1-based values, i.e. as in ds9.
    - 'ra'    : ra values, in degrees. Calculated from the fits header WCS
    - 'dec'   : dec values in degrees. ditto
    - 'flux'  : Flux given by the gauss fit of the object
    - 'refid' : Reference ID for the reference star found in the field
    - 'refmag': Reference magnitude. 'refid' and 'refmag' will be fill
                by the 'correlateWithReferenceCatalogs' function.
    
    :param adinput: image(s) to detect sources in
    :type adinput: AstroData objects, either a single instance or a list
    
    :param method: source detection algorithm to use
    :type method: string; options are 'daofind','sextractor'

    :param centroid_function: Function for centroid fitting with daofind
    :type centroid_function: string, can be: 'moffat','gauss'
                    Default: 'moffat'

    :param sigma: The mean of the background value for daofind. If nothing
                  is passed, it will be automatically determined
    :type sigma: float
    
    :param threshold: Threshold intensity for a point source for daofind; should
                   generally be at least 3 or 4 sigma above background RMS.
    :type threshold: float
    
    :param fwhm: FWHM to be used in the convolve filter for daofind. This
                 ends up playing a factor in determining the size of the kernel
                 put through the gaussian convolve.
    :type fwhm: float
    
    """
    
    # Instantiate the log. This needs to be done outside of the try block,
    # since the log object is used in the except block 
    log = gemLog.getGeminiLog()
    
    # The validate_input function ensures that adinput is not None and returns
    # a list containing one or more AstroData objects
    adinput = gt.validate_input(adinput=adinput)
    
    # Define the keyword to be used for the time stamp for this user level
    # function
    timestamp_key = timestamp_keys["detect_sources"]
    
    # Initialize the list of output AstroData objects
    adoutput_list = []
    try:
        
        # Loop over each input AstroData object in the input list
        for ad in adinput:
            
            seeing_est = ad.phu_get_key_value("MEANFWHM")
            for sciext in ad["SCI"]:
                
                extver = sciext.extver()
                
                # find objects in pixel coordinates
                if method not in ["sextractor","daofind"]:
                    raise Errors.InputError("Source detection method "+
                                            method+" is unsupported.")
                
                if method=="sextractor":
                    dqext = ad["DQ",extver]
                    try:
                        obj_list,seeing_est = _sextractor(sciext=sciext,
                                                          dqext=dqext,
                                                     seeing_estimate=seeing_est)
                    except:
                        log.warning("Sextractor failed. Setting method=daofind")
                        method="daofind"
                    else:
                        if len(obj_list)==0:
                            log.stdinfo("No sources found in %s['SCI',%d]" %
                                        (ad.filename,extver))
                            obj_x,obj_y,obj_ra,obj_dec = ([],[],[],[])
                            flux,fwhm_pix,fwhm_arcsec,ellip = (None,None,None,None)
                            class_star,flags = (None,None)
                        else:
                            obj_x = obj_list['x']
                            obj_y = obj_list['y']
                            obj_ra = obj_list['ra']
                            obj_dec = obj_list['dec']
                            flux = obj_list['flux']
                            fwhm_pix = obj_list['fwhm_pix']
                            fwhm_arcsec = obj_list['fwhm_arcsec']
                            ellip = obj_list['ellipticity']
                            class_star = obj_list['class_star']
                            flags = obj_list['flags']

                            nobj = len(obj_ra)
                            log.stdinfo("Found %d sources in %s['SCI',%d]" %
                                        (nobj,ad.filename,extver))
                if method=="daofind":
                    pixscale = sciext.pixel_scale()
                    if pixscale is None:
                        log.warning("%s does not have a pixel scale, "% ad.filename +
                                    "using 1.0 arcsec/pix")
                        pixscale = 1.0

                    if fwhm is None:
                        if seeing_est is not None:
                            fwhm = seeing_est / pixscale
                        else:
                            fwhm = 0.8 / pixscale

                    obj_list = _daofind(sciext=sciext, sigma=sigma,
                                        threshold=threshold, fwhm=fwhm)

                    # daofind does not return flux, fwhm, ellipticity, etc.
                    flux,fwhm_pix,fwhm_arcsec,ellip = (None,None,None,None)
                    class_star,flags = (None,None)

                    if len(obj_list)==0:
                        log.stdinfo("No sources found in %s['SCI',%d]" %
                                    (ad.filename,extver))
                        obj_x,obj_y,obj_ra,obj_dec = ([],[],[],[])
                    else:

                        # separate pixel coordinates into x, y lists
                        obj_x, obj_y = [np.asarray(obj_list)[:,k] for k in [0,1]]
                
                        # use WCS to convert pixel coordinates to RA/Dec
                        wcs = pywcs.WCS(sciext.header)
                        obj_ra, obj_dec = wcs.wcs_pix2sky(obj_x,obj_y,1)
                
                        nobj = len(obj_ra)
                        log.stdinfo("Found %d sources in %s['SCI',%d]" %
                                    (nobj,ad.filename,extver))
                
            
                adoutput = add_objcat(adinput=ad, extver=extver, 
                                      x=obj_x, y=obj_y, 
                                      ra=obj_ra, dec=obj_dec,
                                      flux=flux,fwhm_pix=fwhm_pix,
                                      fwhm_arcsec=fwhm_arcsec,
                                      ellipticity=ellip,
                                      class_star=class_star,
                                      flags=flags,
                                      replace=True)
                
                ad = adoutput[0]

            
            # Do some simple photometry to get fwhm, ellipticity
            if method=="daofind":
                log.stdinfo("Fitting sources for simple photometry")
                if seeing_est is None:
                    # Run the fit once to get a rough seeing estimate 
                    junk,seeing_est = _fit_sources(ad,ext=1,max_sources=20,
                                                   threshold=threshold,
                                                   centroid_function=centroid_function,
                                                   seeing_estimate=None)
                ad,seeing_est = _fit_sources(ad,max_sources=max_sources,
                                             threshold=threshold,
                                             centroid_function=centroid_function,
                                             seeing_estimate=seeing_est)
        
            # Add the appropriate time stamps to the PHU
            gt.mark_history(adinput=ad, keyword=timestamp_key)
            
            # Append the output AstroData object to the list of output
            # AstroData objects
            adoutput_list.append(ad)
        
        # Return the list of output AstroData objects
        return adoutput_list
    except:
        # Log the message from the exception
        log.critical(repr(sys.exc_info()[1]))
        raise


##############################################################################
# Below are the helper functions for the user level functions in this module #
##############################################################################

def _daofind(sciext=None, sigma=None, threshold=2.5, fwhm=5.5, 
             sharplim=[0.2,1.0], roundlim=[-1.0,1.0], window=None,
             grid=False, rejection=None, ratio=None):
    """
    Performs similar to the source detecting algorithm 
    'http://idlastro.gsfc.nasa.gov/ftp/pro/idlphot/find.pro'.
    
    References:
        This code is heavily influenced by 
        'http://idlastro.gsfc.nasa.gov/ftp/pro/idlphot/find.pro'.
        'find.pro' was written by W. Landsman, STX February, 1987.
        
        This code was converted to Python with areas re-written for 
        optimization by:
        River Allen, Gemini Observatory, December 2009. riverallen@gmail.com
        
        Updated by N. Zarate and M. Clarke for incorporation into gempy
        package, February 2011 and June 2011.
    """
    
    # import a few things only required by this helper function
    import time
    from convolve import convolve2d
    
    log = gemLog.getGeminiLog()
    
    if not sciext:
        raise Errors.InputError("_daofind requires a science extension.")
    else:
        sciData = sciext.data
        
    if window is not None:
        if type(window) == tuple:
            window = [window]
        elif type(window) == list:
            pass
        else:
            raise Errors.InputError("'window' must be a tuple of length 4, " +
                                    "or a list of tuples length 4.")
            
        for wind in window:
            if type(wind) == tuple:
                if len(wind) == 4:
                    continue
                else:
                    raise Errors.InputError("A window tuple has incorrect " +
                                            "information, %s, require x,y," +
                                            "width,height" %(str(wind)))
            else:
                raise Errors.InputError("The window list contains a " +
                                        "non-tuple. %s" %(str(wind)))
            
    if len(sharplim) < 2:
        raise Errors.InputError("Sharplim parameter requires 2 num elements. "+
                                "(i.e. [0.2,1.0])")
    if len(roundlim) < 2:
        raise Errors.InputError("Roundlim parameter requires 2 num elements. "+
                                "(i.e. [-1.0,1.0])")
             
    # Setup
    # -----
    
    ost = time.time()
    #Maximum size of convolution box in pixels 
    maxConvSize = 13
    
    #Radius is 1.5 sigma
    radius = np.maximum(0.637 * fwhm, 2.001)
    radiusSQ = radius ** 2
    kernelHalfDimension = np.minimum(np.array(radius, copy=0).astype(np.int32), 
                                  (maxConvSize - 1) / 2)
    # Dimension of the kernel or "convolution box"
    kernelDimension = 2 * kernelHalfDimension + 1 
    
    sigSQ = (fwhm / 2.35482) ** 2
    
    # Mask identifies valid pixels in convolution box 
    mask = np.zeros([kernelDimension, kernelDimension], np.int8)
    # g will contain Gaussian convolution kernel
    gauss = np.zeros([kernelDimension, kernelDimension], np.float32)
    
    row2 = (np.arange(kernelDimension) - kernelHalfDimension) ** 2
    
    for i in np.arange(0, (kernelHalfDimension)+(1)):
        temp = row2 + i ** 2
        gauss[kernelHalfDimension - i] = temp
        gauss[kernelHalfDimension + i] = temp
    
    #MASK is complementary to SKIP in Stetson's Fortran
    mask = np.array(gauss <= radiusSQ, copy=0).astype(np.int32)
    #Value of c are now equal to distance to center
    good = np.where(np.ravel(mask))[0]
    pixels = good.size
    
    # Compute quantities for centroid computations that can be used
    # for all stars
    gauss = np.exp(-0.5 * gauss / sigSQ)
    
    """
     In fitting Gaussians to the marginal sums, pixels will arbitrarily be
     assigned weights ranging from unity at the corners of the box to
     kernelHalfDimension^2 at the center (e.g. if kernelDimension = 5 or 7,
     the weights will be
    
                                     1   2   3   4   3   2   1
          1   2   3   2   1          2   4   6   8   6   4   2
          2   4   6   4   2          3   6   9  12   9   6   3
          3   6   9   6   3          4   8  12  16  12   8   4
          2   4   6   4   2          3   6   9  12   9   6   3
          1   2   3   2   1          2   4   6   8   6   4   2
                                     1   2   3   4   3   2   1
    
     respectively). This is done to desensitize the derived parameters to
     possible neighboring, brighter stars.[1]
    """
    
    xwt = np.zeros([kernelDimension, kernelDimension], np.float32)
    wt = kernelHalfDimension - abs(np.arange(kernelDimension).astype(np.float32)
                                   - kernelHalfDimension) + 1
    for i in np.arange(0, kernelDimension):
        xwt[i] = wt
    
    ywt = np.transpose(xwt)
    sgx = np.sum(gauss * xwt, 1)
    sumOfWt = np.sum(wt)
    
    sgy = np.sum(gauss * ywt, 0)
    sumgx = np.sum(wt * sgy)
    sumgy = np.sum(wt * sgx)
    sumgsqy = np.sum(wt * sgy * sgy)
    sumgsqx = np.sum(wt * sgx * sgx)
    vec = kernelHalfDimension - np.arange(kernelDimension).astype(np.float32)
    
    dgdx = sgy * vec
    dgdy = sgx * vec
    sdgdxs = np.sum(wt * dgdx ** 2)
    sdgdx = np.sum(wt * dgdx)
    sdgdys = np.sum(wt * dgdy ** 2)
    sdgdy = np.sum(wt * dgdy)
    sgdgdx = np.sum(wt * sgy * dgdx)
    sgdgdy = np.sum(wt * sgx * dgdy)
    
    kernel = gauss * mask          #Convolution kernel now in c
    sumc = np.sum(kernel)
    sumcsq = np.sum(kernel ** 2) - (sumc ** 2 / pixels)
    sumc = sumc / pixels
    
    # The reason for the flatten is because IDL and numpy treat 
    # statements like arr[index], where index 
    # is an array, differently. For example, arr.shape = (100,100), 
    # in IDL index=[400], arr[index]
    # would work. In numpy you need to flatten in order to get the 
    # arr[4][0] you want.
    kshape = kernel.shape
    kernel = kernel.flatten()
    kernel[good] = (kernel[good] - sumc) / sumcsq
    kernel.shape = kshape
    
    # Using row2 here is pretty confusing (From IDL code)
    # row2 will be something like: [1   2   3   2   1]
    c1 = np.exp(-.5 * row2 / sigSQ)
    sumc1 = np.sum(c1) / kernelDimension
    sumc1sq = np.sum(c1 ** 2) - sumc1
    c1 = (c1 - sumc1) / sumc1sq
    
    # From now on we exclude the central pixel
    mask[kernelHalfDimension,kernelHalfDimension] = 0
    
    # Reduce the number of valid pixels by 1
    pixels = pixels - 1
    # What this operation looks like:
    # ravel(mask) = [0 0 1 1 1 0 0 0 1 1 1 1 1 0 1 1 1 1 1 1 1 1 1 1 0 1 ...]
    # where(ravel(mask)) = (array([ 2,  3,  4,  8,  9, 10, 11, 12, 14, ...]),)
    # ("good" identifies position of valid pixels)
    good = np.where(np.ravel(mask))[0]
    
    # x and y coordinate of valid pixels 
    xx = (good % kernelDimension) - kernelHalfDimension
    
    # relative to the center
    yy = np.array(good / kernelDimension, 
                  copy=0).astype(np.int32) - kernelHalfDimension
    
    # Extension and Window / Grid
    # ---------------------------
    xyArray = []
    outputLines = []
    
    # Estimate the background if none provided
    if sigma is None:
        sigma = _estimate_sigma(sciData)
        log.fullinfo("Estimated Background: %.3f" % sigma)

    hmin = sigma * threshold
    
    if window is None:
        # Make the window the entire image
        window = [(0,0,sciData.shape[1],sciData.shape[0])]
    
    if grid:
        ySciDim, xSciDim = sciData.shape
        xgridsize = int(xSciDim / ratio) 
        ygridsize = int(ySciDim / ratio)
        window = []
        for ypos in range(ratio):
            for xpos in range(ratio):
                window.append( (xpos * xgridsize, ypos * ygridsize, 
                                xgridsize, ygridsize) )
    
    if rejection is None:
        rejection = []
        
    windName = 0
    for wind in window:
        windName += 1
        subXYArray = []
        
        ##@@TODO check for negative values, check that dimensions
        #        don't violate overall dimensions.
        yoffset, xoffset, yDimension, xDimension = wind
        
        sciSection = sciData[xoffset:xoffset+xDimension,
                             yoffset:yoffset+yDimension]
        
        # Quickly determine if a window is worth processing
        rejFlag = False
        
        for rejFunc in rejection:
            if rejFunc(sciSection, sigma, threshold):
                rejFlag = True
                break
        
        if rejFlag:
            # Reject
            continue
        
        # Convolve image with kernel
        log.debug("Beginning convolution of image")
        st = time.time()
        h = convolve2d( sciSection, kernel )
        
        et = time.time()
        log.debug("Convolve Time: %.3f" % (et-st))
        
        if not grid:
            h[0:kernelHalfDimension,:] = 0
            h[xDimension - kernelHalfDimension:xDimension,:] = 0
            h[:,0:kernelHalfDimension] = 0
            h[:,yDimension - kernelHalfDimension:yDimension] = 0
        
        log.debug("Finished convolution of image")
        
        # Filter
        offset = yy * xDimension + xx
        
        # Valid image pixels are greater than hmin
        index = np.where(np.ravel(h >= hmin))[0]
        nfound = index.size
        
        # Any maxima found?
        if nfound > 0:
            h = h.flatten()
            for i in np.arange(pixels):
                # Needs to be changed
                try:
                    stars = np.where(np.ravel(h[index] 
                                              >= h[index+ offset[i]]))[0]
                except:
                    break
                nfound = stars.size
                # Do valid local maxima exist?
                if nfound == 0:
                    log.debug("No objects found.")
                    break
                index = index[stars]
            h.shape = (xDimension, yDimension)
            
            ix = index % yDimension               # X index of local maxima
            iy = index / yDimension               # Y index of local maxima
            ngood = index.size
        else:
            log.debug("No objects above hmin (%s) were found." %(str(hmin)))
            continue
        
        # Loop over star positions; compute statistics
        
        st = time.time()
        for i in np.arange(ngood):
            temp = np.array(sciSection[iy[i]-kernelHalfDimension :
                                           (iy[i] + kernelHalfDimension)+1,
                                       ix[i] - kernelHalfDimension :
                                           (ix[i] + kernelHalfDimension)+1])
            
            # pixel intensity
            pixIntensity = h[iy[i],ix[i]]
            
            # Compute Sharpness statistic
            #@@FIXME: This should do proper checking...the issue
            # is an out of range index with kernelhalf and temp
            # IndexError: index (3) out of range (0<=index<=0) in dimension 0
            try:
                sharp1 = (temp[kernelHalfDimension,kernelHalfDimension] - 
                          (np.sum(mask * temp)) / pixels) / pixIntensity
            except:
                continue
            
            if (sharp1 < sharplim[0]) or (sharp1 > sharplim[1]):
                # Reject
                # not sharp enough?
                continue
            
            dx = np.sum(np.sum(temp, 1) * c1)
            dy = np.sum(np.sum(temp, 0) * c1)
            
            if (dx <= 0) or (dy <= 0):
                # Reject
                continue
            
            # Roundness statistic
            around = 2 * (dx - dy) / (dx + dy)
            
            # Reject if not within specified roundness boundaries.
            if (around < roundlim[0]) or (around > roundlim[1]):
                # Reject
                continue
            
            """
             Centroid computation: The centroid computation was modified
             in Mar 2008 and now differs from DAOPHOT which multiplies the
             correction dx by 1/(1+abs(dx)). The DAOPHOT method is more robust
             (e.g. two different sources will not merge)
             especially in a package where the centroid will be subsequently be
             redetermined using PSF fitting. However, it is less accurate,
             and introduces biases in the centroid histogram. The change here
             is the same made in the IRAF DAOFIND routine (see
             http://iraf.net/article.php?story=7211&query=daofind ) [1]
            """
            
            sd = np.sum(temp * ywt, 0)
            
            sumgd = np.sum(wt * sgy * sd)
            sumd = np.sum(wt * sd)
            sddgdx = np.sum(wt * sd * dgdx)
            
            hx = (sumgd - sumgx * sumd / sumOfWt) / (sumgsqy - 
                                                     sumgx ** 2 / sumOfWt)
            
            # HX is the height of the best-fitting marginal Gaussian. If
            # this is not positive then the centroid does not make sense. [1]
            if (hx <= 0):
                # Reject
                continue
            
            skylvl = (sumd - hx * sumgx) / sumOfWt
            dx = (sgdgdx -(sddgdx - sdgdx*(hx*sumgx + 
                                           skylvl*sumOfWt))) /(hx*sdgdxs /
                                                               sigSQ)
            
            if abs(dx) >= kernelHalfDimension:
                # Reject
                continue
            
            #X centroid in original array
            xcen = ix[i] + dx
            
            # Find Y centroid
            sd = np.sum(temp * xwt, 1)
            
            sumgd = np.sum(wt * sgx * sd)
            sumd = np.sum(wt * sd)
            
            sddgdy = np.sum(wt * sd * dgdy)
            
            hy = (sumgd - sumgy*sumd/sumOfWt) / (sumgsqx - sumgy**2/sumOfWt)
            
            if (hy <= 0):
                # Reject
                continue
            
            skylvl = (sumd - hy*sumgy) / sumOfWt
            dy = (sgdgdy - (sddgdy - 
                            sdgdy*(hy*sumgy + skylvl*sumOfWt))) / (hy*sdgdys /
                                                                   sigSQ)
            if abs(dy) >= kernelHalfDimension:
                # Reject 
                continue
            
            ycen = iy[i] + dy    #Y centroid in original array
            
            subXYArray.append( [xcen, ycen, pixIntensity] )
            
        et = time.time()
        log.debug("Looping over Stars time: %.3f" % (et-st))
        
        subXYArray = _average_each_cluster( subXYArray, 10 )
        xySize = len(subXYArray)
        
        
        for i in range( xySize ):
            subXYArray[i] = subXYArray[i].tolist()
            # I have no idea why the positions are slightly modified.
            # Was done originally in iqTool, perhaps for minute correcting.
            subXYArray[i][0] += 1
            subXYArray[i][1] += 1
            
            subXYArray[i][0] += yoffset
            subXYArray[i][1] += xoffset
        
        xyArray.extend(subXYArray)
            
    oet = time.time()
    overall_time = (oet-ost)
    log.debug("No. of objects detected: %i" % len(xyArray))
    log.debug("Overall time:%.3f seconds." % overall_time)
    
    return xyArray


def _estimate_sigma(scidata):
    fim = np.copy(scidata)
    stars = np.where(fim > (scidata.mean() + scidata.std()))
    fim[stars] = scidata.mean()
        
    outside = np.where(fim < (scidata.mean() - scidata.std()))
    fim[outside] = scidata.mean()

    sigma = fim.std()

    return sigma

def _average_each_cluster( xyArray, pixApart=10.0 ):
    """
    daofind can produce multiple centers for an object. This
    algorithm corrects that.
    For Example: 
    626.645599527 179.495974369
    626.652254706 179.012831637
    626.664059364 178.930738423
    626.676504143 178.804093054
    626.694643376 178.242374891
    
    This function will try to cluster these close points together, and
    produce a single center by taking the mean of the cluster. This
    function is based off the removeNeighbors function in iqUtil.py
    
    :param xyArray: The list of centers of found stars.
    :type xyArray: List
    
    :param pixApart: The max pixels apart for a star to be considered
                     part of a cluster. 
    :type pixApart: Number
    
    :return: The centroids of the stars sorted by the X dimension.
    :rtype: List
    """

    newXYArray = []
    xyArray.sort()
    xyArray = np.array( xyArray )
    xyArrayForMean = []
    xyClusterFlag = False
    j = 0
    while j < (xyArray.shape[0]):
        i = j + 1
        while i < xyArray.shape[0]:
            diffx = xyArray[j][0] - xyArray[i][0]
            if abs(diffx) < pixApart:
                diffy = xyArray[j][1] - xyArray[i][1]
                if abs(diffy) < pixApart:
                    if not xyClusterFlag:
                        xyClusterFlag = True
                        xyArrayForMean.append(j)
                    xyArrayForMean.append(i)
                    
                i = i + 1
            else:
                break
        
        if xyClusterFlag:
            xyMean = [np.mean( xyArray[xyArrayForMean], axis=0 ),
                      np.mean( xyArray[xyArrayForMean], axis=1 )]
            newXYArray.append( xyMean[0] )
            # Almost equivalent to reverse, except for numpy
            xyArrayForMean.reverse()
            for removeIndex in xyArrayForMean:
                xyArray = np.delete( xyArray, removeIndex, 0 )
            xyArrayForMean = []
            xyClusterFlag = False
            j = j - 1
        else:
            newXYArray.append( xyArray[j] )
        
        
        j = j + 1
    
    return newXYArray

def _replace_ext(ad,extname,extver,new_hdu):
    """
    This is a helper function to replace an existing AD extension with a new
    Pyfits HDU. It should be replaced by an AstroData member function
    when available.
    """
    
    intext = ad.get_int_ext((extname,extver),hduref=True)
    
    if intext==0:
        raise Errors.AstroDataError("Cannot replace_ext on PHU")
    
    ad.hdulist[intext] = new_hdu
    
    return ad


def _sextractor(sciext=None,dqext=None,seeing_estimate=None):

    # Get the log
    log = gemLog.getGeminiLog()

    # Get path to default sextractor parameter files
    default_dict = Lookups.get_lookup_table(
                             "Gemini/source_detection/sextractor_default_dict",
                             "sextractor_default_dict")
    for key in default_dict:
        default_file = lookup_path(default_dict[key]).rstrip(".py")
        default_dict[key] = default_file
    
    # Write the science extension to a temporary file on disk
    scitmpfn = "tmp%ssx%s%s%s" % (str(os.getpid()),sciext.extname(),
                                  sciext.extver(),
                                  os.path.basename(sciext.filename))
    log.fullinfo("Writing temporary file %s to disk" % scitmpfn)
    sciext.write(scitmpfn,rename=False,clobber=True)

    # If DQ extension is given, do the same for it
    if dqext is not None:
        # Make sure DQ data is 16-bit; flagging doesn't work
        # properly if it is 32-bit
        dqext.data = dqext.data.astype(np.int16)
        
        dqtmpfn = "tmp%ssx%s%s%s" % (str(os.getpid()),dqext.extname(),
                                   dqext.extver(),
                                   os.path.basename(dqext.filename))
        log.fullinfo("Writing temporary file %s to disk" % dqtmpfn)
        dqext.write(dqtmpfn,rename=False,clobber=True)

    else:
        os.remove(scitmpfn)
        raise Errors.ScienceError("Sextractor method not supported without " +
                                  "DQ plane.")

    outtmpfn = "tmp%ssxOUT%s%s%s" % (str(os.getpid()),sciext.extname(),
                                     sciext.extver(),
                                     os.path.basename(sciext.filename))

    # if no seeing estimate provided, run sextractor once with
    # default, then re-run to get proper stellar classification
    if seeing_estimate is None:
        iter = [0,1]
    else:
        iter = [0]
    
    log.fullinfo("Calling sextractor")
    for i in iter:

        if seeing_estimate is None:
            # use default seeing estimate for a first pass
            sx_cmd = ["sex",
                      "%s[0]" % scitmpfn,
                      "-c","%s" % default_dict["sex"],
                      "-FLAG_IMAGE","%s[0]" % dqtmpfn,
                      "-CATALOG_NAME","%s" % outtmpfn,
                      "-PARAMETERS_NAME","%s" % default_dict["param"],
                      "-FILTER_NAME","%s" % default_dict["conv"],
                      "-STARNNW_NAME","%s" % default_dict["nnw"],]
        else:
            # run with provided seeing estimate
            sx_cmd = ["sex",
                      "%s[0]" % scitmpfn,
                      "-c","%s" % default_dict["sex"],
                      "-FLAG_IMAGE","%s[0]" % dqtmpfn,
                      "-CATALOG_NAME","%s" % outtmpfn,
                      "-PARAMETERS_NAME","%s" % default_dict["param"],
                      "-FILTER_NAME","%s" % default_dict["conv"],
                      "-STARNNW_NAME","%s" % default_dict["nnw"],
                      "-SEEING_FWHM","%f" % seeing_estimate,
                      ]

        try:
            pipe_out = subprocess.Popen(sx_cmd,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT)
            #subprocess.call(sx_cmd)
        except:
            os.remove(scitmpfn)
            os.remove(dqtmpfn)
            raise Errors.ScienceError("sextractor failed")

        # Sextractor output is full of non-ascii characters, send it
        # only to debug for now
        stdoutdata = pipe_out.communicate()[0]
        log.debug(stdoutdata)

        hdulist = pf.open(outtmpfn)
        tdata = hdulist[1].data

        x = tdata['X_IMAGE']
        y = tdata['Y_IMAGE']
        ra = tdata['ALPHA_SKY']
        dec = tdata['DELTA_SKY']
        flux = tdata['FLUX_BEST']
        fwhm_pix = tdata['FWHM_IMAGE']
        fwhm_arcsec = tdata['FWHM_WORLD']*3600.0
        ellip = tdata['ELLIPTICITY']
        class_star = tdata['CLASS_STAR']
        sxflags = tdata['FLAGS']
        dqflags = tdata['IMAFLAGS_ISO']
        area = tdata['ISOAREA_IMAGE']

        # flag sources with connected area < 100 pix^2
        # This will need revisiting later -- this number is probably
        # instrument dependent.
        aflag = np.where(area<100,1,0)

        # bit masking.  Mask out the bottom 3 bits of the sextractor flags
        # Paul's crazy masking trick.
        sxflags = sxflags & 65528

        # bitwise-or all the flags
        flags = sxflags | dqflags | aflag
        flags = np.where(flags==0,0,1)

        # Get some extra flags to get point sources only
        # for seeing estimate
        eflag = np.where(tdata['ELLIPTICITY']>0.5,1,0)
        sflag = np.where(tdata['CLASS_STAR']<0.6,1,0)
        tflags = flags | eflag | sflag
        good_fwhm = fwhm_arcsec[tflags==0]
        if len(good_fwhm)>2:
            seeing_estimate,sigma = at.clipped_mean(good_fwhm)
            if np.isnan(seeing_estimate) or seeing_estimate==0:
                seeing_estimate = None
                break
        else:
            seeing_estimate = None
            break
        
    log.fullinfo("Removing temporary files from disk:\n%s\n%s" %
                 (scitmpfn,dqtmpfn))
    os.remove(scitmpfn)
    os.remove(dqtmpfn)
    os.remove(outtmpfn)

    obj_list = np.rec.fromarrays([x,y,ra,dec,
                                  flux,fwhm_pix,fwhm_arcsec,ellip,
                                  class_star,flags],
                                 names=["x","y","ra","dec",
                                        "flux","fwhm_pix","fwhm_arcsec",
                                        "ellipticity","class_star","flags"])
    return obj_list,seeing_estimate


def _fit_sources(ad, ext=None, max_sources=50, threshold=5.0,
                 seeing_estimate=None,
                 centroid_function="moffat"):
    """
    This function takes a list of identified sources in an image, fits
    a Gaussian to each one, and stores the fit FWHM and ellipticity to
    the OBJCAT.  Bad fits are marked with a 1 in the 'flags' column.
    If a DQ plane is provided, and a source has a non-zero DQ value,
    it will also receive a 1 in the 'flags' column.
    
    :param ad: input image
    :type ad: AstroData instance with OBJCAT attached

    :param max_sources: Maximum number of sources to fit on each science
                        extension. Will start at the center of the 
                        extension and move outward. If None,
                        will fit all sources.
    :type max_sources: integer

    :param threshold: Number of sigmas above background level to fit source
    :type threshold: float

    :param centroid_function: Function for centroid fitting with daofind
    :type centroid_function: string, can be: 'moffat','gauss'
                    Default: 'moffat'
    """
    
    import scipy.optimize
    from gempy import astrotools as at

    if ext is None:
        sciexts = ad["SCI"]
    else:
        sciexts = ad["SCI",ext]

    good_source = []
    for sciext in sciexts:
        extver = sciext.extver()
        #print 'sci',extver

        objcat = ad["OBJCAT",extver]
        if objcat is None:
            continue
        if objcat.data is None:
            continue

        img_data = sciext.data

        dqext = ad["DQ",extver]

        if dqext is not None:
            # estimate background from non-flagged data
            good_data = img_data[dqext.data==0]
            default_bg = np.median(good_data)
            sigma = _estimate_sigma(good_data)
        else:
            # estimate background from whole image
            default_bg = np.median(img_data)
            sigma = _estimate_sigma(img_data)

        # first guess at fwhm is .8 arcsec
        pixscale = float(sciext.pixel_scale())
        if seeing_estimate is None:
            seeing_estimate = .8
        default_fwhm = seeing_estimate / pixscale

        # stamp is 10*2 times this size on a side (16")
        aperture = 10*default_fwhm
    
        img_objx = objcat.data.field("x")
        img_objy = objcat.data.field("y")
        img_obji = range(len(img_objx))

        # Calculate source's distance from the center of the image
        ctr_x = (img_data.shape[1]-1)/2.0
        ctr_y = (img_data.shape[0]-1)/2.0
        r2 = (img_objx-ctr_x)**2 + (img_objy-ctr_y)**2
        
        obj = np.array(np.rec.fromarrays([img_objx,img_objy,r2,img_obji],
                                         names=["x","y","r2","i"]))
        obj.sort(order="r2")

        count = 0
        for objx,objy,objr2,obji in obj:
        
            # array coords start with 0
            objx-=1
            objy-=1
        
            xlow, xhigh = int(round(objx-aperture)), int(round(objx+aperture))
            ylow, yhigh = int(round(objy-aperture)), int(round(objy+aperture))
        
            if (xlow>0 and xhigh<img_data.shape[1] and 
                ylow>0 and yhigh<img_data.shape[0]):
                stamp_data = img_data[ylow:yhigh,xlow:xhigh]
                if dqext is not None:

                    # Don't fit source if there is a bad pixel within
                    # 2*default_fwhm
                    dxlow, dxhigh = (int(round(objx-default_fwhm*2)),
                                     int(round(objx+default_fwhm*2)))
                    dylow, dyhigh = (int(round(objy-default_fwhm*2)), 
                                     int(round(objy+default_fwhm*2)))
                    stamp_dq = dqext.data[dylow:dyhigh,dxlow:dxhigh]
                    if np.any(stamp_dq):
                        objcat.data.field("flags")[obji] = 1
                        #print 'dq',obji
                        continue
            else:
                # source is too near the edge, skip it
                objcat.data.field("flags")[obji] = 1
                #print 'edge',obji
                continue

            # after flagging for DQ/edge reasons, don't continue
            # with fit if max_sources was reached
            if max_sources is not None and count >= max_sources:
                continue

            # Check for too-near neighbors, don't fit source if found
            too_near = np.any((abs(obj['x']-objx)<default_fwhm) &
                              (abs(obj['y']-objy)<default_fwhm) &
                              (obj['i']!=obji))
            if too_near:
                objcat.data.field("flags")[obji] = 1
                #print 'neighbor',obji
                continue


            # starting values for model fit
            bg = default_bg
            peak = stamp_data.max()-bg
            x_ctr = (stamp_data.shape[1]-1)/2.0
            y_ctr = (stamp_data.shape[0]-1)/2.0
            x_width = default_fwhm
            y_width = default_fwhm
            theta = 0.
            beta = 1.
        
            if peak<threshold*sigma:
                # source is too faint, skip it
                objcat.data.field("flags")[obji] = 1
                #print 'faint',obji
                continue
            
            
            # instantiate model fit object and initial parameters
            if centroid_function=="gauss":
                pars = (bg, peak, x_ctr, y_ctr, x_width, y_width, theta)
                mf = at.GaussFit(stamp_data)
            elif centroid_function=="moffat":
                pars = (bg, peak, x_ctr, y_ctr, x_width, y_width, theta, beta)
                mf = at.MoffatFit(stamp_data)
            else:
                raise Errors.InputError("Centroid function %s not supported" %
                                        centroid_function)
                

            # least squares fit of model to data
            try:
                # for scipy versions < 0.9
                new_pars, success = scipy.optimize.leastsq(mf.calc_diff, pars,
                                                           maxfev=100, 
                                                           warning=False)
            except:
                # for scipy versions >= 0.9
                import warnings
                warnings.simplefilter("ignore")
                new_pars, success = scipy.optimize.leastsq(mf.calc_diff, pars,
                                                           maxfev=100)

            # track number of fits performed
            count += 1
            #print count

            if success>3:
                # fit failed, move on
                objcat.data.field("flags")[obji] = 1
                #print 'fit failed',obji
                continue
        
            if centroid_function=="gauss":
                (bg,peak,x_ctr,y_ctr,x_width,y_width,theta) = new_pars
            else: # Moffat
                (bg,peak,x_ctr,y_ctr,x_width,y_width,theta,beta) = new_pars
                
                # convert width to Gaussian-type sigma
                x_width = x_width*np.sqrt(((2**(1/beta)-1)/(2*np.log(2))))
                y_width = y_width*np.sqrt(((2**(1/beta)-1)/(2*np.log(2))))


            # convert fit parameters to FWHM, ellipticity
            fwhmx = abs(2*np.sqrt(2*np.log(2))*x_width)
            fwhmy = abs(2*np.sqrt(2*np.log(2))*y_width)
            pa = (theta*(180/np.pi))
            pa = pa%360
                
            if fwhmy < fwhmx:
                ellip = 1 - fwhmy/fwhmx
            elif fwhmx < fwhmy:
                ellip = 1 - fwhmx/fwhmy
                pa = pa-90 
            else:
                ellip = 0
                
            # FWHM is geometric mean of x and y FWHM
            fwhm = np.sqrt(fwhmx*fwhmy)


            # Shift PA to 0-180
            if pa > 180:
                pa -= 180
            if pa < 0:
                pa += 180

            # Check fit
            if peak<0.0:
                # source inverted, skip it
                objcat.data.field("flags")[obji] = 1
                #print 'inverted',obji
                continue
            if bg<0.0:
                # bad fit, skip it
                objcat.data.field("flags")[obji] = 1
                #print 'bg<0',obji
                continue
            if peak<threshold*sigma:
                # S/N too low, skip it
                objcat.data.field("flags")[obji] = 1
                #print 's/n low',obji
                continue
                

            # update the position from the fit center
            newx = xlow + x_ctr + 1
            newy = ylow + y_ctr + 1
        

            # update the OBJCAT
            objcat.data.field("x")[obji] = newx
            objcat.data.field("y")[obji] = newy
            objcat.data.field("fwhm_pix")[obji] = fwhm
            objcat.data.field("fwhm_arcsec")[obji] = fwhm * pixscale
            objcat.data.field("ellipticity")[obji] = ellip

            # flag low ellipticity, reasonable fwhm sources as likely stars
            if ellip<0.1:
                objcat.data.field("class_star")[obji] = 0.9
            elif ellip<0.3:
                objcat.data.field("class_star")[obji] = 0.7
            elif ellip<0.5:
                objcat.data.field("class_star")[obji] = 0.5
            else:
                objcat.data.field("class_star")[obji] = 0.2

            if fwhm<1.0:
                # likely cosmic ray
                objcat.data.field("class_star")[obji] *= 0.2
            elif fwhm<2*default_fwhm:
                # potential star
                objcat.data.field("class_star")[obji] *= 0.9
            else:
                # likely extended source or bad fit
                objcat.data.field("class_star")[obji] *= 0.2
                
            #print newx,newy,fwhm,ellip,peak,bg

        flags = (objcat.data.field("flags")==0) & \
                (objcat.data.field("class_star")>0.6)
        good_fwhm = objcat.data.field("fwhm_arcsec")[flags]

        #print good_fwhm
        if len(good_fwhm)>2:
            new_fwhm,sigma = at.clipped_mean(good_fwhm)
            if not(np.isnan(new_fwhm) or new_fwhm==0):
                seeing_estimate = new_fwhm

    return ad, seeing_estimate

