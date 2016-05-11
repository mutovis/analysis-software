#!/usr/bin/env python3

# written by Grey Christoforo <first name [at] last name [not] net>
# please cite our work if you can!
# DOI: 10.3390/photonics2041101

from batch_iv_analysis_UI import Ui_batch_iv_analysis
from prefs_UI import Ui_prefs

#TODO: make area editable
#TODO: handle area from custom input file

from interpolate import SmoothSpline
#cite:
#References
#----------
#.. [1] A. Savitzky, M. J. E. Golay, Smoothing and Differentiation of
    #Data by Simplified Least Squares Procedures. Analytical
    #Chemistry, 1964, 36 (8), pp 1627-1639.
#.. [2] Numerical Recipes 3rd Edition: The Art of Scientific Computing
    #W.H. Press, S.A. Teukolsky, W.T. Vetterling, B.P. Flannery
    #Cambridge University Press ISBN-13: 9780521880688

from collections import OrderedDict
from io import StringIO
import os, sys, inspect, csv

from PyQt5.QtCore import QSettings, Qt, QSignalMapper, QFileSystemWatcher, QDir, QFileInfo
from PyQt5.QtWidgets import QApplication, QDialog, QMainWindow, QFileDialog, QTableWidgetItem, QCheckBox, QPushButton

import mpmath.libmp
assert mpmath.libmp.BACKEND == 'gmpy'
import numpy as np
import sympy
from numpy import nan
from numpy import inf
from numpy import exp

from scipy.special import lambertw

from scipy import odr
from scipy import interpolate
from scipy import optimize
from scipy.stats.distributions import t #needed for confidence interval calculation
import matplotlib.pyplot as plt
plt.switch_backend("Qt5Agg")
#from uncertainties import ufloat

I0, Iph, Rs, Rsh, n, I, V, Vth, V_I0, I_I0, V_n, I_n = sympy.symbols('I0 Iph Rs Rsh n I V Vth V_I0 I_I0 V_n I_n')

cellTemp = 29 #degC all analysis is done assuming the cell is at 29 degC
T = 273.15 + cellTemp #cell temp in K
K = 1.3806488e-23 #boltzman constant
q = 1.60217657e-19 #electron charge
thermalVoltage = K*T/q #thermal voltage ~26mv

#this stuff is from http://dx.doi.org/10.1016/j.solmat.2003.11.018
#symbolic representation for solar cell equation:
lhs = I
rhs = Iph-((V+I*Rs)/Rsh)-I0*(sympy.exp((V+I*Rs)/(n*Vth))-1)
charEqn = sympy.Eq(lhs,rhs)

#isolate current term in solar cell equation
current = sympy.solve(charEqn,I)

#isolate voltage term in solar cell equation
#voltage = sympy.solve(charEqn,V)

#isolate I0  in solar cell equation
eyeNot = sympy.solve(charEqn,I0)
#isolate n  in solar cell equation
#nidf = sympy.solve(charEqn,n)
#RshEqn = sympy.solve(charEqn,Rsh)
RsEqn = sympy.solve(charEqn,Rs)

#solve for I0 in terms of n:
#I0_in_n = eyeNot[0].subs(V,V_I0).subs(I,I_I0)

#use I0 to find a guess value for n:
#nEqn = sympy.Eq(n,nidf[0].subs(I0,I0_in_n).subs(V,V_n).subs(I,I_n))
#forNguess = sympy.solve(nEqn,n)


#Isc = current[0].subs(V,0)
#Isc_n = sympy.lambdify((I0,Iph,Rs,Rsh,n,Vth),Isc)
#Voc = voltage[0].subs(I,0)
#Voc_n = sympy.lambdify((I0,Iph,Rs,Rsh,n,Vth),Voc)

#numeric substitution for thermalVoltage
current = current[0].subs(Vth,thermalVoltage)

#get symbolic solution for current ready for fast number crunching
current_n = sympy.lambdify((V,I0,Iph,Rs,Rsh,n),current)

# might use this to display data
#def round_to_sigfigs (x,n):
#    return lambda x, n: round(x, -int(floor(log10(x))) + (n - 1))

def odrThing(B,x):
    I0, Iph, Rs, Rsh, n = B
    return np.real((Rs*(I0*Rsh + Iph*Rsh - x) - thermalVoltage*n*(Rs + Rsh)*lambertw(I0*Rs*Rsh*np.exp((Rs*(I0*Rsh + Iph*Rsh - x) + x*(Rs + Rsh))/(thermalVoltage*n*(Rs + Rsh)))/(thermalVoltage*n*(Rs + Rsh))))/(Rs*(Rs + Rsh)))    

# find the sum of the square of errors for a fit to some data
# given the fit function, the fit parameters and the x and y data
def sse(fun,params,x,y):
    return sum([(fun(X, *params)-Y)**2 for X,Y in zip(x,y)])
    
# the 0th branch of the lambertW function
def w(x):
    return np.real_if_close(lambertw(x, k=0, tol=1e-15))

# here's the function we want to fit to
#def optimizeThis (x, I0, Iph, Rs, Rsh, n):
#    return (Rs*(I0*Rsh + Iph*Rsh - x) - thermalVoltage*n*(Rs + Rsh)*w(I0*Rs*Rsh*exp((Rs*(I0*Rsh + Iph*Rsh - x) + x*(Rs + Rsh))/(thermalVoltage*n*(Rs + Rsh)))/(thermalVoltage*n*(Rs + Rsh))))/(Rs*(Rs + Rsh))

# here's the function we want to fit to
# returns current [A] from solar cell circuit
# takes arguments: (x, I0, Iph, Rs, Rsh, n)
# where x is voltage
# also takes keyword arguments for everything except voltage
def optimizeThis (*args, **kwargs):
    if len(args) == 1:
        args=list(args[0])
    else:
        args=list(args)
    
    x = args.pop(0)
    if 'I0' in kwargs:
        I0 = kwargs['I0']
    else:
        I0 = args.pop(0)
        
    if 'Iph' in kwargs:
        Iph = kwargs['Iph']
    else:
        Iph = args.pop(0)
        
    if 'Rs' in kwargs:
        Rs = kwargs['Rs']
    else:
        Rs = args.pop(0)
        
    if 'Rsh' in kwargs:
        Rsh = kwargs['Rsh']
    else:
        Rsh = args.pop(0)
        
    if 'n' in kwargs:
        n = kwargs['n']
    else:
        n = args.pop(0)
    
    return (Rs*(I0*Rsh + Iph*Rsh - x) - thermalVoltage*n*(Rs + Rsh)*w(I0*Rs*Rsh*exp((Rs*(I0*Rsh + Iph*Rsh - x) + x*(Rs + Rsh))/(thermalVoltage*n*(Rs + Rsh)))/(thermalVoltage*n*(Rs + Rsh))))/(Rs*(Rs + Rsh))



#allow current solutoin to operate on vectors of voltages (needed for curve fitting)
def vectorizedCurrent(vVector, I0_n, Iph_n, Rsn_n, Rsh_n, n_n):
    if hasattr(vVector, '__iter__'):
        return [float(sympy.re(current_n(x, I0_n,Iph_n,Rsn_n,Rsh_n,n_n))) for x in vVector]
    else:
        return float(sympy.re(current_n(vVector, I0_n,Iph_n,Rsn_n,Rsh_n,n_n)))
    #TODO: this is VERY bad practice to allow global use of current_n in this function 

#residual function for leastsq fit
#def residual(p, vVector, y, weights):
    #I0_n, Iph_n, Rsn_n, Rsh_n, n_n = p
    #weights = np.asarray(weights)
    #return (optimizeThis(vVector, I0_n,Iph_n,Rsn_n,Rsh_n,n_n) -y)*weights
    ##return ([float(sympy.re(current_n(x, I0_n,Iph_n,Rsn_n,Rsh_n,n_n))) for x in vVector] - y)*weights
    ##TODO: this is VERY bad practice to allow global use of current_n in this function

#residual function for leastsq fit with negative penalty
#def residual2(p, vVector, y, weights):
    #negativePenalty = 2
    ##negativePenalty = 1e-10
    #if np.any(p<0):
        #return negativePenalty * np.linalg.norm(p[p<0]) * residual(p, vVector, y, weights)
    #else:
        #return residual(p, vVector, y, weights)

# tests if string is a number
def isNumber(s):
    try:
        float(s)
    except ValueError:
        return False
    return True

def makeAReallySmartGuess(VV,II):
    #data point selection:
    #lowest voltage (might be same as Isc)
    V_start_n = VV[0]
    I_start_n = II[0]
    
    #highest voltage
    V_end_n = VV[-1]
    I_end_n = II[-1]
    
    #Isc
    iFit = interpolate.interp1d(VV,II)
    V_sc_n = 0
    try:
        I_sc_n = float(iFit(V_sc_n))
    except:
        return([[nan,nan,nan,nan,nan], [nan,nan,nan,nan,nan], nan, "hard fail", 10])
    
    #mpp
    VVcalc = VV-VV[0]
    IIcalc = II-min(II)
    Pvirtual= np.array(VVcalc*IIcalc)
    vMaxIndex = Pvirtual.argmax()
    V_vmpp_n = VV[vMaxIndex]
    I_vmpp_n = II[vMaxIndex]
    
    #Vp: half way in voltage between vMpp and the start of the dataset:
    V_vp_n = (V_vmpp_n-V_start_n)/2 +V_start_n
    try:
        I_vp_n = float(iFit(V_vp_n))
    except:
        return([[nan,nan,nan,nan,nan], [nan,nan,nan,nan,nan], nan, "hard fail", 10])
    
    #Ip: half way in current between vMpp and the end of the dataset:
    I_ip_n = (I_vmpp_n-I_end_n)/2 + I_end_n
    iFit2 = interpolate.interp1d(VV,II-I_ip_n)
    try:
        V_ip_n = optimize.brentq(iFit2, VV[0], VV[-1])
    except:
        return([[nan,nan,nan,nan,nan], [nan,nan,nan,nan,nan], nan, "hard fail", 10])
    
    diaplayAllGuesses = False
    def evaluateGuessPlot(dataX, dataY, myguess):
        myguess = [float(x) for x in myguess]
        print("myguess:")
        print(myguess)
        vv=np.linspace(min(dataX),max(dataX),1000)
        ii=vectorizedCurrent(vv,myguess[0],myguess[1],myguess[2],myguess[3],myguess[4])
        plt.title('Guess and raw data')
        plt.plot(vv,ii)
        plt.scatter(dataX,dataY)
        plt.grid(b=True)
        plt.draw()
        plt.show()
    
    # phase 1 guesses:
    I_L_initial_guess = I_sc_n
    R_sh_initial_guess = 1e6
    
    # compute intellegent guesses for Iph, Rsh by forcing the curve through several data points and numerically solving the resulting system of eqns
    newRhs = rhs - I
    aLine = Rsh*V+Iph-I
    eqnSys1 = aLine.subs([(V,V_start_n),(I,I_start_n)])
    eqnSys2 = aLine.subs([(V,V_vp_n),(I,I_vp_n)])
    
    eqnSys = (eqnSys1,eqnSys2)
    
    try:
        nGuessSln = sympy.nsolve(eqnSys,(Iph,Rsh),(I_L_initial_guess,R_sh_initial_guess),maxsteps=10000)
    except:
        return([[nan,nan,nan,nan,nan], [nan,nan,nan,nan,nan], nan, "hard fail", 10])
    
    I_L_guess = nGuessSln[0]
    R_sh_guess = -1*1/nGuessSln[1]
    R_s_guess = -1*(V_end_n-V_ip_n)/(I_end_n-I_ip_n)
    n_initial_guess = 2 #TODO: maybe a more intelligent guess for n can be found using http://pvcdrom.pveducation.org/CHARACT/IDEALITY.HTM
    I0_initial_guess = eyeNot[0].evalf(subs={Vth:thermalVoltage,Rs:R_s_guess,Rsh:R_sh_guess,Iph:I_L_guess,n:n_initial_guess,I:I_ip_n,V:V_ip_n})                         
    
    initial_guess = [I0_initial_guess, I_L_guess, R_s_guess, R_sh_guess, n_initial_guess]
    if diaplayAllGuesses:
        evaluateGuessPlot(VV, II, initial_guess)
    
    # let's try the fit now, if it works great, we're done, otherwise we can continue
    #try:
        #guess = initial_guess
        #fitParams, fitCovariance, infodict, errmsg, ier = optimize.curve_fit(optimizeThis, VV, II,p0=guess,full_output = True,xtol=1e-13,ftol=1e-15)
        #return(fitParams, fitCovariance, infodict, errmsg, ier)
    #except:
        #pass        
    
    #refine guesses for I0 and Rs by forcing the curve through several data points and numerically solving the resulting system of eqns
    eqnSys1 = newRhs.subs([(Vth,thermalVoltage),(Iph,I_L_guess),(V,V_ip_n),(I,I_ip_n),(n,n_initial_guess),(Rsh,R_sh_guess)])
    eqnSys2 = newRhs.subs([(Vth,thermalVoltage),(Iph,I_L_guess),(V,V_end_n),(I,I_end_n),(n,n_initial_guess),(Rsh,R_sh_guess)])
    eqnSys = (eqnSys1,eqnSys2)
    
    try:
        nGuessSln = sympy.nsolve(eqnSys,(I0,Rs),(I0_initial_guess,R_s_guess),maxsteps=10000)
    except:
        return([[nan,nan,nan,nan,nan], [nan,nan,nan,nan,nan], nan, "hard fail", 10])
    
    I0_guess = nGuessSln[0]
    R_s_guess = nGuessSln[1]
    
    #Rs_initial_guess = RsEqn[0].evalf(subs={I0:I0_initial_guess,Vth:thermalVoltage,Rsh:R_sh_guess,Iph:I_L_guess,n:n_initial_guess,I:I_end_n,V:V_end_n})
    #I0_guess = I0_initial_guess
    #R_s_guess = Rs_initial_guess
    
    guess = [I0_guess, I_L_guess, R_s_guess, R_sh_guess, n_initial_guess]
    
    if diaplayAllGuesses:
        evaluateGuessPlot(VV, II, guess)
    
    #nidf
    
    #give 5x weight to data around mpp
    #nP = II*VV
    #maxIndex = np.argmax(nP)
    #weights = np.ones(len(II))
    #halfRange = (V_ip_n-VV[vMaxIndex])/2
    #upperTarget = VV[vMaxIndex] + halfRange
    #lowerTarget = VV[vMaxIndex] - halfRange
    #lowerTarget = 0
    #upperTarget = V_oc_n
    #lowerI = np.argmin(abs(VV-lowerTarget))
    #upperI = np.argmin(abs(VV-upperTarget))
    #weights[range(lowerI,upperI)] = 3
    #weights[maxnpi] = 10
    #todo: play with setting up "key points"
    
    guess = [float(x) for x in guess]
    #VV = [np.float(x) for x in VV]
    #II = [np.float(x) for x in II]
    
    #odrMod = odr.Model(odrThing)
    #myData = odr.Data(VV,II)
    #myodr = odr.ODR(myData, odrMod, beta0=guess,maxit=5000,sstol=1e-20,partol=1e-20)#
    #myoutput = myodr.run()
    #myoutput.pprint()
    #see http://docs.scipy.org/doc/external/odrpack_guide.pdf
    guess = {'I0':guess[0], 'Iph':guess[1], 'Rs':guess[2], 'Rsh':guess[3], 'n':guess[4]}
    return guess

def doTheFit(VV,II,guess,bounds):
    
    # do a constrained fit unless all the bounds are inf (or -inf)
    if sum(sum([np.isinf(value) for key,value in bounds.items()])) == 10:
        constrainedFit = False
    else:
        constrainedFit = True
        
    if constrainedFit:
        # handle the case when the user sets lower bound=upper bound
        # (take that variable out of the optimization)
        myKwargs = {}
        finalFitValues = {}
        finalSigmaValues = {}
        curve_fit_guess = []
        curve_fit_bounds=([],[])
        paramNames = [] # need this to keep track of where each parameter is
        if bounds['I0'][0] == bounds['I0'][1]:
            myKwargs['I0'] = bounds['I0'][0]
            finalFitValues['I0'] = myKwargs['I0']
            finalSigmaValues['I0'] = 0
        else:
            curve_fit_guess.append(guess['I0'])
            curve_fit_bounds[0].append(bounds['I0'][0])
            curve_fit_bounds[1].append(bounds['I0'][1])
            paramNames.append("I0")
        if bounds['Iph'][0] == bounds['Iph'][1]:
            myKwargs['Iph'] = bounds['Iph'][0]
            finalFitValues['Iph'] = myKwargs['Iph']
            finalSigmaValues['Iph'] = 0
        else:
            curve_fit_guess.append(guess['Iph'])
            curve_fit_bounds[0].append(bounds['Iph'][0])
            curve_fit_bounds[1].append(bounds['Iph'][1])
            paramNames.append("Iph")
        if bounds['Rs'][0] == bounds['Rs'][1]:
            myKwargs['Rs'] = bounds['Rs'][0]
            finalFitValues['Rs'] = myKwargs['Rs']
            finalSigmaValues['Rs'] = 0
        else:
            curve_fit_guess.append(guess['Rs'])
            curve_fit_bounds[0].append(bounds['Rs'][0])
            curve_fit_bounds[1].append(bounds['Rs'][1])
            paramNames.append("Rs")
        if bounds['Rsh'][0] == bounds['Rsh'][1]:
            myKwargs['Rsh'] = bounds['Rsh'][0]
            finalFitValues['Rsh'] = myKwargs['Rsh']
            finalSigmaValues['Rsh'] = 0
        else:
            curve_fit_guess.append(guess['Rsh'])
            curve_fit_bounds[0].append(bounds['Rsh'][0])
            curve_fit_bounds[1].append(bounds['Rsh'][1])
            paramNames.append("Rsh")
        if bounds['n'][0] == bounds['n'][1]:
            myKwargs['n'] = bounds['n'][0]
            finalFitValues['n'] = myKwargs['n']
            finalSigmaValues['n'] = 0
        else:
            curve_fit_guess.append(guess['n'])
            curve_fit_bounds[0].append(bounds['n'][0])
            curve_fit_bounds[1].append(bounds['n'][1])
            paramNames.append("n")

        # recondition the arguments of the function we're trying to fit in the case
        # when the user has stipulated a fit parameter (by setting upper bound=lower bound)
        optimizeThat = lambda *myArgs:optimizeThis(myArgs,**myKwargs)
            
        redirected_output = sys.stdout = StringIO()
        redirected_error = sys.stderr = StringIO()
        try:
            fitParams, fitCovariance = optimize.curve_fit(optimizeThat, VV, II, p0=curve_fit_guess, bounds=curve_fit_bounds, method="trf", x_scale="jac", jac ='cs', verbose=1, max_nfev=1200000)
        except:
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__                    
            return([[nan,nan,nan,nan,nan], [nan,nan,nan,nan,nan], nan, "Unexpected Error: " + str(sys.exc_info()[1]) , 10])
        out = redirected_output.getvalue()
        err = redirected_error.getvalue()                
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        infodict = out
        errmsg = out.splitlines()[0]
        ier = 0
        
        sigmas = np.sqrt(np.diag(fitCovariance))
        
        # need this in case we fit less than 5 parameters
        for sigma,paramValue,paramName in zip(sigmas,fitParams,paramNames):
            finalFitValues[paramName] = paramValue
            finalSigmaValues[paramName] = sigma
        fitParams = [finalFitValues['I0'],finalFitValues['Iph'],finalFitValues['Rs'],finalFitValues['Rsh'],finalFitValues['n']]
        sigmas = [finalSigmaValues['I0'],finalSigmaValues['Iph'],finalSigmaValues['Rs'],finalSigmaValues['Rsh'],finalSigmaValues['n']]
    else: # unconstrained "l-m" fit
        curve_fit_guess = (guess['I0'],guess['Iph'],guess['Rs'],guess['Rsh'],guess['n'])
        try:
            fitParams, fitCovariance, infodict, errmsg, ier = optimize.curve_fit(optimizeThis, VV, II, p0=curve_fit_guess, method="lm", full_output=True)
        except:
            return([[nan,nan,nan,nan,nan], [nan,nan,nan,nan,nan], nan, "Unexpected Error: " + str(sys.exc_info()[1]) , 10])
        sigmas = np.sqrt(np.diag(fitCovariance))
    return(fitParams, sigmas, infodict, errmsg, ier)

def analyzeGoodness(VV,II,fitParams,guess,ier,errmsg,infodict):
    SSE = sse(optimizeThis, fitParams, VV, II)
    print("Sum of square of errors:")
    print(SSE)
    print("fit:")
    print(fitParams)                
    print("guess:")
    print(guess)
    print("ier:")
    print(ier)
    print("errmsg:")
    print(errmsg)
    print("infodict:")
    print(infodict)
    
    vv=np.linspace(VV[0],VV[-1],1000)
    ii=vectorizedCurrent(vv,guess[0],guess[1],guess[2],guess[3],guess[4])
    ii2=vectorizedCurrent(vv,fitParams[0],fitParams[1],fitParams[2],fitParams[3],fitParams[4])
    plt.title('Fit analysis')
    p1, = plt.plot(vv,ii, label='Guess',ls='--')
    p2, = plt.plot(vv,ii2, label='Fit')
    p3, = plt.plot(VV,II,ls='None',marker='o', label='Data')
    #p4, = plt.plot(VV[range(lowerI,upperI)],II[range(lowerI,upperI)],ls="None",marker='o', label='5x Weight Data')
    ax = plt.gca()
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc=3)
    plt.grid(b=True)
    plt.draw()
    plt.show()    

class col:
    header = ''
    position = 0
    tooltip = ''

class PrefsWindow(QDialog):
    def __init__(self,parent,settings,bounds):
        QDialog.__init__(self,parent)
        self.ui = Ui_prefs()
        self.ui.setupUi(self)
        self.setModal(True)
        self.setSizeGripEnabled(False)
        self.settings=settings
        self.bounds=bounds
        #self.1(Qt.FramelessWindowHint)
    
    def accept(self):
        self.bounds["I0"]=[float(self.ui.I0_lb.text()),float(self.ui.I0_ub.text())]
        self.bounds["Iph"]=[float(self.ui.Iph_lb.text()),float(self.ui.Iph_ub.text())]
        self.bounds["Rs"]=[float(self.ui.Rs_lb.text()),float(self.ui.Rs_ub.text())]
        self.bounds["Rsh"]=[float(self.ui.Rsh_lb.text()),float(self.ui.Rsh_ub.text())]        
        self.bounds["n"]=[float(self.ui.n_lb.text()),float(self.ui.n_ub.text())]
        self.settings.setValue('I0_lb',self.ui.I0_lb.text())
        self.settings.setValue('I0_ub',self.ui.I0_ub.text())        
        self.settings.setValue('Iph_lb',self.ui.Iph_lb.text())
        self.settings.setValue('Iph_ub',self.ui.Iph_ub.text())        
        self.settings.setValue('Rs_lb',self.ui.Rs_lb.text())
        self.settings.setValue('Rs_ub',self.ui.Rs_ub.text())        
        self.settings.setValue('Rsh_lb',self.ui.Rsh_lb.text())
        self.settings.setValue('Rsh_ub',self.ui.Rsh_ub.text())        
        self.settings.setValue('n_lb',self.ui.n_lb.text())
        self.settings.setValue('n_ub',self.ui.n_ub.text())
        self.done(0)
    def reject(self):
        print("rejected")
        self.done(-1)

class MainWindow(QMainWindow):
    workingDirectory = ''
    fileNames = []
    supportedExtensions = ['*.csv','*.tsv','*.txt','*.liv1','*.liv2']
    bounds ={}
    bounds['I0'] = [0, inf] 
    bounds['Iph'] = [0, inf]
    bounds['Rs'] = [0, inf]
    bounds['Rsh'] = [0, inf]
    bounds['n'] = [0, inf]
    def __init__(self):
        QMainWindow.__init__(self)

        self.settings = QSettings("greyltc", "batch-iv-analysis")

        self.rows = 0 #keep track of how many rows there are in the table

        self.cols = OrderedDict()

        thisKey = 'plotBtn'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'Draw Plot'
        self.cols[thisKey].tooltip = 'Click this button to draw a plot for that row'        

        thisKey = 'exportBtn'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'Export'
        self.cols[thisKey].tooltip = 'Click this button to export\ninterpolated data points from fits'        

        thisKey = 'file'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'File'
        self.cols[thisKey].tooltip = 'File name\nHover to see header from data file'

        thisKey = 'SSE'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'SSE\n[mA^2]'
        self.cols[thisKey].tooltip = 'Sum of the square of the errors between the data points and the fit to the char. eqn. (a measure of fit goodness)'

        thisKey = 'pce'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'PCE\n[%]'
        self.cols[thisKey].tooltip = 'Power conversion efficiency as found from spline fit\nHover for value from characteristic equation fit'

        thisKey = 'pmax'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'P_max\n[mW/cm^2]'
        self.cols[thisKey].tooltip = 'Maximum power density as found from spline fit\nHover for value from characteristic equation fit'

        thisKey = 'jsc'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'J_sc\n[mA/cm^2]'
        self.cols[thisKey].tooltip = 'Short-circuit current density as found from spline spline fit V=0 crossing\nHover for value from characteristic equation fit V=0 crossing'

        thisKey = 'voc'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'V_oc\n[mV]'
        self.cols[thisKey].tooltip = 'Open-circuit voltage as found from spline fit I=0 crossing\nHover for value from characteristic equation fit I=0 crossing'

        thisKey = 'ff'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'FF'
        self.cols[thisKey].tooltip = 'Fill factor as found from spline fit\nHover for value from characteristic equation fit'

        thisKey = 'rs'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'R_s\n[ohm*cm^2]'
        self.cols[thisKey].tooltip = 'Specific series resistance as found from characteristic equation fit\nHover for 95% confidence interval'

        thisKey = 'rsh'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'R_sh\n[ohm*cm^2]'
        self.cols[thisKey].tooltip = 'Specific shunt resistance as found from characteristic equation fit\nHover for 95% confidence interval'

        thisKey = 'jph'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'J_ph\n[mA/cm^2]'
        self.cols[thisKey].tooltip = 'Photogenerated current density as found from characteristic equation fit\nHover for 95% confidence interval'

        thisKey = 'j0'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'J_0\n[nA/cm^2]'
        self.cols[thisKey].tooltip = 'Reverse saturation current density as found from characteristic equation fit\nHover for 95% confidence interval'

        thisKey = 'n'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'n'
        self.cols[thisKey].tooltip = 'Diode ideality factor as found from characteristic equation fit\nHover for 95% confidence interval'

        thisKey = 'Vmax'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'V_max\n[mV]'
        self.cols[thisKey].tooltip = 'Voltage at maximum power point as found from spline fit\nHover for value from characteristic equation fit'

        thisKey = 'area'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'Area\n[cm^2]'
        self.cols[thisKey].tooltip = 'Device area'

        thisKey = 'pmax2'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'P_max\n[mW]'
        self.cols[thisKey].tooltip = 'Maximum power as found from spline fit\nHover for value from characteristic equation fit'

        thisKey = 'isc'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'I_sc\n[mA]'
        self.cols[thisKey].tooltip = 'Short-circuit current as found from spline V=0 crossing\nHover for value from characteristic equation V=0 crossing'

        thisKey = 'iph'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'I_ph\n[mA]'
        self.cols[thisKey].tooltip = 'Photogenerated current as found from characteristic equation fit\nHover for 95% confidence interval'

        thisKey = 'i0'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'I_0\n[nA]'
        self.cols[thisKey].tooltip = 'Reverse saturation current as found from characteristic equation fit\nHover for 95% confidence interval'

        thisKey = 'rs2'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'R_s\n[ohm]'
        self.cols[thisKey].tooltip = 'Series resistance as found from characteristic equation fit\nHover for 95% confidence interval'

        thisKey = 'rsh2'
        self.cols[thisKey] = col()
        self.cols[thisKey].header = 'R_sh\n[ohm]'
        self.cols[thisKey].tooltip = 'Shunt resistance as found from characteristic equation fit\nHover for 95% confidence interval'		


        #how long status messages show for
        self.messageDuration = 2500#ms

        # Set up the user interface from Designer.
        self.ui = Ui_batch_iv_analysis()
        self.ui.setupUi(self)
        
        # put the prefs window on the central widget
        self.prefs = PrefsWindow(self.ui.centralwidget,self.settings,self.bounds)
        
        # set defaults
        I0_lb_string = "0" if not self.settings.contains('I0_lb') else self.settings.value('I0_lb')
        Iph_lb_string = "0" if not self.settings.contains('Iph_lb') else self.settings.value('Iph_lb')
        Rs_lb_string = "0" if not self.settings.contains('Rs_lb') else self.settings.value('Rs_lb')
        Rsh_lb_string = "0" if not self.settings.contains('Rsh_lb') else self.settings.value('Rsh_lb')
        n_lb_string = "0" if not self.settings.contains('n_lb') else self.settings.value('n_lb')
    
        I0_ub_string = "inf" if not self.settings.contains('I0_ub') else self.settings.value('I0_ub')
        Iph_ub_string = "inf" if not self.settings.contains('Iph_ub') else self.settings.value('Iph_ub')
        Rs_ub_string = "inf" if not self.settings.contains('Rs_ub') else self.settings.value('Rs_ub')
        Rsh_ub_string = "inf" if not self.settings.contains('Rsh_ub') else self.settings.value('Rsh_ub')
        n_ub_string = "inf" if not self.settings.contains('n_ub') else self.settings.value('n_ub')        
        
        self.bounds['I0'][0] = np.float(I0_lb_string)
        self.bounds['Iph'][0] = np.float(Iph_lb_string)
        self.bounds['Rs'][0] = np.float(Rs_lb_string)
        self.bounds['Rsh'][0] = np.float(Rsh_lb_string)
        self.bounds['n'][0] = np.float(n_lb_string)
        
        self.bounds['I0'][1] = np.float(I0_ub_string)
        self.bounds['Iph'][1] = np.float(Iph_ub_string)
        self.bounds['Rs'][1] = np.float(Rs_ub_string)
        self.bounds['Rsh'][1] = np.float(Rsh_ub_string)
        self.bounds['n'][1] = np.float(n_ub_string)
        
        self.prefs.ui.I0_lb.setText(I0_lb_string)
        self.prefs.ui.Iph_lb.setText(Iph_lb_string)
        self.prefs.ui.Rs_lb.setText(Rs_lb_string)
        self.prefs.ui.Rsh_lb.setText(Rsh_lb_string)
        self.prefs.ui.n_lb.setText(n_lb_string)
        
        self.prefs.ui.I0_ub.setText(I0_ub_string)
        self.prefs.ui.Iph_ub.setText(Iph_ub_string)
        self.prefs.ui.Rs_ub.setText(Rs_ub_string)
        self.prefs.ui.Rsh_ub.setText(Rsh_ub_string)
        self.prefs.ui.n_ub.setText(n_ub_string)

        #insert cols
        for item in self.cols:
            blankItem = QTableWidgetItem()
            thisCol = list(self.cols.keys()).index(item)
            self.ui.tableWidget.insertColumn(thisCol)
            blankItem.setToolTip(self.cols[item].tooltip)
            blankItem.setText(self.cols[item].header)
            self.ui.tableWidget.setHorizontalHeaderItem(thisCol,blankItem)

        #file system watcher
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(self.handleWatchUpdate)

        #connect signals generated by gui elements to proper functions 
        self.ui.actionOpen.triggered.connect(self.openCall)
        self.ui.actionEnable_Watching.triggered.connect(self.watchCall)
        self.ui.actionSave.triggered.connect(self.handleSave)
        self.ui.actionWatch_2.triggered.connect(self.handleWatchAction)
        self.ui.actionFit_Constraints.triggered.connect(self.openFitConstraintDialog)
        self.ui.statusbar.messageChanged.connect(self.statusChanged)

        self.ui.actionClear_Table.triggered.connect(self.clearTableCall)

    def exportInterp(self,row):
        thisGraphData = self.ui.tableWidget.item(row,list(self.cols.keys()).index('plotBtn')).data(Qt.UserRole)
        fitX = thisGraphData["fitX"]
        modelY = thisGraphData["modelY"]
        splineY = thisGraphData["splineY"]
        a = np.asarray([fitX, modelY, splineY])
        a = np.transpose(a)
        destinationFolder = os.path.join(self.workingDirectory,'exports')
        QDestinationFolder = QDir(destinationFolder)
        if not QDestinationFolder.exists():
            QDir().mkdir(destinationFolder)
        saveFile = os.path.join(destinationFolder,str(self.ui.tableWidget.item(row,list(self.cols.keys()).index('file')).text())+'.csv')
        header = 'Voltage [V],CharEqn Current [mA/cm^2],Spline Current [mA/cm^2]'
        try:
            np.savetxt(saveFile, a, delimiter=",",header=header)
            self.goodMessage()
            self.ui.statusbar.showMessage("Exported " + saveFile,5000)
        except:
            self.badMessage()
            self.ui.statusbar.showMessage("Could not export " + saveFile,self.messageDuration)

    def handleButton(self):
        btn = self.sender()
        #kinda hacky:
        row = self.ui.tableWidget.indexAt(btn.pos()).row()
        col = self.ui.tableWidget.indexAt(btn.pos()).column()
        if col == 0:
            self.rowGraph(row)
        if col == 1:
            self.exportInterp(row)


    def rowGraph(self,row):
        thisGraphData = self.ui.tableWidget.item(row,list(self.cols.keys()).index('plotBtn')).data(Qt.UserRole)
        filename = str(self.ui.tableWidget.item(row,list(self.cols.keys()).index('file')).text())

        v = thisGraphData["v"]
        i = thisGraphData["i"]
        if not thisGraphData["vsTime"]:
            plt.plot(v, i, c='b', marker='o', ls="None",label='I-V Data')
            plt.scatter(thisGraphData["Vmax"], thisGraphData["Imax"], c='g',marker='x',s=100)
            plt.scatter(thisGraphData["Voc"], 0, c='g',marker='x',s=100)
            plt.scatter(0, thisGraphData["Isc"], c='g',marker='x',s=100)
            fitX = thisGraphData["fitX"]
            modelY = thisGraphData["modelY"]
            splineY = thisGraphData["splineY"]
            if not np.isnan(modelY[0]):
                plt.plot(fitX, modelY,c='k', label='CharEqn Best Fit')
            plt.plot(fitX, splineY,c='g', label='Spline Fit')
            plt.autoscale(axis='x', tight=True)
            plt.grid(b=True)
            ax = plt.gca()
            handles, labels = ax.get_legend_handles_labels()
            ax.legend(handles, labels, loc=3)

            plt.annotate(
                thisGraphData["Voc"].__format__('0.4f')+ ' V', 
                xy = (thisGraphData["Voc"], 0), xytext = (40, 20),
                textcoords = 'offset points', ha = 'right', va = 'bottom',
                bbox = dict(boxstyle = 'round,pad=0.5', fc = 'yellow', alpha = 0.5),
                arrowprops = dict(arrowstyle = '->', connectionstyle = 'arc3,rad=0'))

            plt.annotate(
                float(thisGraphData["Isc"]).__format__('0.4f') + ' mA/cm^2', 
                xy = (0,thisGraphData["Isc"]), xytext = (40, 20),
                textcoords = 'offset points', ha = 'right', va = 'bottom',
                bbox = dict(boxstyle = 'round,pad=0.5', fc = 'yellow', alpha = 0.5),
                arrowprops = dict(arrowstyle = '->', connectionstyle = 'arc3,rad=0'))

            plt.annotate(
                float(thisGraphData["Imax"]*thisGraphData["Vmax"]).__format__('0.4f') + '% @(' + float(thisGraphData["Vmax"]).__format__('0.4f') + ',' + float(thisGraphData["Imax"]).__format__('0.4f') + ')', 
                xy = (thisGraphData["Vmax"],thisGraphData["Imax"]), xytext = (80, 40),
                textcoords = 'offset points', ha = 'right', va = 'bottom',
                bbox = dict(boxstyle = 'round,pad=0.5', fc = 'yellow', alpha = 0.5),
                arrowprops = dict(arrowstyle = '->', connectionstyle = 'arc3,rad=0'))		

            plt.ylabel('Current [mA/cm^2]')
            plt.xlabel('Voltage [V]')
        else: #vs time
            time = thisGraphData["time"]

            fig, ax1 = plt.subplots()
            ax1.plot(time, v, 'b-',label='Voltage [V]')
            ax1.set_xlabel('Time [s]')
            # Make the y-axis label and tick labels match the line color.
            ax1.set_ylabel('Voltage [V]', color='b')
            for tl in ax1.get_yticklabels():
                tl.set_color('b')
            #fdsf
            ax2 = ax1.twinx()
            ax2.plot(time, i, 'r-')
            ax2.set_ylabel('Current [mA/cm^2]', color='r')
            for tl in ax2.get_yticklabels():
                tl.set_color('r')            

        plt.title(filename)
        plt.draw()
        plt.show()

    def handleSave(self):
        if self.settings.contains('lastFolder'):
            saveDir = self.settings.value('lastFolder')
        else:
            saveDir = '.'
        path = QFileDialog.getSaveFileName(self, caption='Set Export File', directory=saveDir)
        if not str(path[0]) == '':
            with open(path[0], 'w') as stream:
                writer = csv.writer(stream)
                rowdata = []
                for column in range(self.ui.tableWidget.columnCount()):
                    item = self.ui.tableWidget.horizontalHeaderItem(column)
                    if item is not None:
                        rowdata.append(str(item.text()).replace('\n',' '))
                    else:
                        rowdata.append(b'')
                writer.writerow(rowdata[2:])                
                for row in range(self.ui.tableWidget.rowCount()):
                    rowdata = []
                    for column in range(self.ui.tableWidget.columnCount()):
                        item = self.ui.tableWidget.item(row, column)
                        if item is not None:
                            rowdata.append(str(item.text()))
                        else:
                            rowdata.append('')
                    writer.writerow(rowdata[2:])
                stream.close()

    def clearTableCall(self):
        for ii in range(self.rows):
            self.ui.tableWidget.removeRow(0)
        self.ui.tableWidget.clearContents()
        self.rows = 0
        self.fileNames = []

    def processFile(self,fullPath):
        fileName, fileExtension = os.path.splitext(fullPath)
        fileName = os.path.basename(fullPath)
        self.fileNames.append(fileName)
        isSnaithFile = False
        if fileExtension == '.csv':
            delimiter = ','
        elif fileExtension == '.tsv':
            delimiter = '\t'        
        else:
            delimiter = None

        self.ui.statusbar.showMessage("processing: "+ fileName,2500)

        #wait here for the file to be completely written to disk and closed before trying to read it
        fi = QFileInfo(fullPath)
        while (not fi.isWritable()):
            time.sleep(0.001)
            fi.refresh()

        fp = open(fullPath, mode='r')
        fileBuffer = fp.read()
        fp.close()
        if len(fileBuffer) < 25:
            self.badMessage()
            self.ui.statusbar.showMessage('Could not read' + fileName +'. This file is less than 25 characters long.',2500)
            return
        first10 = fileBuffer[0:10]
        last25 = fileBuffer[-26:-1]

        isMcFile = False #true if this is a McGehee iv file format
        isSnaithFile = False # true if this is a Snaith iv file format
        #mcFile test:
        if (not first10.__contains__('#')) and (first10.__contains__('/')) and (first10.__contains__('\t')):#the first line is not a comment
            nMcHeaderLines = 25 #number of header lines in mcgehee IV file format
            #the first 8 chars do not contain comment symbol and do contain / and a tab, it's safe to assume mcgehee iv file format
            isMcFile = True
            #comment out the first 25 rows here
            fileBuffer = '#'+fileBuffer
            fileBuffer = fileBuffer.replace('\n', '\n#',nMcHeaderLines-1)
        #snaithFile test:
        elif last25.__contains__('suns:\t'):
            nSnaithFooterLines = 11 #number of footer lines in snaith IV file format
            isSnaithFile = True
            delimiter = '\t'
            if fileExtension == '.liv1':
                snaithReverse = True
            if fileExtension == '.liv2':
                snaithReverse = False
            fileBuffer = fileBuffer[::-1] # reverse the buffer
            fileBuffer = fileBuffer.replace('\n', '#\n',nSnaithFooterLines+1) # comment out the footer lines
            fileBuffer = fileBuffer[::-1] # un-reverse the buffer
            fileBuffer = fileBuffer[:-3] # remove the last (extra) '\r\n#'

        splitBuffer = fileBuffer.splitlines(True)

        suns = 1
        area = 1 # in cm^2
        noArea = True
        noIntensity = True
        vsTime = False #this is not an i,v vs t data file
        #extract comments lines and search for area and intensity
        comments = []
        for line in splitBuffer:
            if line.startswith('#'):
                comments.append(line)
                if line.__contains__('Area'):
                    numbersHere = [float(s) for s in line.split() if isNumber(s)]
                    if len(numbersHere) is 1:
                        area = numbersHere[0]
                        noArea = False
                elif line.__contains__('I&V vs t'):
                    if float(line.split(' ')[5]) == 1:
                        vsTime = True
                elif line.__contains__('Number of suns:'):
                    numbersHere = [float(s) for s in line.split() if isNumber(s)]
                    if len(numbersHere) is 1:
                        suns = numbersHere[0]
                        noIntensity = False                

        outputScaleFactor = np.array(1000/area) #for converstion to [mA/cm^2]

        c = StringIO(fileBuffer) # makes string look like a file 

        #read in data
        try:
            data = np.loadtxt(c,delimiter=delimiter)
        except:
            self.badMessage()
            self.ui.statusbar.showMessage('Could not read' + fileName +'. Prepend # to all non-data lines and try again',2500)
            return
        VV = data[:,0]
        II = data[:,1]
        if vsTime:
            time = data[:,2]

        if isMcFile or isSnaithFile: #convert to amps
            II = II/1000*area

        if not vsTime:
            #sort data by ascending voltage
            newOrder = VV.argsort()
            VV=VV[newOrder]
            II=II[newOrder]
            #remove duplicate voltage entries
            VV, indices = np.unique(VV, return_index =True)
            II = II[indices]
        else:
            #sort data by ascending time
            newOrder = time.argsort()
            VV=VV[newOrder]
            II=II[newOrder]
            time=time[newOrder]
            time=time-time[0]#start time at t=0

        #catch and fix flipped current sign
        #The philosoply in use here is that energy producers have positive current defined as flowing out of the positive terminal
        if II[0] < II[-1]:
            II = II * -1

        indexInQuad1 = np.logical_and(VV>0,II>0)
        if any(indexInQuad1): #enters statement if there is at least one datapoint in quadrant 1
            isDarkCurve = False
        else:
            self.ui.statusbar.showMessage("Dark curve detected",500)
            isDarkCurve = True

        #put items in table
        self.ui.tableWidget.insertRow(self.rows)
        for ii in range(len(self.cols)):
            self.ui.tableWidget.setItem(self.rows,ii,QTableWidgetItem())        

        if not vsTime:
            
            # set bounds on the fit variables
            # if upper=lower bound, then that variable will be taken out of the optimization
            #bounds ={}
            #bounds['I0'] = [0, inf] 
            #bounds['Iph'] = [0, inf]
            #bounds['Rs'] = [0, inf]
            #bounds['Rsh'] = [0, inf]
            #bounds['n'] = [0, inf]
            localBounds = self.bounds
 
            # scale the current up so that the curve fit algorithm doesn't run into machine precision
            currentScaleFactor = 1e3 
            II = II*currentScaleFactor
            localBounds['I0'] = [x*currentScaleFactor for x in localBounds['I0']]
            localBounds['Iph'] = [x*currentScaleFactor for x in localBounds['Iph']]
            localBounds['Rs'] = [x/currentScaleFactor for x in localBounds['Rs']]
            localBounds['Rsh'] = [x/currentScaleFactor for x in localBounds['Rsh']]
            
            # take a guess at what the fit parameters will be
            guess = makeAReallySmartGuess(VV,II)
            
            # let's make sure we're not guessing outside the bounds
            if guess['I0'] < localBounds['I0'][0]:
                guess['I0'] = localBounds['I0'][0]
            elif guess['I0'] > localBounds['I0'][1]:
                guess['I0'] = localBounds['I0'][1]
            
            if guess['Iph'] < localBounds['Iph'][0]:
                guess['Iph'] = localBounds['Iph'][0]
            elif guess['Iph'] > localBounds['Iph'][1]:
                guess['Iph'] = localBounds['Iph'][1]
            
            if guess['Rs'] < localBounds['Rs'][0]:
                guess['Rs'] = localBounds['Rs'][0]
            elif guess['Rs'] > localBounds['Rs'][1]:
                guess['Rs'] = localBounds['Rs'][1]
            
            if guess['Rsh'] < localBounds['Rsh'][0]:
                guess['Rsh'] = localBounds['Rsh'][0]
            elif guess['Rsh'] > localBounds['Rsh'][1]:
                guess['Rsh'] = localBounds['Rsh'][1]
            
            if guess['n'] < localBounds['n'][0]:
                guess['n'] = localBounds['n'][0]
            elif guess['n'] > localBounds['n'][1]:
                guess['n'] = localBounds['n'][1]

            fitParams, sigmas, infodict, errmsg, ier = doTheFit(VV,II,guess,localBounds)
            
            # now unscale everything
            II = II/currentScaleFactor
            fitParams[0] = fitParams[0]/currentScaleFactor
            fitParams[1] = fitParams[1]/currentScaleFactor
            fitParams[2] = fitParams[2]*currentScaleFactor
            fitParams[3] = fitParams[3]*currentScaleFactor
            guess['I0'] = guess['I0']/currentScaleFactor
            guess['Iph'] = guess['Iph']/currentScaleFactor
            guess['Rs'] = guess['Rs']*currentScaleFactor
            guess['Rsh'] = guess['Rsh']*currentScaleFactor
            sigmas[0] = sigmas[0]/currentScaleFactor
            sigmas[1] = sigmas[1]/currentScaleFactor
            sigmas[2] = sigmas[2]*currentScaleFactor
            sigmas[3] = sigmas[3]*currentScaleFactor
            
            # this will produce an evaluation of how well the fit worked
            #analyzeGoodness(VV,II,fitParams,guess,ier,errmsg,infodict)
            
            SSE = sse(optimizeThis, fitParams, VV, II) # sum of square of differences between data and fit [A^2]

            if ier < 5: # no error
                self.goodMessage()
                self.ui.statusbar.showMessage("Good fit because: " + errmsg,2500) #print the fit message
            else:
                self.badMessage()

            I0_fit = fitParams[0]
            Iph_fit = fitParams[1]
            Rs_fit = fitParams[2]
            Rsh_fit = fitParams[3]
            n_fit = fitParams[4]

            #0 -> LS-straight line
            #1 -> cubic spline interpolant (thr)
            smoothingParameter = 1-2e-6
            #iFitSpline = interpolate.UnivariateSpline(VV, II, s=99)
            iFitSpline = SmoothSpline(VV, II, p=smoothingParameter)

            def cellModel(voltageIn):
                #voltageIn = np.array(voltageIn)
                return vectorizedCurrent(voltageIn, I0_fit, Iph_fit, Rs_fit, Rsh_fit, n_fit)

            def invCellPowerSpline(voltageIn):
                if voltageIn < 0:
                    return 0
                else:
                    return -1*voltageIn*iFitSpline(voltageIn)

            def invCellPowerModel(voltageIn):
                if voltageIn < 0:
                    return 0
                else:
                    return -1*voltageIn*cellModel(voltageIn)

            if not isDarkCurve:
                VVq1 = VV[indexInQuad1]
                IIq1 = II[indexInQuad1]
                vMaxGuess = VVq1[np.array(VVq1*IIq1).argmax()]
                powerSearchResults = optimize.minimize(invCellPowerSpline,vMaxGuess)
                #catch a failed max power search:
                if not powerSearchResults.status == 0:
                    print("power search exit code = " + str(powerSearchResults.status))
                    print(powerSearchResults.message)
                    vMax = nan
                    iMax = nan
                    pMax = nan
                else:
                    vMax = powerSearchResults.x[0]
                    iMax = iFitSpline([vMax])[0]
                    pMax = vMax*iMax                

                #only do this stuff if the char eqn fit was good
                if ier < 5:
                    powerSearchResults_charEqn = optimize.minimize(invCellPowerModel,vMaxGuess)
                    #catch a failed max power search:
                    if not powerSearchResults_charEqn.status == 0:
                        print("power search exit code = " + str(powerSearchResults_charEqn.status))
                        print(powerSearchResults_charEqn.message)
                        vMax_charEqn = nan
                    else:
                        vMax_charEqn = powerSearchResults_charEqn.x[0]
                    #dude
                    try:
                        Voc_nn_charEqn=optimize.brentq(cellModel, VV[0], VV[-1])
                    except:
                        Voc_nn_charEqn = nan
                else:
                    Voc_nn_charEqn = nan
                    vMax_charEqn = nan


                try:
                    Voc_nn = optimize.brentq(iFitSpline, VV[0], VV[-1])
                except:
                    Voc_nn = nan

            else:
                Voc_nn = nan
                vMax = nan
                iMax = nan
                pMax = nan
                Voc_nn_charEqn = nan
                vMax_charEqn = nan
                iMax_charEqn = nan
                pMax_charEqn = nan



            if ier < 5:
                dontFindBounds = False
                iMax_charEqn = cellModel([vMax_charEqn])[0]
                pMax_charEqn = vMax_charEqn*iMax_charEqn
                Isc_nn_charEqn = cellModel(0)
                FF_charEqn = pMax_charEqn/(Voc_nn_charEqn*Isc_nn_charEqn)
            else:
                dontFindBounds = True
                iMax_charEqn = nan
                pMax_charEqn = nan
                Isc_nn_charEqn = nan
                FF_charEqn = nan

            #there is a maddening bug in SmoothingSpline: it can't evaluate 0 alone, so I have to do this:
            try:
                Isc_nn = iFitSpline([0,1e-55])[0]
            except:
                Isc_nn = nan

            FF = pMax/(Voc_nn*Isc_nn)

            if (ier != 7) and (ier != 6) and (not dontFindBounds):
                #error estimation:
                alpha = 0.05 # 95% confidence interval = 100*(1-alpha)

                nn = len(VV)    # number of data points
                p = len(fitParams) # number of parameters

                dof = max(0, nn - p) # number of degrees of freedom

                # student-t value for the dof and confidence level
                tval = t.ppf(1.0-alpha/2., dof) 

                lowers = []
                uppers = []
                #calculate 95% confidence interval
                for a, p, sigma in zip(list(range(nn)), fitParams, sigmas):
                    lower = p - sigma*tval
                    upper = p + sigma*tval
                    lowers.append(lower)
                    uppers.append(upper)

            else:
                uppers = [nan,nan,nan,nan,nan]
                lowers = [nan,nan,nan,nan,nan]

            plotPoints = 1000
            fitX = np.linspace(VV[0],VV[-1],plotPoints)

            if ier < 5:
                modelY = cellModel(fitX)*outputScaleFactor
            else:
                modelY = np.empty(plotPoints)*nan
            splineY = iFitSpline(fitX)*outputScaleFactor
            graphData = {'vsTime':vsTime,'origRow':self.rows,'fitX':fitX,'modelY':modelY,'splineY':splineY,'i':II*outputScaleFactor,'v':VV,'Voc':Voc_nn,'Isc':Isc_nn*outputScaleFactor,'Vmax':vMax,'Imax':iMax*outputScaleFactor}		

            #export button
            exportBtn = QPushButton(self.ui.tableWidget)
            exportBtn.setText('Export')
            exportBtn.clicked.connect(self.handleButton)
            self.ui.tableWidget.setCellWidget(self.rows,list(self.cols.keys()).index('exportBtn'), exportBtn)
            
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('SSE')).setData(Qt.DisplayRole,float(round(SSE*1e6,5)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('pce')).setData(Qt.DisplayRole,float(round(pMax/area/suns*1e3,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('pce')).setToolTip(str(round(pMax_charEqn/area/suns*1e3,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('pmax')).setData(Qt.DisplayRole,float(round(pMax/area*1e3,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('pmax')).setToolTip(str(round(pMax_charEqn/area*1e3,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('jsc')).setData(Qt.DisplayRole,float(round(Isc_nn/area*1e3,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('jsc')).setToolTip(str(round(Isc_nn_charEqn/area*1e3,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('voc')).setData(Qt.DisplayRole,round(Voc_nn*1e3,3))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('voc')).setToolTip(str(round(Voc_nn_charEqn*1e3,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('ff')).setData(Qt.DisplayRole,float(round(FF,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('ff')).setToolTip(str(round(FF_charEqn,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('rs')).setData(Qt.DisplayRole,float(round(Rs_fit*area,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('rs')).setToolTip('[{0}  {1}]'.format(lowers[2]*area, uppers[2]*area))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('rsh')).setData(Qt.DisplayRole,float(round(Rsh_fit*area,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('rsh')).setToolTip('[{0}  {1}]'.format(lowers[3]*area, uppers[3]*area))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('jph')).setData(Qt.DisplayRole,float(round(Iph_fit/area*1e3,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('jph')).setToolTip('[{0}  {1}]'.format(lowers[1]/area*1e3, uppers[1]/area*1e3))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('j0')).setData(Qt.DisplayRole,float(round(I0_fit/area*1e9,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('j0')).setToolTip('[{0}  {1}]'.format(lowers[0]/area*1e9, uppers[0]/area*1e9))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('n')).setData(Qt.DisplayRole,float(round(n_fit,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('n')).setToolTip('[{0}  {1}]'.format(lowers[4], uppers[4]))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('Vmax')).setData(Qt.DisplayRole,float(round(vMax*1e3,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('Vmax')).setToolTip(str(round(vMax_charEqn*1e3,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('area')).setData(Qt.DisplayRole,round(area,3))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('pmax2')).setData(Qt.DisplayRole,float(round(pMax*1e3,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('pmax2')).setToolTip(str(round(pMax_charEqn*1e3,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('isc')).setData(Qt.DisplayRole,float(round(Isc_nn*1e3,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('isc')).setToolTip(str(round(Isc_nn_charEqn*1e3,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('iph')).setData(Qt.DisplayRole,float(round(Iph_fit*1e3,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('iph')).setToolTip('[{0}  {1}]'.format(lowers[1]*1e3, uppers[1]*1e3))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('i0')).setData(Qt.DisplayRole,float(round(I0_fit*1e9,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('i0')).setToolTip('[{0}  {1}]'.format(lowers[0]*1e9, uppers[0]*1e9))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('rs2')).setData(Qt.DisplayRole,float(round(Rs_fit,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('rs2')).setToolTip('[{0}  {1}]'.format(lowers[2], uppers[2]))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('rsh2')).setData(Qt.DisplayRole,float(round(Rsh_fit,3)))
            self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('rsh2')).setToolTip('[{0}  {1}]'.format(lowers[3], uppers[3]))

        else:#vs time
            graphData = {'vsTime':vsTime,'origRow':self.rows,'time':time,'i':II*outputScaleFactor,'v':VV}

        #file name
        self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('file')).setText(fileName)
        self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('file')).setToolTip(''.join(comments))          

        #plot button
        plotBtn = QPushButton(self.ui.tableWidget)
        plotBtn.setText('Plot')
        plotBtn.clicked.connect(self.handleButton)
        self.ui.tableWidget.setCellWidget(self.rows,list(self.cols.keys()).index('plotBtn'), plotBtn)
        self.ui.tableWidget.item(self.rows,list(self.cols.keys()).index('plotBtn')).setData(Qt.UserRole,graphData)

        self.ui.tableWidget.resizeColumnsToContents()
        self.rows = self.rows + 1

    def openCall(self):
        #remember the last path the user opened
        if self.settings.contains('lastFolder'):
            openDir = self.settings.value('lastFolder')
        else:
            openDir = '.'

        fileNames = QFileDialog.getOpenFileNames(self, directory = openDir, caption="Select one or more files to open", filter = '(*.csv *.tsv *.txt *.liv1 *.liv2);;Folders (*)')

        if len(fileNames[0])>0:#check if user clicked cancel
            self.workingDirectory = os.path.dirname(str(fileNames[0][0]))
            self.settings.setValue('lastFolder',self.workingDirectory)
            for fullPath in fileNames[0]:
                fullPath = str(fullPath)
                self.processFile(fullPath)

            if self.ui.actionEnable_Watching.isChecked():
                watchedDirs = self.watcher.directories()
                self.watcher.removePaths(watchedDirs)
                self.watcher.addPath(self.workingDirectory)
                self.handleWatchUpdate(self.workingDirectory)

    #user chose file --> watch
    def handleWatchAction(self):
        #remember the last path th user opened
        if self.settings.contains('lastFolder'):
            openDir = self.settings.value('lastFolder')
        else:
            openDir = '.'

        myDir = QFileDialog.getExistingDirectory(self,directory = openDir, caption="Select folder to watch")

        if len(myDir)>0:#check if user clicked cancel
            self.workingDirectory = str(myDir)
            self.settings.setValue('lastFolder',self.workingDirectory)
            self.ui.actionEnable_Watching.setChecked(True)
            watchedDirs = self.watcher.directories()
            self.watcher.removePaths(watchedDirs)
            self.watcher.addPath(self.workingDirectory)
            self.handleWatchUpdate(self.workingDirectory)

    #user toggeled Tools --> Enable Watching
    def watchCall(self):
        watchedDirs = self.watcher.directories()
        self.watcher.removePaths(watchedDirs)
        if self.ui.actionEnable_Watching.isChecked():
            if (self.workingDirectory != ''):
                self.watcher.addPath(self.workingDirectory)
                self.handleWatchUpdate(self.workingDirectory)

    def handleWatchUpdate(self,path):
        myDir = QDir(path)
        myDir.setNameFilters(self.supportedExtensions)
        allFilesNow = myDir.entryList()
        allFilesNow = list(allFilesNow)
        allFilesNow = [str(item) for item in allFilesNow]

        differentFiles = list(set(allFilesNow) ^ set(self.fileNames))
        if differentFiles != []:
            for aFile in differentFiles:
                if self.fileNames.__contains__(aFile):
                    #TODO: delete the file from the table
                    self.ui.statusbar.showMessage('Removed' + aFile,2500)
                else:
                    #process the new file
                    self.processFile(os.path.join(self.workingDirectory,aFile))

    def openFitConstraintDialog(self):
        self.prefs.show()

    def statusChanged(self,args):
        if not args:
            # reset the statusbar background
            self.ui.statusbar.setStyleSheet("QStatusBar{padding-left:8px;background:rgba(0,0,0,0);color:black;font-weight:bold;}")

    def goodMessage(self):
        self.ui.statusbar.setStyleSheet("QStatusBar{padding-left:8px;background:rgba(0,128,0,255);color:black;font-weight:bold;}")

    def badMessage(self):
        self.ui.statusbar.setStyleSheet("QStatusBar{padding-left:8px;background:rgba(255,0,0,255);color:black;font-weight:bold;}")    

if __name__ == "__main__":
    app = QApplication(sys.argv)
    analysis = MainWindow()
    analysis.show()
    sys.exit(app.exec_())
