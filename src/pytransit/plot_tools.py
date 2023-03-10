import matplotlib.pyplot as plt
import numpy

def plot_scatter(control, experimental, control_rep = 0, experimental_rep = 0,
                 log_scale = True):
    """ transit_gui.scatterFunc(), plots scatter plot of TA insertions across two samples.

    I haven't figured out fetch_name() yet, so for the moment I commented out the
    x and y axis labels, which is dumb: FIXME.  Once I fix that, put the function call
    into transit_gui.scatterFunc() so that it may be called interactively or via the GUI.

    Arguments:
    control -- Sample to place on the x-axis, it really does not need to be a control.
    experimental -- Sample for the y-axis.

    Keyword arguments:
    control_rep -- Replicate among the x-axis samples to plot.
    experimental_rep -- Replicate among the y-axis samples to plot.
    log_scale -- Do a log1p() on the values if that will make it easier to read.
    """
    X = control[control_rep, :]
    Y = experimental[experimental_rep, :]
    if log_scale:
        X = numpy.log1p(X)
        Y = numpy.log1p(Y)

    plt.plot(X, Y, "bo")
    plt.title('Scatter plot - Reads at TA sites')
    ## plt.xlabel(transit_tools.fetch_name(datasets[0]))
    ## plt.ylabel(transit_tools.fetch_name(datasets[1]))
    plt.show(block = False)
