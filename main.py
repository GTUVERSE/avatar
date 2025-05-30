# UDP server for multiple camera feeds
from body import BodyThread
import time
import global_vars
from sys import exit

# Input ports for camera feeds
INPUT_PORTS = [52700, 52701, 52702, 52703, 52704, 52705, 52706, 52707]

# Start a thread for each input port
threads = []
for input_port in INPUT_PORTS:
    output_port = input_port + 33  # Map to output port
    print(f"Starting thread for port {input_port} -> {output_port}")
    thread = BodyThread(input_port, output_port)
    thread.start()
    threads.append(thread)

try:
    i = input()
finally:
    print("Exiting...")
    global_vars.KILL_THREADS = True
    time.sleep(0.5)
    exit()