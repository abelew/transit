import sys
import wx
import os
import time
import math
import random
import numpy
import scipy.stats
import datetime

import base
import transit_tools

import tnseq_tools
import norm_tools
import stat_tools

#method_name = "hmm"


############# GUI ELEMENTS ##################
def Hide(wxobj):
    wxobj.hmmPanel.Hide()

def Show(wxobj):
    wxobj.hmmPanel.Show()

def getInstructions():
        return """Instructions:

1. Make sure you have one control sample selected.
2. Modify the options as desired.
3. Click on the "Run HMM" button.
4. Choose a name for the output file.
5. Wait until the execution finishes and the output is added to the file list at the bottom of the screen.
                """



def getPanel(wxobj):
    wxobj.hmmPanel = wx.Panel( wxobj.m_scrolledWindow1, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL )
    #wxobj.hmmPanel.SetMinSize( wx.Size( 50,1 ) )
    #wxobj.hmmPanel.SetMaxSize( wx.Size( 250,-1 ) )

    hmmSection = wx.BoxSizer( wx.VERTICAL )

    wxobj.hmmLabel = wx.StaticText( wxobj.hmmPanel, wx.ID_ANY, u"HMM Options", wx.DefaultPosition, wx.DefaultSize, 0 )
    wxobj.hmmLabel.Wrap( -1 )
    hmmSection.Add( wxobj.hmmLabel, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL, 5 )

    hmmSizer1 = wx.BoxSizer( wx.HORIZONTAL )
    hmmSection.Add( hmmSizer1, 1, wx.EXPAND, 5 )

    wxobj.hmmButton = wx.Button( wxobj.hmmPanel, wx.ID_ANY, u"Run HMM", wx.DefaultPosition, wx.DefaultSize, 0 )
    hmmSection.Add( wxobj.hmmButton, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL, 5 )

    wxobj.hmmPanel.SetSizer( hmmSection )
    wxobj.hmmPanel.Layout()
    hmmSection.Fit( wxobj.hmmPanel )

    #Connect events
    wxobj.hmmButton.Bind( wx.EVT_BUTTON, wxobj.RunMethod )

    return wxobj.hmmPanel


def updateProgressBar(wxobj, count):
    wxobj.hmmProgress.SetValue(count)

def SetProgressRange(wxobj, X):
    wxobj.hmmProgress.SetRange(X)

def enableButton(wxobj):
    wxobj.hmmButton.Enable()





########## CLASS #######################

class HMM(base.SingleConditionMethod):
    """   
    HMM
 
    """
    def __init__(self,
                ctrldata,
                annotation_path,
                output_file,
                normalization=None,
                LOESS=False,
                ignoreCodon=True,
                NTerminus=0.0,
                CTerminus=0.0, wxobj=None):

        base.SingleConditionMethod.__init__(self, "HMM", "HMM Method", "The HMM method described in 2013 by DeJesus et al.", ctrldata, annotation_path, output_file, normalization=normalization, LOESS=LOESS, NTerminus=NTerminus, CTerminus=CTerminus, wxobj=wxobj)

        try:
            T = len([1 for line in open(ctrldata[0]).readlines() if not line.startswith("#")])
            self.maxiterations = T*4 + 1
        except:
            self.self.maxiterations = 100
        self.count = 1


    @classmethod
    def fromGUI(self, wxobj):
        """ """
        #Get selected files
        all_selected = wxobj.ctrlSelected()
        if len(all_selected) ==0:
            wxobj.ShowError("Error: No dataset selected.")
            return None

        #Get Annotation file
        annotationPath = wxobj.annotationFilePicker.GetPath()
        if not annotationPath:
            wxobj.ShowError("Error: No annotation file selected.")
            return None


        #Read the parameters from the wxPython widgets
        ctrldata = all_selected
        ignoreCodon = True
        NTerminus = float(wxobj.globalNTerminusText.GetValue())
        CTerminus = float(wxobj.globalCTerminusText.GetValue())
        normalization = None
        LOESS = False

        #Get output path
        name = transit_tools.basename(all_selected[0])
        defaultFileName = "hmm_output.dat"
        defaultDir = os.getcwd()
        output_path = wxobj.SaveFile(defaultDir, defaultFileName)
        if not output_path: return None
        output_file = open(output_path, "w")



        return self(ctrldata,
                annotationPath,
                output_file,
                normalization,
                LOESS,
                ignoreCodon,
                NTerminus,
                CTerminus, wxobj)

    @classmethod
    def fromargs(self, rawargs): 
        (args, kwargs) = transit_tools.cleanargs(rawargs)

        ctrldata = args[0].split(",")
        annotationPath = args[1]
        outpath = args[2]
        output_file = open(outpath, "w")

        normalization = None
        LOESS = False
        ignoreCodon = True
        NTerminus = 0.0
        CTerminus = 0.0

        return self(ctrldata,
                annotationPath,
                output_file,
                normalization,
                LOESS,
                ignoreCodon,
                NTerminus,
                CTerminus)

    def Run(self):

        self.transit_message("Starting HMM Method")
        start_time = time.time()
        
        #Get orf data
        self.transit_message("Getting Data")
        (data, position) = transit_tools.get_data(self.ctrldata)
        hash = transit_tools.get_pos_hash(self.annotation_path)
        rv2info = transit_tools.get_gene_info(self.annotation_path)
        self.transit_message("Combining Replicates as '%s'" % self.replicates)

        if self.replicates == "Sum":
            O = numpy.round(numpy.sum(data,0))
        elif self.replicates == "Mean":
            O = numpy.round(numpy.mean(data,0))
        elif self.replicates == "TTRMean":
            factors = transit_tools.TTR_factors(data)
            data = factors * data
            target_factors = transit_tools.norm_to_target(data, 100)
            data = target_factors * data
            O = numpy.round(numpy.mean(data,0))
        else:
            O = data[0,:]

        O = O + 1 # Adding 1 to because of shifted geometric in scipy

        #Parameters
        Nstates = 4
        label = {0:"ES", 1:"GD", 2:"NE",3:"GA"}

        reads = O-1
        reads_nz = sorted(reads[reads !=0 ])
        size = len(reads_nz)
        mean_r = numpy.average(reads_nz[:int(0.95 * size)])
        mu = numpy.array([1/0.99, 0.01 * mean_r + 2,  mean_r, mean_r*5.0])
        L = 1.0/mu
        B = [] # Emission Probability Distributions
        for i in range(Nstates):
            B.append(scipy.stats.geom(L[i]).pmf)

        pins = self.calculate_pins(O-1)
        pins_obs = sum([1 for rd in O if rd >=2])/float(len(O))
        pnon = 1.0 - pins
        pnon_obs = 1.0 - pins_obs

        for r in range(100):
            if pnon ** r < 0.01: break

        A = numpy.zeros((Nstates,Nstates))
        a = math.log1p(-B[int(Nstates/2)](1)**r)
        b = r*math.log(B[int(Nstates/2)](1)) + math.log(1.0/3) # change to Nstates-1?
        for i in range(Nstates):
            A[i] = [b]*Nstates
            A[i][i] = a

        PI = numpy.zeros(Nstates) # Initial state distribution
        PI[0] = 0.7; PI[1:] = 0.3/(Nstates-1);


        self.progress_range(self.maxiterations)
        

        ###############
        ### VITERBI ###
        (Q_opt, delta, Q) = self.viterbi(A, B, PI, O)
        ###############

        ##################
        ### ALPHA PASS ###
        (log_Prob_Obs, alpha, C) = self.forward_procedure(numpy.exp(A), B, PI, O)
        ##################

        #################
        ### BETA PASS ###
        beta = self.backward_procedure(numpy.exp(A), B, PI, O, C)
        #################

        T = len(O); total=0; state2count = dict.fromkeys(range(Nstates),0)
        for t in xrange(T):
            state = Q_opt[t]
            state2count[state] +=1
            total+=1
 
            
       
        self.output.write("#HMM - Sites\n")
        self.output.write("# Tn-HMM\n")
 
        if self.wxobj:
            members = sorted([attr for attr in dir(self) if not callable(getattr(self,attr)) and not attr.startswith("__")])
            memberstr = ""
            for m in members:
                memberstr += "%s = %s, " % (m, getattr(self, m))
            self.output.write("#GUI with: ctrldata=%s, annotation=%s, output=%s\n" % (",".join(self.ctrldata), self.annotation_path, self.output))
        else:
            self.output.write("#Console: python %s\n" % " ".join(sys.argv))
       
        self.output.write("# \n")
        self.output.write("# Mean:\t%2.2f\n" % (numpy.average(reads_nz)))
        self.output.write("# Median:\t%2.2f\n" % numpy.median(reads_nz))
        self.output.write("# pins (obs):\t%f\n" % pins_obs)
        self.output.write("# pins (est):\t%f\n" % pins)
        self.output.write("# Run length (r):\t%d\n" % r)
        self.output.write("# State means:\n")
        self.output.write("#    %s\n" % "   ".join(["%s: %8.4f" % (label[i], mu[i]) for i in range(Nstates)]))
        self.output.write("# Self-Transition Prob:\n")
        self.output.write("#    %s\n" % "   ".join(["%s: %2.4e" % (label[i], A[i][i]) for i in range(Nstates)]))
        self.output.write("# State Emission Parameters (theta):\n")
        self.output.write("#    %s\n" % "   ".join(["%s: %1.4f" % (label[i], L[i]) for i in range(Nstates)]))
        self.output.write("# State Distributions:")
        self.output.write("#    %s\n" % "   ".join(["%s: %2.2f%%" % (label[i], state2count[i]*100.0/total) for i in range(Nstates)]))
         

        states = [int(Q_opt[t]) for t in range(T)]
        last_orf = ""
        for t in xrange(T):
            s_lab = label.get(states[t], "Unknown State")
            gamma_t = (alpha[:,t] * beta[:,t])/numpy.sum(alpha[:,t] * beta[:,t])
            genes_at_site = hash.get(position[t], [""])
            genestr = ""
            if not (len(genes_at_site) == 1 and not genes_at_site[0]):
                genestr = ",".join(["%s_(%s)" % (g,rv2info.get(g, "-")[0]) for g in genes_at_site])

            self.output.write("%s\t%s\t%s\t%s\t%s\n" % (int(position[t]), int(O[t])-1, "\t".join(["%-9.2e" % g for g in gamma_t]), s_lab, genestr))

        self.output.close()

        self.transit_message("") # Printing empty line to flush stdout 
        self.transit_message("Finished HMM - Sites Method")
        self.transit_message("Adding File: %s" % (self.output.name))
        self.add_file()
        
        #Gene Files
        self.transit_message("Creating HMM Genes Level Output")
        genes_path = ".".join(self.output.name.split(".")[:-1]) + "_genes." + self.output.name.split(".")[-1] 

        tempObs = numpy.zeros((1,len(O)))
        tempObs[0,:] = O - 1
        self.post_process_genes(tempObs, position, states, genes_path)


        self.transit_message("Adding File: %s" % (genes_path))
        self.add_file(genes_path)
        self.finish()
        self.transit_message("Finished HMM Method") 

    @classmethod
    def usage_string(self):
        return """python %s hmm <comma-separated .wig files> <annotation .prot_table> <output file>""" % (sys.argv[0])



    def forward_procedure(self, A, B, PI, O):
        T = len(O)
        N = len(B)
        alpha = numpy.zeros((N,  T))
        C = numpy.zeros(T)

        alpha[:,0] = PI * [B[i](O[0]) for i in range(N)]

        C[0] = 1.0/numpy.sum(alpha[:,0])
        alpha[:,0] = C[0] * alpha[:,0]

        for t in xrange(1, T):
            #B[i](O[:,t])  =>  numpy.prod(B[i](O[:,t]))
            #b_o = numpy.array([numpy.prod(B[i](O[:,t])) for i in range(N)])
            b_o = [B[i](O[t]) for i in range(N)]
        
            alpha[:,t] = numpy.dot(alpha[:,t-1], A) * b_o
            
            C[t] = numpy.nan_to_num(1.0/numpy.sum(alpha[:,t]))
            alpha[:,t] = numpy.nan_to_num(alpha[:,t] * C[t])

            if numpy.sum(alpha[:,t]) == 0:
                alpha[:,t] = 0.0000000000001
           
            self.progress_update("hmm", self.count)
            self.transit_message_inplace("Running HMM Method... %1.1f%%" % (100.0*self.count/self.maxiterations))
            self.count+=1
            #print t, O[:,t], alpha[:,t]

        log_Prob_Obs = - (numpy.sum(numpy.log(C)))
        return(( log_Prob_Obs, alpha, C ))

    def backward_procedure(self, A, B, PI, O, C=None):

        N = len(B)
        T = len(O)
        beta = numpy.zeros((N,T))

        beta[:,T-1] = 1.0
        if C!=None: beta[:,T-1] = beta[:,T-1] * C[T-1]

        for t in xrange(T-2, -1, -1):
            #B[i](O[:,t])  =>  numpy.prod(B[i](O[:,t]))
            #b_o = numpy.array([numpy.prod(B[i](O[:,t])) for i in range(N)])
            b_o = [B[i](O[t]) for i in range(N)]

            beta[:,t] = numpy.nan_to_num(numpy.dot(A, (b_o * beta[:,t+1] ) ))

            if sum(beta[:,t]) == 0:
                beta[:,t] = 0.0000000000001

            if C!=None:
                beta[:,t] = beta[:,t] * C[t]

            self.progress_update("hmm", self.count)
            self.transit_message_inplace("Running HMM Method... %1.1f%%" % (100.0*self.count/self.maxiterations))
            self.count+=1

        return(beta)



    def viterbi(self, A, B, PI, O):
        N=len(B)
        T = len(O)
        delta = numpy.zeros((N, T))

        b_o = [B[i](O[0]) for i in range(N)]
        delta[:,0] = numpy.log(PI) + numpy.log(b_o)

        Q = numpy.zeros((N, T))

        for t in xrange(1, T):
            b_o = [B[i](O[t]) for i in range(N)]
            #nus = delta[:, t-1] + numpy.log(A)
            nus = delta[:, t-1] + A
            delta[:,t] = nus.max(1) + numpy.log(b_o)
            Q[:,t] = nus.argmax(1)
            self.progress_update("hmm", self.count)
            self.transit_message_inplace("Running HMM Method... %1.1f%%" % (100.0*self.count/self.maxiterations))
            self.count+=1

        Q_opt = [numpy.argmax(delta[:,T-1])]
        for t in xrange(T-2, -1, -1):
            Q_opt.insert(0, Q[Q_opt[0],t+1])
            self.progress_update("hmm", self.count)
            self.transit_message_inplace("Running HMM Method... %1.1f%%" % (100.0*self.count/self.maxiterations))
            self.count+=1

        self.progress_update("hmm", self.count)
        self.transit_message_inplace("Running HMM Method... %1.1f%%" % (100.0*self.count/self.maxiterations))

        return((Q_opt, delta, Q))


    def calculate_pins(self, reads):
        non_ess_reads = []
        temp = []
        for rd in reads:

            if rd >=1:
                if len(temp) < 10: non_ess_reads.extend(temp)
                non_ess_reads.append(rd)
                temp = []
            else:
                temp.append(rd)

        return(sum([1 for rd in non_ess_reads if rd >= 1])/float(len(non_ess_reads)) )



    def post_process_genes(self, data, position, states, output_path):

        output = open(output_path, "w")
        pos2state = dict([(position[t],states[t]) for t in range(len(states))])
        theta = numpy.mean(data > 0)
        G = tnseq_tools.Genes(self.ctrldata, self.annotation_path, data=data, position=position)
        
        for gene in G:
            
            reads_nz = [c for c in gene.reads.flatten() if c > 0]
            avg_read_nz = 0
            if len(reads_nz) > 0:
                avg_read_nz = numpy.average(reads_nz)

            # State
            genestates = [pos2state[p] for p in gene.position]
            statedist = {}
            for st in states:
                if st not in statedist: statedist[st] = 0
                statedist[st] +=1

            # State counts
            n0 = statedist.get("ES", 0); n1 = statedist.get("GD", 0);
            n2 = statedist.get("NE", 0); n3 = statedist.get("GA", 0);


            if gene.n > 0:
                E = tnseq_tools.ExpectedRuns(gene.n,   1.0 - theta)
                V = tnseq_tools.VarR(gene.n,   1.0 - theta)
                if n0 == gene.n: S = "ES"
                elif n0 >= int(E+(3*math.sqrt(V))): S = "ES"
                else: S = max([(statedist.get(s, 0), s) for s in ["ES", "GD", "NE", "GA"]])[1]
            else:
                E = 0.0
                V = 0.0
                S = "N/A"
            output.write("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%1.4f\t%1.2f\t%s\n" % (gene.orf, gene.name, gene.desc, gene.n, n0, n1, n2, n3, gene.theta(), avg_read_nz, S))

        output.close()



    




if __name__ == "__main__":

    (args, kwargs) = transit_tools.cleanargs(sys.argv)

    print "ARGS:", args
    print "KWARGS:", kwargs

    G = HMM.fromargs(sys.argv)

    G.console_message("Printing the member variables:")   
    G.print_members()

    print ""
    print "Running:"

    G.Run()


