"""
RTSP Person Detection System - Windows Edition v3
Requirements: pip install ultralytics opencv-python requests
Quit: Press Q/ESC in video window, or Ctrl+C in console.
"""

import cv2
import threading
import time
import os
import queue
import configparser
import ctypes
import winsound
import requests
import traceback
import signal
import sys
from datetime import datetime
from pathlib import Path
from ultralytics import YOLO

# -- Global stop event ---------------------------------
stop_event = threading.Event()

def shutdown(reason=""):
    if not stop_event.is_set():
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Shutting down... {reason}")
        stop_event.set()

def _sigint_handler(sig, frame):
    shutdown("(Ctrl+C)")

signal.signal(signal.SIGINT, _sigint_handler)

# -- Load Config ---------------------------------------
cfg = configparser.ConfigParser()
cfg.read("config.ini", encoding="utf-8")

def cfg_get(section, key, fallback=""):
    try:
        return cfg.get(section, key).strip()
    except Exception:
        return fallback

RTSP_URLS    = [u.strip() for u in cfg_get("camera", "rtsp_urls").split(",") if u.strip()]
MODEL_PATH   = cfg_get("detection", "model", "yolov8n.pt")
CONF_THRES   = float(cfg_get("detection", "confidence", "0.50"))
DETECT_FPS   = int(cfg_get("detection", "detect_fps", "5"))
COOLDOWN     = int(cfg_get("alert", "cooldown_seconds", "15"))
SHOW_WINDOW  = cfg_get("alert", "show_window", "True").lower() == "true"
SAVE_SHOTS   = cfg_get("alert", "save_screenshots", "True").lower() == "true"
SHOT_DIR     = cfg_get("alert", "screenshot_dir", "alerts")
WIN_POPUP    = cfg_get("notification", "windows_popup", "True").lower() == "true"
POPUP_DUR    = int(cfg_get("notification", "popup_duration", "6"))
WECOM_HOOK   = cfg_get("notification", "wecom_webhook", "")
DD_HOOK      = cfg_get("notification", "dingtalk_webhook", "")
SOUND_ALERT  = cfg_get("notification", "sound_alert", "True").lower() == "true"

if SAVE_SHOTS:
    Path(SHOT_DIR).mkdir(exist_ok=True)

LOG_FILE = "alert_log.csv"
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("time,camera,persons,confidence,screenshot\n")

# -- Logging -------------------------------------------
print_lock = threading.Lock()

def log(msg):
    with print_lock:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def write_log_csv(cam_name, count, conf, shot_path):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{ts},{cam_name},{count},{conf:.3f},{shot_path}\n")

# -- Windows Popup -------------------------------------
def windows_toast(title, msg, duration=6):
    if stop_event.is_set():
        return
    try:
        st = title.replace("'", "")
        sm = msg.replace("'", "").replace("\n", " | ")
        ps = (f"Add-Type -AssemblyName System.Windows.Forms;"
              f"$n=New-Object System.Windows.Forms.NotifyIcon;"
              f"$n.Icon=[System.Drawing.SystemIcons]::Warning;"
              f"$n.Visible=$true;"
              f"$n.ShowBalloonTip({duration*1000},'{st}','{sm}',"
              f"[System.Windows.Forms.ToolTipIcon]::Warning);"
              f"Start-Sleep -Seconds {duration+1};$n.Dispose()")
        import subprocess
        subprocess.Popen(["powershell","-WindowStyle","Hidden","-Command",ps],
                         creationflags=0x08000000)
    except Exception:
        try:
            ctypes.windll.user32.MessageBoxW(0, msg, title, 0x00001030)
        except Exception:
            pass

# -- Sound ---------------------------------------------
def play_sound():
    if stop_event.is_set():
        return
    try:
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        time.sleep(0.3)
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception:
        pass

# -- WeCom ---------------------------------------------
def send_wecom(cam_name, count, conf, img_path=None):
    if not WECOM_HOOK or stop_event.is_set():
        return
    try:
        text = (f"[Alert] Person Detected\nCamera: {cam_name}\n"
                f"Count: {count}\nConfidence: {conf:.0%}\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        requests.post(WECOM_HOOK, json={"msgtype":"text","text":{"content":text}}, timeout=5)
        if img_path and os.path.exists(img_path):
            import base64, hashlib
            data = open(img_path,"rb").read()
            requests.post(WECOM_HOOK, json={"msgtype":"image","image":{
                "base64":base64.b64encode(data).decode(),
                "md5":hashlib.md5(data).hexdigest()}}, timeout=10)
    except Exception as e:
        log(f"[WeCom ERROR] {e}")

# -- DingTalk ------------------------------------------
def send_dingtalk(cam_name, count, conf):
    if not DD_HOOK or stop_event.is_set():
        return
    try:
        content = (f"## [Alert] Person Detected\n\n"
                   f"> **Camera**: {cam_name}\n\n> **Count**: {count}\n\n"
                   f"> **Confidence**: {conf:.0%}\n\n"
                   f"> **Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        requests.post(DD_HOOK, json={"msgtype":"markdown",
            "markdown":{"title":"Person Detected","text":content}}, timeout=5)
    except Exception as e:
        log(f"[DingTalk ERROR] {e}")

# -- Alert Worker --------------------------------------
alert_queue = queue.Queue()

def alert_worker():
    while not stop_event.is_set():
        try:
            item = alert_queue.get(timeout=1)
        except queue.Empty:
            continue
        try:
            cam_name, count, conf, annotated_frame = item
            shot_path = ""
            if SAVE_SHOTS and annotated_frame is not None:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                shot_path = os.path.join(SHOT_DIR, f"{cam_name}_{ts}_p{count}.jpg")
                cv2.imwrite(shot_path, annotated_frame)
                log(f"[Screenshot] Saved -> {shot_path}")
            write_log_csv(cam_name, count, conf, shot_path)
            title = "Person Detected - Security Alert"
            msg   = (f"Camera {cam_name}: {count} person(s) detected\n"
                     f"Confidence {conf:.0%}  {datetime.now().strftime('%H:%M:%S')}")
            tasks = []
            if WIN_POPUP:
                tasks.append(threading.Thread(target=windows_toast, args=(title,msg,POPUP_DUR), daemon=True))
            if SOUND_ALERT:
                tasks.append(threading.Thread(target=play_sound, daemon=True))
            if WECOM_HOOK:
                tasks.append(threading.Thread(target=send_wecom, args=(cam_name,count,conf,shot_path), daemon=True))
            if DD_HOOK:
                tasks.append(threading.Thread(target=send_dingtalk, args=(cam_name,count,conf), daemon=True))
            for t in tasks:
                t.start()
        except Exception:
            traceback.print_exc()
        finally:
            alert_queue.task_done()

threading.Thread(target=alert_worker, daemon=True, name="AlertWorker").start()

# -- Camera Thread -------------------------------------
def camera_thread(rtsp_url, cam_index, model):
    cam_name    = f"CAM-{cam_index+1:02d}"
    last_alert  = 0
    frame_gap   = 1.0 / DETECT_FPS
    last_detect = 0

    log(f"[{cam_name}] Connecting: {rtsp_url}")

    while not stop_event.is_set():
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)

        if not cap.isOpened():
            log(f"[{cam_name}] Connection failed, retrying in 5s...")
            stop_event.wait(5)
            continue

        log(f"[{cam_name}] Connected OK")
        fail_count = 0

        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                fail_count += 1
                if fail_count > 10:
                    log(f"[{cam_name}] Too many dropped frames, reconnecting...")
                    break
                time.sleep(0.1)
                continue
            fail_count = 0

            now = time.time()

            # Throttle to detect_fps
            if now - last_detect < frame_gap:
                if SHOW_WINDOW:
                    cv2.imshow(cam_name, frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (ord('q'), 27):
                        shutdown("(Q/ESC pressed)")
                continue

            last_detect = now

            results  = model(frame, classes=[0], conf=CONF_THRES, verbose=False)
            boxes    = results[0].boxes
            persons  = len(boxes)
            max_conf = float(boxes.conf.max()) if persons > 0 else 0.0
            annotated = results[0].plot() if (SHOW_WINDOW or SAVE_SHOTS) else None

            if persons > 0 and (now - last_alert) >= COOLDOWN:
                last_alert = now
                log(f"[{cam_name}] ALERT! {persons} person(s), conf {max_conf:.0%}")
                alert_queue.put((cam_name, persons, max_conf, annotated))

            if SHOW_WINDOW and annotated is not None:
                color = (0, 255, 80) if persons > 0 else (200, 200, 200)
                cv2.putText(annotated, f"Persons: {persons}" if persons else "Clear",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
                cv2.putText(annotated, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            (10, annotated.shape[0]-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180,180,180), 1)
                cv2.imshow(cam_name, annotated)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord('q'), 27):
                    shutdown("(Q/ESC pressed)")

        cap.release()
        if not stop_event.is_set():
            stop_event.wait(2)

    log(f"[{cam_name}] Thread stopped.")

# -- Main ----------------------------------------------
def main():
    print("=" * 52)
    print("  RTSP Person Detection System - Windows v3")
    print("=" * 52)
    print(f"  Cameras    : {len(RTSP_URLS)}")
    print(f"  Model      : {MODEL_PATH}")
    print(f"  Confidence : {CONF_THRES:.0%}")
    print(f"  Cooldown   : {COOLDOWN}s")
    print(f"  Detect FPS : {DETECT_FPS}")
    print(f"  Show window: {SHOW_WINDOW}")
    print(f"  Screenshots: {SAVE_SHOTS}")
    print("=" * 52)
    print("  HOW TO QUIT:")
    print("    - Press Q or ESC in the video window, OR")
    print("    - Press Ctrl+C in this console (once is enough)")
    print("=" * 52)
    print()

    if not RTSP_URLS:
        print("[ERROR] No rtsp_urls found in config.ini")
        input("Press Enter to exit...")
        return

    log(f"Loading model {MODEL_PATH} ...")
    try:
        model = YOLO(MODEL_PATH)
        log("Model loaded OK")
    except Exception as e:
        print(f"[ERROR] Failed to load model: {e}")
        input("Press Enter to exit...")
        return

    threads = []
    for i, url in enumerate(RTSP_URLS):
        t = threading.Thread(target=camera_thread, args=(url, i, model),
                             daemon=True, name=f"Camera-{i+1}")
        t.start()
        threads.append(t)
        time.sleep(0.5)

    # Main loop - just waits for stop_event
    while not stop_event.is_set():
        time.sleep(0.5)

    log("Waiting for threads to finish (max 3s)...")
    for t in threads:
        t.join(timeout=3)

    # destroyAllWindows MUST be called from main thread on Windows
    try:
        cv2.destroyAllWindows()
        cv2.waitKey(200)
    except Exception:
        pass

    log("Goodbye.")
    sys.exit(0)

if __name__ == "__main__":
    main()
