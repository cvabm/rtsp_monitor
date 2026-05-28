"""
Interactive RTSP region selector.
Reads the first RTSP URL from config.ini, lets user drag a rectangle,
then writes detection.region back to config.ini as ratio coordinates.
"""

import configparser
import sys
import time

import cv2

CONFIG_PATH = "config.ini"
WINDOW_NAME = "Region Selector"

cfg = configparser.ConfigParser()
cfg.read(CONFIG_PATH, encoding="utf-8")


def cfg_get(section, key, fallback=""):
    try:
        return cfg.get(section, key).strip()
    except Exception:
        return fallback


def parse_region_spec(raw_value):
    if not raw_value:
        return None
    try:
        parts = [p.strip() for p in raw_value.split(",")]
        if len(parts) != 4:
            raise ValueError("need 4 numbers")
        return tuple(float(p) for p in parts)
    except Exception:
        return None


def resolve_region(frame_shape, region_spec):
    h, w = frame_shape[:2]
    if not region_spec:
        return (0, 0, w, h)

    use_ratio = all(0.0 <= v <= 1.0 for v in region_spec)
    if use_ratio:
        x1 = int(round(region_spec[0] * w))
        y1 = int(round(region_spec[1] * h))
        x2 = int(round(region_spec[2] * w))
        y2 = int(round(region_spec[3] * h))
    else:
        x1, y1, x2, y2 = [int(round(v)) for v in region_spec]

    x1 = max(0, min(x1, w - 1))
    y1 = max(0, min(y1, h - 1))
    x2 = max(1, min(x2, w))
    y2 = max(1, min(y2, h))

    if x2 <= x1 or y2 <= y1:
        return (0, 0, w, h)
    return (x1, y1, x2, y2)


def format_region_ratio(region_rect, frame_shape):
    h, w = frame_shape[:2]
    x1, y1, x2, y2 = region_rect
    values = (x1 / w, y1 / h, x2 / w, y2 / h)
    return ",".join(f"{v:.4f}" for v in values)


def write_region(region_value):
    if not cfg.has_section("detection"):
        cfg.add_section("detection")
    cfg.set("detection", "region", region_value)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        cfg.write(f)


def open_stream(rtsp_url):
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def main():
    rtsp_urls = [u.strip() for u in cfg_get("camera", "rtsp_urls").split(",") if u.strip()]
    if not rtsp_urls:
        print("[ERROR] No rtsp_urls found in config.ini")
        input("Press Enter to exit...")
        return 1

    current_region = parse_region_spec(cfg_get("detection", "region", ""))
    cap = open_stream(rtsp_urls[0])
    if not cap.isOpened():
        print(f"[ERROR] Failed to open RTSP stream: {rtsp_urls[0]}")
        input("Press Enter to exit...")
        return 1

    print("Instructions:")
    print("  Drag with left mouse button to select the detection region")
    print("  Press S to save")
    print("  Press R to reset to full frame")
    print("  Press Q or ESC to cancel")

    state = {
        "dragging": False,
        "anchor": None,
        "region": None,
        "preview": None,
    }

    frame = None
    for _ in range(60):
        ret, frame = cap.read()
        if ret:
            break
        time.sleep(0.05)

    if frame is None or not ret:
        cap.release()
        print("[ERROR] Could not read a frame from the stream")
        input("Press Enter to exit...")
        return 1

    state["region"] = resolve_region(frame.shape, current_region)

    def normalize_rect(x1, y1, x2, y2):
        left, right = sorted((x1, x2))
        top, bottom = sorted((y1, y2))
        left = max(0, min(left, frame.shape[1] - 1))
        top = max(0, min(top, frame.shape[0] - 1))
        right = max(1, min(right, frame.shape[1]))
        bottom = max(1, min(bottom, frame.shape[0]))
        if right <= left or bottom <= top:
            return None
        return (left, top, right, bottom)

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            state["dragging"] = True
            state["anchor"] = (x, y)
            state["preview"] = (x, y, x, y)
        elif event == cv2.EVENT_MOUSEMOVE and state["dragging"] and state["anchor"]:
            ax, ay = state["anchor"]
            state["preview"] = normalize_rect(ax, ay, x, y)
        elif event == cv2.EVENT_LBUTTONUP and state["dragging"] and state["anchor"]:
            ax, ay = state["anchor"]
            state["dragging"] = False
            state["anchor"] = None
            rect = normalize_rect(ax, ay, x, y)
            if rect:
                state["region"] = rect
            state["preview"] = None

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(WINDOW_NAME, on_mouse)

    while True:
        ret, live_frame = cap.read()
        if ret:
            frame = live_frame

        display = frame.copy()
        rect = state["preview"] or state["region"]
        if rect:
            x1, y1, x2, y2 = rect
            cv2.rectangle(display, (x1, y1), (x2 - 1, y2 - 1), (0, 215, 255), 2)
            cv2.putText(display, "Detection Region",
                        (x1 + 4, y1 - 10 if y1 > 28 else y1 + 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 215, 255), 2)

        cv2.putText(display, "Drag: select  S: save  R: reset  Q/ESC: cancel",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.imshow(WINDOW_NAME, display)

        key = cv2.waitKey(20) & 0xFF
        if key in (ord("q"), 27):
            print("Canceled, config.ini not changed.")
            break
        if key == ord("r"):
            state["region"] = (0, 0, frame.shape[1], frame.shape[0])
            state["preview"] = None
            print("Region reset to full frame.")
        if key == ord("s"):
            region_value = format_region_ratio(state["region"], frame.shape)
            write_region(region_value)
            print(f"Saved detection.region = {region_value}")
            break

    cap.release()
    cv2.destroyAllWindows()
    cv2.waitKey(100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
