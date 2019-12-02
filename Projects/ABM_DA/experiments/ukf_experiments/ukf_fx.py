#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Dec  2 11:42:17 2019

@author: rob
"""
import os
import sys
"used in fx to restore stepped model"
from copy import deepcopy  
class HiddenPrints:


    """stop repeating printing from stationsim
    https://stackoverflow.com/questions/8391411/suppress-calls-to-print-python
    """
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout

def fx(x, base_model):
    
    
    """Transition function for the StationSim
    
    -Copies current base model
    -Replaces position with sigma point
    -Moves replaced model forwards one time point
    -record new stationsim positions as forecasted sigmapoint
    
    Parameters
    ------
    x : array_like
        Sigma point of measured state `x`
    **fx_args
        arbitrary arguments for transition function fx
        
    Returns
    -----
    state : array_like
        predicted measured state for given sigma point
    """   
        
    #f = open(f"temp_pickle_model_ukf_{self.time1}","rb")
    #model = pickle.load(f)
    #f.close()
    model = deepcopy(base_model)
    model.set_state(state = x,sensor="location")    
    with HiddenPrints():
        model.step() #step model with print suppression
    state = model.get_state(sensor="location")
    
    return state
