#!/usr/bin/env python3
"""最小webview测试"""
import webview

def main():
    print("创建窗口...")
    window = webview.create_window(
        'Test',
        'http://localhost:5173',
        width=800,
        height=600,
        hidden=False
    )
    print("窗口已创建，准备启动...")
    webview.start(debug=True)
    print("webview.start() 返回了")

if __name__ == "__main__":
    main()
