# state_orient.py


# ++++++++++++++ Imports/Installs ++++++++++++++ #
import math
import asyncio
from lib.pysquared.sensor_reading.light import Light
from lib.pysquared.hardware.light_sensor.manager.veml7700 import VEML7700Manager

# ++++++++++++++ Functions: Helper ++++++++++++++ #
class StateOrient:
    def __init__(self, dp_obj, logger, tca, rx0, rx1, tx0, tx1):
        """
        Initialize the class object
        """
        self.dp_obj = dp_obj
        self.logger = logger
        self.tca = tca
        self.running = False
        self.done = False
        self.rx0 = rx0
        self.rx1 = rx1
        self.tx0 = tx0
        self.tx1 = tx1

        try:
            self.face0_sensor = VEML7700Manager(logger, tca[0])
        except Exception:
            self.logger.debug("[WARNING] Light sensor 0 failed to initialize")
        try:
            self.face1_sensor = VEML7700Manager(logger, tca[1])
        except Exception:
            self.logger.debug("[WARNING] Light sensor 1 failed to initialize")
        try:
            self.face2_sensor = VEML7700Manager(logger, tca[2])
        except Exception:
            self.logger.debug("[WARNING] Light sensor 2 failed to initialize")
        try:
            self.face3_sensor = VEML7700Manager(logger, tca[3])
        except Exception:
            self.logger.debug("[WARNING] Light sensor 3 failed to initialize")

    def vector_mul_scalar(self, v, scalar):
        """ Multiply two vectors by a scalar. """
        return [v[0] * scalar, v[1] * scalar]
    
    def vector_add(self, v1, v2):
        """ Add two vectors. """
        return [v1[0]+v2[0], v1[1]+v2[1]]
    
    def vector_norm(self, v):
        """ Get the norm of a vector. """
        return math.sqrt(v[0]**2 + v[1]**2)
    
    def dot_product(self, v1, v2):
        """ Compute dot product between two vectors. """
        return v1[0]*v2[0] + v1[1]*v2[1]

    async def run(self):
        """
        Run the deployment sequence asynchronously
        """
        self.running = True
        while self.running:
            await asyncio.sleep(2)

            # step 1: get light readings
            # lights: [scalar, scalar, scalar, scalar]
            try:
                light1 = self.face0_sensor.get_light()
                light2 = self.face1_sensor.get_light()
                light3 = self.face2_sensor.get_light()
                light4 = self.face3_sensor.get_light()
                lights = [light1, light2, light3, light4]
            # if fail, set all to 0
            except Exception as e:
                self.logger.error(f"Failed to read light sensors: {e}")
                lights = [Light(0.0), Light(0.0), Light(0.0), Light(0.0)]

            # step 2: create light vectors
            # light_vec: [v1, v2, v3, v4]
            pos_xvec = [1, 0]
            neg_xvec = [-1, 0]
            pos_yvec = [0, 1]
            neg_yvec = [0, -1]
            lightvecs = [pos_xvec, neg_xvec, pos_yvec, neg_yvec]

            # step 3: weight the light vectors by the light reading
            light_vec = [[0.0, 0.0] for _ in range(4)]
            for i in range(4):
                light_vec[i] = self.vector_mul_scalar(lightvecs[i], lights[i]._value)

            # step 4: compute the norm sum of the weighted light vectors, net_vec is the sun vector magnitude
            # lightvecs is list of vectors, lights is list of scalars
            weighted_vecs = [self.vector_mul_scalar(lightvecs[i], lights[i]) for i in range(4)]
            net_vec = [0.0, 0.0]
            for v in weighted_vecs:
                net_vec = self.vector_add(net_vec, v)

            # step 5: determine all the directions from which to pull
            # either right, left, north south or combinations of corners
            inv_sqrt2 = 1 / math.sqrt(2)
            point_vecs = [
                [1,0], [-1,0], [0,1], [0,-1],
                [inv_sqrt2, inv_sqrt2], [inv_sqrt2, -inv_sqrt2],
                [-inv_sqrt2, inv_sqrt2], [-inv_sqrt2, -inv_sqrt2]
            ]
            
            # step 6: find best alginment
            # find maximum dot product between net_vec and point_vecs
            max_dot_product = -float('inf')
            best_direction = 0
            for i in range(8):
                dot_product = sum([a * b for a, b in zip(net_vec, point_vecs[i])])
                if dot_product > max_dot_product:
                    max_dot_product = dot_product
                    best_direction = i

            # step 7: log the results
            self.logger.info(f"Sun vector: {net_vec}")
            self.logger.info(f"Best direction: {best_direction}, Alignment: {max_dot_product:.3f}")
            
            # activate the spring corresponding to best_direction
            # TODO: Implement actual spring activation based on best_direction
            # Direction mapping:
                # 0: +X
                # 1: -X
                # 2: +Y
                # 3: -Y
                # 4: +X+Y diagonal
                # 5: +X-Y diagonal  
                # 6: -X+Y diagonal
                # 7: -X-Y diagonal
            if best_direction == -1:
                    self.logger.info("No current through any springs")
                    self.rx0.value = False
                    self.rx1.value = False
                    self.tx0.value = False
                    self.tx1.value = False
            if best_direction == 0:
                    self.logger.info("Activating +X spring")
                    self.rx0.value = True
                    self.rx1.value = False
                    self.tx0.value = False
                    self.tx1.value = False
            if best_direction == 1:
                    self.logger.info("Activating -X spring")
                    self.rx0.value = False
                    self.rx1.value = True
                    self.tx0.value = False
                    self.tx1.value = False
            if best_direction == 2:
                    self.logger.info("Activating +Y spring")
                    self.rx0.value = False
                    self.rx1.value = False
                    self.tx0.value = True
                    self.tx1.value = False
            if best_direction == 3:
                    self.logger.info("Activating -Y spring")
                    self.rx0.value = False
                    self.rx1.value = False
                    self.tx0.value = False
                    self.tx1.value = True
            if best_direction == 4:
                    self.logger.info("Activating +X+Y diagonal spring")
                    self.rx0.value = True
                    self.rx1.value = False
                    self.tx0.value = True
                    self.tx1.value = False
            if best_direction == 5:
                    self.logger.info("Activating +X-Y diagonal spring")
                    self.rx0.value = True
                    self.rx1.value = False
                    self.tx0.value = False
                    self.tx1.value = True
            if best_direction == 6:
                    self.logger.info("Activating -X+Y diagonal spring")
                    self.rx0.value = False
                    self.rx1.value = True
                    self.tx0.value = True
                    self.tx1.value = False
            if best_direction == 7:
                    self.logger.info("Activating -X-Y diagonal spring")
                    self.rx0.value = False
                    self.rx1.value = False
                    self.tx0.value = True
                    self.tx1.value = True

    def stop(self):
        """
        Used by FSM to manually stop run()
        """
        self.running = False

    def is_done(self):
        """
        Checked by FSM to see if the run() completed on its own
        If it did complete, it shuts down the async task run()
        """
        return self.done