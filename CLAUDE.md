# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Pulsar MCP (Model Context Protocol) documentation service that serves Apache Pulsar documentation to LLMs. It provides structured access to Pulsar concepts, architecture, and overview documentation through HTTP endpoints.

## Running the Service

```bash
python server.py
```

The server runs on port 8080 by default. Key endpoints:
- `/` - Lists available files (JSON)
- `/health` - Health check endpoint
- `/llms.txt` - MCP service documentation
- `/{filename}` - Serves any file in the directory

## Architecture

Single-file Python HTTP server (`server.py`) using the standard library `http.server` module. No external dependencies required.

The server:
- Serves static markdown documentation files
- Adds CORS headers for cross-origin access
- Provides MCP-style resource listing and reading patterns

## Documentation Files

- `llms.txt` - MCP endpoint documentation for LLM clients
- `pulsar-overview.md` - Apache Pulsar introduction and features
- `pulsar-concepts.md` - Core concepts: Producer, Consumer, Topic, Subscription, etc.
- `pulsar-architecture.md` - Layered architecture: Broker, BookKeeper, ZooKeeper

## Language

Documentation content is primarily in Chinese. Code comments and service messages are also in Chinese.