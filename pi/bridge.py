#!/usr/bin/env python3
# 树莓派端桥接：读取 OpenMV 的 USB 串口 MJPEG 流，编码成 H.264 后
# 同时推给【本地 MediaMTX】和【云端 MediaMTX】。
# 每个目标独立线程，卡死/掉线会自动重启该目标，互不影响。
#
# 依赖：  sudo apt install -y python3-serial ffmpeg
# 用法：  python3 bridge.py [串口] [本地RTSP] [云端RTMP]

import sys
import time
import queue
import threading
import subprocess

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
LOCAL = sys.argv[2] if len(sys.argv) > 2 else "rtsp://127.0.0.1:8554/cam"
REMOTE = sys.argv[3] if len(sys.argv) > 3 else "rtmp://<云端IP>:1935/cam?user=pusher&pass=<推流密码>"
BAUD = 115200

TARGETS = [
    ["-f", "rtsp", "-rtsp_transport", "tcp", LOCAL],
    ["-f", "flv", REMOTE],
]

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
VF = ("drawtext=fontfile=" + FONT +
      ":text='%{localtime\\:%Y-%m-%d %H-%M-%S}'"
      ":x=12:y=12:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.5")

BASE = [
    "ffmpeg", "-hide_banner", "-loglevel", "warning",
    "-fflags", "nobuffer",
    "-f", "mjpeg", "-i", "-",
    "-vf", VF,
    "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
    "-pix_fmt", "yuv420p", "-g", "15", "-b:v", "1200k",
]


class Target(threading.Thread):
    def __init__(self, target):
        super().__init__(daemon=True)
        self.cmd = BASE + target
        self.name = target[-1]
        self.q = queue.Queue(maxsize=60)
        self.lock = threading.Lock()
        self.proc = None
        self.strikes = 0
        self._spawn()

    def _spawn(self):
        self.proc = subprocess.Popen(self.cmd, stdin=subprocess.PIPE, bufsize=0)
        self.strikes = 0
        self.spawn_t = time.time()

    def feed(self, data):
        try:
            self.q.put_nowait(data)
            self.strikes = 0
            return
        except queue.Full:
            pass
        # 启动宽限期：给 ffmpeg 建连时间，期间满了就丢帧，不算卡死
        if time.time() - self.spawn_t < 20:
            self.strikes = 0
            return
        self.strikes += 1
        if self.strikes >= 10:
            print("[bridge] %s stalled, restarting" % self.name, file=sys.stderr)
            try:
                self.proc.kill()
            except Exception:
                pass
            while True:
                try:
                    self.q.get_nowait()
                except queue.Empty:
                    break
            self.strikes = 0

    def run(self):
        while True:
            try:
                data = self.q.get(timeout=2)
            except queue.Empty:
                data = None

            p = self.proc
            if p is None or p.poll() is not None:
                with self.lock:
                    if self.proc is None or self.proc.poll() is not None:
                        self._spawn()
                    p = self.proc

            if data is None:
                continue
            try:
                p.stdin.write(data)
            except Exception:
                pass


def main():
    targets = [Target(t) for t in TARGETS]
    for t in targets:
        t.start()

    while True:
        try:
            ser = serial.Serial(PORT, BAUD, timeout=5)
        except Exception as exc:
            print("[bridge] serial open failed: %s" % exc, file=sys.stderr)
            time.sleep(2)
            continue

        print("[bridge] serial open, streaming to %d targets" % len(targets),
              file=sys.stderr)
        try:
            while True:
                data = ser.read(8192)
                if not data:
                    continue
                for t in targets:
                    t.feed(data)
        except Exception as exc:
            print("[bridge] serial error: %s" % exc, file=sys.stderr)
            try:
                ser.close()
            except Exception:
                pass
            time.sleep(1)


if __name__ == "__main__":
    main()
