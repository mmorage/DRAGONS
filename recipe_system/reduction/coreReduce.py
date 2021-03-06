"""
class Reduce provides one (1) public method:

    runr()

which calls on the mapper classes and passes the received data to them.

"""
# ------------------------------------------------------------------------------
#                                                                        DRAGONS
#
#                                                                  coreReduce.py
# ------------------------------------------------------------------------------
from __future__ import print_function
from builtins import str
from builtins import object
# ---------------------------- Package Import ----------------------------------
import os
import sys
import inspect
import traceback

from importlib import import_module

import astrodata
import gemini_instruments

from gempy.utils import logutils

from astrodata.core import AstroDataError

from recipe_system import __version__

from recipe_system.utils.errors import ModeError
from recipe_system.utils.errors import RecipeNotFound
from recipe_system.utils.errors import PrimitivesNotFound

from recipe_system.utils.reduce_utils import buildParser
from recipe_system.utils.reduce_utils import normalize_ucals
from recipe_system.utils.reduce_utils import set_btypes

from recipe_system.mappers.recipeMapper import RecipeMapper
from recipe_system.mappers.primitiveMapper import PrimitiveMapper

# ------------------------------------------------------------------------------
log = logutils.get_logger(__name__)

def _log_traceback():
    exc_type, exc_value, exc_traceback = sys.exc_info()
    tblist = traceback.format_exception(exc_type, exc_value, exc_traceback)
    [log.error(line.rstrip()) for line in tblist]
    return


class Reduce(object):
    """
    The Reduce class encapsulates the core processing to be done by reduce.
    __init__ may receive one (1) parameter, nominally, an argparse Namespace
    instance. However, this object type is not required, but only that any
    passed object *must* present an equivalent interface to that of an
    <argparse.Namespace> instance, i.e. a duck type.

    The class provides one (1) public method, runr(), the only call needed to
    run reduce on the supplied argument set.

    Parameters
    ----------
    sys_args : :class:`argparse.Namespace` (optional) or <duck-type object>
            This object type is not required, per se, but only that any passed
            object *must* present an equivalent interface to that of an
            :class:`argparse.Namespace` instance.

    Attributes
    ----------
    adinputs: <list>
          attribute is a list of the input astrodata objects as made from
          the 'files' list (see 'files' below).

    output_filenames: <list>
          read-only property is a list of final output filenames.

    mode: <str>
          operational mode. Currently, only 'qa', 'sq' modes are supported.

    drpkg: <str>
          Data reduction package name. Default is 'geminidr', the Gemini
          Observatory data reduction package.

    files: <list>
          List of input filenames. Passed to Reduce.__init__(), these are
          converted to astrodata objects.

    suffix: <str>
          User supplied suffix to be applied as a final suffix to output
          filenames.

    ucals: <dict>
          Dictionary of calibration files passed by --user_cals flag.

    uparms: <dict>
          Dictionary of user parameters as passed by -p, --param flag.

    upload : <list>
          List of products to upload to fitsstore as passed by --upload.
          E.g.,
              --upload metrics calibs
                                    ==> upload == ['metrics', 'calibs']
         will upload QA metrics to fitsstore and processing calibration
         files.

    recipename: <str>
        The name of the recipe that will be run. If None, the 'default'
        recipe is used, as specified in the appropriate recipe library.

    """
    def __init__(self, sys_args=None):
        if sys_args:
            args = sys_args
        elif self._confirm_args():
            args = buildParser(__version__).parse_args()
        else:
            args = buildParser(__version__).parse_args([])

        # acquire any new astrodata classes.
        if args.adpkg:
            import_module(args.adpkg)

        self.adinputs = None
        self.mode = args.mode
        self.drpkg = args.drpkg
        self.files = args.files
        self.suffix = args.suffix
        self.ucals = normalize_ucals(args.files, args.user_cal)
        self.uparms = set_btypes(args.userparam)
        self._upload = args.upload
        self._output_filenames = None
        self.recipename = args.recipename if args.recipename else 'default'

    @property
    def upload(self):
        return self._upload

    @upload.setter
    def upload(self, upl):
        if upl is None:
            self._upload = None
        elif isinstance(upl, str):
            self._upload = [seg.lower().strip() for seg in upl.split(',')]
        elif isinstance(upl, list):
            self._upload = upl
        return

    @property
    def output_filenames(self):
        return self._output_filenames


    def runr(self):
        """
        Map and run the requested or defaulted recipe.

        Parameters
        ----------
        <void>

        Returns
        -------
        <void>

        """
        recipe = None
        try:
            ffiles = self._check_files(self.files)
        except IOError as err:
            log.error(str(err))
            raise

        try:
            self.adinputs = self._convert_inputs(ffiles)
        except IOError as err:
            log.error(str(err))
            raise

        rm = RecipeMapper(self.adinputs, mode=self.mode, drpkg=self.drpkg,
                          recipename=self.recipename)

        pm = PrimitiveMapper(self.adinputs, mode=self.mode, drpkg=self.drpkg,
                             usercals=self.ucals, uparms=self.uparms,
                             upload=self.upload)

        try:
            recipe = rm.get_applicable_recipe()
        except ModeError as err:
            log.warn("WARNING: {}".format(err))
            pass
        except RecipeNotFound as err:
            pass

        try:
            p = pm.get_applicable_primitives()
        except PrimitivesNotFound as err:
            log.error(str(err))
            raise

        # If the RecipeMapper was unable to find a specified user recipe,
        # it is possible that the recipe passed was a primitive name.
        # Here we examine the primitive set to see if this recipe is actually
        # a primitive name.
        if recipe is None:
            try:
                primitive_as_recipe = getattr(p, self.recipename)
            except AttributeError as err:
                err = "Recipe {} Not Found".format(self.recipename)
                log.error(str(err))
                raise

            pname = primitive_as_recipe.__name__
            log.stdinfo("Found '{}' as a primitive.".format(pname))
            self._logheader(pname)
            try:
                primitive_as_recipe()
            except Exception as err:
                _log_traceback()
                log.error(str(err))
                raise
        else:
            self._logheader(recipe)
            try:
                recipe(p)
            except Exception as err:
                log.error("Reduce received an unhandled exception. Aborting ...")
                _log_traceback()
                log.stdinfo("Writing final outputs ...")
                self._write_final(p.streams['main'])
                self.output_filenames = [ad.filename for ad in p.streams['main']]
                raise

        self._write_final(p.streams['main'])
        self._output_filenames = [ad.filename for ad in p.streams['main']]
        msg = "\nreduce completed successfully."
        log.stdinfo(str(msg))
        return

    # -------------------------------- prive -----------------------------------
    def _check_files(self, ffiles):
        """
        Sanity check on submitted files.

        Parameters
        --------
        ffiles: <list>
                list of passed FITS files.

        Return
        ------
        input_files: <list>
              list of 'good' input fits datasets.

        """
        try:
            assert ffiles
        except AssertionError:
            log.error("NO INPUT FILE(s) specified")
            log.stdinfo("type 'reduce -h' for usage information")
            raise IOError("NO INPUT FILE(s) specified")

        input_files = []
        bad_files = []

        for image in ffiles:
            if not os.access(image, os.R_OK):
                log.error('Cannot read file: '+str(image))
                bad_files.append(image)
            else:
                input_files.append(image)
        try:
            assert bad_files
            err = "\n\t".join(bad_files)
            log.warn("Files not found or cannot be loaded:\n\t%s" % err)
            try:
                assert input_files
                found = "\n\t".join(input_files)
                log.stdinfo("These datasets were loaded:\n\t%s" % found)
            except AssertionError:
                log.error("Caller passed no valid input files")
                raise IOError("No valid files passed.")
        except AssertionError:
            log.stdinfo("All submitted files appear valid:")
            if len(input_files) > 1:
                filestr = input_files[0]
                filestr += " ... " + input_files[-1]
                filestr += ", {} files submitted.".format(len(input_files))
            else:
                filestr = input_files[0]

            log.stdinfo(filestr)
        return input_files

    def _convert_inputs(self, inputs):
        """
        Convert files into AstroData objects.

        Parameters
        ----------
        inputs: <list>, list of FITS file names

        Return
        ------
        allinputs: <list>, list of AstroData objects

        """
        allinputs = []
        for inp in inputs:
            try:
                ad = astrodata.open(inp)
            except AstroDataError as err:
                log.warning("Can't Load Dataset: %s" % inp)
                log.warning(err)
                continue
            except IOError as err:
                log.warning("Can't Load Dataset: %s" % inp)
                log.warning(err)
                continue

            if not len(ad):
                log.warning("%s contains no extensions." % ad.filename)
                continue

            allinputs.append(ad)

        return allinputs

    def _confirm_args(self):
        """
        Confirm that the first executable frame in the call stack is a reduce
        command line. This asserts that a nominal reduce parser, as returned by
        buildParser() function, is an equivalent Namespace object to that
        of an 'args' key in the stack's 'f_locals' namespace. If the Namespace
        objects are not equal, reduce is not calling this class.

        Parameters
        ----------
        <void>

        Returns
        -------
        is_reduce: <bool>,
            Did 'reduce' call this?

        """
        is_reduce = False
        exe_path = sys.argv[0]
        red_namespace = buildParser(__version__).parse_args([])
        if exe_path:
            cstack = inspect.stack()
            for local, value in list(cstack[-1][0].f_locals.items()):
                if local == 'args':
                    try:
                        assert(
                            list(value.__dict__.keys()) ==
                            list(red_namespace.__dict__.keys())
                        )
                        is_reduce = True
                    except AttributeError:
                        pass
                    except AssertionError:
                        log.stdinfo("A non-reduce command line was detected.")
                        pass

        return is_reduce

    def _logheader(self, recipe):
        if self.recipename == 'default':
            r_actual = recipe.__name__
        else:
            r_actual = self.recipename

        logstring = "RECIPE: {}".format(r_actual)
        log.status("="*80)
        log.status(logstring)
        log.status("="*80)
        return

    def _write_final(self, outputs):
        """
        Write final outputs. Write only if filename is not == orig_filename, or
        if there is a user suffix (self.suffix)

        Parameters
        ----------
        outputs: <list>, List of AstroData objects

        Return
        ------
        <void>

        """
        outstr = "\tWrote {} in output directory"
        def _sname(name):
            head, tail = os.path.splitext(name)
            ohead = head.split("_")[0]
            newname = ohead + self.suffix + tail
            return newname

        for ad in outputs:
            if self.suffix:
                username = _sname(ad.filename)
                ad.write(username, overwrite=True)
                log.stdinfo(outstr.format(username))
            elif ad.filename != ad.orig_filename:
                ad.write(ad.filename, overwrite=True)
                log.stdinfo(outstr.format(ad.filename))
        return
