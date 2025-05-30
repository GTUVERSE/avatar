# Internally used, don't mind this.
KILL_THREADS = False

# Toggle this in order to view how your WebCam is being interpreted (reduces performance).
DEBUG = False

# Change UDP connection settings (must match Unity side)
USE_LEGACY_PIPES = False # Only supported on Windows (if True, use NamedPipes rather than UDP sockets)
HOST = '192.168.255.198'  # Local receiver IP (stays same)
PORT = 52733

# Output IP for sending processed data (can be different from HOST)
OUTPUT_HOST = '192.168.255.160'  # Change this to send to different IP

# Settings do not universally apply, not all WebCams support all frame rates and resolutions
CAM_INDEX = 0 # OpenCV2 webcam index, try changing for using another (ex: external) webcam.
USE_CUSTOM_CAM_SETTINGS = False
FPS = 60
WIDTH = 320
HEIGHT = 240

# [0, 2] Higher numbers are more precise, but also cost more performance. The demo video used 2 (good environment is more important).
MODEL_COMPLEXITY = 0

# List of input UDP ports for camera feeds
INPUT_PORTS = [52700, 52701, 52702, 52703, 52704, 52705, 52706, 52707]

# Function to get output port for a given input port
get_output_port = lambda input_port: input_port + 33

# Debug prefix for easy debug removal
DEBUG_PREFIX = 'DEBUG_'