import numpy as np
import param

from ... import aux
from .basic import Effector
from ...param import PositiveNumber, RangeRobust
from .remote_brian_interface import RemoteBrianModelInterface

__all__ = [
    'Sensor',
    'Olfactor',
    'Toucher',
    'WindSensor',
    'Thermosensor',
]


class Sensor(Effector):
    output_range = RangeRobust((-1.0, 1.0), readonly=True)
    perception = param.Selector(objects=['log','linear', 'null'], label='sensory transduction mode',
                                doc='The method used to calculate the perceived sensory activation from the current and previous sensory input.')
    decay_coef = PositiveNumber(0.1, softmax=2.0, step=0.01, label='sensory decay coef',
                                doc='The linear decay coefficient of the olfactory sensory activation.')
    brute_force = param.Boolean(False, doc='Whether to apply direct rule-based modulation on locomotion or not.')
    gain_dict = param.Dict(default=aux.AttrDict(), doc='Dictionary of sensor gain per stimulus ID')



    def __init__(self, brain=None, **kwargs):
        super().__init__(**kwargs)

        self.brain = brain

        self.exp_decay_coef = np.exp(- self.dt * self.decay_coef)

        self.X = aux.AttrDict({id: 0.0 for id in self.gain_ids})
        self.dX = aux.AttrDict({id: 0.0 for id in self.gain_ids})
        self.gain = self.gain_dict

    def compute_dif(self, input):
        pass

    # def update_gain(self):
    #     pass

    # def update_output(self,output):
    #     return self.apply_noise(output, self.output_noise, range=(self.A0,self.A1))

    def update(self):
        # self.update_gain()
        if len(self.input) == 0:
            self.output = 0
        elif self.brute_force:
            if self.brain is not None:
                self.affect_locomotion(L=self.brain.locomotor)
            self.output = 0
        else:
            self.compute_dX(self.input)
            self.output *= self.exp_decay_coef
            self.output += self.dt * np.sum([self.gain[id] * self.dX[id] for id in self.gain_ids])

    def affect_locomotion(self, L):
        pass



    def get_dX(self):
        return self.dX

    def get_X_values(self, t, N):
        return list(self.X.values())

    def get_gain(self):
        return self.gain

    def set_gain(self, value, gain_id):
        self.gain[gain_id] = value

    def reset_gain(self, gain_id):
        self.gain[gain_id] = self.gain_dict[gain_id]

    def reset_all_gains(self):
        self.gain = self.gain_dict

    def compute_single_dx(self, cur, prev):
        if self.perception == 'log':
            return cur / prev - 1 if prev != 0 else 0
        elif self.perception == 'linear':
            return cur - prev if prev != 0 else 0
        elif self.perception == 'null':
            return cur

    def compute_dX(self, input):
        for id, cur in input.items():
            if id not in self.X :
                self.add_novel_gain(id, con=cur)
            else:
                prev = self.X[id]
                self.dX[id] = self.compute_single_dx(cur, prev)
        self.X = input

    def add_novel_gain(self, id, con=0.0, gain=0.0):
        self.gain_dict[id] = gain
        self.gain[id] = gain
        self.dX[id] = 0.0
        self.X[id] = con

    @property
    def gain_ids(self):
        return list(self.gain_dict.keys())


class Olfactor(Sensor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


    # @property
    # def novel_odors(self):
    #     ids = []
    #     if self.brain is not None:
    #         if self.brain.agent is not None:
    #             ids = self.brain.agent.model.odor_ids
    #             ids = aux.nonexisting_cols(ids, self.gain_ids)
    #     return ids

    # def update_gain(self):
    #     for id in self.novel_odors:
    #         if isinstance(self.input, dict) and id in self.input.keys():
    #             con = self.input[id]
    #         else:
    #             con = 0
    #         self.add_novel_gain(id, con=con)

    def affect_locomotion(self, L):
        if self.output < 0 and L.stride_completed:
            if np.random.uniform(0, 1, 1) <= np.abs(self.output):
                L.intermitter.interrupt_locomotion()

    @property
    def first_odor_concentration(self):
        return list(self.X.values())[0]

    @property
    def second_odor_concentration(self):
        return list(self.X.values())[1]

    @property
    def first_odor_concentration_change(self):
        return list(self.dX.values())[0]

    @property
    def second_odor_concentration_change(self):
        return list(self.dX.values())[1]


class Toucher(Sensor):
    initial_gain = PositiveNumber(40.0, label='tactile sensitivity coef', doc='The initial gain of the tactile sensor.')
    touch_sensors = param.List(default=[], item_type=int, doc='The location indexes of sensors around body contour.')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.init_sensors()

    def init_sensors(self):
        if self.brain is not None:
            if self.brain.agent is not None:
                self.brain.agent.add_touch_sensors(self.touch_sensors)
                for s in self.brain.agent.touch_sensorIDs:
                    if s not in self.gain:
                        self.add_novel_gain(id=s, gain=self.initial_gain)

    def affect_locomotion(self, L):
        for id in self.gain_ids:
            if self.dX[id] == 1:
                L.intermitter.trigger_locomotion()
                break
            elif self.dX[id] == -1:
                L.intermitter.interrupt_locomotion()
                break


class WindSensor(Sensor):
    gain_dict = param.Dict(default=aux.AttrDict({'windsensor': 1.0}))
    perception = param.Selector(default='null')

    def __init__(self, weights, **kwargs):
        super().__init__(**kwargs)
        self.weights = weights


# @todo add class Thermosensor(Sensor) here with a double gain dict
class Thermosensor(Sensor):
    #gain_dict = param.Dict(default=aux.AttrDict({'warm': 0.0, 'cool': 0.0}))
    cool_gain = PositiveNumber(0.0, label='cool sensitivity coef', doc='The gain of the cool sensor.')
    warm_gain = PositiveNumber(0.0, label='warm sensitivity coef', doc='The gain of the warm sensor.')

    def __init__(self, cool_gain=0.0, warm_gain=0.0, **kwargs):  # thermodict={"cool", "warm"}
        super().__init__(gain_dict=aux.AttrDict({'warm': warm_gain, 'cool': cool_gain}), **kwargs)

    @property
    def warm_sensor_input(self):
        return self.X['warm']  # @todo do I need to make self.thermoX.values? same for dX.

    @property
    def warm_sensor_perception(self):
        return self.dX['warm']

    @property
    def cool_sensor_input(self):
        return self.X['cool']  # @todo do I need to make self.thermoX.values? same for dX.

    @property
    def cool_sensor_perception(self):
        return self.dX['cool']


class BrianOlfactor(Olfactor):
    def __init__(self, response_key='OSN_rate', server_host='localhost', server_port=5795, remote_dt=100, remote_warmup=0, **kwargs):
        super().__init__(**kwargs)
        self.brianInterface = RemoteBrianModelInterface(server_host, server_port, remote_dt)
        self.brian_warmup = remote_warmup
        self.response_key = response_key
        self.remote_dt = remote_dt
        self.agent_id = RemoteBrianModelInterface.getRandomModelId()


    def update(self):
        agent_id = self.brain.agent.unique_id if self.brain is not None else self.agent_id
        
        msg_kws = {
            # Default :
            'odor_id': 0, # TODO: can we get this info from somewhere ?
            # The concentration change :
            'concentration_mmol': self.first_odor_concentration,
            'concentration_change_mmol': self.first_odor_concentration_change,
        }

        response = self.brianInterface.executeRemoteModelStep(agent_id, t_sim=self.remote_dt, t_warmup=self.brian_warmup, **msg_kws)
        self.output = response.param(self.response_key)
        super().update()