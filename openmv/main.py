# OpenMV Cam H7 Plus (R3) - USB 直连 MJPEG 发送
# 保存到 OpenMV 的 SD 卡 / 内部 Flash，命名为 main.py，上电自动运行。
# 效果：通过 USB 虚拟串口 (ttyACM0) 连续输出 MJPEG(JPEG 帧首尾相连)，
#        树莓派端 ffmpeg 的 -f mjpeg 可直接解析。
#
# 注意：不要在本脚本里使用 print()，因为 CDC 与 REPL 共用同一通道，
#       会污染视频流。

import sensor
from pyb import USB_VCP

usb = USB_VCP()

sensor.reset()
sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.VGA)          # 640x480；想更流畅可改 QVGA(320x240)
sensor.skip_frames(time=2000)             # 等自动曝光/白平衡稳定
sensor.set_auto_gain(True)
sensor.set_auto_whitebal(True)

QUALITY = 60                              # JPEG 质量 60~75，越大越清晰也越卡

while True:
    img = sensor.snapshot()
    jpg = img.compress(quality=QUALITY)   # 返回 JPEG bytes
    usb.send(jpg)                          # 连续发送，帧之间靠 FFD8/FFD9 自动分隔
