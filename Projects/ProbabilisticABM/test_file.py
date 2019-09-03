from super_simple_model.visualiser import Visualiser
from super_simple_model.agent import Agent
from super_simple_model.door import Door
from super_simple_model.environment import Environment
from super_simple_model.sensor import Sensor
import super_simple_model.renderer as renderer

import matplotlib as plt
import numpy as np
import pyro
from pyro.infer import Importance
pyro.set_rng_seed(7)

environment = Environment()
width, height = 20, 100
environment.doors = [Door(id=0, xy=(1000 - width / 2, (500 * 1.33) - height / 2),
							  width=width, height=height, fill=True),
						 Door(id=1, xy=(1000 - width / 2, (500 * 0.66) - height / 2),
							  width=width, height=height, fill=True)]


def main():
	posterior = None
	sensor = build_observations()
	agent = Agent(x=0., y=500.)
	agent.pick_destination(doors=environment.doors)
	visualiser = Visualiser(environment=environment, agent=agent)
	infer = Importance(model=agent.step, num_samples=10)

	for step in range(350):
		if (step % 100) == 0 and (step != 0):
			obs = sensor.aggregate_obs(step)
			print('Assimilating_Observation at Step {}'.format(step))
			sensor.print_detail(step)
			posterior = pyro.infer.EmpiricalMarginal(infer.run(posterior=posterior().mean(), obs=obs), sites=['xy'])
		else:
			obs = None
			posterior = pyro.infer.EmpiricalMarginal(infer.run(obs=obs), sites=['xy'])

		print('xy: {}, {}'.format(agent.xy[0].item(), agent.xy[1].item()))
	# print('Posterior X Mean: {} STD: {}'.format(posterior.mean[0].item(), posterior.stddev[0].item()))
	# print('Posterior Y Mean: {} STD: {}'.format(posterior.mean[1].item(), posterior.stddev[1].item()))

	visualiser.plot_agent()
	visualiser.plot_environment()
	visualiser.save_plt()
	visualiser.clear_frame()


def build_observations(n_samples=1, steps=350):
	n_samples = n_samples
	steps = steps
	agent = Agent(x=0., y=500., bias=0.0, n_samples=n_samples)
	sensor = Sensor(freq=1, n_samples=n_samples)
	agent.pick_destination(doors=environment.doors)
	renderer.clear_output_folder()
	for t in range(steps):
		if t != 0:
			sensor.observe(t, agent)

		agent.step(posterior=agent.xy)
	return sensor


if __name__ == '__main__':
	main()
