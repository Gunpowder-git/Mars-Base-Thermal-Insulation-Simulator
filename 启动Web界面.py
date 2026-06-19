#!/usr/bin/env python3
"""
火星基地隔热墙优化 — Web 界面启动器
双击此文件即可启动，浏览器会自动打开
"""
import sys
import os
import webbrowser
import threading
import time

os.chdir(os.path.dirname(os.path.abspath(__file__)))

def open_browser():
    time.sleep(1.5)
    webbrowser.open('http://localhost:5000')

print("=" * 50)
print("  火星基地隔热墙优化 · 热设计工作室 (Web版)")
print("=" * 50)

# 检查依赖
try:
    from app import app
except ImportError as e:
    print(f"\n缺少依赖: {e}")
    print("请先运行: pip install flask numpy")
    input("\n按回车退出...")
    sys.exit(1)

# 自动打开浏览器
threading.Thread(target=open_browser, daemon=True).start()

print("\n  浏览器即将打开: http://localhost:5000")
print("  关闭此窗口即可停止服务")
print("=" * 50)

try:
    app.run(debug=False, host='0.0.0.0', port=5000)
except OSError:
    print("\n端口 5000 被占用，尝试 5001...")
    threading.Thread(target=lambda: webbrowser.open('http://localhost:5001'), daemon=True).start()
    app.run(debug=False, host='0.0.0.0', port=5001)
