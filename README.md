# 轻量级远程视频监控系统（OpenMV + 树莓派 + 阿里云 + Android）

> 一套从「摄像头采集」到「手机 App 远程观看」的完整、低成本、可自托管的视频监控链路。
> 目标：把 **OpenMV → 树莓派 → 云端中转 → Android App** 这条链路完整打通，支持约 10 人/多设备观看，并且开机能自启动、掉线能自愈。

---

## 目录

- [1. 项目简介](#1-项目简介)
- [2. 系统架构](#2-系统架构)
- [3. 硬件清单](#3-硬件清单)
- [4. 软件与技术栈](#4-软件与技术栈)
- [5. 目录结构](#5-目录结构)
- [6. 搭建步骤](#6-搭建步骤)
  - [6.1 OpenMV 端](#61-openmv-端)
  - [6.2 树莓派端](#62-树莓派端)
  - [6.3 阿里云服务器端](#63-阿里云服务器端)
  - [6.4 Android App](#64-android-app)
- [7. 网络诊断与发现](#7-网络诊断与发现cgnat--ipv6)
- [8. 关键技术实现](#8-关键技术实现)
- [9. 使用与观看](#9-使用与观看)
- [10. 成本](#10-成本)
- [11. 已知问题与踩坑记录](#11-已知问题与踩坑记录)
- [12. 附录：完整配置与命令](#12-附录完整配置与命令)

---

## 1. 项目简介

### 需求
- 用 **OpenMV 摄像头** + **树莓派 4B** 搭建一个轻量级监控系统；
- 规模很小，约 **10 人**观看；
- 最终目的：**手机 App 上能看到监控画面**（带时间水印），最好在外面用流量也能看。

### 最终实现
- OpenMV 通过 USB 把 JPEG 帧送到树莓派；
- 树莓派用 `ffmpeg` 编码成 H.264，并叠加**真实时间水印**，同时推给：
  - 本地 MediaMTX（局域网近零延迟观看）；
  - 云端 MediaMTX（公网中转，给远程用户看）；
- 云端提供 **WebRTC（低延迟，< 1s）** 与 **HLS（兼容性最好）** 两种观看方式；
- Android App 内嵌 WebRTC 播放页，装上即看，可分发安装包给朋友；
- 树莓派与云端均配置 **systemd 开机自启**，并做了**掉线自愈**。

---

## 2. 系统架构

```
                        USB (MJPEG over CDC)
   [OpenMV Cam H7 Plus] ──────────────────────┐
                                               ▼
                                        [树莓派 4B]
                                    bridge.py (pyserial)
                                               │
                                     ffmpeg: 解码JPEG → H.264
                                       + drawtext 时间水印
                                               │
                        ┌──────────────────────┴───────────────────────┐
                        ▼                                               ▼
         [本地 MediaMTX]                                    RTMP 推流 (经公网)
       RTSP :8554 / HLS :8888                                       │
       WebRTC :8889（局域网）                                        ▼
                                                          [阿里云 ECS · 香港]
                                                             MediaMTX (中转)
                                                        ┌────────────┴────────────┐
                                                        ▼                         ▼
                                                 WebRTC :8889                 HLS :8888
                                                 （Android App，<1s）        （浏览器 / VLC）
```

- **就近观看**：局域网内可直接看树莓派的本地流，延迟最低、不占公网流量。
- **远程观看**：经云端中转，任何人任何网络（含 4G/5G）都能看。
- **协议选择**：WebRTC 负责低延迟实时观看；HLS 负责最大兼容性。

---

## 3. 硬件清单

| 设备 | 型号 / 规格 | 用途 |
|---|---|---|
| 摄像头 | **OpenMV Cam H7 Plus（R3）**（STM32H743 + OV5640 5MP，4.3mm 镜头） | 图像采集、JPEG 压缩 |
| 主控/网关 | **Raspberry Pi 4 Model B Rev 1.5，8GB** | 读取摄像头、编码、推流、本地分发 |
| 存储 | microSD 卡 16GB+（建议 A1/A2，长期运行建议 USB 启动） | 系统盘 |
| 电源 | **5V/3A 及以上** 的优质电源（重要，见踩坑） | 树莓派供电 |
| 摄像头连接 | 优质短 USB 数据线，建议**直插树莓派**，避免劣质 USB Hub | OpenMV 供电/数据 |
| 云端 | 阿里云 ECS（香港）2 vCPU / 2 GiB / 40 GiB | 公网中转 |
| 客户端 | 任意 Android 手机 | 观看 |

> 说明：OpenMV 的 **USB 供电稳定性**是整套系统的关键，务必使用好电源、好线材、直插主板。

---

## 4. 软件与技术栈

| 环节 | 软件 / 技术 |
|---|---|
| 摄像头固件/脚本 | OpenMV IDE 5.0.0 + OpenMV MicroPython |
| 摄像头推流 | MicroPython `sensor` + `img.compress()` + `pyb.USB_VCP` |
| 树莓派系统 | Raspberry Pi OS / Debian 13 (trixie) 64-bit |
| 串口读取 | Python 3 + `pyserial` |
| 视频编码 | `ffmpeg`（libx264, ultrafast, zerolatency） |
| 时间水印 | ffmpeg `drawtext` 滤镜 |
| 流媒体服务 | **MediaMTX v1.21.2**（RTSP / RTMP / HLS / WebRTC 一体化） |
| 服务托管 | systemd |
| 云端 | 阿里云 ECS（Ubuntu 22.04 LTS） |
| 手机端 | Flutter 3.44 + `webview_flutter`（内嵌 WebRTC 播放页） |

---

## 5. 目录结构

```
monitor-system/
├── openmv/
│   └── main.py            # OpenMV 端：采集 + JPEG + USB 发送
├── pi/
│   ├── bridge.py          # 树莓派端：串口 → ffmpeg → 本地+云端
│   ├── mediamtx.yml       # （可选）本地 MediaMTX 配置
│   ├── mediamtx.service   # 本地 MediaMTX 开机自启
│   └── bridge.service     # 桥接服务开机自启
└── cloud/
    ├── mediamtx.yml       # 云端 MediaMTX 配置（含鉴权、WebRTC、LL-HLS）
    └── mediamtx.service   # 云端 MediaMTX 开机自启

monitor-app/               # 独立的 Flutter 安卓工程（另见 6.4）
└── lib/main.dart          # WebView 内嵌 WebRTC 播放页
```

---

## 6. 搭建步骤

### 6.1 OpenMV 端

**目标**：让摄像头开机自动把画面以 JPEG 连续输出到 USB 串口。

1. 安装 **OpenMV IDE**（<https://openmv.io/pages/download>），连接摄像头，识别为 **OpenMV Cam H7 Plus**。
2. 需要时用 `工具 → 安装最新固件` 刷入对应固件（H7 Plus 对应 `OPENMV4P`）。
3. 把下面的脚本保存到摄像头（`工具 → 将打开的脚本保存到OpenMV Cam (作为main.py)`）：

`openmv/main.py`：

```python
# OpenMV Cam H7 Plus - USB 直连 MJPEG 发送
# 通过 USB 虚拟串口 (ttyACM0) 连续输出 JPEG 帧（首尾相连），
# 树莓派端 ffmpeg 用 -f mjpeg 可直接解析。
# 注意：不要用 print()，CDC 与 REPL 共用通道会污染视频流。

import sensor
from pyb import USB_VCP

usb = USB_VCP()

sensor.reset()
sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.VGA)          # 640x480；想更流畅可改 QVGA
sensor.skip_frames(time=2000)
sensor.set_auto_gain(True)
sensor.set_auto_whitebal(True)

QUALITY = 60

while True:
    img = sensor.snapshot()
    jpg = img.compress(quality=QUALITY)
    usb.send(jpg)
```

> 实测：VGA(640×480)、JPEG 质量 60，约 25 FPS，单帧约 23KB。

---

### 6.2 树莓派端

**目标**：读取串口 MJPEG，编码 H.264 + 时间水印，同时推给本地和云端。

#### 6.2.1 依赖

```bash
sudo apt update
sudo apt install -y ffmpeg python3-serial
```

#### 6.2.2 部署 MediaMTX（本地分发）

```bash
# 树莓派为 aarch64（64位）
curl -L -o mediamtx.tar.gz \
  https://github.com/bluenviron/mediamtx/releases/download/v1.21.2/mediamtx_v1.21.2_linux_arm64.tar.gz
mkdir -p ~/mediamtx && tar -xzf mediamtx.tar.gz -C ~/mediamtx
```

本地直接使用 MediaMTX 自带默认配置（默认已开启 RTSP/HLS/WebRTC，并接受任意路径推流）：

```bash
cd ~/mediamtx && ./mediamtx mediamtx.yml
```

#### 6.2.3 桥接脚本

`pi/bridge.py`（读取串口 → ffmpeg → 本地 RTSP + 云端 RTMP，**双线程 + 卡死自愈**）：

```python
#!/usr/bin/env python3
import sys, time, queue, threading, subprocess
import serial

PORT   = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
LOCAL  = sys.argv[2] if len(sys.argv) > 2 else "rtsp://127.0.0.1:8554/cam"
REMOTE = sys.argv[3] if len(sys.argv) > 3 else \
         "rtmp://<云端IP>:1935/cam?user=pusher&pass=<推流密码>"
BAUD = 115200

TARGETS = [
    ["-f", "rtsp", "-rtsp_transport", "tcp", LOCAL],
    ["-f", "flv", REMOTE],
]

# 时间水印（真实时间；因 ffmpeg 转义限制，时间用横杠分隔）
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
        # 启动宽限期：给 ffmpeg 建连时间，期间丢帧不算卡死
        if time.time() - self.spawn_t < 20:
            self.strikes = 0
            return
        self.strikes += 1
        if self.strikes >= 10:
            print("[bridge] %s stalled, restarting" % self.name, file=sys.stderr)
            try: self.proc.kill()
            except Exception: pass
            while True:
                try: self.q.get_nowait()
                except queue.Empty: break
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
    for t in targets: t.start()
    while True:
        try:
            ser = serial.Serial(PORT, BAUD, timeout=5)
        except Exception as exc:
            print("[bridge] serial open failed: %s" % exc, file=sys.stderr)
            time.sleep(2); continue
        print("[bridge] serial open, streaming to %d targets" % len(targets),
              file=sys.stderr)
        try:
            while True:
                data = ser.read(8192)
                if not data: continue
                for t in targets: t.feed(data)
        except Exception as exc:
            print("[bridge] serial error: %s" % exc, file=sys.stderr)
            try: ser.close()
            except Exception: pass
            time.sleep(1)

if __name__ == "__main__":
    main()
```

#### 6.2.4 开机自启（systemd）

`pi/mediamtx.service`：

```ini
[Unit]
Description=MediaMTX streaming server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=<pi用户>
WorkingDirectory=/home/<pi用户>/mediamtx
ExecStart=/home/<pi用户>/mediamtx/mediamtx /home/<pi用户>/mediamtx/mediamtx.yml
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

`pi/bridge.service`：

```ini
[Unit]
Description=OpenMV to RTSP bridge
After=network-online.target mediamtx.service
Wants=network-online.target
Requires=mediamtx.service

[Service]
Type=simple
User=<pi用户>
ExecStart=/usr/bin/python3 -u /home/<pi用户>/monitor/bridge.py /dev/ttyACM0 rtsp://127.0.0.1:8554/cam
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo cp mediamtx.service bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mediamtx bridge
```

---

### 6.3 阿里云服务器端

**目标**：做一个公网中转，让远程用户能看。

#### 6.3.1 选购
- 产品：**阿里云 ECS 免费试用（个人版）**，或普通 ECS / 轻量应用服务器；
- 地域：**中国香港**（内地地域每月免费流量仅 20GB，香港有 200GB，且免备案）；
- 镜像：**Ubuntu 22.04 LTS 64 位**；
- 规格：最低配（2 vCPU / 2 GiB）即可，仅做流中转。

#### 6.3.2 部署 MediaMTX（本机中转）

ECS 是 x86_64，下载 `linux_amd64` 版本：

```bash
curl -L -o mediamtx.tar.gz \
  https://github.com/bluenviron/mediamtx/releases/download/v1.21.2/mediamtx_v1.21.2_linux_amd64.tar.gz
mkdir -p /root/mediamtx && tar -xzf mediamtx.tar.gz -C /root/mediamtx
```

`cloud/mediamtx.yml`：

```yaml
logLevel: info

rtsp: true
rtspAddress: :8554

rtmp: true
rtmpAddress: :1935

hls: true
hlsAddress: :8888
hlsAlwaysRemux: true
hlsVariant: lowLatency          # 低延迟 HLS
hlsSegmentDuration: 1s
hlsPartDuration: 200ms
hlsSegmentCount: 7

webrtc: true
webrtcAddress: :8889
webrtcAdditionalHosts: [<云端公网IP>]

# 鉴权：只有知道密码的人能推流；观看开放
authInternalUsers:
  - user: pusher
    pass: <推流密码>
    ips: []
    permissions:
      - action: publish
        path: cam
  - user: any
    pass:
    ips: []
    permissions:
      - action: read
        path: cam

paths:
  cam:
    source: publisher
```

`cloud/mediamtx.service`：

```ini
[Unit]
Description=MediaMTX relay
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/mediamtx
ExecStart=/root/mediamtx/mediamtx /root/mediamtx/mediamtx.yml
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo mv mediamtx.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mediamtx
```

#### 6.3.3 放行安全组端口（阿里云控制台）

ECS 默认只开放 22，需要在 **安全组 → 入方向** 手动添加：

| 协议 | 端口范围 | 授权对象 | 用途 |
|---|---|---|---|
| 自定义 TCP | `1935/8889` | `0.0.0.0/0` | RTMP 推流 + HLS + WebRTC 信令 |
| 自定义 UDP | `8189/8189` | `0.0.0.0/0` | WebRTC 媒体（低延迟观看必需） |

> 系统内 `ufw` 默认关闭、`iptables` 放行，实际挡在外面的是**安全组**。

---

### 6.4 Android App

用 **Flutter** 开发，内嵌一个 **WebView 加载云端 WebRTC 播放页**。

#### 6.4.1 关键点
- 默认地址：`http://<云端IP>:8889/cam`（MediaMTX 自带 WebRTC 播放页）；
- 需要 Manifest 允许明文 HTTP：`usesCleartextTraffic="true"`，并声明 `INTERNET` 权限；
- WebView 关闭「需要用户手势才能播放」，实现自动播放。

#### 6.4.2 依赖

```yaml
dependencies:
  webview_flutter: ^4.14.1
  webview_flutter_android: ^4.14.1
  shared_preferences: ^2.3.2
```

#### 6.4.3 核心代码（`lib/main.dart` 简化）

```dart
final controller = WebViewController()
  ..setJavaScriptMode(JavaScriptMode.unrestricted)
  ..setBackgroundColor(const Color(0xFF000000))
  ..loadRequest(Uri.parse(_url));

final platform = controller.platform;
if (platform is AndroidWebViewController) {
  platform.setMediaPlaybackRequiresUserGesture(false); // 自动播放
}
// 用 WebViewWidget(controller: controller) 展示
```

#### 6.4.4 打包

```bash
flutter pub get
flutter build apk --release
# 产物：build/app/outputs/flutter-apk/app-release.apk
# 直接发给朋友安装即可（已内置云端地址，无需配置）
```

> 国内网络下建议配置镜像：
> `PUB_HOSTED_URL=https://pub.flutter-io.cn`
> `FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn`
> 并在 Gradle 中加入阿里云 Maven 镜像（见附录）。

---

## 7. 网络诊断与发现（CGNAT / IPv6）

搭建过程中对家庭宽带做了一次诊断：

- 宽带：**中国移动**家庭宽带；
- **IPv4 是 CGNAT**：登录光猫后台读取到 `INTERNET` 连接的 WAN 口地址是 `100.64.x.x`（运营商大内网），因此**无法做端口映射**，外网进不来；
- **IPv6 是公网**：网关给内网下发 `2409:.../64` 的**公网 IPv6** 前缀，内网设备可获得全局可达 IPv6；
- 手机热点网络同样处于 CGNAT。

**结论**：因为 IPv4 无法端口映射，所以选择了「**云服务器中转**」作为外网入口（稳定、通用、不依赖运营商）。

> 其他可选方案：
> - **IPv6 直连 + DDNS**：免费、无中转，但要求观看端也有 IPv6；
> - **Tailscale**：无视 CGNAT 的异地组网，适合自用，但不适合「打包成 App 发给朋友」（无手机端嵌入 SDK，且免费版用户数有限）。

---

## 8. 关键技术实现

1. **USB MJPEG 直通**：OpenMV 端不做协议封装，直接连续发送 JPEG，树莓派用 `ffmpeg -f mjpeg -i -` 解析，简单可靠。
2. **时间水印**：用 ffmpeg `drawtext` 叠加 `%{localtime}`，水印烧进视频里，所有人看到的是**同一个真实时间**。
   - 注意：ffmpeg 对 `%{localtime:...}` 内的冒号转义很麻烦，最终采用横杠格式 `%Y-%m-%d %H-%M-%S`。
3. **双目标推流 + 卡死自愈**：`bridge.py` 为每个输出目标开独立线程 + 队列；某个 ffmpeg 卡住/掉线时**独立重启**，不互相影响。并设「启动宽限期」，避免 ffmpeg 建连期间被误杀。
4. **云端鉴权**：MediaMTX 用 `authInternalUsers` 限制**只有持密码者能推流**，观看开放。
5. **低延迟观看**：云端同时提供 **WebRTC**（< 1s）与 **LL-HLS**（低延迟 HLS，约 2s）。
6. **开机自启**：树莓派与云端均用 systemd `enable`，断电恢复后自动拉起。
7. **TCP 保活**：本地 RTSP 推流使用 `-rtsp_transport tcp`，更稳。

---

## 9. 使用与观看

设云端公网 IP 为 `<IP>`：

| 方式 | 地址 | 延迟 | 说明 |
|---|---|---|---|
| **WebRTC（推荐）** | `http://<IP>:8889/cam` | **< 1s** | App / 浏览器直接看 |
| HLS | `http://<IP>:8888/cam/index.m3u8` | ~2s | 兼容性最好 |
| RTSP | `rtsp://<IP>:8554/cam` | 低 | VLC |
| 本地（局域网） | `http://<树莓派IP>:8889/cam` | 近零 | 局域网内首选 |

- **Android App**：安装 `app-release.apk` 即看；右上角可刷新/改地址。
- **朋友分发**：直接发 APK。

---

## 10. 成本

| 项目 | 费用 |
|---|---|
| OpenMV Cam H7 Plus | 一次性硬件 |
| 树莓派 4B | 一次性硬件 |
| 阿里云 ECS | 试用期免费；之后约 ¥10~30/月（按流量/配置） |

> 流量估算：单路 640×480@25fps ≈ 1.2 Mbps。香港地域试用含 200GB/月出流量，够 10 人日常观看。

---

## 11. 已知问题与踩坑记录

1. **OpenMV USB 掉线/复位**：断电重启后曾出现摄像头每几十秒复位一次（序列号变回默认值）。
   - 排查方向：**供电不足 / USB Hub / 线材**；已关闭 `usbcore` 的 USB 自动挂起（autosuspend）。
   - 建议：优质电源、**直插主板**、好线材；必要时重新刷固件/擦除文件系统。
2. **桥接误杀**：网络变慢时 ffmpeg 建连变慢，曾被「卡死重启」逻辑反复杀死 → 已加**启动宽限期**修复。
3. **RTMP 鉴权格式**：MediaMTX 的 RTMP 推流密码需用 **URL 查询参数** `?user=..&pass=..`，不能用 `user:pass@`。
4. **HLS 延迟**：默认切片模式延迟可达数十秒，改用 **LL-HLS** 后大幅下降；追求极致低延迟请用 **WebRTC**。
5. **有线未自启**：某次断电后 `eth0` 未建立链路，设备退回 WiFi。需检查路由器/网线。
6. **HLS 首访 302**：MediaMTX 的 HLS 有 cookie 校验，浏览器/播放器会自动处理，命令行需带 cookie。

---

## 12. 附录：完整配置与命令

### 12.1 查看实时状态

```bash
# 树莓派
systemctl status mediamtx bridge
journalctl -u bridge -n 20 --no-pager

# 云端
journalctl -u mediamtx -n 20 --no-pager
```

### 12.2 抓一帧验证画面（本机有 ffmpeg 时）

```bash
ffmpeg -rtsp_transport tcp -i rtsp://<IP>:8554/cam -frames:v 1 frame.png
```

### 12.3 Flutter Gradle 国内镜像（`android/settings.gradle.kts` 与 `build.gradle.kts`）

```kotlin
repositories {
    maven { url = uri("https://maven.aliyun.com/repository/google") }
    maven { url = uri("https://maven.aliyun.com/repository/public") }
    google()
    mavenCentral()
}
```

Gradle 分发包镜像（`android/gradle/wrapper/gradle-wrapper.properties`）：

```
distributionUrl=https\://mirrors.cloud.tencent.com/gradle/gradle-9.1.0-all.zip
```

### 12.4 端口一览

| 端口 | 协议 | 服务 |
|---|---|---|
| 8554 | TCP | RTSP |
| 1935 | TCP | RTMP（推流） |
| 8888 | TCP | HLS |
| 8889 | TCP | WebRTC（信令/页面） |
| 8189 | UDP | WebRTC（媒体） |

---

## License

MIT（按需修改）
