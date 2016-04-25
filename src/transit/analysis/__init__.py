#__all__ = []

from os.path import dirname, basename, isfile
import glob
modules = glob.glob(dirname(__file__)+"/*.py")
__all__ = [ basename(f)[:-3] for f in modules if isfile(f)]

import base

import gumbel
import example
import globalruns
import binomial
import griffin
import resampling
import hmm
import rankproduct


methods = {}
methods["example"] = example.ExampleAnalysis()
methods["gumbel"] = gumbel.GumbelAnalysis()
methods["binomial"] = binomial.BinomialAnalysis()
methods["griffin"] = griffin.GriffinAnalysis()
methods["hmm"] = hmm.HMMAnalysis()
methods["resampling"] = resampling.ResamplingAnalysis()
methods["globalruns"] = globalruns.GlobalGumbelAnalysis()
methods["rankproduct"] = rankproduct.RankProductAnalysis()



