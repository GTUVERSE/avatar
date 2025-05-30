# MediaPipe Body - Optimized Version
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from clientUDP import ClientUDP
import cv2
import threading
import time
import global_vars
import struct
import socket
import numpy as np
from collections import deque

# Debug prefix for easy removal
DEBUG_PREFIX = "DEBUG_"

# Performance constants - Optimized
MAX_BUFFER_SIZE = 512 * 1024  # Reduced buffer size
PROCESS_WIDTH = 320  # Increased resolution for better accuracy
PROCESS_HEIGHT = 240
MAX_QUEUE_SIZE = 3  # Reduced queue size for lower latency

# Smoothing parameters
SMOOTHING_FACTOR = 0.7  # Higher = more smoothing
MIN_MOVEMENT_THRESHOLD = 0.001  # Ignore tiny movements

class FrameBuffer:
    def __init__(self, max_size=MAX_BUFFER_SIZE):
        self.buffer = bytearray()
        self.max_size = max_size

    def add(self, data):
        if len(self.buffer) + len(data) > self.max_size:
            self.clear()
        self.buffer.extend(data)

    def clear(self):
        self.buffer = bytearray()

class UDPFrameReceiver(threading.Thread):
    def __init__(self, port):
        super().__init__()
        self.port = port
        self.frame_queue = deque(maxlen=MAX_QUEUE_SIZE)
        self.isRunning = False
        self.daemon = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Optimize socket settings
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 512 * 1024)  # Reduced buffer
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(0.1)  # Add timeout to prevent hanging
        
        try:
            self.sock.bind((global_vars.HOST, self.port))
        except Exception as e:
            print(f"{DEBUG_PREFIX}Failed to bind to port {self.port}: {e}")
            return
            
        self.frame_buffer = FrameBuffer()
        self.frame_count = 0
        self.last_stats_time = time.time()
        print(f"{DEBUG_PREFIX}UDP receiver started on port {self.port}")

    def run(self):
        self.isRunning = True
        consecutive_timeouts = 0
        
        while not global_vars.KILL_THREADS and consecutive_timeouts < 50:  # Exit after 5 seconds of no data
            try:
                data, _ = self.sock.recvfrom(65536)
                consecutive_timeouts = 0  # Reset timeout counter
                
                if data.startswith(b'FRAME_START'):
                    self.frame_buffer.clear()
                elif data.startswith(b'FRAME_END'):
                    if len(self.frame_queue) < MAX_QUEUE_SIZE:
                        self.frame_queue.append(self.frame_buffer.buffer[:])
                    self.frame_buffer.clear()
                    self.frame_count += 1
                else:
                    self.frame_buffer.add(data)

                # Print stats less frequently
                if time.time() - self.last_stats_time >= 2:  # Every 2 seconds
                    fps = self.frame_count / 2
                    print(f"{DEBUG_PREFIX}Port {self.port}: {fps:.1f} FPS")
                    self.frame_count = 0
                    self.last_stats_time = time.time()

            except socket.timeout:
                consecutive_timeouts += 1
                continue
            except Exception as e:
                print(f"{DEBUG_PREFIX}UDP error on port {self.port}: {e}")
                consecutive_timeouts += 1
                
        self.sock.close()
        print(f"{DEBUG_PREFIX}UDP receiver stopped on port {self.port}")

    def get_frame(self):
        if not self.frame_queue:
            return None
        try:
            buffer = self.frame_queue.popleft()
            np_arr = np.frombuffer(buffer, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if frame is not None:
                # Resize for processing
                frame = cv2.resize(frame, (PROCESS_WIDTH, PROCESS_HEIGHT), interpolation=cv2.INTER_LINEAR)
            return frame
        except Exception as e:
            print(f"{DEBUG_PREFIX}Frame decode error on port {self.port}: {e}")
            return None

class LandmarkSmoother:
    def __init__(self, smoothing_factor=SMOOTHING_FACTOR):
        self.smoothing_factor = smoothing_factor
        self.previous_landmarks = None
        self.stable_landmarks = None
        self.movement_threshold = MIN_MOVEMENT_THRESHOLD

    def smooth(self, landmarks):
        if landmarks is None:
            return self.stable_landmarks

        current_landmarks = []
        for landmark in landmarks.landmark:
            current_landmarks.append([landmark.x, landmark.y, landmark.z])

        if self.previous_landmarks is None:
            self.previous_landmarks = current_landmarks
            self.stable_landmarks = current_landmarks
            return landmarks

        # Apply smoothing
        smoothed_landmarks = []
        for i, (curr, prev) in enumerate(zip(current_landmarks, self.previous_landmarks)):
            smoothed = []
            for j in range(3):  # x, y, z
                # Calculate movement
                movement = abs(curr[j] - prev[j])
                
                # Apply smoothing only if movement is significant
                if movement > self.movement_threshold:
                    smoothed_value = prev[j] * self.smoothing_factor + curr[j] * (1 - self.smoothing_factor)
                else:
                    smoothed_value = prev[j]  # Keep previous value for small movements
                    
                smoothed.append(smoothed_value)
            smoothed_landmarks.append(smoothed)

        self.previous_landmarks = smoothed_landmarks
        self.stable_landmarks = smoothed_landmarks

        # Create new landmark list with smoothed values
        smoothed_result = type(landmarks)()
        for i, smoothed_point in enumerate(smoothed_landmarks):
            landmark = smoothed_result.landmark.add()
            landmark.x = smoothed_point[0]
            landmark.y = smoothed_point[1]
            landmark.z = smoothed_point[2]

        return smoothed_result

class BodyThread(threading.Thread):
    def __init__(self, input_port, output_port):
        super().__init__()
        self.input_port = input_port
        self.output_port = output_port
        self.receiver = UDPFrameReceiver(self.input_port)
        self.client = ClientUDP(global_vars.HOST, self.output_port)
        self.smoother = LandmarkSmoother()
        
        # Performance monitoring
        self.frame_count = 0
        self.last_stats_time = time.time()
        self.processing_times = deque(maxlen=30)  # Keep last 30 processing times
        
        print(f"{DEBUG_PREFIX}Body thread started: {input_port} -> {output_port}")

    def run(self):
        mp_pose = mp.solutions.pose
        self.receiver.start()
        self.client.start()

        # Optimized pose settings
        with mp_pose.Pose(
            min_detection_confidence=0.6,  # Lowered for better performance
            min_tracking_confidence=0.5,
            model_complexity=0,  # Fastest model
            static_image_mode=False,
            enable_segmentation=False,
            smooth_landmarks=True  # Enable MediaPipe's built-in smoothing
        ) as pose:
            print(f"{DEBUG_PREFIX}Pose model started on port {self.input_port}")

            consecutive_failures = 0
            max_failures = 100  # Exit after too many failures

            while not global_vars.KILL_THREADS and consecutive_failures < max_failures:
                frame = self.receiver.get_frame()
                if frame is None:
                    time.sleep(0.001)  # Very short sleep
                    consecutive_failures += 1
                    continue

                consecutive_failures = 0  # Reset failure counter
                start_time = time.time()

                try:
                    # Process frame
                    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    image.flags.writeable = False  # Improve performance
                    results = pose.process(image)

                    if results.pose_world_landmarks:
                        # Apply custom smoothing
                        smoothed_landmarks = self.smoother.smooth(results.pose_world_landmarks)
                        
                        if smoothed_landmarks:
                            # Build data string more efficiently
                            data_parts = []
                            for i in range(33):  # 33 pose landmarks
                                landmark = smoothed_landmarks.landmark[i]
                                data_parts.append(f"{i}|{landmark.x:.6f}|{landmark.y:.6f}|{landmark.z:.6f}")
                            
                            data_string = "\n".join(data_parts) + "\n"
                            self.send_data(data_string)

                except Exception as e:
                    print(f"{DEBUG_PREFIX}Processing error on port {self.input_port}: {e}")
                    consecutive_failures += 1

                # Performance monitoring
                process_time = time.time() - start_time
                self.processing_times.append(process_time)
                self.frame_count += 1

                # Print stats less frequently
                if time.time() - self.last_stats_time >= 3:  # Every 3 seconds
                    avg_time = sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0
                    fps = self.frame_count / 3
                    print(f"{DEBUG_PREFIX}Port {self.input_port}: {fps:.1f} FPS, avg process: {avg_time*1000:.1f}ms")
                    self.frame_count = 0
                    self.last_stats_time = time.time()

        self.receiver.isRunning = False
        print(f"{DEBUG_PREFIX}Body thread stopped: {self.input_port}")

    def send_data(self, message):
        try:
            self.client.sendMessage(message)
        except Exception as e:
            print(f"{DEBUG_PREFIX}Send error on port {self.output_port}: {e}")