"""Talk to a SixEyes arm over USB. Start with `Arm`."""
from ._protocol import JOINTS, PROTOCOL_VERSION, Capability, ControlSource, Fault, HomingState, State
from .session import Arm, ArmError

__all__ = ["Arm", "ArmError", "JOINTS", "PROTOCOL_VERSION", "Capability", "ControlSource", "Fault", "HomingState", "State"]
__version__ = "0.0.1"
