#!/usr/bin/env python3
"""
Pulsar MCP 文档服务
基于 Flask 实现的 MCP (Model Context Protocol) 服务器
"""

from flask import Flask, jsonify, request, Response
import os

app = Flask(__name__)

# 文档资源目录
DOCS_DIR = os.path.dirname(os.path.abspath(__file__))

# 可用资源定义
RESOURCES = {
    "llms.txt": {
        "name": "llms.txt",
        "description": "MCP 服务说明文档",
        "mimeType": "text/markdown",
        "file": "llms.txt"
    },
    "pulsar-overview": {
        "name": "pulsar-overview",
        "description": "Apache Pulsar 概述：介绍 Pulsar 的定位、特性和适用场景",
        "mimeType": "text/markdown",
        "file": "pulsar-overview.md"
    },
    "pulsar-concepts": {
        "name": "pulsar-concepts",
        "description": "Pulsar 核心概念：Producer、Consumer、Topic、Subscription、Broker、BookKeeper 等详细说明",
        "mimeType": "text/markdown",
        "file": "pulsar-concepts.md"
    },
    "pulsar-architecture": {
        "name": "pulsar-architecture",
        "description": "Pulsar 架构设计：分层架构、存储模型、高可用设计和部署方案",
        "mimeType": "text/markdown",
        "file": "pulsar-architecture.md"
    }
}

# 文档内容缓存
DOCS_CONTENT = {}


def load_docs():
    """从本地文件加载文档内容"""
    global DOCS_CONTENT

    for resource_id, meta in RESOURCES.items():
        file_path = os.path.join(DOCS_DIR, meta["file"])
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    DOCS_CONTENT[resource_id] = f.read()
                print(f"✓ 已加载: {meta['file']}")
            except Exception as e:
                print(f"✗ 加载失败 {meta['file']}: {e}")
                DOCS_CONTENT[resource_id] = f"# 错误\n\n无法加载文档: {meta['file']}"
        else:
            print(f"✗ 文件不存在: {meta['file']}")
            DOCS_CONTENT[resource_id] = f"# 文件不存在\n\n文档文件 {meta['file']} 不存在"


@app.route("/")
def index():
    """首页"""
    return jsonify({
        "name": "Pulsar MCP 文档服务",
        "version": "1.0.0",
        "description": "基于 MCP 协议的 Pulsar 文档服务，为 LLM 提供结构化的 Pulsar 知识",
        "protocol": "MCP 1.0",
        "endpoints": {
            "/": "服务信息",
            "/llms.txt": "服务说明文档（llms.txt 规范）",
            "/mcp/list-resources": "列出所有可用资源",
            "/mcp/read-resource": "读取资源内容 (参数: name)",
            "/mcp/tools": "列出可用工具",
            "/mcp/call-tool": "调用工具 (POST)"
        },
        "resources": list(RESOURCES.keys())
    })


@app.route("/llms.txt")
def get_llms_txt():
    """返回 llms.txt 文档"""
    content = DOCS_CONTENT.get("llms.txt", "")
    return Response(content, mimetype="text/markdown; charset=utf-8")


@app.route("/mcp/list-resources")
def list_resources():
    """MCP 协议：列出所有可用资源"""
    resources = []
    for resource_id, meta in RESOURCES.items():
        resources.append({
            "uri": f"resource://{resource_id}",
            "name": meta["name"],
            "description": meta["description"],
            "mimeType": meta["mimeType"]
        })

    return jsonify({
        "resources": resources,
        "protocol": "mcp/1.0",
        "count": len(resources)
    })


@app.route("/mcp/read-resource")
def read_resource():
    """MCP 协议：读取指定资源内容"""
    name = request.args.get("name") or request.args.get("uri", "").replace("resource://", "")

    if not name:
        return jsonify({
            "error": "缺少资源名称参数",
            "usage": "请提供 name 或 uri 参数",
            "example": "/mcp/read-resource?name=pulsar-overview"
        }), 400

    if name not in RESOURCES and name not in DOCS_CONTENT:
        return jsonify({
            "error": f"资源 '{name}' 不存在",
            "available": list(RESOURCES.keys())
        }), 404

    content = DOCS_CONTENT.get(name, "")
    meta = RESOURCES.get(name, {})

    return jsonify({
        "uri": f"resource://{name}",
        "name": meta.get("name", name),
        "description": meta.get("description", ""),
        "mimeType": meta.get("mimeType", "text/markdown"),
        "text": content,
        "size": len(content)
    })


@app.route("/mcp/tools")
def list_tools():
    """MCP 协议：列出可用工具"""
    tools = [
        {
            "name": "list-resources",
            "description": "列出所有可用的文档资源",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "read-resource",
            "description": "读取指定文档资源的内容",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "资源名称，可选值: pulsar-overview, pulsar-concepts, pulsar-architecture, llms.txt",
                        "enum": list(RESOURCES.keys())
                    }
                },
                "required": ["name"]
            }
        },
        {
            "name": "search-docs",
            "description": "在文档中搜索关键词",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
                    },
                    "resource": {
                        "type": "string",
                        "description": "可选：限定搜索的资源范围",
                        "enum": list(RESOURCES.keys()) + [None]
                    }
                },
                "required": ["query"]
            }
        }
    ]

    return jsonify({
        "tools": tools,
        "protocol": "mcp/1.0"
    })


@app.route("/mcp/call-tool", methods=["POST"])
def call_tool():
    """MCP 协议：调用工具"""
    data = request.get_json() or {}
    tool_name = data.get("name") or data.get("tool")
    arguments = data.get("arguments", {})

    if tool_name == "list-resources":
        resources = list(RESOURCES.keys())
        return jsonify({
            "result": {
                "resources": resources,
                "count": len(resources),
                "details": {k: {"description": v["description"]} for k, v in RESOURCES.items()}
            }
        })

    elif tool_name == "read-resource":
        name = arguments.get("name")
        if not name:
            return jsonify({"error": "缺少资源名称", "available": list(RESOURCES.keys())}), 400

        content = DOCS_CONTENT.get(name)
        if content is None:
            return jsonify({"error": f"资源 '{name}' 不存在", "available": list(RESOURCES.keys())}), 404

        return jsonify({
            "result": {
                "resource": name,
                "content": content,
                "size": len(content)
            }
        })

    elif tool_name == "search-docs":
        query = arguments.get("query", "").lower()
        resource_filter = arguments.get("resource")

        if resource_filter and resource_filter in DOCS_CONTENT:
            search_in = {resource_filter: DOCS_CONTENT[resource_filter]}
        else:
            search_in = DOCS_CONTENT

        results = []
        for resource_name, content in search_in.items():
            # 搜索并提取上下文
            content_lower = content.lower()
            start = 0
            while True:
                idx = content_lower.find(query, start)
                if idx == -1:
                    break

                # 提取上下文（前后各 100 字符）
                context_start = max(0, idx - 100)
                context_end = min(len(content), idx + len(query) + 100)
                context = content[context_start:context_end]

                results.append({
                    "resource": resource_name,
                    "position": idx,
                    "context": context,
                    "match": content[idx:idx + len(query)]
                })

                start = idx + 1

        return jsonify({
            "result": {
                "query": query,
                "matches": results,
                "count": len(results),
                "searched_resources": list(search_in.keys())
            }
        })

    else:
        return jsonify({"error": f"未知工具: {tool_name}", "available_tools": ["list-resources", "read-resource", "search-docs"]}), 400


if __name__ == "__main__":
    # 加载文档
    print("=" * 60)
    print("Pulsar MCP 文档服务")
    print("=" * 60)
    load_docs()
    print("-" * 60)

    # 启动服务
    print(f"服务地址: http://localhost:5000")
    print(f"llms.txt: http://localhost:5000/llms.txt")
    print(f"资源列表: http://localhost:5000/mcp/list-resources")
    print("=" * 60)

    app.run(host="0.0.0.0", port=5000, debug=True)