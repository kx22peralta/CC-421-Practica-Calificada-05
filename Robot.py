"""

Mobile robot motion planning sample with Dynamic Window Approach

author: Atsushi Sakai (@Atsushi_twi), Göktuğ Karakaşlı

"""

import math
from enum import Enum

import matplotlib.pyplot as plt
import numpy as np
from numpy.distutils.command.config import config
import pygame
from sys import exit
""" pygame.sprite.Sprite """

class RobotType(Enum):
    circle = 0
    rectangle = 1

class Config:
    """
    clase de parámetro de simulación
    """

    def __init__(self):
        # parametros del robot

        self.max_speed = 1.0  # [m/s]
        self.min_speed = -0.5  # [m/s]
        self.max_yaw_rate = 40.0 * math.pi / 180.0  # [rad/s]
        self.max_accel = 0.2  # [m/ss]
        self.max_delta_yaw_rate = 40.0 * math.pi / 180.0  # [rad/ss]
        self.v_resolution = 0.01  # [m/s]
        self.yaw_rate_resolution = 0.1 * math.pi / 180.0  # [rad/s]
        self.dt = 0.1  # [s] marca de tiempo para la predicción en movimiento
        self.predict_time = 3.0  # [s]
        self.to_goal_cost_gain = 0.15
        self.speed_cost_gain = 1.0
        self.obstacle_cost_gain = 1.0
        self.robot_stuck_flag_cons = 0.001  # constante para probar que el robot se atasque.
        self.robot_type = RobotType.circle

        # if robot_type == RobotType.circle
        #También se utiliza para comprobar si se alcanza el objetivo en ambos tipos
        self.robot_radius = 1.0  # [m] para control de colisión

        # if robot_type == RobotType.rectangle
        self.robot_width = 0.5  # [m] para control de colisión
        self.robot_length = 1.2  # [m]para control de colisión
        # obstaculos [x(m) y(m), ....]
        self.ob = np.array([[-1, -1],
                            [0, 2],
                            [4.0, 2.0],
                            [5.0, 4.0],
                            [5.0, 5.0],
                            [5.0, 6.0],
                            [5.0, 9.0],
                            [8.0, 9.0],
                            [7.0, 9.0],
                            [8.0, 10.0],
                            [9.0, 11.0],
                            [12.0, 13.0],
                            [12.0, 12.0],
                            [15.0, 15.0],
                            [13.0, 13.0]
                            ])

    @property
    def robot_type(self):
        return self._robot_type

    @robot_type.setter
    def robot_type(self, value):
        if not isinstance(value, RobotType):
            raise TypeError("robot_type must be an instance of RobotType")
        self._robot_type = value

""" Obstaculos son circulos """
class Obstaculo(pygame.sprite.Sprite):
    def __init__(self, tupla, radio):
        super().__init__()
        self.center = tupla
        self.radio = radio
       
    def coordenadas(self):
        return [self.center[0], self.center[1]] 

""" Robots """
class Robot(pygame.sprite.Sprite):
    """ Estado inicial del vehiculo (parametros iniciales)
         [x(m), y(m), yaw(rad), v(m/s), omega(rad/s)] ,
          x(m) : posición en x
          y(m) : posición en y
          yaw(rad) : posición angular con respecto al eje horizontal 
          v (m/s) : velocidad
          omega (rad/s) : velocidad angular """
    """ posición de la meta  [x(m), y(m)] 
           x(m) : posición en x de la meta
           y(m) : posición de y de la meta"""
    def __init__(self,robot_type ):
        super().__init__()
        self.config = Config()
        self.config.robot_type = robot_type

    def motion(self, x, u):
        x[2] += u[1] * self.config.dt
        x[0] += u[0] * math.cos(x[2]) * self.config.dt
        x[1] += u[0] * math.sin(x[2]) * self.config.dt
        x[3] = u[0]
        x[4] = u[1]
        return x

    def dwa_control(self, x):
        dw = self.calc_dynamic_window(x)
        u, trajectory , trayectorias_candidatas= self.calc_control_and_trajectory(x, dw)
        return u, trajectory, trayectorias_candidatas

    def calc_dynamic_window(self,x):
        Vs = [self.config.min_speed, self.config.max_speed,
        -self.config.max_yaw_rate, self.config.max_yaw_rate]
        
        Vd = [x[3] - self.config.max_accel * self.config.dt,
        x[3] + self.config.max_accel * self.config.dt,
        x[4] - self.config.max_delta_yaw_rate * self.config.dt,
        x[4] + self.config.max_delta_yaw_rate * self.config.dt]
          
        dw = [max(Vs[0], Vd[0]), min(Vs[1], Vd[1]),
          max(Vs[2], Vd[2]), min(Vs[3], Vd[3])]
        
        return dw
    
    def predict_trajectory(self, x_init, v, y):
        x = np.array(x_init)
        trajectory = np.array(x)
        time = 0
        while time <= self.config.predict_time:
            x = self.motion(x, [v, y])
            trajectory = np.vstack((trajectory, x))
            time += self.config.dt
        return trajectory
    
    def calc_control_and_trajectory(self, x, dw):
        x_init = x[:]
        min_cost = float("inf")
        best_u = [0.0, 0.0]
        best_trajectory = np.array([x])
        trayectorias_candidatas = []

        for v in np.arange(dw[0], dw[1], self.config.v_resolution):
            for y in np.arange(dw[2], dw[3], self.config.yaw_rate_resolution):
                trajectory = self.predict_trajectory(x_init, v, y)

                trayectorias_candidatas.append(trajectory)
                
                to_goal_cost = self.config.to_goal_cost_gain * self.calc_to_goal_cost(trajectory)
                speed_cost = self.config.speed_cost_gain * (self.config.max_speed - trajectory[-1, 3])
                ob_cost = self.config.obstacle_cost_gain * self.calc_obstacle_cost(trajectory)

                final_cost = to_goal_cost + speed_cost + ob_cost
                if min_cost >= final_cost:
                    min_cost = final_cost
                    best_u = [v, y]
                    best_trajectory = trajectory
                    if abs(best_u[0]) < self.config.robot_stuck_flag_cons \
                            and abs(x[3]) < self.config.robot_stuck_flag_cons:
                        best_u[1] = -self.config.max_delta_yaw_rate
        
        return best_u, best_trajectory, trayectorias_candidatas
    
    def calc_obstacle_cost(self, trajectory):
        ox = self.config.ob[:, 0]
        oy = self.config.ob[:, 1]
        dx = trajectory[:, 0] - ox[:, None]
        dy = trajectory[:, 1] - oy[:, None]
        r = np.hypot(dx, dy)
        if self.config.robot_type == RobotType.rectangle:
            yaw = trajectory[:, 2]
            rot = np.array([[np.cos(yaw), -np.sin(yaw)], [np.sin(yaw), np.cos(yaw)]])
            rot = np.transpose(rot, [2, 0, 1])
            local_ob = self.config.ob[:, None] - trajectory[:, 0:2]
            local_ob = local_ob.reshape(-1, local_ob.shape[-1])
            local_ob = np.array([local_ob @ x for x in rot])
            local_ob = local_ob.reshape(-1, local_ob.shape[-1])
            """ Checking si alguno llega a chocar al robot """
            upper_check = local_ob[:, 0] <= self.config.robot_length / 2
            right_check = local_ob[:, 1] <= self.config.robot_width / 2
            bottom_check = local_ob[:, 0] >= -self.config.robot_length / 2
            left_check = local_ob[:, 1] >= -self.config.robot_width / 2
            if (np.logical_and(np.logical_and(upper_check, right_check),
                            np.logical_and(bottom_check, left_check))).any():
                return float("Inf")
        elif self.config.robot_type == RobotType.circle:
            if np.array(r <= self.config.robot_radius).any():
                return float("Inf")
    
        min_r = np.min(r)
        return 1.0 / min_r  # OK

    def calc_to_goal_cost(self, trajectory):
        dx = self.goal[0] - trajectory[-1, 0]
        dy = self.goal[1] - trajectory[-1, 1]
        error_angle = math.atan2(dy, dx)
        cost_angle = error_angle - trajectory[-1, 2]
        cost = abs(math.atan2(math.sin(cost_angle), math.cos(cost_angle)))
        return cost
    
    def add_ob(self,o):
        self.config.ob.append(o)
    
    def calcular_coordenadas(self,x):
        rot =np.array([ [np.cos(x[2]), -np.sin(x[2])], 
                                         [np.sin(x[2]), np.cos(x[2]) ] ])
        coord = np.array( [ [x[0] -(self.config.robot_length/2),
                                                                x[0] -(self.config.robot_length/2),
                                                                x[0] + (self.config.robot_length/2) ,
                                                                x[0] + (self.config.robot_length/2)] ,
                                                                
                                                                [x[1]+(self.config.robot_width/2),
                                                                x[1]-(self.config.robot_width/2),
                                                                x[1]-(self.config.robot_width/2),
                                                                x[1]+(self.config.robot_width/2) ] ]) @ rot
        return coord.transpose()
    
    def dibujo_robot(self, x):
        if self.config.robot_type == RobotType.circle:
            self.shape = pygame.draw.circle((x[0],x[1]), self.config.robot_radius)
        elif self.config.robot_type == RobotType.rectangle:
            coord = self.calcular_coordenadas(x)
            self.shape = pygame.draw.polygon(coord)

    def dibuja_trayectorias(x,trayectorias_candidatas):
        print("trayectorias candidatas")

    def dibuja_trayectoria(x,predicted_trajectory):
        print("trayectoria")

    def dibuja_obstaculos(ob):
        print("dibuja obstaculos")

    def dibuja_meta(goal):
        print("dibuja la meta")
    
    def movimiento(self,x):
        print("movimiento")

    def run(self, x , goal):
         """  Bucle de avance , mientras el objetivo no alcance la meta. """
         self.inicio = x
         self.goal = goal 
         trajectory = np.array(x)
         while True:
            u, predicted_trajectory, trayectorias_candidatas = self.dwa_control(x)
            x = self.motion(x, u)  # simulate robot
            print(x)
            trajectory = np.vstack((trajectory, x))  # store state history
            dist_to_goal = math.hypot(x[0] - goal[0], x[1] - goal[1])
            if dist_to_goal <= self.config.robot_radius:
                print("Goal!!")
                break

def simulacion(Robot,x,goal):
    trajectory = np.array(x)
    while True:
        Robot.goal = goal
        u, predicted_trajectory, trayectorias_candidatas = Robot.dwa_control(x)
        x = Robot.motion(x, u)  # simulate robot
        print(x)
        trajectory = np.vstack((trajectory, x))  # store state history
        dist_to_goal = math.hypot(x[0] - Robot.goal[0], x[1] - Robot.goal[1])
        if dist_to_goal <= Robot.config.robot_radius:
            print("Goal!!")
            break


def main():
    Robot1 =  Robot(RobotType.rectangle)
    x = np.array([0.0, 0.0, math.pi / 8.0, 0.0, 0.0])
    goal = np.array([10.0, 10.0])
    #Robot1.run(x,goal)
    simulacion(Robot1,x,goal)

def SIMULACION(Robot, x , goal ):
           #Bucle de avance , mientras el objetivo no alcance la meta.
        Robot.goal = goal 
        trajectory = np.array(x)
        pygame.init()
        screen = pygame.display.set_mode((400,600))
        pygame.display.set_caption("Dynamic window approach")
        width_robot = 0.2
        length_robot = 1.2
        test_surface = pygame.Surface((length_robot, width_robot))
        test_surface.fill('Red')
        clock = pygame.time.Clock()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()
                # insertar la superficie en el display surface en la posición 0,0
                screen.blit(test_surface, (0,0))
                # actualiza todo el screen
                pygame.display.update()
                clock.tick(60)
        



if __name__ == '__main__':
    main()