# Apache Pulsar 概述

## 什么是 Pulsar？

Apache Pulsar 是一个云原生的分布式消息流平台，最初由 Yahoo 开发，于 2016 年开源并捐赠给 Apache 基金会。Pulsar 结合了传统消息队列和流处理的能力，提供统一的消息模型。

## 核心定位

Pulsar 定位为企业级的消息流平台，解决以下问题：

- **高吞吐量消息传递**：支持百万级 Topic 和每秒百万级消息
- **低延迟**：端到端延迟可低于 5ms
- **高可用性**：99.99% 可用性保证
- **地理分布**：跨数据中心复制能力
- **多租户隔离**：企业级资源隔离

## 主要特性

### 云原生架构

Pulsar 采用分层架构设计，将服务层（Broker）与存储层（BookKeeper）分离：

```
┌─────────────────┐
│  Broker 服务层   │  无状态，可水平扩展
├─────────────────┤
│ BookKeeper 存储层 │  持久化，高可靠
└─────────────────┘
```

优势：
- 服务层和存储层独立扩展
- Broker 无状态，故障恢复快
- 存储层可针对不同负载优化

### 多租户支持

原生多租户架构：

- **Tenant（租户）**：顶级资源隔离单位
- **Namespace（命名空间）**：租户内的逻辑分组
- **Topic（主题）**：消息传递的基本单位

资源隔离包括：
- 配额管理
- 访问控制
- 流量控制

### 统一消息模型

Pulsar 统一支持两种消息模式：

#### 队列模式（Queuing）

```
Producer → [Message Queue] → Consumer A
                           → Consumer B
                           → Consumer C
```

- 消息被多个消费者共享消费
- 每条消息只被消费一次
- 适合任务分发场景

#### 发布-订阅模式（Pub-Sub）

```
Producer → [Topic] → Consumer A (Subscription 1)
                    → Consumer B (Subscription 2)
                    → Consumer C (Subscription 3)
```

- 消息广播给所有订阅者
- 每个订阅独立维护消费进度
- 适合事件通知场景

### 持久化存储

基于 Apache BookKeeper 的高可靠存储：

- **Ledger**：不可变的日志段，顺序追加写入
- **多副本**：每条消息写入多个 Bookie 节点
- **强一致性**：使用 Quorum 机制保证一致性

### 地理复制

内置跨数据中心复制能力：

```
┌──────────┐     ┌──────────┐
│ 区域 A   │ ←→  │ 区域 B   │
│ Pulsar   │     │ Pulsar   │
└──────────┘     └──────────┘
```

- 异步复制：低延迟，最终一致
- 同步复制：强一致性保证
- 自动故障转移

### 可扩展性

- 支持 **百万级 Topic**
- **水平扩展** Broker 和 BookKeeper
- 自动分区和负载均衡
- 支持海量 Topic 场景

## 与其他系统对比

### Pulsar vs Kafka

| 特性 | Pulsar | Kafka |
|------|--------|-------|
| 架构 | 分层（服务+存储） | 单体架构 |
| 多租户 | 原生支持 | 需额外方案 |
| 地理复制 | 内置 | 需 MirrorMaker |
| 消息模型 | 队列 + 流 | 流为主 |
| 存储 | BookKeeper | 本地磁盘 |
| Topic 数量 | 百万级 | 万级（受限于分区） |

### Pulsar vs RabbitMQ

| 特性 | Pulsar | RabbitMQ |
|------|--------|----------|
| 吞吐量 | 高（百万/秒） | 中等 |
| 延迟 | 低（<5ms） | 低 |
| 持久化 | 强一致 | 可配置 |
| 协议支持 | 多协议 | AMQP |
| 分布式 | 云原生 | 集群模式 |

## 适用场景

### 1. 消息队列

- 任务分发
- 异步处理
- 服务解耦

### 2. 事件流处理

- 事件溯源
- 日志聚合
- 实时数据分析

### 3. 微服务通信

- 服务间消息传递
- 事件驱动架构
- CQRS 实现

### 4. 金融交易

- 高可靠消息传递
- 强一致性保证
- 低延迟要求

### 5. 物联网（IoT）

- 海量设备连接
- 地理分布式部署
- 实时数据处理

## 快速开始

### 启动单机模式

```bash
# 使用 Docker
docker run -it \
  -p 6650:6650 \
  -p 8080:8080 \
  --name pulsar-standalone \
  apachepulsar/pulsar:latest \
  bin/pulsar standalone
```

### 创建生产者

```python
from pulsar import Client

client = Client('pulsar://localhost:6650')
producer = client.create_producer('persistent://public/default/my-topic')

for i in range(10):
    producer.send(('Hello Pulsar %d' % i).encode('utf-8'))

client.close()
```

### 创建消费者

```python
from pulsar import Client

client = Client('pulsar://localhost:6650')
consumer = client.subscribe(
    'persistent://public/default/my-topic',
    'my-subscription'
)

while True:
    msg = consumer.receive()
    print("Received message:", msg.data().decode('utf-8'))
    consumer.acknowledge(msg)

client.close()
```

## 版本历史

- **2016** - Yahoo 开源 Pulsar
- **2018** - Pulsar 成为 Apache 顶级项目
- **2022** - Pulsar 2.10 发布，增强事务支持
- **2023** - Pulsar 3.0 发布，Java 17 支持
- **2024** - Pulsar 4.0 发布，性能大幅提升

## 参考链接

- [Apache Pulsar 官网](https://pulsar.apache.org/)
- [Pulsar 官方文档](https://pulsar.apache.org/docs/)
- [Pulsar GitHub](https://github.com/apache/pulsar)