#!/usr/bin/env python3
"""
简单的 HTTP 文件服务
支持读取当前目录下的任何文件
"""

import http.server
import socketserver
import os
import mimetypes

PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))


class FileHandler(http.server.SimpleHTTPRequestHandler):
    """自定义文件处理器"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        # 添加 CORS 头
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        # 添加缓存控制
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def do_OPTIONS(self):
        """处理 OPTIONS 请求"""
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        """处理 GET 请求"""
        # 根路径返回文件列表
        if self.path == '/' or self.path == '':
            self.list_files()
            return

        # 健康检查
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
            return

        # 其他路径尝试读取文件
        super().do_GET()

    def list_files(self):
        """列出可用文件"""
        files = []
        for f in os.listdir(DIRECTORY):
            filepath = os.path.join(DIRECTORY, f)
            if os.path.isfile(filepath) and not f.startswith('.'):
                size = os.path.getsize(filepath)
                mime_type, _ = mimetypes.guess_type(filepath)
                files.append({
                    'name': f,
                    'size': size,
                    'type': mime_type or 'application/octet-stream'
                })

        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()

        import json
        response = {
            'service': 'Pulsar 文档服务',
            'files': files,
            'usage': 'GET /{filename} 获取文件内容'
        }
        self.wfile.write(json.dumps(response, ensure_ascii=False, indent=2).encode('utf-8'))


if __name__ == '__main__':
    with socketserver.TCPServer(("", PORT), FileHandler) as httpd:
        print(f"文档服务启动: http://localhost:{PORT}")
        print(f"文件列表: http://localhost:{PORT}/")
        print(f"llms.txt: http://localhost:{PORT}/llms.txt")
        print("按 Ctrl+C 停止")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n服务已停止")