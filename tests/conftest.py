import sys
import os
import importlib

# Add module dir to sys.path
module_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'SlicerAICopilot'))
if module_dir not in sys.path:
    sys.path.insert(0, module_dir)

# Import SlicerAICopilotLib and alias it as SlicerAICopilot for tests
import SlicerAICopilotLib
sys.modules['SlicerAICopilot'] = SlicerAICopilotLib

submodules = [
    'schemas', 'action_engine', 'file_manager', 'llm_client',
    'scene_manager', 'utils', 'validator', 'verification', 'chat_ui'
]

for name in submodules:
    try:
        mod = importlib.import_module(f'SlicerAICopilotLib.{name}')
        sys.modules[f'SlicerAICopilot.{name}'] = mod
        setattr(SlicerAICopilotLib, name, mod)
    except Exception as e:
        pass
