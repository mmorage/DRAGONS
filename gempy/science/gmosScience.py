# Author: Kyle Mede, February 2011
# For now, this module is to hold the code which performs the actual work of the 
# primitives that is considered generic enough to be at the 'GMOS' level of
# the hierarchy tree, but too specific for the 'gemini' level above this.

import os

import pyfits as pf
import numpy as np
from copy import deepcopy

from astrodata.AstroData import AstroData
from astrodata.adutils import gemLog
from astrodata.adutils.gemutil import pyrafLoader
from astrodata.Errors import ScienceError
from gempy.instruments import geminiTools  as gemt
from gempy.instruments import gmosTools  as gmost
from gempy.instruments.geminiCLParDicts import CLDefaultParamsDict


def overscan_subtract(adInputs, fl_trim=False, fl_vardq='AUTO', 
            biassec='[1:25,1:2304],[1:32,1:2304],[1025:1056,1:2304]',
            outNames=None, suffix=None, log=None, logName='gemini.log', 
                                                logLevel=1, noLogFile=False):
    """
    This function uses the CL script gireduce to subtract the overscan 
    from the input images.
    
    WARNING: 
    The gireduce script used here replaces the previously 
    calculated DQ frames with its own versions.  This may be corrected 
    in the future by replacing the use of the gireduce
    with a Python routine to do the overscan subtraction.

    note
    The inputs to this function MUST be prepared.

    String representing the name of the log file to write all log messages to
    can be defined, or a default of 'gemini.log' will be used.  If the file
    all ready exists in the directory you are working in, then this file will 
    have the log messages during this function added to the end of it.

    FOR FUTURE
    This function has many GMOS dependencies that would be great to work out
    so that this could be made a more general function (say at the Gemini level)
    .  In the future the parameters can be looked into and the CL script can be 
    upgraded to handle things like row based overscan calculations/fitting/
    modeling... vs the column based used right now, add the model, nbiascontam,
    ... params to the functions inputs so the user can choose them for 
    themselves.

    :param adInputs: Astrodata inputs to be converted to Electron pixel units
    :type adInputs: Astrodata objects, either a single or a list of objects
    
    :param fl_trim: Trim the overscan region from the frames?
    :type fl_trim: Python boolean (True/False)
    
    :param fl_vardq: Create variance and data quality frames?
    :type fl_vardq: 
        Python boolean (True/False), OR string 'AUTO' to do 
        it automatically if there are VAR and DQ frames in the inputs.
        NOTE: 'AUTO' uses the first input to determine if VAR and DQ frames  
        exist, so, if the first does, then the rest MUST also have them as well.

    :param biassec: biassec parameter of format '[#:#,#:#],[#:#,#:#],[#:#,#:#]'
    :type biassec: string. 
                   default: '[1:25,1:2304],[1:32,1:2304],[1025:1056,1:2304]' 
                   is ideal for 2x2 GMOS data.
    
    :param outNames: filenames of output(s)
    :type outNames: String, either a single or a list of strings of same length 
                    as adInputs.
    
    :param suffix: string to postpend on the end of the input filenames 
                   (or outNames if not None) for the output filenames.
    :type suffix: string
    
    :param log: logger object to send log messges to
    :type log: A gemLog object from astrodata/adutils/gemLog.py .
               It is an upgraded version of the Python logger for use 
               with all new scripts in gemini_python/ .
               Note: the logName, logLevel and noLogFile will be automatically
               determined from the logger object passed in to 'log' with the 
               ScienceFunctionManager.startUp() function.
    
    :param logName: Name of the log file, default is 'gemini.log'
    :type logName: string
    
    :param logLevel: 
         verbosity setting for the log messages to screen,
         default is 'critical' messages only.
         Note: independent of logLevel setting, all messages always go 
         to the logfile if it is not turned off.
    :type logLevel: integer from 0-6, 0=nothing to screen, 6=everything to 
                    screen. OR the message level as a string (ie. 'critical', 
                    'status', 'fullinfo'...)

    :param noLogFile: A boolean to make it so no log file is created
    :type noLogFile: Python boolean (True/False)
    """

    # Instantiate ScienceFunctionManager object
    sfm = gemt.ScienceFunctionManager(adInputs, outNames, suffix, log, logName,
                                      logLevel, noLogFile, 
                                      funcName='overscan_subtract') 
    # Perform start up checks of the inputs, prep/check of outnames, and get log
    # and the log params for later use if needed.
    adInputs, outNames, log, logName, logLevel, noLogFile = sfm.startUp()
    
    try: 
        # loading and bringing the pyraf related modules into the name-space
        pyraf, gemini, yes, no = pyrafLoader() 
         
        # Creating empty list of ad's to be returned that will be filled below
        adOutputs=[]
                
        # Converting input True/False to yes/no or detecting fl_vardq value
        # if 'AUTO' chosen with autoVardq in the ScienceFunctionManager
        fl_vardq = sfm.autoVardq(fl_vardq)
        
        # To clean up log and screen if multiple inputs
        log.fullinfo('+'*50, category='format')                                 
            
        # Preparing input files, lists, parameters... for input to 
        # the CL script
        clm=gemt.CLManager(imageIns=adInputs, imageOutsNames=outNames,  
                           suffix=suffix, funcName='overscanSubtract',   
                           logName=logName, logLevel=logLevel, 
                           noLogFile=noLogFile)
        
        # Check the status of the CLManager object, True=continue, False= issue warning
        if clm.status:                     
            # Parameters set by the gemt.CLManager or the definition 
            # of the primitive 
            clPrimParams = {
              'inimages'    :clm.imageInsFiles(type='string'),
              'gp_outpref'  :clm.prefix,
              'outimages'   :clm.imageOutsFiles(type='string'),
              # This returns a unique/temp log file for IRAF
              'logfile'     :clm.templog.name,      
              'fl_over'     :yes, 
              # This is actually in the default dict but wanted to show it again
              'Stdout'      :gemt.IrafStdout(logLevel=logLevel), 
              # This is actually in the default dict but wanted to show it again
              'Stderr'      :gemt.IrafStdout(logLevel=logLevel), 
              # This is actually in the default dict but wanted to show it again
              'verbose'     :yes                
                          }
            
            # Taking care of the biasec->nbiascontam param
            if not biassec == '':
                nbiascontam = gemt.nbiascontam(adInputs, biassec, logLevel)
                log.fullinfo('nbiascontam parameter was updated to = '+
                             str(nbiascontam))
            else: 
                # Do not try to calculate it, just use default value of 4.
                log.fullinfo('Using default nbiascontam parameter = 4')
                nbiascontam = 4
            
            # Parameters from the Parameter file that are adjustable by the user
            clSoftcodedParams = {
               # pyrafBoolean converts the python booleans to pyraf ones
               'fl_trim'    :gemt.pyrafBoolean(fl_trim),
               'outpref'    :suffix,
               'fl_vardq'   :fl_vardq,
               'nbiascontam':nbiascontam
                               }
            # Grabbing the default params dict and updating it with 
            # the two above dicts
            clParamsDict = CLDefaultParamsDict('gireduce', 
                                               logLevel=logLevel)
            clParamsDict.update(clPrimParams)
            clParamsDict.update(clSoftcodedParams)
            
            # Logging the parameters that were not defaults
            log.fullinfo('\nParameters set automatically:', 
                         category='parameters')
            # Loop through the parameters in the clPrimParams dictionary
            # and log them
            gemt.logDictParams(clPrimParams, logLevel=logLevel)
            
            log.fullinfo('\nParameters adjustable by the user:', 
                         category='parameters')
            # Loop through the parameters in the clSoftcodedParams 
            # dictionary and log them
            gemt.logDictParams(clSoftcodedParams,logLevel=logLevel)
            
            log.debug('Calling the gireduce CL script for inputs '+
                  clm.imageInsFiles(type='string'))
        
            gemini.gmos.gireduce(**clParamsDict)
            
            if gemini.gmos.gireduce.status:
                log.critical('gireduce failed for inputs '+
                             clm.imageInsFiles(type='string'))
                raise ScienceError()
            else:
                log.status('Exited the gireduce CL script successfully')
            
            # Renaming CL outputs and loading them back into memory, and 
            # cleaning up the intermediate tmp files written to disk
            # refOuts and arrayOuts are None here
            imageOuts, refOuts, arrayOuts = clm.finishCL() 
            
            # Renaming for symmetry
            adOutputs=imageOuts
            
            # Wrap up logging
            i=0
            for adOut in adOutputs:
                # Verifying gireduce was actually ran on the file
                if adOut.phuGetKeyValue('GIREDUCE'): 
                    # If gireduce was ran, then log the changes to the files 
                    # it made
                    log.fullinfo('\nFile '+clm.preCLimageNames()[i]+
                                 ' had its overscan subracted successfully')
                    log.fullinfo('New file name is: '+adOut.filename)
                i = i+1
                # Updating GEM-TLM and OVERSUB time stamps in the PHU
                adOut.historyMark(key='OVERSUB', stomp=False)  
                
                # Updating GEM-TLM (automatic) and BIASCORR time stamps to the PHU
                # and updating logger with updated/added time stamps
                sfm.markHistory(adOutputs=adOut, historyMarkKey='OVERSUB')
        else:
            log.critical('One of the inputs has not been prepared,\
            the overscanSubtract function can only work on prepared data.')
            raise ScienceError()
        
        log.status('**FINISHED** the overscan_subtract function')
        
        # Return the outputs list, even if there is only one output
        return adOutputs
    except:
        raise ScienceError('An error occurred while trying to run \
                                                            overscan_subtract') 
                
                
def fringe_correct(adInputs, fringes, fl_statscale=False, scale=0.0, statsec='',
            outNames=None, suffix=None, log=None, logName='gemini.log', 
            logLevel=1, noLogFile=False):
    """
    This primitive will scale and subtract the fringe frame from the inputs.
    It utilizes the Python re-written version of cl script girmfringe now called
    rmImgFringe in gmosTools to do the work.
    
    NOTE:
    String representing the name of the log file to write all log messages to
    can be defined, or a default of 'gemini.log' will be used.  If the file
    all ready exists in the directory you are working in, then this file will 
    have the log messages during this function added to the end of it.

    FOR FUTURE
    This function has many GMOS dependencies that would be great to work out
    so that this could be made a more general function (say at the Gemini level)
    .
    
    :param adInputs: Astrodata input(s) to be fringe corrected
    :type adInputs: Astrodata objects, either a single or a list of objects
    
    :param fringes: Astrodata input fringe(s)
    :type fringes: AstroData objects in a list, or a single instance.
                   Note: If there is multiple inputs and one fringe provided, 
                   then the same fringe will be applied to all inputs; else the   
                   fringes list must match the length of the inputs.
    
    :param fl_statscale: Scale by statistics rather than exposure time
    :type fl_statscale: Boolean
    
    :param statsec: image section used to determine the scale factor 
                    if fl_statsec=True
    :type statsec: string of format '[EXTNAME,EXTVER][x1:x2,y1:y2]'
                   default: If CCDSUM = '1 1' :[SCI,2][100:1900,100:4500]'
                   If CCDSUM = '2 2' : [SCI,2][100:950,100:2250]'
    
    :param scale: Override auto-scaling if not 0.0
    :type scale: real

    :param outNames: filenames of output(s)
    :type outNames: String, either a single or a list of strings of same 
                    length as adInputs.
    
    :param suffix: string to postpend on the end of the input filenames 
                   (or outNames if not None) for the output filenames.
    :type suffix: string
    
    :param log: logger object to send log messges to
    :type log: A gemLog object from astrodata/adutils/gemLog.py .
               It is an upgraded version of the Python logger for use 
               with all new scripts in gemini_python/ .
               Note: the logName, logLevel and noLogFile will be automatically
               determined from the logger object passed in to 'log' with the 
               ScienceFunctionManager.startUp() function.
    
    :param logName: Name of the log file, default is 'gemini.log'
    :type logName: string
    
    :param logLevel: 
         verbosity setting for the log messages to screen,
         default is 'critical' messages only.
         Note: independent of logLevel setting, all messages always go 
         to the logfile if it is not turned off.
    :type logLevel: integer from 0-6, 0=nothing to screen, 6=everything 
                    to screen. OR the message level as a string (ie. 'critical',  
                    'status', 'fullinfo'...)

    :param noLogFile: A boolean to make it so no log file is created
    :type noLogFile: Python boolean (True/False)
    """

    # Instantiate ScienceFunctionManager object
    sfm = gemt.ScienceFunctionManager(adInputs, outNames, suffix, log, logName,
                                      logLevel, noLogFile, 
                                      funcName='fringe_correct') 
    # Perform start up checks of the inputs, prep/check of outnames, and get log
    # and the log params for later use if needed.
    adInputs, outNames, log, logName, logLevel, noLogFile = sfm.startUp()
    
    try:
        # Set up counter for looping through outNames/BPMs lists
        count=0
        
        # Creating empty list of ad's to be returned that will be filled below
        adOutputs=[]
        
        for ad in adInputs:
            
            # Setting up the fringe correctly
            if (isinstance(fringes,list)) and (len(fringes)>1):
                fringe = fringes[count]
            elif (isinstance(fringes,list)) and (len(fringes)==1):
                # Not sure if I need this check, but can't hurt
                fringe = fringes[0]
            else:
                fringe = fringes
                    
            # Loading up a dictionary with the input parameters for rmImgFringe
            paramDict = {
                         'inimage'        :ad,
                         'fringe'         :fringe,
                         'fl_statscale'   :fl_statscale,
                         'statsec'        :statsec,
                         'scale'          :scale,
                         'logLevel'       :logLevel
                         }
            
            # Logging values set in the parameters dictionary above
            log.fullinfo('\nParameters being used for rmImgFringe '+
                         'function:\n')
            gemt.logDictParams(paramDict,logLevel=logLevel)
            
            # Calling the rmImgFringe function to perform the fringe 
            # corrections, this function will return the corrected image as
            # an AstroData instance
            adOut = gmost.rmImgFringe(**paramDict)
            
            # renaming the output ad filename
            adOut.filename = outNames[count]
                    
            log.status('File name updated to '+adOut.filename)
            
            # Updating GEM-TLM (automatic) and BIASCORR time stamps to the PHU
            # and updating logger with updated/added time stamps
            sfm.markHistory(adOutputs=adOut, historyMarkKey='RMFRINGE')
        
            # Appending to output list
            adOutputs.append(adOut)
    
            count=count+1
                
        log.status('**FINISHED** the fringe_correct function')
        # Return the outputs (list or single, matching adInputs)
        return adOutputs
    except:
        raise ScienceError('An error occurred while trying to run \
                                                                fringe_correct')
    
def make_fringe_frame_imaging(adInputs, fl_vardq='AUTO', method='median', 
            outNames=None, suffix=None, log=None, logName='gemini.log', 
                                                logLevel=1, noLogFile=False):
    """
    This function will create and return a single fringe image from all the 
    inputs.  It utilizes the CL script gifringe to create the fringe image.
    
    NOTE: The inputs to this function MUST be prepared. 

    A string representing the name of the log file to write all log messages to
    can be defined, or a default of 'gemini.log' will be used.  If the file
    all ready exists in the directory you are working in, then this file will 
    have the log messages during this function added to the end of it.
    
    :param adInputs: Astrodata inputs to be combined
    :type adInputs: Astrodata objects, either a single or a list of objects
    
    :param fl_vardq: Create variance and data quality frames?
    :type fl_vardq: Python boolean (True/False), OR string 'AUTO' to do 
                    it automatically if there are VAR and DQ frames in the 
                    inputs.
                    NOTE: 'AUTO' uses the first input to determine if VAR and DQ  
                    frames exist, so, if the first does, then the rest MUST also 
                    have them as well.
    
    :param method: type of combining method to use.
    :type method: string, options: 'average', 'median'.
    
    :param outNames: filenames of output(s)
    :type outNames: String, either a single or a list of strings of same length
                    as adInputs.
    
    :param suffix: string to add on the end of the input filenames 
                    (or outNames if not None) for the output filenames.
    :type suffix: string
    
    :param log: logger object to send log messges to
    :type log: A gemLog object from astrodata/adutils/gemLog.py .
               It is an upgraded version of the Python logger for use 
               with all new scripts in gemini_python/ .
               Note: the logName, logLevel and noLogFile will be automatically
               determined from the logger object passed in to 'log' with the 
               ScienceFunctionManager.startUp() function.
    
    :param logName: Name of the log file, default is 'gemini.log'
    :type logName: string
    
    :param logLevel: verbosity setting for the log messages to screen,
                    default is 'critical' messages only.
                    Note: independent of logLevel setting, all messages always  
                    go to the logfile if it is not turned off.
    :type logLevel: integer from 0-6, 0=nothing to screen, 6=everything to 
                    screen. OR the message level as a string (ie. 'critical',  
                    'status', 'fullinfo'...)
                    
    :param noLogFile: A boolean to make it so no log file is created
    :type noLogFile: Python boolean (True/False)
    """
    
    # Instantiate ScienceFunctionManager object
    sfm = gemt.ScienceFunctionManager(adInputs, outNames, suffix, log, logName,
                                       logLevel, noLogFile, 
                                       funcName='make_fringe_frame_imaging', 
                                       combinedInputs=True)
    # Perform start up checks of the inputs, prep/check of outnames, and get log
    # and the log params for later use if needed.
    adInputs, outNames, log, logName, logLevel, noLogFile = sfm.startUp()
    
    try:
        # Set up counter for looping through outNames list
        count=0
        
        # Ensuring there is more than one input to make a fringe frame from
        if (len(adInputs)>1):
            
            # loading and bringing the pyraf related modules into the name-space
            pyraf, gemini, yes, no = pyrafLoader() 
             
            # Creating empty list of ad's to be returned that will be filled below
            adOutputs=[]
                    
            # Converting input True/False to yes/no or detecting fl_vardq value
            # if 'AUTO' chosen with autoVardq in the ScienceFunctionManager
            fl_vardq = sfm.autoVardq(fl_vardq)
            
            # To clean up log and screen if multiple inputs
            log.fullinfo('+'*50, category='format')                                 
                
            # Preparing input files, lists, parameters... for input to 
            # the CL script
            clm=gemt.CLManager(imageIns=adInputs, imageOutsNames=outNames,  
                               suffix=suffix, funcName='makeFringeFrame', 
                               combinedImages=True, logName=logName,   
                               logLevel=logLevel, noLogFile=noLogFile)
            
            # Check the status of the CLManager object, True=continue, False= issue warning
            if clm.status:                     
            
                # Parameters set by the gemt.CLManager or the definition 
                # of the primitive 
                clPrimParams = {
                    # Retrieving the inputs as a list from the CLManager
                    'inimages'    :clm.imageInsFiles(type='listFile'),
                    # Maybe allow the user to override this in the future. 
                    'outimage'    :clm.imageOutsFiles(type='string'), 
                    # This returns a unique/temp log file for IRAF  
                    'logfile'     :clm.templog.name,  
                    # This is actually in the default dict but wanted to 
                    # show it again       
                    'Stdout'      :gemt.IrafStdout(logLevel=logLevel), 
                    # This is actually in the default dict but wanted to 
                    # show it again    
                    'Stderr'      :gemt.IrafStdout(logLevel=logLevel),
                    # This is actually in the default dict but wanted to 
                    # show it again     
                    'verbose'     :yes                    
                              }
    
                # Creating a dictionary of the parameters from the Parameter 
                # file adjustable by the user
                clSoftcodedParams = {
                    'fl_vardq'      :gemt.pyrafBoolean(fl_vardq),
                    'combine'       :method,
                    'reject'        :'none',
                                    }
                # Grabbing the default parameters dictionary and updating 
                # it with the two above dictionaries
                clParamsDict = CLDefaultParamsDict('gifringe', 
                                                   logLevel=logLevel)
                clParamsDict.update(clPrimParams)
                clParamsDict.update(clSoftcodedParams)
                
                # Logging the values in the soft and prim parameter dictionaries
                log.fullinfo('\nParameters set by the CLManager or  '+
                         'dictated by the definition of the primitive:\n', 
                         category='parameters')
                gemt.logDictParams(clPrimParams,logLevel=logLevel)
                log.fullinfo('\nUser adjustable parameters in the '+
                             'parameters file:\n', category='parameters')
                gemt.logDictParams(clSoftcodedParams,logLevel=logLevel)
                
                log.debug('Calling the gifringe CL script for input list '+
                              clm.imageInsFiles(type='listFile'))
                
                gemini.gifringe(**clParamsDict)
                
                if gemini.gifringe.status:
                    log.critical('gifringe failed for inputs '+
                                 rc.inputsAsStr())
                    raise GMOS_IMAGEException('gifringe failed')
                else:
                    log.status('Exited the gifringe CL script successfully')
                    
                # Renaming CL outputs and loading them back into memory 
                # and cleaning up the intermediate temp files written to disk
                # refOuts and arrayOuts are None here
                imageOuts, refOuts, arrayOuts = clm.finishCL() 
                
                # Renaming for symmetry
                adOutputs=imageOuts
            
                # Renaming for symmetry
                adOutputs=imageOuts
                
                # Updating GEM-TLM (automatic) and COMBINE time stamps to the PHU
                # and updating logger with updated/added time stamps
                sfm.markHistory(adOutputs=adOutputs, historyMarkKey='FRINGE')
            else:
                log.critical('One of the inputs has not been prepared,\
                the combine function can only work on prepared data.')
                raise ScienceError('One of the inputs was not prepared')
        else:
            log.warning('Only one input was passed in for adInputs, so \
                    make_fringe_frame_imaging is simply passing the inputs  \
                    into the outputs list without doing anything to them.')
            adOutputs = adInputs
        
        log.status('**FINISHED** the make_fringe_frame_imaging function')
        
        # Return the outputs list, even if there is only one output
        return adOutputs
    except:
        raise ScienceError('An error occurred while trying to run \
                                                    make_fringe_frame_imaging')
    
    
    
    