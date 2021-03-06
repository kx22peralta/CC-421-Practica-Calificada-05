import math
from enum import Enum
import numpy as np
import pygame
from pygame.transform import flip, scale, rotate, rotozoom
from sys import exit
import time
# Definiendo Colores
BLACK  = (   0,   0,   0)
WHITE  = ( 255, 255, 255)
GREEN  = (   0, 255,   0)
RED    = ( 255,   0,   0)
BLUE   = (   0,   0, 255)
# Mapa de ubicaciones
cadena=[]
cadena2 =[]
filename = 'Arena1.txt'
with open(filename) as f_obj:
    for line in f_obj:
        line = line.rstrip()
        cadena.append(line.split(','))
for i in cadena:
    i =list(map(lambda x :float(x),i))
    cadena2.append(i)

obstacleList =np.array(cadena2)

class RobotType(Enum):
    """ Clase para identicar la forma del robot """
    circle = 0
    rectangle = 1

class Config:
    """
    clase para la configuración del Robot
    """

    def __init__(self, pixel):
        # Parámetros del robot

        self.max_speed = 1.0 * pixel # velocidad máxima [m/s]
        self.min_speed = -0.5  * pixel # velocidad mínima [m/s]
        self.max_yaw_rate =  ( 40.0 * math.pi / 180.0)  # [rad/s]
        self.max_accel = 0.2  * pixel # [m/s]
        self.max_delta_yaw_rate = (40.0 * math.pi / 180.0 ) # [rad/ss]
        self.v_resolution = 0.01 * pixel # [m/s]
        self.yaw_rate_resolution = (0.1 * math.pi / 180.0)  # [rad/s]
        self.dt = 0.1  # [s] marca de tiempo para la predicción en movimiento
        self.predict_time = 2.0   # [s]
        self.to_goal_cost_gain = 0.15 * pixel 
        self.speed_cost_gain = 1.0 * pixel 
        self.obstacle_cost_gain = 1.0 * pixel*10
        self.robot_stuck_flag_cons = 0.001 * pixel # constante para probar que el robot se atasque.
        self.robot_type = RobotType.circle 

        # if robot_type == RobotType.circle
        #También se utiliza para comprobar si se alcanza el objetivo en ambos tipos
        self.robot_radius = 1  * pixel # [m] para control de colisión
        self.obs_radius = 0.5 * pixel
        # if robot_type == RobotType.rectangle
        self.robot_width = 1.2 * pixel# [m] para control de colisión
        self.robot_length = 2 * pixel # [m]para control de colisión
        self.ob = "vacio"

    @property
    def robot_type(self):
        return self._robot_type

    @robot_type.setter
    def robot_type(self, value):
        if not isinstance(value, RobotType):
            raise TypeError("robot_type debe ser una instania de RobotType")
        self._robot_type = value

""" Robots """
class Robot(pygame.sprite.Sprite):
    """ Se define la configuración inicial del robot :
    tipo , tamaño de los pixeles y la imagen """
    def __init__(self,robot_type, pixel = 10 ):
        super().__init__()
        self.config = Config(pixel)
        self.config.robot_type = robot_type
        self.auto = flip(scale(pygame.image.load("auto.png"), (int(self.config.robot_width), int(self.config.robot_length))), False, True)
      
    """ Movimiento del robot
    x : estado actual
    u : [velocidad, velocidad angular] """  
    def motion(self, x, u):
        x[2] += u[1] * self.config.dt
        x[0] += u[0] * math.cos(x[2]) * self.config.dt
        x[1] += u[0] * math.sin(x[2]) * self.config.dt
        x[3] = u[0]
        x[4] = u[1]
        return x

    """ Función que calcula la ventana dinamica y trayectorias, retorna el parametro 
    u : [velocidad, velocidad angular] optimas
    trajectory : trayectoria optima
    trayectorias_candidatas : trayectorias candidatas """
    def dwa_control(self, x):
        dw = self.calc_dynamic_window(x)
        u, trajectory , trayectorias_candidatas= self.calc_control_and_trajectory(x, dw)
        return u, trajectory, trayectorias_candidatas

    """  calculo del Venana Dinamica(Dynamic Window)
            x : estado actual
            config : configuraciones generales del robot (restricciones )
            retorna un espacio de velocidad y velocidades angulares """
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
    
    """ Predice una trayectoria desde la posición actual (x_init) hasta un tiempo predict_time con velocidad y velocidad angular dados (v,y) """
    def predict_trajectory(self, x_init, v, y):
        x = np.array(x_init)
        trajectory = np.array(x)
        time = 0
        while time <= self.config.predict_time:
            x = self.motion(x, [v, y])
            trajectory = np.vstack((trajectory, x))
            time += self.config.dt
        return trajectory
    
    """ Calcula las trayectorias para una posición x y una ventana dinamica dw
    retorna mejor par [velocidad, velocidad angular], mejor trayectoria y trayectorias candidatas. """
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
    
    """ Calcula el costo de los obstaculos mapeados se le pasa una trayectoria y se calcula si esta trayectoria colisiona en algún momento con un obstaculo.
    Si no hay obstaculos retorna = 0
    Si hay obstaculos y estos chocas retorna infinito 
    en otro caso retorna la inversa de la distancia al objeto."""
    def calc_obstacle_cost(self, trajectory):
        if( self.config.ob =="vacio" ): return 0
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
            """ Verificando si alguno llega a chocar al robot """
            upper_check = local_ob[:, 0] <= self.config.robot_length / 2
            right_check = local_ob[:, 1]  <= self.config.robot_width / 2
            bottom_check = local_ob[:, 0]  >= -self.config.robot_length / 2
            left_check = local_ob[:, 1]  >= -self.config.robot_width / 2
            if (np.logical_and(np.logical_and(upper_check, right_check),
                            np.logical_and(bottom_check, left_check))).any():
                return float("Inf")
        elif self.config.robot_type == RobotType.circle:
            if np.array(r <= self.config.robot_radius).any():
                return float("Inf")
    
        min_r = np.min(r)
        return 1.0 / min_r  # OK

    """Calculo del costo de meta de la trayectoria del ultimo momento (por eso escoge la ultima  fila de la matriz trayectoria, la trayectoria despues de predict_time instantes.) dependiendo el angulo"""
    def calc_to_goal_cost(self, trajectory):
        dx = self.goal[0] - trajectory[-1, 0]
        dy = self.goal[1] - trajectory[-1, 1]
        error_angle = math.atan2(dy, dx)
        cost_angle = error_angle - trajectory[-1, 2]
        cost = abs(math.atan2(math.sin(cost_angle), math.cos(cost_angle)))
        return cost
    
    """ Agrega los obstaculos a lista de obstaculos del robot """
    def add_ob(self,o):
        if(self.config.ob=="vacio"):
             self.config.ob = o
        else:
            self.config.ob=np.vstack((self.config.ob, o ))

    """ Resetea la lista de los obstaculos de los robot """
    def reset_ob(self):
        self.config.ob = "vacio"
    

""" Encontrando obstaculos """

""" Función que agrega puntos de muestra alrededor de un centro x,y """
def fun_puntos(arr, radio):
    x = int(arr[0])
    y = int(arr[1])
    radio = int(radio)
    matriz = np.array([ [x, y] ])
    for i in range(x-radio,x+radio+1):
        for j in range(y-radio,y+radio+1):
            matriz = np.vstack((matriz, [i, j] ))
    return matriz

""" Función que encuentra obstaculos  a un radio de tamaño :Large
Esta función agrega obstaculos desde un centro x,y y los agrega a la lista del Robot. """
def encontrar_obstaculos(Robot,x,y,large):
    ox = obstacleList[: , 0]
    oy = obstacleList[:, 1]
    dx = x - ox[:, None]
    dy = y - oy[:, None]
    r = np.hypot(dx, dy)
    for ind,r in zip(range(r.shape[0]),r):
        if(r<large):
            muestraobstaculos = fun_puntos( obstacleList[ind] ,Robot.config.obs_radius)
            Robot.add_ob(muestraobstaculos)
    

""" Dibujos """    

def dibuja_trayectorias(x,trayectorias_candidatas, screen):
    for trayectoria in trayectorias_candidatas:
        pygame.draw.line(screen,BLACK, (x[0],x[1]), (trayectoria[-1,0],trayectoria[-1,1]), width=1)

def dibuja_trayectoria(x,predicted_trajectory,screen):
    pygame.draw.line(screen,RED ,(x[0],x[1]), (predicted_trajectory[-1,0],predicted_trajectory[-1,1]),2)

def dibujar_trayectoria_completa(screen,trayectoria):
    coord = trayectoria[:,0:2]
    for coord_init,coord_finish in zip(coord[:-1,], coord [1:,]):
       pygame.draw.line(screen,RED,(coord_init[0],coord_init[1]), (coord_finish[0],coord_finish[1]), width=2); 

def dibuja_obstaculos(ob, screen,tam):
    for i in range(ob.shape[0]):
        obstaculo1=scale(pygame.image.load("arbusto.png").convert_alpha(), (int(tam), int(tam)))
        screen.blit(obstaculo1, obstaculo1.get_rect( center=(ob[i][0], ob[i][1])))     
        
def dibuja_meta(goal,screen,tam):
    meta=scale(pygame.image.load("inicio-fin.png").convert_alpha(), (int(tam), int(tam)))
    screen.blit(meta, meta.get_rect(center=(goal[0],goal[1])))

""" Halla el angulo de rotación en grados """
def find_rotation_degrees(radians):
    degree = (radians * (180 / 3.1415) * -1) + 90
    return degree

""" Método para determinar cuántos radianes rotar la imagen del jugador """
def find_rotation_radians(mouse_X, mouse_Y, center_X, center_Y):
    radians = math.atan2(mouse_Y - center_Y, mouse_X - center_X)
    return radians

# Simulación del juego
def SIMULACION(Robot, x , goal):
    Robot.goal = goal # personaje (jugador)
    trajectory = np.array(x) # trayectoria
    pygame.init() # Inicializando Pygame
    clock = pygame.time.Clock() # Función tiempo para controlar FPS
    screen = pygame.display.set_mode((800, 650)) # Tamaño de ventana del juego
    icono = pygame.image.load("icono.png") # Ícono del juego
    pygame.display.set_icon(icono)
    pygame.display.set_caption("Auto inteligente") # Título del juego
    trayectoria_completa = 0
    movement = True
    inicio = time.time()
    while True:
        # Evento para salir de la simulación
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
        if movement:
            encontrar_obstaculos(Robot,x[0],x[1],100)
            u, predicted_trajectory, trayectorias_candidatas = Robot.dwa_control(x)
            x = Robot.motion(x, u)  # Nuevo estado del robot
            """ print(x) """
            trajectory = np.vstack((trajectory, x))  # guardando estado
            dist_to_goal = math.hypot(x[0] - Robot.goal[0], x[1] - Robot.goal[1])
            if dist_to_goal <= Robot.config.robot_radius:
                print("Goal!!")
                fin = time.time()
                print("El robot tarda :",fin-inicio,  " segundos.")
                movement = False
                trayectoria_completa = trajectory
        
        ##############--------ZONA DE DIBUJO------##########################################################
        screen.fill('gray') # Pintando la ventana dinámica
        # screen.blit(rotate(Robot.auto, x[3]),rotate(Robot.auto, x[3]).get_rect( center=(int(x[0]), int(x[1])))) # dibunjando el robot
        if not(movement):
            dibujar_trayectoria_completa(screen,trayectoria_completa)
        dibuja_meta(goal, screen, Robot.config.obs_radius) # Ubicación de la meta
        dibuja_obstaculos(obstacleList, screen, Robot.config.obs_radius) # Ubicando obstáculos
        """ dibuja_trayectorias(x, trayectorias_candidatas, screen) """
        dibuja_trayectoria(x, predicted_trajectory, screen)
        # Obteniendo variables para la rotación
        radians = find_rotation_radians(predicted_trajectory[-1,0], predicted_trajectory[-1,1], x[0], x[1])
        degrees = find_rotation_degrees(radians)
        playerImgRotated = pygame.transform.rotate(Robot.auto, degrees)
        # Ubicando al jugador 
        screen.blit(playerImgRotated,playerImgRotated.get_rect(center=(x[0],x[1])))
        #####################################################################################################
        Robot.reset_ob()
        pygame.display.update()
        clock.tick(60)


""" Función principal """
def main():
    Robot1 =  Robot(RobotType.circle,20)
    x = np.array([10.0, 10.0, math.pi / 8.0, 0.0, 0.0])
    goal = np.array([500.0, 500.0])
    SIMULACION(Robot1,x,goal)

if __name__ == '__main__':
    main()