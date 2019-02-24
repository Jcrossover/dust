from StationSim_KM import Model

import multiprocessing
import numpy as np
from copy import deepcopy
import matplotlib.pyplot as plt
import time
import warnings



class ParticleFilter: 
    '''
    A particle filter to model the dynamics of the
    state of the model as it develops in time.
    '''

    def __init__(self, Model, model_params, filter_params):
        '''
        Initialise Particle Filter
            
        PARAMETERS
         - number_of_particles:     The number of particles used to simulate the model
         - number_of_iterations:    The number of iterations to run the model/particle filter
         - resample_window:         The number of iterations between resampling particles
         - agents_to_visualise:     The number of agents to plot particles for
         - particle_std:            The standard deviation of the noise added to particle states
         - model_std:               The standard deviation of the noise added to model observations
         - do_save:                 Boolean to determine if data should be saved and stats printed
         - do_ani:                  Boolean to determine if particle filter data should be animated
                                    and displayed
        
        DESCRIPTION
        Firstly, set all attributes using filter parameters. Set time and
        initialise base model using model parameters. Initialise particle
        models using a deepcopy of base model. Determine particle filter 
        dimensions, initialise all remaining arrays, and set initial
        particle states to the base model state using multiprocessing. 
        '''    
        for key, value in filter_params.items():
            setattr(self, key, value)
        self.time = 0
        self.number_of_iterations = model_params['batch_iterations']
        self.base_model = Model(model_params)
        self.models = list([deepcopy(self.base_model) for _ in range(self.number_of_particles)])  
        self.dimensions = len(self.base_model.agents2state())
        self.states = np.zeros((self.number_of_particles, self.dimensions))
        self.weights = np.ones(self.number_of_particles)
        self.indexes = np.zeros(self.number_of_particles, 'i')
        self.window_counter = 0 # Just for printing the progress of the PF
        if self.do_save:
            self.active_agents = []
            self.means = []
            self.mean_errors = []
            self.variances = []
            self.unique_particles = []
        
        self.states = np.array(pool.starmap(ParticleFilter.initial_state,list(zip(range(self.number_of_particles),[self]*self.number_of_particles))))


    # Multiprocessing methods
    @classmethod
    def initial_state(cls, particle,self):
        """
        Set the state of the particles to the state of the
        base model.
        """
        self.states[particle,:] = self.base_model.agents2state()
        return self.states[particle]

    @classmethod
    def assign_agents(cls, particle,self):
        """
        Assign the state of the particles to the
        locations of the agents.
        """
        self.models[particle].state2agents(self.states[particle])
        return self.models[particle]

    @classmethod
    def step_particles(cls, particle_num, self):
        """
        Step each particle model, assign the locations of the
        agents to the particle state with some noise, and
        then use the new particle state to set the location
        of the agents.

        :param particle_num: The particle number to step
        :param self: A pointer to the calling ParticleFilter object.
        """
        warnings.warn(
            "step_particles has been replaced with step_particle and should no longer be used",
            DeprecationWarning
        )
        self.models[particle_num].step()
        self.states[particle_num] = (self.models[particle_num].agents2state()
                                     + np.random.normal(0, self.particle_std ** 2,
                                                        size=self.states[particle_num].shape))
        self.models[particle_num].state2agents(self.states[particle_num])
        return self.models[particle_num], self.states[particle_num]

    @classmethod
    def step_particle(cls, particle_num, model, particle_std, particle_shape):
        """
        Step a particle, assign the locations of the
        agents to the particle state with some noise, and
        then use the new particle state to set the location
        of the agents.

        :param particle_num: The particle number to step
        :param self: A pointer to the calling ParticleFilter object.
        """
        #self.models[particle_num].step()
        model.step()
        state = (model.agents2state() +
                 np.random.normal(0, particle_std ** 2, size=particle_shape))
        model.state2agents(state)
        return model, state

    def step(self):
        '''
        Step Particle Filter
        
        DESCRIPTION
        Loop through process. Predict the base model and particles
        forward. If the resample window has been reached, 
        reweight particles based on distance to base model and resample 
        particles choosing particles with higher weights. Then save
        and animate the data. When done, plot save figures.

        :return: Information about the run as a tuple:
           max(self.mean_errors)
           np.average(self.mean_errors)
           max(self.variances)
           np.average(self.variances)
        '''
        print("Starting particle filter step()")
        while self.time < self.number_of_iterations:
            self.time += 1
            
            if any([agent.active != 2 for agent in self.base_model.agents]):
                #print(self.time/self.number_of_iterations)
                self.predict()
                
                if self.time % self.resample_window == 0:
                    print("\tWindow {}, step {}".format(self.window_counter, self.time))
                    self.reweight()
                    self.resample()
    
                if self.do_save:
                    self.save()
    
            if self.do_ani:
                    self.ani()
              
        if self.plot_save:
            self.p_save()
            
        
        return max(self.mean_errors), np.average(self.mean_errors), max(self.variances), np.average(self.variances)
    
    def predict(self):
        '''
        Predict
        
        DESCRIPTION
        Increment time. Step the base model. Set self as a constant
        in step_particles and then use a multiprocessing method to step 
        particle models, set the particle states as the agent 
        locations with some added noise, and reassign the
        locations of the particle agents using the new particle
        states. We extract the models and states from the stepped
        particles variable.
        '''
        self.base_model.step()

        #stepped_particles = pool.starmap(ParticleFilter.step_particles, \
        #                                 list(zip(range(self.number_of_particles), [self]*self.number_of_particles)))

        stepped_particles = pool.starmap(ParticleFilter.step_particle, list(zip(
            range(self.number_of_particles), # Particle numbers
            [ m for m in self.models],  # Associated Models
            [self.particle_std]*self.number_of_particles, # Particle std (for adding noise
            [ s.shape for s in self.states], #Shape (for adding noise)
        )))

        self.models = [stepped_particles[i][0] for i in range(len(stepped_particles))]
        self.states = np.array([stepped_particles[i][1] for i in range(len(stepped_particles))])
        
        return
    
    def reweight(self):
        '''
        Reweight
        
        DESCRIPTION
        Add noise to the base model state to get a measured state. Calculate 
        the distance between the particle states and the measured base model 
        state and then calculate the new particle weights as 1/distance. 
        Add a small term to avoid dividing by 0. Normalise the weights.
        '''
        measured_state = (self.base_model.agents2state() 
                          + np.random.normal(0, self.model_std**2, size=self.states.shape))
        distance = np.linalg.norm(self.states - measured_state, axis=1)
        self.weights = 1 / (distance + 1e-99)**2
        self.weights /= np.sum(self.weights)
        return

    def resample(self):
        '''
        Resample
        
        DESCRIPTION
        Calculate a random partition of (0,1) and then 
        take the cumulative sum of the particle weights.
        Carry out a systematic resample of particles.
        Set the new particle states and weights and then
        update agent locations in particle models using 
        multiprocessing methods.
        '''
        offset_partition = ((np.arange(self.number_of_particles) 
                             + np.random.uniform()) / self.number_of_particles)
        cumsum = np.cumsum(self.weights)
        i, j = 0, 0
        while i < self.number_of_particles:
            if offset_partition[i] < cumsum[j]:
                self.indexes[i] = j
                i += 1
            else:
                j += 1
                
        self.states[:] = self.states[self.indexes]
        self.weights[:] = self.weights[self.indexes]
        
        self.unique_particles.append(len(np.unique(self.states,axis=0)))

        self.models = pool.starmap(ParticleFilter.assign_agents,list(zip(range(self.number_of_particles),[self]*self.number_of_particles)))

        return

    def save(self):
        '''
        Save
        
        DESCRIPTION
        Calculate number of active agents, mean, and variance 
        of particles and calculate mean error between the mean 
        and the true base model state. Plot active agents,mean 
        error and mean variance. 
        '''
        self.active_agents.append(sum([agent.active == 1 for agent in self.base_model.agents]))
        
        active_states = [agent.active == 1 for agent in self.base_model.agents for _ in range(2)]
        
        if any(active_states):
            mean = np.average(self.states[:,active_states], weights=self.weights, axis=0)
            variance = np.average((self.states[:,active_states] - mean)**2, weights=self.weights, axis=0)
            
            self.means.append(mean)
            self.variances.append(np.average(variance))

            truth_state = self.base_model.agents2state()
            self.mean_errors.append(np.linalg.norm(mean - truth_state[active_states], axis=0))
        
        return
    
    def p_save(self):
        '''
        Plot Save
        
        DESCRIPTION
        Plot active agents, mean error and mean variance. 
        '''
        plt.figure(2)
        plt.plot(self.active_agents)
        plt.ylabel('Active agents')
        plt.show()
        
        plt.figure(3)
        plt.plot(self.mean_errors)
        plt.ylabel('Mean Error')
        plt.show()
        
        plt.figure(4)
        plt.plot(self.variances)
        plt.ylabel('Mean Variance')
        plt.show()
        
        plt.figure(5)
        plt.plot(self.unique_particles)
        plt.ylabel('Unique Particles')
        plt.show()
        
        print('Max mean error = ',max(self.mean_errors))
        print('Average mean error = ',np.average(self.mean_errors))
        print('Max mean variance = ',max(self.variances[2:]))
        print('Average mean variance = ',np.average(self.variances[2:]))

    def ani(self):
        '''
        Animate
        
        DESCRIPTION
        Plot the base model state and some of the 
        particles. Only do this if there is at least 1 active
        agent in the base model. We adjust the markersizes of
        each particle to represent the weight of that particle.
        We then plot some of the agent locations in the particles
        and draw lines between the particle agent location and 
        the agent location in the base model. 
        '''
        if any([agent.active == 1 for agent in self.base_model.agents]):
    
            plt.figure(1)
            plt.clf()
            
            markersizes = self.weights
            if np.std(markersizes) != 0:
                markersizes *= 4 / np.std(markersizes)   # revar
            markersizes += 8 - np.mean(markersizes)  # remean

            particle = -1
            for model in self.models:
                particle += 1
                markersize = np.clip(markersizes[particle], .5, 8)
                for agent in model.agents[:self.agents_to_visualise]:
                    if agent.active == 1:
                        unique_id = agent.unique_id
                        if self.base_model.agents[unique_id].active == 1:     
                            locs = np.array([self.base_model.agents[unique_id].location, agent.location]).T
                            plt.plot(*locs, '-k', alpha=.1, linewidth=.3)
                            plt.plot(*agent.location, 'or', alpha=.3, markersize=markersize)
            
            for agent in self.base_model.agents:                
                if agent.active == 1:
                    plt.plot(*agent.location, 'sk',markersize = 4)
            
            plt.axis(np.ravel(self.base_model.boundaries, 'F'))
            plt.pause(1 / 4)


def single_run_particle_numbers():
    runs = 5
    filter_params = {
        'number_of_particles': 5,
        'resample_window': 100,
        'agents_to_visualise': 2,
        'particle_std': 1,
        'model_std': 1,
        'do_save': True,
        'plot_save': False,
        'do_ani': False,
    }

    # Open a file to write the results to
    outfile = "results/pf"+str(int(time.time()*1000))+".csv"
    with open(outfile, 'w') as f:
        # Write the parameters first
        f.write("PF params: "+str(filter_params)+"\n")
        f.write("Model params: "+str(model_params)+"\n")
        # Now write the csv headers
        f.write("Max_Mean_errors,"+"Average_mean_errors,"+"Max_variances,"+"Average_variances\n")

    print("Running filter with {} particles and {} runs (on {} cores). Saving files to: {}".format(
        filter_params['number_of_particles'], runs, multiprocessing.cpu_count(), outfile))


    for i in range(runs):

        # Run the particle filter
        pf = ParticleFilter(Model, model_params, filter_params)
        result = pf.step()

        # Write the results of this run
        with open(outfile, 'a') as f:
            f.write(str(result)[1:-1].replace(" ","")+"\n") # (slice to get rid of the brackets aruond the tuple)
        print("Run: {}, particles: {}, result: {}".format(i, filter_params['number_of_particles'], result))

    print("Finished single run")

if __name__ == '__main__':
    __spec__ = None

    # Pool object needed for multiprocessing
    pool = multiprocessing.Pool(processes=multiprocessing.cpu_count())

    model_params = {
        'width': 200,
        'height': 100,
        'pop_total': 700,
        'entrances': 3,
        'entrance_space': 2,
        'entrance_speed': .1,
        'exits': 2,
        'exit_space': 1,
        'speed_min': .1,
        'speed_desire_mean': 1,
        'speed_desire_std': 1,
        'separation': 2,
        'batch_iterations': 4000,
        'do_save': False,
        'do_ani': False,
        }
    #Model(model_params).batch() # Runs the model as normal (one run)

    # Run the particle filter
    single_run_particle_numbers()
