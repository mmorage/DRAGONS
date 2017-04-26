# This parameter file contains the parameters related to the primitives located
# in the primitives_ccd.py file, in alphabetical order.

from geminidr import ParametersBASE

class ParametersCCD(ParametersBASE):
    biasCorrect = {
        "suffix"            : "_biasCorrected",
        "bias"              : None,
    }
    overscanCorrect = {
        "suffix"            : "_overscanCorrected",
        "average"           : "mean",
        "niterate"          : 2,
        "high_reject"       : 3.0,
        "low_reject"        : 3.0,
        "nbiascontam"       : None,
        "order"             : None,
    }
    subtractBias = {
        "suffix"            : "_biasCorrected",
        "bias"              : None,
    }
    subtractOverscan = {
        "suffix"            : "_overscanSubtracted",
        "average"           : "mean",
        "niterate"          : 2,
        "high_reject"       : 3.0,
        "low_reject"        : 3.0,
        "fit_spline"        : True,
        "nbiascontam"       : None,
        "order"             : None,
    }
    trimOverscan = {
        "suffix"            : "_overscanTrimmed",
    }
