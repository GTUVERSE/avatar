# friend_camera.py - Arkadaşlarınız için basit kamera client'ı
import sys
import cv2
import websockets
import asyncio
import json
import base64
import time


class FriendCameraClient:
    def __init__(self, server_ip="192.168.1.100", username=None):
        # Arkadaşlarınız sadece sizin IP'nizi yazacak
        self.server_uri = f"ws://{server_ip}:52733"
        self.username = username or input("Adınızı girin: ").strip() or f"User_{time.time():.0f}"

        # Kamera ayarları
        if sys.platform == "darwin":
            self.backend = cv2.CAP_AVFOUNDATION
        elif sys.platform.startswith("win"):
            self.backend = cv2.CAP_DSHOW
        else:
            self.backend = cv2.CAP_V4L2

        self.cap = None

    def _find_camera(self):
        """Kamerayı bul ve aç"""
        print(f"🎥 {self.username} için kamera aranıyor...")

        for camera_index in range(4):
            cap = cv2.VideoCapture(camera_index, self.backend)
            if cap.isOpened():
                print(f"✅ Kamera bulundu (index {camera_index})")
                self.cap = cap
                return True
            cap.release()

        print("❌ Kamera bulunamadı!")
        return False

    def _setup_camera(self):
        """Kamerayı ayarla"""
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = self.cap.get(cv2.CAP_PROP_FPS)

        print(f"📹 Kamera ayarlandı: {w}×{h} @ {fps:.1f} FPS")

    async def connect_and_stream(self):
        """Sunucuya bağlan ve stream başlat"""
        if not self._find_camera():
            return

        self._setup_camera()

        print(f"🔗 {self.username} sunucuya bağlanıyor: {self.server_uri}")

        try:
            async with websockets.connect(
                    self.server_uri,
                    ping_interval=30,
                    ping_timeout=10
            ) as ws:

                # Kayıt ol
                registration = {
                    "type": "camera_feed",
                    "username": self.username
                }
                await ws.send(json.dumps(registration))

                # Kayıt yanıtını al
                response = await ws.recv()
                data = json.loads(response)

                if "error" in data:
                    print(f"❌ Kayıt başarısız: {data['error']}")
                    return

                user_id = data.get("user_id", "unknown")
                color = data.get("color", "#FF6B6B")

                print(f"✅ {self.username} başarıyla kaydedildi!")
                print(f"   👤 Kullanıcı ID: {user_id}")
                print(f"   🎨 Renk: {color}")
                print(f"   📡 Sunucuya bağlandı, streaming başlıyor...")

                frame_count = 0
                start_time = time.time()
                last_info_time = time.time()

                # Ana streaming döngüsü
                while True:
                    ret, frame = self.cap.read()
                    if not ret:
                        print("⚠️  Kameradan frame alınamadı")
                        break

                    # Kullanıcı bilgisini frame'e ekle
                    self._add_user_info(frame, self.username, user_id, color)

                    # Frame'i encode et
                    ok, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if not ok:
                        continue

                    # Sunucuya gönder
                    payload = {
                        "type": "frame",
                        "frame": base64.b64encode(buffer).decode('ascii'),
                        "timestamp": time.time(),
                        "frame_number": frame_count
                    }

                    await ws.send(json.dumps(payload))
                    frame_count += 1

                    # Bilgi göster
                    current_time = time.time()
                    if current_time - last_info_time >= 5.0:
                        elapsed = current_time - start_time
                        avg_fps = frame_count / elapsed
                        print(f"📈 {self.username}: {frame_count} frame gönderildi, ortalama {avg_fps:.1f} FPS")
                        last_info_time = current_time

                    # Frame rate kontrolü
                    await asyncio.sleep(1 / 30)

        except websockets.exceptions.ConnectionClosed:
            print(f"🔌 {self.username}: Sunucu bağlantısı kesildi")
        except websockets.exceptions.InvalidURI:
            print(f"❌ {self.username}: Geçersiz sunucu adresi: {self.server_uri}")
            print("💡 Sunucu IP adresini kontrol edin!")
        except Exception as e:
            print(f"❌ {self.username}: Hata oluştu: {e}")
        finally:
            if self.cap:
                self.cap.release()
                print(f"📷 {self.username}: Kamera kapatıldı")

    def _add_user_info(self, frame, username, user_id, color):
        """Frame'e kullanıcı bilgisi ekle"""
        # Rengi BGR formatına çevir
        color_bgr = self._hex_to_bgr(color)

        # Arka plan kutusu
        cv2.rectangle(frame, (10, 10), (300, 70), (0, 0, 0), -1)
        cv2.rectangle(frame, (10, 10), (300, 70), color_bgr, 2)

        # Yazıları ekle
        cv2.putText(frame, username, (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(frame, f"ID: {user_id}", (20, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        # Bağlantı durumu
        cv2.circle(frame, (280, 30), 8, color_bgr, -1)

    def _hex_to_bgr(self, hex_color):
        """Hex rengi BGR'ye çevir"""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6:
            return (255, 255, 255)

        try:
            rgb = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
            return (rgb[2], rgb[1], rgb[0])  # BGR formatı
        except:
            return (255, 255, 255)


async def main():
    print("=== 📷 Avatar Kamera Client'ı ===")
    print("Sunucuya bağlanarak kameranızı paylaşır")
    print()

    # Sunucu IP'sini al
    server_ip = input("Sunucu IP adresini girin (örn: 192.168.1.100): ").strip()
    if not server_ip:
        server_ip = "192.168.1.100"  # Varsayılan

    # Kullanıcı adını al
    username = input("Adınızı girin: ").strip()
    if not username:
        username = f"User_{int(time.time()) % 10000}"

    print(f"👤 Kullanıcı: {username}")
    print(f"🌐 Sunucu: {server_ip}")
    print()

    # Client'ı başlat
    client = FriendCameraClient(server_ip, username)
    await client.connect_and_stream()


if __name__ == "__main__":
    print("🎬 Kamera Client'ı başlatılıyor...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Kullanıcı tarafından durduruldu")
    except Exception as e:
        print(f"❌ Kritik hata: {e}")
    finally:
        print("👋 Kamera client'ı kapatıldı")