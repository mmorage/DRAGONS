import numpy as np
import pywcs
from astrodata import Errors
from astrodata import Lookups
from astrodata.adutils import gemLog
from gempy import astrotools as at
from gempy import geminiTools as gt
from gempy import managers as mgr
from primitives_GENERAL import GENERALPrimitives

class RegistrationPrimitives(GENERALPrimitives):
    """
    This is the class containing all of the primitives for the GEMINI level of
    the type hierarchy tree. It inherits all the primitives from the level
    above, 'GENERALPrimitives'.
    """
    astrotype = "GEMINI"
    
    def init(self, rc):
        GENERALPrimitives.init(self, rc)
        return rc
    init.pt_hide = True
    
    def correctWCSToReferenceImage(self, rc):
        """ 
        This primitive registers images to a reference image by correcting
        the relative error in their world coordinate systems. The function
        uses points of reference common to the reference image and the
        input images to fit the input WCS to the reference one. The fit
        is done by a least-squares minimization of the difference between
        the reference points in the input image pixel coordinate system.
        This function is intended to be followed by the
        align_to_reference_image function, which applies the relative
        transformation encoded in the WCS to transform input images into the
        reference image pixel coordinate system.
        
        The primary registration method is intended to be by direct mapping
        of sources in the image frame to correlated sources in the reference
        frame. This method fails when there are no correlated sources in the
        field, or when the WCSs are very far off to begin with. As a back-up
        method, the user can try correcting the WCS by the shifts indicated 
        in the POFFSET and QOFFSET header keywords (option fallback='header'), 
        or by hand-selecting common points of reference in an IRAF display
        (option fallback='user'). By default, only the direct method is
        attempted, as it is expected that the relative WCS will generally be
        more correct than either indirect method. If the user prefers not to
        attempt direct mapping at all, they may set method to either 'user'
        or 'header'.
        
        In order to use the direct mapping method, sources must have been
        detected in the frame and attached to the AstroData instance in an 
        OBJCAT extension. This can be accomplished via the detectSources
        primitive. Running time is optimal, and sometimes the solution is 
        more robust, when there are not too many sources in the OBJCAT. Try
        running detectSources with threshold=20. The solution may also be
        more robust if sub-optimal sources are rejected from the set of 
        correlated sources (use option cull_sources=True). This option may
        substantially increase the running time if there are many sources in
        the OBJCAT.
        
        It is expected that the relative difference between the WCSs of 
        images to be combined should be quite small, so it may not be necessary
        to allow rotation and scaling degrees of freedom when fitting the image
        WCS to the reference WCS. However, if it is desired, the options 
        rotate and scale can be used to allow these degrees of freedom. Note
        that these options refer to rotation/scaling of the WCS itself, not the
        images. Significant rotation and scaling of the images themselves 
        will generally already be encoded in the WCS, and will be corrected for
        when the images are aligned.
        
        The WCS keywords in the headers of the output images are updated
        to contain the optimal registration solution.
        
        :param method: method to use to generate reference points. Options
                       are 'sources' to directly map sources from the input
                       image to the reference image, 'user' to select 
                       reference points by cursor from an IRAF display, 
                       or 'header' to generate reference points from the 
                       POFFSET and QOFFSET keywords in the image headers.
        :type method: string, either 'sources', 'user', or 'header'
        
        :param fallback: back-up method for generating reference points.
                         if the primary method fails. The 'sources' option
                         cannot be used as the fallback.
        :type fallback: string, either 'user' or 'header'.
        
        :param cull_sources: flag to indicate whether sub-optimal sources 
                             should be rejected before attempting a direct
                             mapping. If True, sources that are saturated, 
                             not well-fit by a Gaussian, too broad, or too
                             elliptical will be eliminated from the
                             list of reference points.
        :type cull_sources: bool
        
        :param rotate: flag to indicate whether the input image WCSs should
                       be allowed to rotate with respect to the reference image
                       WCS
        :type rotate: bool
        
        :param scale: flag to indicate whether the input image WCSs should
                      be allowed to scale with respect to the reference image
                      WCS. The same scale factor is applied to all dimensions.
        :type scale: bool
        """
        
        # Instantiate the log
        log = gemLog.getGeminiLog(logType=rc["logType"],
                                  logLevel=rc["logLevel"])
        
        # Log the standard "starting primitive" debug message
        log.debug(gt.log_message("primitive", "correctWCSToReferenceImage",
                                 "starting"))
        
        # Define the keyword to be used for the time stamp for this primitive
        timestamp_key = self.timestamp_keys["correctWCSToReferenceImage"]

        # Initialize the list of output AstroData objects
        adoutput_list = []
        
        # Check whether two or more input AstroData objects were provided
        adinput = rc.get_inputs_as_astrodata()
        correcting = True
        if len(adinput) <= 1:
            log.warning("No correction will be performed, since at least " \
                        "two input AstroData objects are required for " \
                        "correctWCSToReferenceImage")
            # Set the input AstroData object list equal to the output AstroData
            # objects list without further processing
            adoutput_list = adinput
            correcting = False

        # Check that method is sensibly defined
        if correcting:

            # Get the necessary parameters from the RC
            method = rc["method"]
            fallback = rc["fallback"]
            cull_sources = rc["cull_sources"]
            rotate = rc["rotate"]
            scale = rc["scale"]

            if method=="None":
                method=None
            if fallback=="None":
                fallback=None
            
            if method is None:
                if fallback is None:
                    log.warning("No correction will be performed, since both " \
                                "method and fallback are None")
                    adoutput_list = adinput
                    correcting = False
                else:
                    method = fallback
                
        # Check that images have one SCI extension, and if necessary,
        # sources defined in an OBJCAT extension
        if correcting:
            n_test = []
            for ad in adinput:

                # Make sure all images have one science extension
                if len(ad["SCI"])!=1:
                    raise Errors.InputError("Input images must have only one "
                                            "SCI extension.")
                
                # Get number of objects from OBJCAT
                objcat = ad["OBJCAT"]
                if objcat is None:
                    num_cat = 0
                else:
                    num_cat = len(objcat)
                if num_cat==0:
                    n_obj = 0
                elif num_cat>1:
                    raise Errors.InputError("Input images must have only one " +
                                            "OBJCAT extension.")
                else:
                    n_obj = len(objcat.data)
                
                n_test.append(n_obj)
            
            if n_test[0]==0 and method=="sources":
                log.warning("No objects found in reference image.")
                if fallback is not None:
                    log.warning("Only attempting indirect WCS alignment, " +
                                "via " + fallback + " mapping")
                    method=fallback
                
                else:
                    log.warning("WCS can only be corrected indirectly " +
                                "and fallback method is set to None. Not " +
                                "attempting WCS correction.")
                    adoutput_list = adinput
                    correcting = False

        # If input passed all checks, apply the selected method
        if correcting:
            
            # Reference image is first one supplied
            # (won't be modified)
            reference = adinput[0]
            adoutput_list.append(reference)
            log.stdinfo("Reference image: "+reference.filename)
            
            # If no OBJCAT/no sources in reference image, or user choice,
            # use indirect alignment for all images at once
            if method=="header":
                reg_ad = _header_align(reference, adinput[1:])
                adoutput_list.extend(reg_ad)
            elif method=="user":
                reg_ad = _user_align(reference, adinput[1:], rotate, scale)
                adoutput_list.extend(reg_ad)
            elif method!="sources":
                raise Errors.InputError("Did not recognize method " + method)
            
            # otherwise try to do direct alignment for each image by correlating
            # sources in the reference and input images
            else:
                
                for i in range(1,len(adinput)):
                
                    ad = adinput[i]

                    if n_test[i] == 0:
                        log.warning("No objects found in "+ ad.filename)
                        if fallback is not None:
                            log.warning(
                                "Only attempting indirect WCS alignment, " +
                                "via " + fallback + " mapping")
                            if fallback=="header":
                                adoutput = _header_align(reference, ad)
                            elif fallback=="user":
                                adoutput = _user_align(reference, ad, 
                                                       rotate, scale)
                            else:
                                raise Errors.InputError(
                                    "Did not recognize fallback method " + 
                                    fallback)
                        
                        else:
                            log.warning(
                                "WCS can only be corrected indirectly "+
                                "and fallback=None. Not attempting WCS " +
                                "correction for " + ad.filename)
                            adoutput_list.append(ad)
                            continue
                    else:
                        log.fullinfo("Number of objects in image %s: %d" %
                                     (ad.filename, n_test[i]))
                        
                        log.fullinfo("Cross-correlating sources in %s, %s" %
                                   (reference.filename, ad.filename))
                        obj_list = _correlate_sources(reference, ad, 
                                                      cull_sources=cull_sources)
                        
                        n_corr = len(obj_list[0])
                        
                        if n_corr==0:
                            log.warning("No correlated sources found.")
                            if fallback is not None:
                                log.warning("Only attempting indirect WCS " +
                                            "alignment, via " + fallback + 
                                            " mapping")
                                
                                if fallback=="header":
                                    adoutput = _header_align(reference, ad)
                                elif fallback=="user":
                                    adoutput = _user_align(reference, ad, 
                                                           rotate, scale)
                                else:
                                    raise Errors.InputError(
                                        "Did not recognize " +
                                        "fallback method " + fallback)
                            
                            else:
                                log.warning(
                                    "WCS can only be corrected indirectly "+
                                    "and fallback=None. Not attempting " +
                                    "WCS correction for " + ad.filename)
                                adoutput_list.append(ad)
                                continue
                        else:
                            log.fullinfo("Number of correlated sources: %d" % 
                                         n_corr)
                            
                            # Check the fit geometry depending on the 
                            # number of objects
                            if n_corr == 1:
                                log.warning("Too few objects. Setting " +
                                            "rotate=False, " +
                                            "scale=False")
                                rotate=False
                                scale=False
                            
                            log.fullinfo("\nSources used to align frames:")
                            log.fullinfo("  %7s %7s %7s %7s\n%s" % 
                                         (" Ref. x","Ref. y",
                                          "Img. x","Img. y",
                                          "  "+"-"*31))
                            output_obj = zip(obj_list[0],obj_list[1])
                            for obj in output_obj:
                                obj_string = ("  %7.2f %7.2f %7.2f %7.2f" % 
                                              (obj[0][0],obj[0][1],
                                               obj[1][0],obj[1][1]))
                                log.fullinfo(obj_string)
                            log.fullinfo("")
                            
                            adoutput = _align_wcs(reference, ad, [obj_list], 
                                                  rotate=rotate, scale=scale)
    
                    adoutput_list.extend(adoutput)

            # Change the filenames and add the appropriate timestamps
            for ad in adoutput_list:
                gt.mark_history(adinput=ad, keyword=timestamp_key)

                ad.filename = gt.fileNameUpdater(adIn=ad, suffix=rc["suffix"], 
                                                 strip=True)
        
        # Report the list of output AstroData objects to the reduction
        # context
        rc.report_output(adoutput_list)
        
        yield rc
    
    def determineAstrometricSolution(self, rc):
        """
        This primitive calculates the average astrometric offset between
        the positions of sources in the reference catalog, and their
        corresponding object in the object catalog.
        It then reports the astrometric correction vector.
        For now, this is limited to a translational offset only.
        
        If the 'correct_wcs' parameter == True, it then applies that
        correction to the WCS of the image and also applies the same
        correction to the RA, DEC columns of the object catalog.
        """

        # Instantiate the log
        log = gemLog.getGeminiLog(logType=rc["logType"],
                                  logLevel=rc["logLevel"])

        # Log the standard "starting primitive" debug message
        log.debug(gt.log_message("primitive", "determineAstrometricSolution",
                                 "starting"))

        # Define the keyword to be used for the time stamp for this primitive
        timestamp_key = self.timestamp_keys["determineAstrometricSolution"]

        # Initialize the list of output AstroData objects
        adoutput_list = []

        # Loop over each input AstroData object in the input list
        for ad in rc.get_inputs_as_astrodata():

            # Get the necessary parameters from the RC
            correctWCS = rc["correct_wcs"]

            # Objcats to process
            objcats = ad['OBJCAT']
            # If there are *no* reference catalogs, don't even bother
            if ad['REFCAT'] is None:
                objcats = []

            # Initialise lists to keep the total offsets in
            all_delta_ra = []
            all_delta_dec = []

            # Loop over the OBJCAT extensions
            for objcat in objcats:
                extver = objcat.extver()

                # Check that a refcat exists for this objcat extver
                refcat = ad['REFCAT',extver]
                if(not(refcat)):
                    log.warning("Missing [REFCAT,%d] in %s - cannot calculate astrometry" % (extver, ad.filename))
                else:
                    # Initialise lists to keep the offsets in
                    delta_ra = []
                    delta_dec = []

                    # Need to build an index array that lets us quickly find the
                    # row in the refcat, given the id from the objcat
                    m = max(refcat.data['Id'])
                    m = m+1
                    refindex=([None] * m)
                    # Loop through the refcat, populating the index
                    for i in range(len(refcat.data)):
                        ref=refcat.data[i]
                        refindex[ref['Id']] = i
                    # so now you can find a refid with refcat.data[refindex[refid]]


                    # Loop through the objcat, 
                    for obj in objcat.data:
                        if(obj['REF_NUMBER'] != -999):
                            refid = obj['REF_NUMBER']
                            obj_ra = obj['X_WORLD']
                            obj_dec = obj['Y_WORLD']
                            ref_ra = None
                            ref_dec = None
                            # Find the reference catalog line.
                            ref = refcat.data[refindex[refid]]
                            if(ref['Id'] == refid):
                                ref_ra = ref['RAJ2000']
                                ref_dec = ref['DEJ2000']
                            dra = ref_ra - obj_ra
                            ddec = ref_dec - obj_dec
                            if(np.isfinite(dra) and np.isfinite(ddec)):
                                delta_ra.append(dra)
                                delta_dec.append(ddec)
                                all_delta_ra.append(dra)
                                all_delta_dec.append(ddec)

                    # Report the mean and standard deviation of the offsets:
                    ra_mean = np.mean(delta_ra) * 3600.0
                    ra_sigma = np.std(delta_ra) * 3600.0
                    dec_mean = np.mean(delta_dec) * 3600.0
                    dec_sigma = np.std(delta_dec) * 3600.0
                    ra_median_degs = np.median(delta_ra)
                    dec_median_degs = np.median(delta_dec)
                    ra_median = ra_median_degs * 3600.0
                    dec_median = dec_median_degs * 3600.0

                    log.fullinfo("Astrometric Offset between [OBJCAT, %d] and [REFCAT, %d] is:" % (extver, extver))
                    log.fullinfo("RA_mean +- RA_sigma: %.2f +- %.2f arcsec" % (ra_mean, ra_sigma))
                    log.fullinfo("Dec_mean +- Dec_sigma: %.2f +- %.2f arcsec" % (dec_mean, dec_sigma))
                    log.fullinfo("Median Offset is: %.2f, %.2f arcsec" % (ra_median, dec_median))


                    # Once we've done the great ULF - primitive refactor of late 2011, we agreed we should
                    # split this out into a separate primitive - this primitive should store the WCS solution
                    # in the rc (preferably as James' fancy WCS object that doesn't actually exist yet)
                    # then the other primitive should apply that to the WCS in the astrodata instance.
                    if(correctWCS):
                        # Handle the image extensions first
                        for thing in ['SCI', 'VAR', 'DQ']:
                            image = ad[thing, extver]
                            if(image):
                                image.header['CRVAL1'] += ra_median_degs
                                image.header['CRVAL2'] += dec_median_degs
                                if(thing == 'SCI'):
                                    log.stdinfo("Correcting WCS in [%s, %d] by (%.3f, %.3f) arcsec" % (thing, extver, ra_median, dec_median))
                                else:
                                    log.fullinfo("Correcting WCS in [%s, %d] by (%.3f, %.3f) arcsec" % (thing, extver, ra_median, dec_median))

                        # Now fix the objcat, according to the SCI wcs
                        sci = ad['SCI', extver]
                        wcs = pywcs.WCS(sci.header)
                        log.stdinfo("Correcting RA, Dec columns in ['OBJCAT', %d]" % extver)
                        for row in objcat.data:
                            xy = np.array([row['X_IMAGE'], row['Y_IMAGE']])
                            radec = wcs.wcs_pix2sky([xy], 1)[0]
                            # FIXME - is it correct to set oring to 1 here?
                            # Also we should be setting ra_dec_order=True, but that 
                            # breaks with the wcs missing the lattype property
                            row['X_WORLD'] = radec[0]
                            row['Y_WORLD'] = radec[1]

            
            if(objcats):
                # Report the mean and standard deviation of all the offsets over all the sci extensions:
                ra_mean = np.mean(all_delta_ra) * 3600.0
                ra_sigma = np.std(all_delta_ra) * 3600.0
                dec_mean = np.mean(all_delta_dec) * 3600.0
                dec_sigma = np.std(all_delta_dec) * 3600.0

                log.stdinfo("Mean Astrometric Offset between OBJCAT and REFCAT:")
                log.stdinfo("     RA: %.2f +- %.2f    Dec: %.2f +- %.2f   arcsec" % (ra_mean, ra_sigma, dec_mean, dec_sigma))

                # Only change the name and set the timestamp if the
                # correct_wcs parameter was set
                if(correctWCS):
                    # Add the appropriate time stamps to the PHU
                    gt.mark_history(adinput=ad, keyword=timestamp_key)

                    # Change the filename
                    ad.filename = gt.fileNameUpdater(adIn=ad, suffix=rc["suffix"],
                                                 strip=True)
            else:
                log.stdinfo("Could not determine astrometric offset as no reference sources found")

            adoutput_list.append(ad)

        # Report the list of output AstroData objects to the reduction
        # context
        rc.report_output(adoutput_list)

        yield rc

##############################################################################
# Below are the helper functions for the user level functions in this module #
##############################################################################

# Load the standard comments for header keywords that will be updated
# in these functions
keyword_comments = Lookups.get_lookup_table("Gemini/keyword_comments",
                                            "keyword_comments")

def _cull_sources(ad, img_obj):
    """
    This function takes a list of identified sources in an image, fits
    a Gaussian to each one, and rejects it from the list if it is not
    sufficiently star-like. The criteria for good sources are that they
    must be fittable by a Gaussian, not be too near the edge of the frame,
    have a peak value below saturation (as defined in the header of
    the image), have ellipticity less than 0.25, and have FWHM less than
    2.4 arcsec. The return value is a list of the objects that meet these
    criteria, with their positions updated to the fit center.
    
    :param ad: input image
    :type ad: AstroData instance
    
    :param img_obj: list of [x,y] positions for sources detected in the
                    input image
    :type img_obj: list
    """
    
    import scipy.optimize
    
    if len(ad["SCI"])!=1:
        raise Errors.InputError("Reference image must have only " +
                                  "one SCI extension.")
    
    img_data = ad["SCI"].data
    
    # first guess at background is mean of whole image
    default_bg = img_data.mean()
    
    # first guess at fwhm is .8 arcsec
    default_fwhm = .8/float(ad.pixel_scale())
    
    # stamp is 2 times this size on a side
    aperture = default_fwhm
    
    # for rejecting saturated sources
    saturation = ad.saturation_level()
    
    good_source = []
    for objx,objy in img_obj:
        
        # array coords start with 0
        objx-=1
        objy-=1
        
        xlow, xhigh = int(round(objx-aperture)), int(round(objx+aperture)), 
        ylow, yhigh = int(round(objy-aperture)), int(round(objy+aperture)),
        
        if (xlow>0 and xhigh<img_data.shape[1] and 
            ylow>0 and yhigh<img_data.shape[0]):
            stamp_data = img_data[ylow:yhigh,xlow:xhigh]
        else:
            # source is too near the edge, skip it
            continue
        
        # starting values for Gaussian fit
        bg = default_bg
        peak = stamp_data.max()
        x_ctr = (stamp_data.shape[1]-1)/2.0
        y_ctr = (stamp_data.shape[0]-1)/2.0
        x_width = default_fwhm
        y_width = default_fwhm
        theta = 0.
        
        if peak >= saturation:
            # source is too bright, skip it
            continue
        
        pars = (bg, peak, x_ctr, y_ctr, x_width, y_width, theta)
        
        # instantiate fit object
        gf = at.GaussFit(stamp_data)
        
        # least squares fit of model to data
        try:
            # for scipy versions < 0.9
            new_pars, success = scipy.optimize.leastsq(gf.calc_diff, pars,
                                                       maxfev=1000, 
                                                       warning=False)
        except:
            # for scipy versions >= 0.9
            import warnings
            warnings.simplefilter("ignore")
            new_pars, success = scipy.optimize.leastsq(gf.calc_diff, pars,
                                                       maxfev=1000)
        
        if success>=4:
            # fit failed, move on
            continue
        
        (bg, peak, x_ctr, y_ctr, x_width, y_width, theta) = new_pars
        
        # convert fit parameters to FWHM, ellipticity
        fwhmx = abs(2*np.sqrt(2*np.log(2))*x_width)
        fwhmy = abs(2*np.sqrt(2*np.log(2))*y_width)
        pa = (theta*(180/np.pi))
        pa = pa%360
                
        if fwhmy < fwhmx:
            ellip = 1 - fwhmy/fwhmx
            fwhm = fwhmx
        elif fwhmx < fwhmy:
            ellip = 1 - fwhmx/fwhmy
            pa = pa-90 
            fwhm = fwhmy
        else: #fwhmx == fwhmy
            ellip = 0
            fwhm = fwhmx
        
        if ellip>.25:
            # source not round enough, skip it
            continue
        
        if fwhm>3*default_fwhm: # ie. 2.4 arcsec -- probably not due to seeing
            # source not pointy enough, skip it
            continue
        
        # update the position from the fit center
        newx = xlow + x_ctr + 1
        newy = ylow + y_ctr + 1
        
        good_source.append([newx,newy])
    
    return good_source

def _correlate_sources(ad1, ad2, delta=None, firstPass=10, cull_sources=False):
    """
    This function takes sources from the OBJCAT extensions in two
    images and attempts to correlate them. It returns a list of 
    reference source positions and their correlated image source 
    positions.
    
    :param ad1: reference image
    :type ad1: AstroData instance
    
    :param ad2: input image
    :type ad2: AstroData instance
    
    :param delta: maximum distance in pixels to allow a match. If
                  left as None, it will attempt to find an appropriate
                  number (recommended).
    :type delta: float
    
    :param firstPass: estimated maximum distance between correlated
                      sources. This distance represents the expected
                      mismatch between the WCSs of the input images.
    :type firstPass: float
    
    :param cull_sources: flag to indicate whether to reject sources that
                   are insufficiently star-like. If true, will fit
                   a Gaussian to each correlated source, and return
                   the fit center of good sources (rather than the raw
                   OBJCAT position).
    :type cull_sources: bool
    """
    
    log = gemLog.getGeminiLog()
    
    # get data and WCS from image 1
    x1 = ad1["OBJCAT"].data.field("X_IMAGE")
    y1 = ad1["OBJCAT"].data.field("Y_IMAGE")
    wcs1 = pywcs.WCS(ad1["SCI"].header)
    
    # get data and WCS from image 2
    x2 = ad2["OBJCAT"].data.field("X_IMAGE")
    y2 = ad2["OBJCAT"].data.field("Y_IMAGE")
    wcs2 = pywcs.WCS(ad2["SCI"].header)
    
    # convert image 2 data to sky coordinates
    ra2, dec2 = wcs2.wcs_pix2sky(x2,y2,1)
    
    # convert image 2 sky data to image 1 pixel coordinates
    conv_x2, conv_y2 = wcs1.wcs_sky2pix(ra2,dec2,1)
    
    # find matches
    ind1,ind2 = at.match_cxy(x1,conv_x2,y1,conv_y2,
                             delta=delta, firstPass=firstPass, log=log)
    
    if len(ind1)!=len(ind2):
        raise Errors.ScienceError("Mismatched arrays returned from match_cxy")
    
    if len(ind1)<1 or len(ind2)<1:
        return [[],[]]
    else:
        obj_list = [zip(x1[ind1], y1[ind1]),
                    zip(x2[ind2], y2[ind2])]
        
        if cull_sources:
            log.stdinfo("Rejecting non-Gaussian sources")
            obj_list_1 = np.array(_cull_sources(ad1, obj_list[0]))
            obj_list_2 = np.array(_cull_sources(ad2, obj_list[1]))
            
            x1,y1 = obj_list_1[:,0],obj_list_1[:,1]
            x2,y2 = obj_list_2[:,0],obj_list_2[:,1]
            
            # re-match sources
            ra2, dec2 = wcs2.wcs_pix2sky(x2,y2,1)
            conv_x2, conv_y2 = wcs1.wcs_sky2pix(ra2,dec2,1)
            ind1,ind2 = at.match_cxy(x1,conv_x2,y1,conv_y2,
                                     delta=delta, firstPass=firstPass, log=log)
            
            if len(ind1)!=len(ind2):
                raise Errors.ScienceError("Mismatched arrays returned " +
                                          "from match_cxy")
            
            if len(ind1)<1 or len(ind2)<1:
                return [[],[]]
            else:
                obj_list = [zip(x1[ind1], y1[ind1]),
                            zip(x2[ind2], y2[ind2])]
        
        return obj_list

def _align_wcs(reference, adinput, objIns, rotate=False, scale=False):
    """
    This function fits an input image's WCS to a reference image's WCS
    by minimizing the difference in the input image frame between
    reference points present in both images.
    
    :param reference: reference image to register other images to. Must
                      have only one SCI extension.
    :type reference: AstroData object
    
    :param adinput: images to register to reference image. Must have
                  only one SCI extension.
    :type adinput: AstroData objects, either a single instance or a list
    
    :param objIns: list of object lists, one for each input image
    :type objIns: list of output lists from _correlate_sources
    
    :param rotate: flag to indicate whether the input image WCSs should
                   be allowed to rotate with respect to the reference image
                   WCS
    :type rotate: bool
    
    :param scale: flag to indicate whether the input image WCSs should
                  be allowed to scale with respect to the reference image
                  WCS. The same scale factor is applied to all dimensions.
    :type scale: bool
    """
    
    log = gemLog.getGeminiLog()
    
    if not isinstance(adinput,list):
        adinput = [adinput]
    if not isinstance(objIns,list):
        objIns = [objIns]
    if len(objIns) != len(adinput):
        raise Errors.InputError("Argument objIns should have the same " +
                                "number of elements as adinput")
    
    import scipy.optimize
    
    adoutput_list = []
    for i in range(len(adinput)):
        
        # copy input ad and rename
        ad = adinput[i]
        
        log.fullinfo("Adjusting WCS for " + ad.filename )
        
        ref_xy, inp_xy = objIns[i]
        ref_xy = np.array(ref_xy)
        inp_xy = np.array(inp_xy)
        
        ref_wcs = pywcs.WCS(reference["SCI"].header)
        inp_wcs = pywcs.WCS(ad["SCI"].header)
        
        # convert the reference coordinates to RA/Dec
        ref_radec = ref_wcs.wcs_pix2sky(ref_xy,1)
        
        # instantiate the alignment object used to fit input
        # WCS to reference WCS
        wcstweak = at.WCSTweak(inp_wcs, inp_xy, ref_radec, 
                               rotate=rotate, scale=scale)
        
        # find optimum WCS shift and rotation with
        # starting parameters: dRA, dDec = 0
        # (and dTheta=0 if rotate=True, dMag=1 if scale=True)
        
        update = False
        if rotate and scale:
            pars = [0,0,0,1]
        elif rotate:
            pars = [0,0,0]
        elif scale:
            pars = [0,0,1]
        else:
            pars = [0,0]
        
        try:
            # for scipy versions < 0.9
            new_pars,success = scipy.optimize.leastsq(wcstweak.calc_diff, pars,
                                                      warning=False, 
                                                      maxfev=1000)
        except:
            # for scipy versions >= 0.9
            import warnings
            warnings.simplefilter("ignore")
            new_pars,success = scipy.optimize.leastsq(wcstweak.calc_diff, pars,
                                                      maxfev=1000)
        
        if success<4:
            update = True
            if rotate and scale:
                (dRA, dDec, dTheta, dMag) = new_pars
                log.fullinfo("Best fit dRA, dDec, dTheta, dMag: " +
                             "%.5f %.5f %.5f %.5f" %
                             (dRA, dDec, dTheta, dMag))
            elif rotate:
                (dRA, dDec, dTheta) = new_pars
                log.fullinfo("Best fit dRA, dDec, dTheta: %.5f %.5f %.5f" %
                             (dRA, dDec, dTheta))
            elif scale:
                (dRA, dDec, dMag) = new_pars
                log.fullinfo("Best fit dRA, dDec, dMag: %.5f %.5f %.5f" %
                             (dRA, dDec, dMag))
            else:
                (dRA, dDec) = new_pars
                log.fullinfo("Best fit dRA, dDec: %.5f %.5f" % (dRA, dDec))
        else:
            log.warning("WCS alignment did not converge. Not updating WCS.")
        
        # update WCS in ad
        if update:
            log.fullinfo("Updating WCS in header")
            ad.phu_set_key_value("CRVAL1", wcstweak.wcs.wcs.crval[0],
                                 comment=keyword_comments["CRVAL1"])
            ad.phu_set_key_value("CRVAL2", wcstweak.wcs.wcs.crval[1],
                                 comment=keyword_comments["CRVAL2"])
            ad.phu_set_key_value("CD1_1", wcstweak.wcs.wcs.cd[0,0],
                                 comment=keyword_comments["CD1_1"])
            ad.phu_set_key_value("CD1_2", wcstweak.wcs.wcs.cd[0,1],
                                 comment=keyword_comments["CD1_2"])
            ad.phu_set_key_value("CD2_1", wcstweak.wcs.wcs.cd[1,0],
                                 comment=keyword_comments["CD2_1"])
            ad.phu_set_key_value("CD2_2", wcstweak.wcs.wcs.cd[1,1],
                                 comment=keyword_comments["CD2_2"])
            
            for ext in ad:
                if ext.extname() in ["SCI","VAR","DQ"]:
                    ext.set_key_value("CRVAL1", wcstweak.wcs.wcs.crval[0],
                                      comment=keyword_comments["CRVAL1"])
                    ext.set_key_value("CRVAL2", wcstweak.wcs.wcs.crval[1],
                                      comment=keyword_comments["CRVAL2"])
                    ext.set_key_value("CD1_1", wcstweak.wcs.wcs.cd[0,0],
                                      comment=keyword_comments["CD1_1"])
                    ext.set_key_value("CD1_2", wcstweak.wcs.wcs.cd[0,1],
                                      comment=keyword_comments["CD1_2"])
                    ext.set_key_value("CD2_1", wcstweak.wcs.wcs.cd[1,0],
                                      comment=keyword_comments["CD2_1"])
                    ext.set_key_value("CD2_2", wcstweak.wcs.wcs.cd[1,1],
                                      comment=keyword_comments["CD2_2"])
        
        adoutput_list.append(ad)
    
    return adoutput_list

def _header_align(reference, adinput):
    """
    This function uses the POFFSET and QOFFSET header keywords
    to get reference points to use in correcting an input WCS to
    a reference WCS. Positive POFFSET is assumed to mean higher x
    value, and positive QOFFSET is assumed to mean higher y value.
    This function only allows for relative shifts between the images;
    rotations and scales will not be handled properly
    
    :param reference: reference image to register other images to. Must
                      have only one SCI extension.
    :type reference: AstroData object
    
    :param adinput: images to register to reference image. Must have
                  only one SCI extension.
    :type adinput: AstroData objects, either a single instance or a list
    """
    
    log = gemLog.getGeminiLog()
    
    if not isinstance(adinput,list):
        adinput = [adinput]
    
    # get starting offsets from reference image (first one given)
    pixscale = float(reference.pixel_scale())
    ref_xoff = reference.phu_get_key_value("POFFSET")/pixscale
    ref_yoff = reference.phu_get_key_value("QOFFSET")/pixscale
    
    # reference position is the center of the reference frame
    data_shape = reference["SCI"].data.shape
    ref_coord = [data_shape[1]/2,data_shape[0]/2]
    
    log.fullinfo("Pixel scale: %.4f" % pixscale)
    log.fullinfo("Reference offsets: %.4f %.4f" % (ref_xoff, ref_yoff))
    log.fullinfo("Reference coordinates: %.1f %.1f" % 
                 (ref_coord[0], ref_coord[1]))
    
    objIns = []
    for i in range(len(adinput)):
        ad = adinput[i]
        pixscale = float(ad.pixel_scale())
        xoff = ad.phu_get_key_value("POFFSET")/pixscale
        yoff = ad.phu_get_key_value("QOFFSET")/pixscale
        
        img_x = xoff-ref_xoff + ref_coord[0]
        img_y = yoff-ref_yoff + ref_coord[1]
        
        log.fullinfo("For image " + ad.filename + ":")
        log.fullinfo("   Image offsets: %.4f %.4f" % (xoff, yoff))
        log.fullinfo("   Coordinates to transform: %.4f %.4f" % (img_x, img_y))
        
        objIns.append(np.array([[ref_coord],[[img_x,img_y]]]))
    
    adoutput_list = _align_wcs(reference, adinput, objIns, 
                               rotate=False, scale=False)
    
    return adoutput_list

def _user_align(reference, adinput, rotate, scale):
    """
    This function takes user input to get reference points to use in 
    correcting an input WCS to a reference WCS. The images are 
    displayed by IRAF and the common points selected by an image cursor.
    If rotation or scaling degrees of freedom are desired, two 
    common points must be selected. If only shifts are desired, one
    common point must be selected.
    
    :param reference: reference image to register other images to. Must
                      have only one SCI extension.
    :type reference: AstroData object
    
    :param adinput: images to register to reference image. Must have
                  only one SCI extension.
    :type adinput: AstroData objects, either a single instance or a list
    
    :param rotate: flag to indicate whether the input image WCSs should
                   be allowed to rotate with respect to the reference image
                   WCS
    :type rotate: bool
    
    :param scale: flag to indicate whether the input image WCSs should
                  be allowed to scale with respect to the reference image
                  WCS. The same scale factor is applied to all dimensions.
    :type scale: bool
    """
    
    log = gemLog.getGeminiLog()
    
    # load pyraf modules
    from astrodata.adutils.gemutil import pyrafLoader
    pyraf, gemini, yes, no = pyrafLoader()
    
    if not isinstance(adinput,list):
        adinput = [adinput]
    
    # start cl manager for iraf display
    all_input = [reference] + adinput
    clm = mgr.CLManager(imageIns=all_input, funcName="display", log=log)
    tmpfiles = clm.imageInsFiles(type="list")
    
    # display the reference image
    print " ==> Reference image: " + reference.filename
    pyraf.iraf.display(tmpfiles[0]+"[SCI]", 1)
    
    if not rotate and not scale:
        # only one object needed for pure shifts
        print "Point to one common object in reference image"
        print "    strike any key"
        words = pyraf.iraf.cl.imcur.split()
        x11 = float(words[0])
        y11 = float(words[1])
        ref_coord = [[x11,y11]]
    else:
        # select two objects for rotation/scaling
        print "Point to first common object in reference image"
        print "    strike any key"
        words = pyraf.iraf.cl.imcur.split()
        x11 = float(words[0])
        y11 = float(words[1])
        print "Point to second common object in reference image"
        print "    strike any key"
        words = pyraf.iraf.cl.imcur.split()
        x12 = float(words[0])
        y12 = float(words[1])
        ref_coord = [[x11,y11],[x12,y12]]
    
    objIns = []
    for i in range(len(adinput)):
        ad = adinput[i]
        
        print " ==> Image to be transformed:", ad.filename
        pyraf.iraf.display(tmpfiles[i+1]+"[SCI]", 1)
        
        if not rotate and not scale:
            print "Point to one common object in image to be transformed"
            print "    coordinates for last image: %.1f, %.1f" % (x11, y11)
            print "    strike any key"
            words = pyraf.iraf.cl.imcur.split()
            x21 = float(words[0])
            y21 = float(words[1])
            img_coord = [[x21, y21]]
        else:
            print "Point to first common object in image to be transformed"
            print "    coordinates for last image: %.1f, %.1f" % (x11, y11)
            print "    strike any key"
            words = pyraf.iraf.cl.imcur.split()
            x21 = float(words[0])
            y21 = float(words[1])
            
            print "Point to second common object in image to be transformed"
            print "    coordinates for last image: %.1f, %.1f" % (x12, y12)
            print "    strike any key"
            words = pyraf.iraf.cl.imcur.split()
            x22 = float(words[0])
            y22 = float(words[1])
            img_coord = [[x21, y21],[x22,y22]]
        
        log.fullinfo("Reference coordinates: "+repr(ref_coord))
        log.fullinfo("Coordinates to transform: "+repr(img_coord))
        objIns.append([ref_coord,img_coord])
    
    # delete temporary files
    clm.finishCL()
    
    adoutput_list = _align_wcs(reference, adinput, objIns, 
                               rotate=rotate, scale=scale)
    
    return adoutput_list
