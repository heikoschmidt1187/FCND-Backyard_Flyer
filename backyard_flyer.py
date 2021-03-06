import argparse
import time
from enum import Enum

import numpy as np

from udacidrone import Drone
from udacidrone.connection import MavlinkConnection, WebSocketConnection  # noqa: F401
from udacidrone.messaging import MsgID


class States(Enum):
    MANUAL = 0
    ARMING = 1
    TAKEOFF = 2
    WAYPOINT = 3
    LANDING = 4
    DISARMING = 5


class BackyardFlyer(Drone):

    def __init__(self, connection):
        super().__init__(connection)
        self.target_position = np.array([0.0, 0.0, 0.0])
        self.all_waypoints = []
        self.in_mission = True
        self.check_state = {}

        # initial state
        self.flight_state = States.MANUAL

        # TODO: Register all your callbacks here
        self.register_callback(MsgID.LOCAL_POSITION, self.local_position_callback)
        self.register_callback(MsgID.LOCAL_VELOCITY, self.velocity_callback)
        self.register_callback(MsgID.STATE, self.state_callback)

    def local_position_callback(self):
        """
        This triggers when `MsgID.LOCAL_POSITION` is received and self.local_position contains new data
        """
        if self.flight_state == States.TAKEOFF:
            # check if target position is reached to some point and switch to
            # waypoint following mode
            if -1. * self.local_position[2] > 0.95 * self.target_position[2]:
                self.all_waypoints = self.calculate_box()
                self.waypoint_transition()
        elif self.flight_state == States.WAYPOINT:
            # check if current waypoint position has been reached - this is done by
            # calculating the Euclidian norm between target and local position
            if (np.linalg.norm(self.target_position[0:2] - self.local_position[0:2]) < 1.) and \
                (np.linalg.norm(self.local_velocity[0:2]) < 1.):
                # check if there are waypoints left
                if len(self.all_waypoints) > 0:
                    # get next waypoint as target position
                    self.waypoint_transition()
                else:
                    # transition to landing if the drone is hovering quite static
                    if np.linalg.norm(self.local_velocity[0:2]) < 1.:
                        self.landing_transition()

    def velocity_callback(self):
        """
        This triggers when `MsgID.LOCAL_VELOCITY` is received and self.local_velocity contains new data
        """

        # handle landing state finish hered
        if self.flight_state == States.LANDING:
            if self.global_position[2] - self.global_home[2] < 1:
                if abs(self.local_position[2]) < 0.01:
                    self.disarming_transition()

    def state_callback(self):
        """
        This triggers when `MsgID.STATE` is received and self.armed and self.guided contain new data
        """
        if not self.in_mission:
            return;
        elif self.flight_state == States.MANUAL:
            self.arming_transition()
        elif self.flight_state == States.ARMING:
            if self.armed:
                self.takeoff_transition()
        elif self.flight_state == States.DISARMING:
            if not self.armed and not self.guided:
                self.manual_transition()

    def calculate_box(self):
        print("Calculate box waypoints")

        # 20m to the left, 20m forward, 20 right, 20m back
        return[[20., 0., 3.], [20., 20., 3.], [0., 20., 3.], [0., 0., 3.]]

    def arming_transition(self):

        print("arming transition")

        # switch to controlled mode
        self.take_control()

        # switch drone on
        self.arm()

        # remember the current position as home position
        self.set_home_position(self.global_position[0],
                               self.global_position[1],
                               self.global_position[2])

        # set the new flight state
        self.flight_state = States.ARMING

    def takeoff_transition(self):

        print("takeoff transition")

        # set target position
        self.target_position[2] = 3.

        # command to takeoff
        self.takeoff(3.)

        # set new flight state
        self.flight_state = States.TAKEOFF

    def waypoint_transition(self):
        print("waypoint transition")

        # pop the next position
        self.target_position = self.all_waypoints.pop(0)

        # command drone to position
        self.cmd_position(self.target_position[0], self.target_position[1], self.target_position[2], 0.)

        # switch to waypoint flight state
        self.flight_state = States.WAYPOINT

    def landing_transition(self):
        print("landing transition")

        # landing command
        self.land()

        # switch state
        self.flight_state = States.LANDING

    def disarming_transition(self):
        print("disarm transition")

        # disarm drone
        self.disarm()

        # free the control
        self.release_control()

        # set new flight state
        self.flight_state = States.DISARMING

    def manual_transition(self):

        print("manual transition")

        self.release_control()
        self.stop()
        self.in_mission = False
        self.flight_state = States.MANUAL

    def start(self):
        print("Creating log file")
        self.start_log("Logs", "NavLog.txt")
        print("starting connection")
        self.connection.start()
        print("Closing log file")
        self.stop_log()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5760, help='Port number')
    parser.add_argument('--host', type=str, default='127.0.0.1', help="host address, i.e. '127.0.0.1'")
    args = parser.parse_args()

    conn = MavlinkConnection('tcp:{0}:{1}'.format(args.host, args.port), threaded=False, PX4=False)
    #conn = WebSocketConnection('ws://{0}:{1}'.format(args.host, args.port))
    drone = BackyardFlyer(conn)
    time.sleep(2)
    drone.start()
