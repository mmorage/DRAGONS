from astrodata import Errors
from astrodata.adutils import gemLog
from gempy import geminiTools as gt
from gempy.science import preprocessing as pp
from gempy.science import qa
from gempy.science import stack as sk
from primitives_GMOS import GMOSPrimitives

class GMOS_IMAGEPrimitives(GMOSPrimitives):
    """
    This is the class containing all of the primitives for the GMOS_IMAGE
    level of the type hierarchy tree. It inherits all the primitives from the
    level above, 'GMOSPrimitives'.
    """
    astrotype = "GMOS_IMAGE"
    
    def init(self, rc):
        GMOSPrimitives.init(self, rc)
        return rc

    def iqDisplay(self, rc):

        # Instantiate the log
        log = gemLog.getGeminiLog(logType=rc["logType"],
                                  logLevel=rc["logLevel"])

        # Log the standard "starting primitive" debug message
        log.debug(gt.log_message("primitive", "qaDisplay", "starting"))

        # Loop over each input AstroData object in the input list
        frame = rc["frame"]
        if frame is None:
            frame = 1
        for ad in rc.get_inputs(style="AD"):

            ad = qa.iq_display_gmos(adinput=ad,frame=frame)
            frame += 1

        yield rc

    def makeFringe(self, rc):
        # Instantiate the log
        log = gemLog.getGeminiLog(logType=rc["logType"],
                                  logLevel=rc["logLevel"])

        # Log the standard "starting primitive" debug message
        log.debug(gt.log_message("primitive", "makeFringe", "starting"))

        adinput = rc.get_inputs(style="AD")
        if len(adinput)<2:
            if rc["context"]=="QA":
                log.warning("Fewer than 2 frames provided as input. " +
                            "Not making fringe frame.")
            else:
                raise Errors.PrimitiveError("Fewer than 2 frames " +
                                            "provided as input.")
        else:

            # Check that filter is either i or z; this step doesn't
            # help data taken in other filters
            red = True
            for ad in adinput:
                filter = ad.filter_name(pretty=True)
                if filter not in ["i","z"]:
                    if rc["context"]=="QA":
                        # in QA context, don't bother trying
                        red = False
                        log.warning("No fringe necessary for filter " +
                                    filter)
                        break
                    else:
                        # in science context, let the user do it, but warn
                        # that it's pointless
                        log.warning("No fringe necessary for filter " + filter)
                elif filter=="i" and len(adinput)<5:
                    if rc["context"]=="QA":
                        # If fewer than 5 frames and in QA context, don't
                        # bother making a fringe -- it'll just make the data
                        # look worse.
                        red = False
                        log.warning("Fewer than 5 frames provided as input " +
                                    "with filter i. Not making fringe frame.")
                        break
                    else:
                        # Allow it in the science case, but warn that it
                        # may not be helpful.
                        log.warning("Fewer than 5 frames " +
                                    "provided as input with filter i. Fringe " +
                                    "correction is not recommended.")
            if red:

                recipe_list = []
                # Call the makeFringeFrame primitive
                recipe_list.append("makeFringeFrame")

                # Store the generated fringe
                recipe_list.append("storeProcessedFringe")
                
                rc.run("\n".join(recipe_list))

        # Report all the input files back to the reduction context
        rc.report_output(adinput)
        yield rc

    def makeFringeFrame(self, rc):
        """
        This primitive makes a fringe frame by masking out sources
        in the science frames and stacking them together.  It calls 
        gifringe to do so, so works only for GMOS imaging currently.
        """
        # Instantiate the log
        log = gemLog.getGeminiLog(logType=rc["logType"],
                                  logLevel=rc["logLevel"])

        # Log the standard "starting primitive" debug message
        log.debug(gt.log_message("primitive", "makeFringeFrame", "starting"))

        adinput = rc.get_inputs(style="AD")
        if len(adinput)<2:
            log.warning('Less than 2 frames provided as input. ' +
                        'Not making fringe frame.')
            adoutput = adinput
        else:
            # Call the make_fringe_image_gmos user level function
            adoutput = pp.make_fringe_image_gmos(adinput=adinput,
                                                 suffix=rc["suffix"],
                                                 operation=rc["operation"])

        # Report the list of output AstroData objects to the reduction
        # context
        rc.report_output(adoutput)
        
        yield rc

    def normalize(self, rc):
        """
        This primitive will normalize a stacked flat frame
        using the CL script giflat.
        
        Warning: giflat calculates its own DQ frames and thus replaces the
        previously produced ones in addDQ. This may be fixed in the
        future by replacing giflat with a Python equivilent with more
        appropriate options for the recipe system. 
        
        :param saturation: Defines saturation level for the raw frame, in ADU
        :type saturation: string, can be 'default', or a number (default
                          value for this primitive is '45000')

        :param logLevel: Verbosity setting for log messages to the screen.
        :type logLevel: integer from 0-6, 0=nothing to screen, 6=everything to 
                        screen. OR the message level as a string (i.e.,
                        'critical', 'status', 'fullinfo'...)
        """
        # Instantiate the log
        log = gemLog.getGeminiLog(logType=rc["logType"],
                                  logLevel=rc["logLevel"])
        # Log the standard "starting primitive" debug message
        log.debug(gt.log_message("primitive", "normalize", "starting"))
        adoutput_list = []
        for ad in rc.get_inputs(style='AD'):
            if ad.phu_get_key_value('NORMFLAT'):
                log.warning('%s has already been processed by normalize' %
                            (ad.filename))
                adoutput_list.append(ad)
                continue
            
            ad = pp.normalize_image_gmos(adinput=ad, 
                                         saturation=rc['saturation'])
            adoutput_list.append(ad[0])

        rc.report_output(adoutput_list)
        yield rc
    
    def stackFlats(self, rc):
        """
        This primitive will combine the input flats with rejection
        parameters set appropriately for GMOS imaging twilight flats.
        
        :param logLevel: Verbosity setting for log messages to the screen.
        :type logLevel: integer from 0-6, 0=nothing to screen, 6=everything to 
                        screen. OR the message level as a string (i.e.,
                        'critical', 'status', 'fullinfo'...)
        """
        # Instantiate the log
        log = gemLog.getGeminiLog(logType=rc["logType"],
                                  logLevel=rc["logLevel"])

        # Log the standard "starting primitive" debug message
        log.debug(gt.log_message("primitive", "stackFlats", "starting"))

        adinput = rc.get_inputs(style='AD')
        nframes = len(adinput)
        if nframes<2:
            log.warning("At least two frames must be provided to " +
                        "stackFlats")
            # Report input to RC without change
            adoutput_list = adinput

        else:            
            # Define rejection parameters based on number of input frames,
            # to be used with minmax rejection.  Note: if reject_method
            # parameter is overridden, these parameters will just be
            # ignored
            if (nframes <= 5):
                nlow = 1
                nhigh = 1
            elif (nframes <= 10):
                nlow = 2
                nhigh = 2
            else:
                nlow = 2
                nhigh = 3

            adoutput_list = sk.stack_frames(adinput=adinput,
                                   suffix=rc["suffix"],
                                   operation=rc["operation"],
                                   mask_type=rc["mask_type"],
                                   reject_method=rc["reject_method"],
                                   grow=rc["grow"],
                                   nlow=nlow,
                                   nhigh=nhigh)

        rc.report_output(adoutput_list)
        yield rc
    

