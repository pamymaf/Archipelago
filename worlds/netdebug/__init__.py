
from worlds.LauncherComponents import Component, components, Type, launch_subprocess


def launch_client():
    from .NetDebugClient import launch as TCMain
    launch_subprocess(TCMain, name="Network debug client")

class NetDebugWorld:
    pass

components.append(Component("NetDebug", None, func=launch_client, component_type=Type.CLIENT))