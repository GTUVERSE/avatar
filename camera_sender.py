import cv2
import socket
import time
import global_vars

# Maximum size per UDP packet (safe limit)
MAX_UDP_PACKET_SIZE = 65000

# UDP sender for camera frames
def send_camera_frames():
    cap = cv2.VideoCapture(global_vars.CAM_INDEX)
    if global_vars.USE_CUSTOM_CAM_SETTINGS:
        cap.set(cv2.CAP_PROP_FPS, global_vars.FPS)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, global_vars.WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, global_vars.HEIGHT)
    print(f"{global_vars.DEBUG_PREFIX}Camera opened at {cap.get(cv2.CAP_PROP_FPS)} fps")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    targets = [
               ("192.168.255.160", 52700),
               ]  # Example IP address of your friend

    print(f"{global_vars.DEBUG_PREFIX}UDP sender targeting {targets}")

    try:
        while not global_vars.KILL_THREADS:
            ret, frame = cap.read()
            if not ret:
                print(f"{global_vars.DEBUG_PREFIX}Failed to capture frame")
                continue

            _, jpeg = cv2.imencode('.jpg', frame)
            data = jpeg.tobytes()

            for target in targets:
                sock.sendto(b'FRAME_START', target)

            # Send data in chunks to all targets
            for i in range(0, len(data), MAX_UDP_PACKET_SIZE):
                chunk = data[i:i + MAX_UDP_PACKET_SIZE]
                for target in targets:
                    sock.sendto(chunk, target)

            for target in targets:
                sock.sendto(b'FRAME_END', target)

            print(f"{global_vars.DEBUG_PREFIX}Sent frame to all targets in {len(data) // MAX_UDP_PACKET_SIZE + 1} chunks (total {len(data)} bytes)")

            time.sleep(0.01)  # Adjust as needed

    finally:
        cap.release()
        sock.close()
        print(f"{global_vars.DEBUG_PREFIX}Camera sender stopped")

send_camera_frames()
