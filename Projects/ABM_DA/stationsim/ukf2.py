# -*- coding: utf-8 -*-

"""
Created on Thu May 23 11:13:26 2019
@author: RC

The Unscented Kalman Filter (UKF) designed to be hyper efficient alternative to similar 
Monte Carlo techniques such as the Particle Filter. This file aims to unify the old 
intern project files by combining them into one single filter. It also aims to be geared 
towards real data with a modular data input approach for a hybrid of sensors.

This is based on
citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.80.1421&rep=rep1&type=pdf

NOTE: To avoid confusion 'observation/obs' are observed stationsim data
not to be confused with the 'observed' boolean 
determining whether to look at observed/unobserved agent subset
(maybe change the former the measurements etc.)

NOTE: __main__ here is now deprecated. use ukf notebook in experiments folder

"""

#general packages used for filtering

"used for a lot of things"
import numpy as np
"general timer"
import datetime 
"used to save clss instances when run finished."
import pickle 
from scipy.stats import chi2

"used for plotting covariance ellipses for each agent. not really used anymore"
# from filterpy.stats import covariance_ellipse  
# from scipy.stats import norm #easy l2 norming  
# from math import cos, sin


def unscented_Mean(sigmas, wm, sigma_function, kf_function, *function_args):
    
    
    """calculate unscented transform estimate for forecasted/desired means
    
    -calculate sigma points using sigma_function 
        (e.g Merwe Scaled Sigma Points (MSSP) or 
        central difference sigma points (CDSP)) 
    - apply kf_function to sigma points (usually transition function or 
        measurement function.) to get transformed sigma points
    - calculate weighted mean of transformed points to get unscented mean
    
    Parameters
    ------
    sigma_function, kf_function : function
        `sigma_function` function defining type of sigmas used and
        `kf_function` defining whether to apply transition of measurement 
        function (f/h) of UKF.
    
    *function_args : args
        `function_args` positional arguements for kf_function. Varies depending
        on the experiment so good to be general here.
        
    Returns 
    ------
    
    sigmas, nl_sigmas, xhat : array_like
        raw `sigmas` from sigma_function, projected non-linear `nl_sigmas`, 
        and the unscented mean of `xhat` of said projections.
        
    """
    
    "calculate either forecasted sigmas X- or measured sigmas Y with f/h"
    nl_sigmas = np.apply_along_axis(kf_function,0,sigmas,*function_args)
    "calculate unscented mean using non linear sigmas and MSSP mean weights"
    xhat = np.dot(nl_sigmas, wm)#unscented mean for predicitons
    
    return nl_sigmas, xhat

    
def covariance(data1, mean1, weight, data2 = None, mean2 = None, addition = None):
    
    
    """within/cross-covariance between sigma points and their unscented mean.
    
    Note: CAN'T use numpy.cov here as it uses the regular mean 
        and not the unscented mean. Maybe theres a faster numpy version
    
    Define sigma point matrices X_{mxp}, Y_{nxp}, 
    some unscented mean vectors a_{mx1}, b_{nx1}
    and some vector of covariance weights wc.
    
    Also define a column subtraction operator COL(X,a) 
    such that we subtract a from every column of X elementwise.
    
    Using the above we calculate the cross covariance between two sets of 
    sigma points as 
    
    P_xy = COL(X-a) * W * COL(Y-b)^T
    
    Given some diagonal weight matrix W with diagonal entries wc and 0 otherwise.
    
    This is similar to the standard statistical covariance with the exceptions
    of a non standard mean and weightings.
    
    Parameters
    ------
    
    data1, mean1` : array_like
        `data1` some array of sigma points and their unscented mean `mean1` 
        
    data2, mean2` : array_like
        `data2` some OTHER array of sigma points and their unscented mean `mean2` 
        can be same as data1, mean1 for within covariance
        
    `weight` : array_like
        `weight` sample covariance weightings
    
    addition : array_like
        some additive noise for the covariance such as the sensor/process noise.
        
    Returns 
    ------
    
    covariance_matrix : array_like
     `covariance_matrix` unscented covariance matrix used in ukf algorithm
        
    """
    

    
    "if no secondary data defined do within covariance. else do cross"
    
    if data2 is None and mean2 is None:
        data2 = data1
        mean2 = mean1
        
    """calculate component matrices for covariance by performing 
        column subtraction and diagonalising weights."""
    
    weighting = np.diag(weight)
    residuals = (data1.T - mean1).T
    residuals2 = (data2.T - mean2).T
    
    "calculate P_xy as defined above"

    covariance_matrix = np.linalg.multi_dot([residuals,weighting,residuals2.T])
    
    """old versions"""
    "old quadratic form version. made faster with multi_dot."
    #covariance_matrix = np.matmul(np.matmul((data1.transpose()-mean1).T,np.diag(weight)),
    #                (data1.transpose()-mean1))+self.q
    
    "numpy quadratic form far faster than this for loop"
    #covariance_matrix =  self.wc[0]*np.outer((data1[:,0].T-mean1),(data2[:,0].T-mean2))+self.Q
    #for i in range(1,len(self.wc)): 
    #    pxx += self.wc[i]*np.outer((nl_sigmas[:,i].T-self.x),nl_sigmas[:,i].T-xhat)
    
    "if some additive noise is involved (as with the Kalman filter) do it here"
    
    if addition is not None:
        covariance_matrix += addition
    
    return covariance_matrix

def MSSP(mean,p,g):
    
    """sigma point calculations based on current mean x and covariance P
    
    Parameters
    ------
    mean , P : array_like
        mean `x` and covariance `P` numpy arrays
        
    Returns
    ------
    sigmas : array_like
        matrix of MSSPs with each column representing one sigma point
    
    """
    n = mean.shape[0]
    s = np.linalg.cholesky(p)
    sigmas = np.ones((n,(2*n)+1)).T*mean
    sigmas=sigmas.T
    sigmas[:,1:n+1] += g*s #'upper' confidence sigmas
    sigmas[:,n+1:] -= g*s #'lower' confidence sigmas
    return sigmas 

#%%

class ukf:
    
    """main ukf class with aggregated measurements
    
    Parameters
    ------
    model_params, ukf_params : dict
        dictionary of model `model_params` and ukf `ukf_params` parameters
    init_x : array_like
        Initial ABM state `init_x`
    fx,hx: function
        transitions and measurement functions `fx` `hx`
    P,Q,R : array_like
        Noise structures `P` `Q` `R`
    
    """
    
    def __init__(self, model_params, ukf_params, base_model):
        
        
        """
        x - state
        n - state size 
        p - state covariance
        fx - transition function
        hx - measurement function
        lam - lambda paramter function of tuning parameters a,b,k
        g - gamma parameter function of tuning parameters a,b,k
        wm/wc - unscented weights for mean and covariances respectively.
        q,r -noise structures for fx and hx
        xs,ps - lists for storage
        """
        
        #init initial state
        "full parameter dictionaries and ABM"
        self.model_params = model_params
        self.ukf_params = ukf_params
        self.base_model = base_model
        
        "pull parameters from dictionary"
        self.x = self.base_model.get_state(sensor="location") #!!initialise some positions and covariances
        self.n = self.x.shape[0] #state space dimension
        self.p = ukf_params["p"]
        self.q = ukf_params["q"]
        self.r = ukf_params["r"]
        self.fx = ukf_params["fx"]
        self.hx = ukf_params["hx"]
        
        self.a = ukf_params["a"]
        self.b = ukf_params["b"]
        self.k = ukf_params["k"]

        "MSSP sigma point scaling parameters"
        self.lam = self.a**2*(self.n+self.k) - self.n 
        self.g = np.sqrt(self.n+self.lam) #gamma parameter

        
        "unscented mean and covariance weights based on a, b, and k"
        main_weight =  1/(2*(self.n+self.lam))
        self.wm = np.ones(((2*self.n)+1))*main_weight
        self.wm[0] *= 2*self.lam
        self.wc = self.wm.copy()
        self.wc[0] += (1-self.a**2+self.b)

        self.xs = []
        self.ps = []



    

    def predict(self):
        
        
        """Transitions sigma points forwards using markovian transition function plus noise Q
        
        - calculate sigmas using prior mean and covariance P.
        - forecast sigmas X- for next timestep using transition function Fx.
        - unscented mean for foreacsting next state.
        - calculate interim mean state x and covariance P
        - pass these onto  update function
        
        """
        sigmas = MSSP(self.x, self.p, self.g)
        nl_sigmas, xhat = unscented_Mean(sigmas, self.wm, 
                                                 MSSP, self.fx,self.base_model)
        self.sigmas = nl_sigmas
        
        pxx = covariance(nl_sigmas,xhat,self.wc,addition = self.q)
        
        self.p = pxx #update Sxx
        self.x = xhat #update xhat
    
    def update(self,z):   
        
        
        """ update forecasts with measurements to get posterior assimilations
        
        - nudges X- sigmas with new pxx from predict
        - calculate measurement sigmas Y = h(X-)
        - calculate unscented mean of Y, yhat
        - calculate measured state covariance pyy sing r
        - calculate cross covariance between X- and Y and Kalman gain (pxy, K)
        - update x and P
        - store x and P updates in lists (xs, ps)
        
        Parameters
        ------
        z : array_like
            measurements from sensors `z`
        """
        
        nl_sigmas, yhat = unscented_Mean(self.sigmas, self.wm, MSSP, self.hx, 
                                                      self.model_params,self.ukf_params)
        pyy =covariance(nl_sigmas, yhat, self.wc, addition=self.r)
        pxy = covariance(self.sigmas, self.x, self.wc, nl_sigmas, yhat)
        k = np.matmul(pxy,np.linalg.inv(pyy))
 
        "i dont know why `self.x += ...` doesnt work here"
        self.x = self.x + np.matmul(k,(z-yhat))
        self.p = self.p - np.linalg.multi_dot([k, pyy, k.T])
        
        self.ps.append(self.p)
        self.xs.append(self.x)

    def batch(self):
        """
        batch function hopefully coming soon
        """
        return
    
#%%
        
 
class adaptive_ukf:
    
    """main ukf class with aggregated measurements
    
    Parameters
    ------
    model_params, ukf_params : dict
        dictionary of model `model_params` and ukf `ukf_params` parameters
    init_x : array_like
        Initial ABM state `init_x`
    fx,hx: function
        transitions and measurement functions `fx` `hx`
    P,Q,R : array_like
        Noise structures `P` `Q` `R`
    
    """
    
    def __init__(self, model_params, ukf_params, base_model):
        
        
        """
        x - state
        n - state size 
        p - state covariance
        fx - transition function
        hx - measurement function
        lam - lambda paramter function of tuning parameters a,b,k
        g - gamma parameter function of tuning parameters a,b,k
        wm/wc - unscented weights for mean and covariances respectively.
        q,r -noise structures for fx and hx
        xs,ps - lists for storage
        """
        
        #init initial state
        "full parameter dictionaries and ABM"
        self.model_params = model_params
        self.ukf_params = ukf_params
        self.base_model = base_model
        
        "pull parameters from dictionary"
        self.x = self.base_model.get_state(sensor="location") #!!initialise some positions and covariances
        self.n = self.x.shape[0] #state space dimension
        self.p = ukf_params["p"]
        self.q = ukf_params["q"]
        self.r = ukf_params["r"]
        self.fx = ukf_params["fx"]
        self.hx = ukf_params["hx"]
        
        self.a = ukf_params["a"]
        self.b = ukf_params["b"]
        self.k = ukf_params["k"]

        "MSSP sigma point scaling parameters"
        self.lam = self.a**2*(self.n+self.k) - self.n 
        self.g = np.sqrt(self.n+self.lam) #gamma parameter
        
        
        self.phi0 = 0.2
        self.delta0 = 0.2
        
        "unscented mean and covariance weights based on a, b, and k"
        main_weight =  1/(2*(self.n+self.lam))
        self.wm = np.ones(((2*self.n)+1))*main_weight
        self.wm[0] *= 2*self.lam
        self.wc = self.wm.copy()
        self.wc[0] += (1-self.a**2+self.b)

        self.xs = []
        self.ps = []

    def predict(self):
        
        
        """Transitions sigma points forwards using markovian transition function plus noise Q
        
        - calculate sigmas using prior mean and covariance P.
        - forecast sigmas X- for next timestep using transition function Fx.
        - unscented mean for foreacsting next state.
        - calculate interim mean state x and covariance P
        - pass these onto  update function
        
        """
        sigmas = MSSP(self.x, self.p, self.g)
        nl_sigmas, xhat = unscented_Mean(sigmas, self.wm, 
                                                 MSSP, self.fx,self.base_model)
        self.sigmas = nl_sigmas
        
        pxx = covariance(nl_sigmas,xhat,self.wc,addition = self.q)
        
        self.p = pxx #update Sxx
        self.x = xhat #update xhat
    
    
    def update(self,z):   
        
        
        """ update forecasts with measurements to get posterior assimilations
        
        - nudges X- sigmas with new pxx from predict
        - calculate measurement sigmas Y = h(X-)
        - calculate unscented mean of Y, yhat
        - calculate measured state covariance pyy sing r
        - calculate cross covariance between X- and Y and Kalman gain (pxy, K)
        - update x and P
        - store x and P updates in lists (xs, ps)
        
        Parameters
        ------
        z : array_like
            measurements from sensors `z`
        """
        
        nl_sigmas, yhat = unscented_Mean(self.sigmas, self.wm, MSSP, self.hx, 
                                                      self.model_params,self.ukf_params)
        pyy =covariance(nl_sigmas, yhat, self.wc, addition=self.r)
        pxy = covariance(self.sigmas, self.x, self.wc, nl_sigmas, yhat)
        k = np.matmul(pxy,np.linalg.inv(pyy))
     
        "i dont know why `self.x += ...` doesnt work here"
        x = self.x + np.matmul(k,(z-yhat))
        p = self.p - np.linalg.multi_dot([k, pyy, k.T])
        
        mu = np.array(z)- np.array(self.hx(self.sigmas[:,0],self.model_params,self.ukf_params))
        
        if np.sum(np.abs(mu))!=0:
            x, p = self.fault_test(z, mu, pxy, pyy, x, p, k, yhat)
        
        self.x = x
        self.p = p
        self.ps.append(self.p)
        self.xs.append(self.x)
        
        
    
    def fault_test(self,z, mu, pxy, pyy, x, p, k, yhat):
        
        
        """ adaptive UKF augmentation
        
        -check chi squared test
        -if fails update q and r.
        -recalculate new x and p
        
        """
        sigma = np.linalg.inv((pyy+ self.r))
        psi = np.linalg.multi_dot([mu.T, sigma, mu])
        critical = chi2.ppf(0.8, df = mu.shape[0]) #critical rejection point
        print(psi, critical)
        if psi <= critical :
            "accept null hypothesis. keep q,r"
            pass
        else:
            eps = z - self.hx(x,self.model_params,self.ukf_params)            
            sigmas = MSSP(x,p,self.g)
            syy = covariance(self.hx(sigmas, self.model_params, self.ukf_params), yhat,self.wc)
            delta_1 =  1 - (self.a*critical)/psi
            delta = np.max(self.delta0,delta_1)
            phi_1 =  1 - (self.b*critical)/psi
            phi = np.max(self.phi0, phi_1)
            
            self.q = (1-phi)*self.q + phi*np.linalg.multi_dot([k, mu, mu.T, k.T])
            self.r = (1-delta)*self.r + delta*(np.linalg.multi_dot([eps, eps.T]) + syy)
            
            print("noises updated")
            "correct estimates using new noise"
            pyy  = syy + self.r
            k = np.matmul(pxy,np.linalg.inv(pyy))
            x = self.x + np.matmul(k,(z-yhat))
            p = self.p - np.linalg.multi_dot([k, pyy, k.T])
            
        return x, p
            
    def batch(self):
        """
        batch function hopefully coming soon
        """
        return
     
    
#%%
class ukf_ss:
    
    
    """UKF for station sim using ukf filter class.
    
    Parameters
    ------
    model_params,filter_params,ukf_params : dict
        loads in parameters for the model, station sim filter and general UKF parameters
        `model_params`,`filter_params`,`ukf_params`
    poly_list : list
        list of polygons `poly_list`
    base_model : method
        stationsim model `base_model`
    """
    
    def __init__(self, model_params, ukf_params, base_model):
        
        
        """
        *_params - loads in parameters for the model, station sim filter and general UKF parameters
        base_model - initiate stationsim 
        pop_total - population total
        number_of_iterations - how many steps for station sim
        sample_rate - how often to update the kalman filter. intigers greater than 1 repeatedly step the station sim forward
        sample_size - how many agents observed if prop is 1 then sample_size is same as pop_total
        index and index 2 - indicate which agents are being observed
        ukf_histories- placeholder to store ukf trajectories
        time1 - start gate time used to calculate run time 
        """
        # call params
        self.model_params = model_params #stationsim parameters
        self.ukf_params = ukf_params # ukf parameters
        self.base_model = base_model #station sim
        

        self.pop_total = self.model_params["pop_total"] #  number of agents
        self.number_of_iterations = model_params['step_limit'] #  number of batch iterations
        self.sample_rate = self.ukf_params["sample_rate"] # how often do we assimilate
        self.obs_key_func = ukf_params["obs_key_func"]  #defines what type of observation each agent has


        """lists for various data outputs
        observations
        ukf assimilations
        pure stationsim forecasts
        ground truths
        list of covariance matrices
        list of observation types for each agents at one time point
        """
        self.obs = []  # actual sensor observations
        self.ukf_histories = []  
        self.forecasts=[] 
        self.truths = []  # noiseless observations

        self.full_ps=[]  # full covariances. again used for animations and not error metrics
        self.obs_key = [] # which agents are observed (0 not, 1 agg, 2 gps)

        "timer"
        self.time1 =  datetime.datetime.now()#timer
        self.time2 = None
    
    def init_ukf(self,ukf_params):
        
        
        """initialise ukf with initial state and covariance structures.
       
        Parameters
        ------
        ukf_params : dict
            dictionary of various ukf parameters `ukf_params`
        
        
        Returns
        ------
        self.ukf : class
            `ukf` class intance for stationsim
        """
        
        
        self.ukf = ukf(self.model_params, ukf_params, self.base_model)
    
    def ss_Predict(self):
        
        
        """ Forecast step of UKF for stationsim.
        
        - forecast state using UKF (unscented transform)
        - update forecasts list
        - jump base_model forwards to forecast time
        - update truths list with new positions
        """
        self.ukf.predict() 
        self.forecasts.append(self.ukf.x)
        self.base_model.step()
        self.truths.append(self.base_model.get_state(sensor="location"))

    def ss_Update(self,step):
        
        
        """ Update step of UKF for stationsim.
        - if step is a multiple of sample_rate
            - measure state from base_model.
            - add some gaussian noise to active agents.
            - apply measurement funciton h to project noisy 
                state onto measured state
            - assimilate ukf with projected noisy state
            - calculate each agents observation type with obs_key_func.
            - append lists of ukf assimilations and model observations
        - else do nothing
        """
        if step%self.sample_rate == 0:
            state = self.base_model.get_state(sensor="location")
            if self.ukf_params["bring_noise"]:
                noise_array=np.ones(self.pop_total*2)
                noise_array[np.repeat([agent.status!=1 for agent in self.base_model.agents],2)]=0
                noise_array*=np.random.normal(0,self.ukf_params["noise"],self.pop_total*2)
                state+=noise_array
                
            "convert full noisy state to actual sensor observations"
            state = self.ukf.hx(state, self.model_params, self.ukf_params)
                
            self.ukf.update(state)
            
            if self.obs_key_func is not None:
                key = self.obs_key_func(state,self.model_params, self.ukf_params)
                "force inactive agents to unobserved"
                key *= [agent.status%2 for agent in self.base_model.agents]
                self.obs_key.append(key)

            self.ukf_histories.append(self.ukf.x) #append histories
            self.obs.append(state)
                 
        
    def main(self):
        """main function for applying ukf to gps style station StationSim
        -    initiates ukf
        -    while any agents are still active
            -    predict with ukf
            -    step true model
            -    update ukf with new model positions
            -    repeat until all agents finish or max iterations reached
        -    if no agents then stop
        
        """
        
        "initialise UKF"
        self.init_ukf(self.ukf_params) 
        for step in range(self.number_of_iterations-1):
            
            "forecast next StationSim state and jump model forwards"
            self.ss_Predict()
            "assimilate forecasts using new model state."
            self.ss_Update(step)
            
            finished = self.base_model.pop_finished == self.pop_total
            if finished: #break condition
                break
            
            #elif np.nansum(np.isnan(self.ukf.x)) == 0:
            #    print("math error. try larger values of alpha else check fx and hx.")
            #    break
          

        self.time2 = datetime.datetime.now()#timer
        print(self.time2-self.time1)

    def data_parser(self):
        
        
        """extracts data into numpy arrays
        
        Returns
        ------
            
        obs : array_like
            `obs` noisy observations of agents positions
        preds : array_like
            `preds` ukf predictions of said agent positions
        forecasts : array_like
            `forecasts` just the first ukf step at every time point
            useful for comparison in experiment 0
        truths : 
            `truths` true noiseless agent positions for post-hoc comparison
            
        nan_array : array_like
            `nan_array` stationsim gets stuck when an agent finishes it's run. good for plotting/metrics            
        """
       
       
            
        """pull actual data. note a and b dont have gaps every sample_rate
        measurements. Need to fill in based on truths (d).
        """
        obs =  np.vstack(self.obs) 
        preds2 = np.vstack(self.ukf_histories)
        truths = np.vstack(self.truths)
        
        
        "full 'd' size placeholders"
        preds= np.zeros((truths.shape[0],self.pop_total*2))*np.nan
        
        "fill in every sample_rate rows with ukf estimates and observation type key"
        for j in range(int(preds.shape[0]//self.sample_rate)):
            preds[j*self.sample_rate,:] = preds2[j,:]

        nan_array = np.ones(shape = truths.shape)*np.nan
        for i, agent in enumerate(self.base_model.agents):
            "find which rows are  NOT (None, None). Store in index. "
            array = np.array(agent.history_locations)
            index = ~np.equal(array,None)[:,0]
            "set anything in index to 1. I.E which agents are still in model."
            nan_array[index,2*i:(2*i)+2] = 1

        return obs,preds,truths,nan_array
          
       
    def obs_key_parser(self):
        """extract obs_key
        
        """
        obs_key2 = np.vstack(self.obs_key)
        shape = np.vstack(self.truths).shape[0]
        obs_key = np.zeros((shape,self.pop_total))*np.nan
        
        for j in range(int(shape//self.sample_rate)):
            obs_key[j*self.sample_rate,:] = obs_key2[j,:]
        
        return obs_key
        
def pickler(instance, pickle_source, f_name):
    
    
    """save ukf run as a pickle
    
    Parameters
    ------
    instance : class
        finished ukf_ss class `instance` to pickle. defaults to None 
        such that if no run is available we load a pickle instead.
        
    f_name, pickle_source : str
        `f_name` name of pickle file and `pickle_source` where to load 
        and save pickles from/to

    """
    
    f = open(pickle_source + f_name,"wb")
    pickle.dump(instance,f)
    f.close()

def depickler(pickle_source, f_name):
    
    
    """load a ukf pickle
    
    Parameters
    ------
    pickle_source : str
        `pickle_source` where to load and save pickles from/to

    instance : class
        finished ukf_ss class `instance` to pickle. defaults to None 
        such that if no run is available we load a pickle instead.
    """
    f = open(pickle_source+f_name,"rb")
    u = pickle.load(f)
    f.close()
    return u

def pickle_main(f_name, pickle_source, do_pickle, instance = None):
    
    
    """main function for saving and loading ukf pickles
    
    - check if we have a finished ukf_ss class and do we want to pickle it
    - if so, pickle it as f_name at pickle_source
    - else, if no ukf_ss class is present, load one with f_name from pickle_source 
        
    Parameters
    ------
    f_name, pickle_source : str
        `f_name` name of pickle file and `pickle_source` where to load 
        and save pickles from/to
    
    do_pickle : bool
        `do_pickle` do we want to pickle a finished run?
   
    instance : class
        finished ukf_ss class `instance` to pickle. defaults to None 
        such that if no run is available we load a pickle instead.
    """
    
    if do_pickle and instance is not None:
        print(f"Pickling file to {f_name}")
        pickler(instance, pickle_source, f_name)
        return
    else:
        print(f"Loading pickle {f_name}")
        instance = depickler(pickle_source, f_name)
        return instance