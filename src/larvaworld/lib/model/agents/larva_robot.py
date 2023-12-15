from ... import aux
from . import LarvaSim
from ...model.modules.motor_controller import MotorController, Actuator
from ...model.modules.sensor2 import ProximitySensor
from ...param import PositiveNumber


__all__ = [
    'LarvaRobot',
    'ObstacleLarvaRobot',
]

__displayname__ = 'Braitenberg-like larva'

class LarvaRobot(LarvaSim):

    def __init__(self, larva_pars,genome=None,**kwargs):
        super().__init__(**larva_pars, **kwargs)
        self.genome = genome



class ObstacleLarvaRobot(LarvaRobot):
    sensor_delta_direction = PositiveNumber(0.4, doc='Sensor delta_direction')
    sensor_saturation_value = PositiveNumber(40.0, doc='Sensor saturation value')
    obstacle_sensor_error = PositiveNumber(0.35, doc='Proximity sensor error')
    sensor_max_distance = PositiveNumber(0.9, doc='Sensor max_distance')
    motor_coefficient = PositiveNumber(8770.0, doc='Motor ctrl_coefficient')
    min_actuator_value = PositiveNumber(35.0, doc='Motor ctrl_min_actuator_value')


    def __init__(self, larva_pars, **kwargs):
        kws = larva_pars.sensorimotor
        larva_pars.pop('sensorimotor', None)
        super().__init__(larva_pars=larva_pars, **kws,**kwargs)
        S_kws = {
            'robot': self,
            'saturation_value': self.sensor_saturation_value,
            'error': self.obstacle_sensor_error,
            'max_distance': int(self.model.screen_manager._scale[0, 0] * self.sensor_max_distance * self.length),
            'collision_distance': int(self.model.screen_manager._scale[0, 0] * self.length / 5),
        }

        M_kws = {
            'coefficient': self.motor_coefficient,
            'min_actuator_value': self.min_actuator_value,
        }


        self.Lmotor = MotorController(sensor=ProximitySensor(delta_direction=self.sensor_delta_direction, **S_kws), actuator=Actuator(), **M_kws)
        self.Rmotor = MotorController(sensor=ProximitySensor(delta_direction=-self.sensor_delta_direction, **S_kws), actuator=Actuator(), **M_kws)

    def sense(self):
        if not self.collision_with_object:
            pos = self.model.screen_manager._transform(self.olfactor_pos)
            try:

                self.Lmotor.sense_and_act(pos=pos, direction=self.direction)
                self.Rmotor.sense_and_act(pos=pos, direction=self.direction)
                Ltorque = self.Lmotor.get_actuator_value()
                Rtorque = self.Rmotor.get_actuator_value()
                dRL = Rtorque - Ltorque
                if dRL > 0:
                    self.brain.locomotor.turner.neural_oscillator.E_r += dRL * self.model.dt
                else:
                    self.brain.locomotor.turner.neural_oscillator.E_l -= dRL * self.model.dt
            except aux.Collision:
                self.collision_with_object = True
                self.brain.locomotor.intermitter.interrupt_locomotion()
        else:
            pass

    def draw(self, v, **kwargs):
        pos = v._transform(self.olfactor_pos)
        # draw the sensor lines

        # in scene_loader a robot doesn't have sensors
        if self.Lmotor is not None:
            self.Lmotor.sensor.draw(pos=pos, direction=self.direction)
            self.Rmotor.sensor.draw(pos=pos, direction=self.direction)

        # call super method to draw the robot
        super().draw(v, **kwargs)
