# RTSP 人员检测系统 - Windows 版

## 快速开始

**第一步：安装环境**
双击运行 `install.bat`（只需运行一次）

**第二步：配置摄像头**
用记事本打开 `config.ini`，修改 rtsp_urls 为你的摄像头地址：
```
rtsp_urls = rtsp://用户名:密码@摄像头IP:端口/stream
```

**第三步：启动**
推荐双击运行 `start.bat`

也可以直接：
- 双击 `start_monitor.bat` 开始监控
- 双击 `start_region_selector.bat` 框选检测区域

**主菜单说明**
`start.bat` 打开后可选择：
- `1` 开始监控
- `2` 框选检测区域
- `3` 退出

**兼容旧方式**
双击运行 `start_monitor.bat`

**可选：鼠标框选检测区域**
双击运行 `start_region_selector.bat`，在画面上拖拽框选后按 `S` 保存。

**退出方式**
* 视频窗口按 `Q` 或 `ESC`

* 控制台按 `Ctrl+C` 一次即可，不用按多次
---

## 目录结构

```
rtsp_monitor/
├── install.bat        ← 首次运行安装依赖
├── start.bat          ← 推荐入口（主菜单）
├── start_monitor.bat  ← 日常启动
├── start_region_selector.bat ← 框选检测区域
├── monitor.py          ← 主程序
├── region_selector.py  ← 区域框选工具
├── config.ini          ← 配置文件（改这里）
├── alert_log.csv       ← 告警日志（自动生成）
└── alerts/             ← 截图保存目录（自动生成）
```

---

## 配置说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| rtsp_urls | 摄像头地址，多路用逗号分隔 | — |
| model | yolov8n(快) / yolov8s / yolov8m(准) | yolov8n.pt |
| confidence | 置信度 0~1，越高误报越少 | 0.50 |
| detect_fps | 每秒检测帧数，越低越省CPU | 5 |
| region | 检测区域，留空为全画面；支持 `x1,y1,x2,y2` | 空 |
| cooldown_seconds | 两次弹框最短间隔 | 15 |
| show_window | 是否显示画面窗口 | True |
| save_screenshots | 是否保存告警截图 | True |
| wecom_webhook | 企业微信机器人地址（留空不推送）| — |
| dingtalk_webhook | 钉钉机器人地址（留空不推送）| — |

---

## 区域配置示例

全画面检测：
```ini
region =
```

按比例设置区域（推荐，适合不同分辨率）：
```ini
region = 0.1,0.2,0.9,0.95
```

按像素设置区域：
```ini
region = 100,200,1280,720
```

说明：
- `x1,y1` 是检测区域左上角
- `x2,y2` 是检测区域右下角
- 如果四个值都在 `0~1` 之间，会按画面宽高比例计算
- 如果存在大于 `1` 的值，会按像素坐标处理
- 预览窗口会显示完整画面，并用框标出检测区域

也可以直接运行 `start_region_selector.bat`：
- 鼠标左键拖拽选择区域
- 按 `S` 保存到 `config.ini`
- 按 `R` 重置为全画面
- 按 `Q` 或 `ESC` 退出不保存

---

## 常见问题

**Q: 连接失败？**
- 确认摄像头 IP 和端口正确
- 确认用户名密码正确
- 试用 VLC 先验证 RTSP 地址能否播放

**Q: 误报太多？**
- 提高 confidence 到 0.65 或 0.70
- 降低 detect_fps 到 2~3
- 缩小 `region`，只保留真正需要监控的区域

**Q: CPU 占用太高？**
- 降低 detect_fps（比如改为 2）
- 换用 yolov8n.pt（最小最快的模型）
- 设置 show_window = False
- 设置 `region`，避免整幅画面都参与检测

**Q: 弹框没出现？**
- 检查 Windows 通知设置是否允许 PowerShell 通知
- 或改为声音提示 sound_alert = True
