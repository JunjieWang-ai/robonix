#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
"""Relay a plain Twist on /cmd_vel into the Jazzy diffdrive's stamped input.

Jazzy's ros2_control DiffDriveController subscribes ~/cmd_vel expecting
geometry_msgs/msg/TwistStamped, and it builds that fully-qualified topic
name itself — launch remappings no longer reach it. Everything upstream
(nav2's velocity chain, the velocity guard, the chassis capability,
teleop) publishes geometry_msgs/msg/Twist on /cmd_vel, so this relay
keeps the whole graph on the plain-Twist contract and adapts at the one
seam only. Stamps follow the node clock (sim time under use_sim_time).

Run only on ROS_DISTRO in {rolling, jazzy, kilted}; on Humble the
controller takes a plain Twist directly (use_stamped_vel: false).
"""
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TwistStamped


class TwistStampedRelay(Node):
    """/cmd_vel (Twist) -> ~/cmd_vel_relayed (TwistStamped) one-seam adapter."""

    def __init__(self) -> None:
        super().__init__('twist_stamped_relay')
        self.declare_parameter('out_topic', '/diffdrive_controller/cmd_vel')
        out = self.get_parameter('out_topic').value
        self.sub = self.create_subscription(Twist, '/cmd_vel', self.on_twist, 10)
        self.pub = self.create_publisher(TwistStamped, out, 10)

    def on_twist(self, msg: Twist) -> None:
        stamped = TwistStamped()
        stamped.header.stamp = self.get_clock().now().to_msg()
        stamped.twist = msg
        self.pub.publish(stamped)


def main() -> None:
    rclpy.init()
    rclpy.spin(TwistStampedRelay())


if __name__ == '__main__':
    main()
