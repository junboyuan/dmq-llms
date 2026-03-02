#!/usr/bin/env python3
"""
MCP (Model Context Protocol) 服务端 - SSE 实现
动态读取目录下所有文件，提供资源列表和内容读取功能
仅使用 Python 标准库实现
"""

import http.server
import socketserver
import json
import os
import mimetypes
import threading
import time
import uuid
from urllib.parse import urlparse, parse_qs
from typing import Optional
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = 8081
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

# 存储 SSE 客户端连接
sse_clients: dict[str, 'MCPHandler'] = {}
sse_clients_lock = threading.Lock()


def get_file_list() -> list[dict]:
    """获取目录下所有文件列表"""
    files = []
    for f in os.listdir(DIRECTORY):
        filepath = os.path.join(DIRECTORY, f)
        if os.path.isfile(filepath) and not f.startswith('.'):
            mime_type, _ = mimetypes.guess_type(filepath)
            try:
                size = os.path.getsize(filepath)
            except OSError:
                size = 0
            files.append({
                'name': f,
                'uri': f'file://{f}',
                'mimeType': mime_type or 'application/octet-stream',
                'size': size
            })
    return files


def read_file_content(filename: str) -> tuple[Optional[str], Optional[str]]:
    """读取文件内容，返回 (内容, MIME类型)"""
    filepath = os.path.join(DIRECTORY, filename)

    # 安全检查：防止路径遍历攻击
    if not os.path.abspath(filepath).startswith(DIRECTORY):
        return None, None

    if not os.path.isfile(filepath):
        return None, None

    mime_type, _ = mimetypes.guess_type(filepath)

    try:
        # 尝试以文本方式读取
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, mime_type or 'text/plain'
    except UnicodeDecodeError:
        # 二进制文件，返回 base64
        import base64
        with open(filepath, 'rb') as f:
            content = base64.b64encode(f.read()).decode('ascii')
        return content, mime_type or 'application/octet-stream'
    except Exception as e:
        logger.error(f"读取文件失败: {e}")
        return None, None


def search_in_files(query: str, filename: Optional[str] = None) -> list[dict]:
    """在文件中搜索关键词"""
    results = []

    if filename:
        files_to_search = [filename]
    else:
        files_to_search = [f['name'] for f in get_file_list()]

    for fname in files_to_search:
        content, _ = read_file_content(fname)
        if content and query.lower() in content.lower():
            lines = content.split('\n')
            matches = []
            for i, line in enumerate(lines):
                if query.lower() in line.lower():
                    start = max(0, i - 2)
                    end = min(len(lines), i + 3)
                    matches.append({
                        'lineNumber': i + 1,
                        'context': '\n'.join(lines[start:end])
                    })
            results.append({
                'filename': fname,
                'matches': matches[:10]  # 限制每个文件最多返回10个匹配
            })

    return results


class MCPHandler(http.server.BaseHTTPRequestHandler):
    """MCP HTTP 请求处理器"""

    protocol_version = 'HTTP/1.1'

    def log_message(self, format, *args):
        """自定义日志格式"""
        logger.info("%s - %s", self.address_string(), format % args)

    def send_cors_headers(self):
        """发送 CORS 头"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        """处理 OPTIONS 请求"""
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        """处理 GET 请求"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path == '/' or path == '':
            self.handle_index()
        elif path == '/health':
            self.handle_health()
        elif path == '/sse':
            self.handle_sse()
        else:
            self.send_error(404, 'Not Found')

    def do_POST(self):
        """处理 POST 请求"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path == '/mcp':
            self.handle_mcp_request()
        else:
            self.send_error(404, 'Not Found')

    def handle_index(self):
        """首页，显示服务信息"""
        files = get_file_list()
        response = {
            'name': 'Pulsar MCP Server (SSE)',
            'version': '1.0.0',
            'protocol': 'MCP over SSE',
            'endpoints': {
                'sse': '/sse',
                'http': '/mcp',
                'health': '/health'
            },
            'files': [f['name'] for f in files],
            'usage': {
                'sse': 'GET /sse - 建立 SSE 连接',
                'http': 'POST /mcp - 发送 JSON-RPC 请求',
                'initialize': 'POST /mcp with {"jsonrpc":"2.0","method":"initialize","id":1}',
                'list_resources': 'POST /mcp with {"jsonrpc":"2.0","method":"resources/list","id":2}',
                'read_resource': 'POST /mcp with {"jsonrpc":"2.0","method":"resources/read","params":{"uri":"file://filename"},"id":3}',
                'list_tools': 'POST /mcp with {"jsonrpc":"2.0","method":"tools/list","id":4}',
            }
        }
        self.send_json_response(response)

    def handle_health(self):
        """健康检查端点"""
        response = {'status': 'ok', 'files': len(get_file_list())}
        self.send_json_response(response)

    def handle_sse(self):
        """处理 SSE 连接"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_cors_headers()
        self.end_headers()

        # 生成客户端 ID
        client_id = str(uuid.uuid4())[:8]

        with sse_clients_lock:
            sse_clients[client_id] = self

        logger.info(f"SSE 客户端连接: {client_id}")

        try:
            # 发送连接成功事件
            self.send_sse_event('connected', {'clientId': client_id})

            # 发送资源列表
            files = get_file_list()
            self.send_sse_event('resources/list', {
                'resources': [
                    {'uri': f['uri'], 'name': f['name'], 'mimeType': f['mimeType']}
                    for f in files
                ]
            })

            # 保持连接，发送心跳
            while True:
                time.sleep(30)
                self.send_sse_event('ping', {'timestamp': time.time()})

        except (BrokenPipeError, ConnectionResetError):
            logger.info(f"SSE 客户端断开: {client_id}")
        finally:
            with sse_clients_lock:
                sse_clients.pop(client_id, None)

    def send_sse_event(self, event: str, data: dict):
        """发送 SSE 事件"""
        message = f'event: {event}\ndata: {json.dumps(data)}\n\n'
        self.wfile.write(message.encode('utf-8'))
        self.wfile.flush()

    def handle_mcp_request(self):
        """处理 MCP JSON-RPC 请求"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            request = json.loads(body)
        except json.JSONDecodeError:
            self.send_json_response(
                {'jsonrpc': '2.0', 'error': {'code': -32700, 'message': 'Parse error'}, 'id': None},
                status=400
            )
            return

        method = request.get('method')
        params = request.get('params', {})
        request_id = request.get('id')

        response = {'jsonrpc': '2.0', 'id': request_id}

        if method == 'initialize':
            response['result'] = {
                'protocolVersion': '2024-11-05',
                'capabilities': {
                    'resources': {'subscribe': True, 'listChanged': True},
                    'tools': {}
                },
                'serverInfo': {
                    'name': 'pulsar-docs-server',
                    'version': '1.0.0'
                }
            }

        elif method == 'resources/list':
            files = get_file_list()
            response['result'] = {
                'resources': [
                    {'uri': f['uri'], 'name': f['name'], 'mimeType': f['mimeType']}
                    for f in files
                ]
            }

        elif method == 'resources/read':
            uri = params.get('uri', '')
            if uri.startswith('file://'):
                filename = uri[7:]
            else:
                filename = uri

            content, mime_type = read_file_content(filename)
            if content is None:
                response['error'] = {'code': -32602, 'message': f'File not found: {filename}'}
            else:
                response['result'] = {
                    'contents': [
                        {'uri': f'file://{filename}', 'mimeType': mime_type, 'text': content}
                    ]
                }

        elif method == 'tools/list':
            response['result'] = {
                'tools': [
                    {
                        'name': 'list_files',
                        'description': '列出目录下所有可用文件',
                        'inputSchema': {'type': 'object', 'properties': {}}
                    },
                    {
                        'name': 'read_file',
                        'description': '读取指定文件的内容',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'filename': {'type': 'string', 'description': '要读取的文件名'}
                            },
                            'required': ['filename']
                        }
                    },
                    {
                        'name': 'search_content',
                        'description': '在文件中搜索关键词',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'query': {'type': 'string', 'description': '搜索关键词'},
                                'filename': {'type': 'string', 'description': '可选，限定搜索的文件名'}
                            },
                            'required': ['query']
                        }
                    }
                ]
            }

        elif method == 'tools/call':
            tool_name = params.get('name')
            arguments = params.get('arguments', {})

            if tool_name == 'list_files':
                files = get_file_list()
                response['result'] = {
                    'content': [{'type': 'text', 'text': json.dumps(files, ensure_ascii=False, indent=2)}]
                }

            elif tool_name == 'read_file':
                filename = arguments.get('filename')
                if not filename:
                    response['error'] = {'code': -32602, 'message': 'Missing filename parameter'}
                else:
                    content, mime_type = read_file_content(filename)
                    if content is None:
                        response['error'] = {'code': -32602, 'message': f'File not found: {filename}'}
                    else:
                        response['result'] = {
                            'content': [{'type': 'text', 'text': content}]
                        }

            elif tool_name == 'search_content':
                query = arguments.get('query', '')
                target_file = arguments.get('filename')
                results = search_in_files(query, target_file)
                response['result'] = {
                    'content': [{'type': 'text', 'text': json.dumps(results, ensure_ascii=False, indent=2)}]
                }

            else:
                response['error'] = {'code': -32601, 'message': f'Unknown tool: {tool_name}'}

        else:
            response['error'] = {'code': -32601, 'message': f'Unknown method: {method}'}

        self.send_json_response(response)

    def send_json_response(self, data: dict, status: int = 200):
        """发送 JSON 响应"""
        body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """支持多线程的 TCP 服务器"""
    allow_reuse_address = True


if __name__ == '__main__':
    with ThreadedTCPServer(("", PORT), MCPHandler) as httpd:
        print(f"MCP SSE 服务启动: http://localhost:{PORT}")
        print(f"  首页: http://localhost:{PORT}/")
        print(f"  SSE 端点: http://localhost:{PORT}/sse")
        print(f"  HTTP 端点: http://localhost:{PORT}/mcp")
        print(f"  健康检查: http://localhost:{PORT}/health")
        print("按 Ctrl+C 停止")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n服务已停止")