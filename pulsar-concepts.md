# Pulsar 核心概念

## 概念总览

Apache Pulsar 的核心概念可以分为三个层次：

```
┌─────────────────────────────────────────┐
│             应用层                       │
│   Producer  ←→  Topic  ←→  Consumer     │
├─────────────────────────────────────────┤
│             服务层                       │
│          Broker 集群                     │
├─────────────────────────────────────────┤
│             存储层                       │
│   BookKeeper + ZooKeeper                │
└─────────────────────────────────────────┘
```

---

## 1. 消息模型

### 1.1 Producer（生产者）

生产者是向 Pulsar 主题发布消息的应用程序。

#### 发送模式

| 模式 | 描述 | 适用场景 |
|------|------|----------|
| 同步发送 | 阻塞等待确认 | 需要确保消息已存储 |
| 异步发送 | 非阻塞，回调通知 | 高吞吐量场景 |
| 延迟发送 | 指定延迟后投递 | 定时任务、延迟处理 |

#### 发送示例

```python
# 同步发送
producer.send(message, sync=True)

# 异步发送
future = producer.send_async(message, callback=callback_func)

# 延迟发送（10秒后）
producer.send(message, deliver_after=timedelta(seconds=10))

# 指定时间发送
producer.send(message, deliver_at=datetime(2025, 1, 1, 0, 0))
```

#### 消息路由

当 Topic 有多个分区时，生产者可以选择路由策略：

| 策略 | 描述 |
|------|------|
| RoundRobinPartition | 轮询分配到各分区（默认） |
| SinglePartition | 随机选择一个分区 |
| CustomPartition | 自定义路由逻辑（基于 Key） |

#### 消息属性

```python
producer.send(
    content,                              # 消息内容
    partition_key='user-123',             # 分区键（保证顺序）
    ordering_key='order-456',              # 排序键
    properties={                          # 自定义属性
        'source': 'web',
        'trace_id': 'abc-123'
    },
    event_timestamp=int(time.time() * 1000),  # 事件时间戳
    sequence_id=1,                        # 序列号
    disable_replication=False             # 是否禁用复制
)
```

---

### 1.2 Consumer（消费者）

消费者订阅主题并处理消息的应用程序。

#### 订阅模式

Pulsar 支持四种订阅模式：

##### Exclusive（独占）

```
Topic ────→ Consumer A（独占）
```

- 只能有一个消费者
- 消息按顺序传递
- 适合顺序处理场景

##### Shared（共享）

```
Topic ────→ Consumer A（处理消息 1, 3, 5...）
      ────→ Consumer B（处理消息 2, 4, 6...）
      ────→ Consumer C（处理消息 7, 8, 9...）
```

- 多个消费者共享订阅
- 消息轮询分配
- 不保证顺序
- 消费者故障时消息可重发

##### Failover（故障转移）

```
Topic ────→ Consumer A（主消费者）───→ 活跃
      ────→ Consumer B（备消费者）───→ 待命
```

- 主消费者处理所有消息
- 备消费者待命
- 主消费者故障时自动切换

##### Key_Shared（键共享）

```
Topic ────→ Consumer A（处理 Key=1 的消息）
      ────→ Consumer B（处理 Key=2 的消息）
      ────→ Consumer C（处理 Key=3 的消息）
```

- 相同 Key 的消息始终发给同一消费者
- 保证 Key 级别的顺序
- 消费者可以动态增减

#### 消息确认

```python
# 确认消息（消费成功）
consumer.acknowledge(msg)

# 否定确认（重新入队）
consumer.negative_acknowledge(msg)

# 批量确认
consumer.acknowledge_cumulative(msg)  # 确认该消息及之前的所有消息
```

#### 重试队列

```python
# 配置重试队列
consumer = client.subscribe(
    topic,
    subscription_name,
    dead_letter_policy=DeadLetterPolicy(
        max_redeliver_count=3,           # 最大重试次数
        dead_letter_topic='dlq-topic'    # 死信队列
    )
)
```

---

### 1.3 Topic（主题）

主题是消息的逻辑通道，生产者向主题发布消息，消费者订阅主题接收消息。

#### Topic 命名格式

```
{persistent|non-persistent}://{tenant}/{namespace}/{topic}
```

| 部分 | 说明 | 示例 |
|------|------|------|
| 持久类型 | persistent 或 non-persistent | `persistent` |
| tenant | 租户名称 | `public` |
| namespace | 命名空间 | `default` |
| topic | 主题名称 | `my-topic` |

完整示例：
```
persistent://public/default/my-topic
non-persistent://company/billing/invoices
```

#### Topic 类型

| 类型 | 特点 | 适用场景 |
|------|------|----------|
| persistent | 消息持久化到 BookKeeper | 需要数据可靠性 |
| non-persistent | 消息只在内存中 | 允许丢失的高吞吐场景 |

#### 分区 Topic

```
persistent://public/default/my-topic
├── partition-0
├── partition-1
├── partition-2
└── partition-3
```

- 分区数量在创建时确定
- 每个分区是一个独立的 Topic
- 提高并行度和吞吐量

---

### 1.4 Message（消息）

消息是生产者和消费者之间传递的数据单元。

#### 消息结构

```
┌────────────────────────────────────┐
│            消息元数据               │
├────────────────────────────────────┤
│ publishTime    │ 发布时间戳         │
│ eventTime      │ 事件时间戳         │
│ sequenceId     │ 序列号             │
│ partitionKey   │ 分区键             │
│ orderingKey    │ 排序键             │
│ properties     │ 自定义属性         │
│ producerName   │ 生产者名称         │
│ schemaVersion  │ Schema 版本        │
├────────────────────────────────────┤
│             消息体                  │
│          (payload)                 │
└────────────────────────────────────┘
```

#### 消息大小限制

- 默认最大消息大小：5MB
- 可配置最大值：取决于配置
- 大消息建议使用分块发送

---

## 2. 订阅与游标

### 2.1 Subscription（订阅）

订阅定义了消费者如何接收消息。

#### 订阅模式选择指南

| 需求 | 推荐模式 |
|------|----------|
| 保证消息顺序 | Exclusive |
| 高吞吐并行处理 | Shared |
| 高可用主备切换 | Failover |
| 按 Key 有序并行 | Key_Shared |

#### 订阅持久化

```
Subscription = Cursor + Topic
```

- 订阅状态（Cursor）持久化存储
- 消费者断开后重新连接，继续从上次位置消费

---

### 2.2 Cursor（游标）

游标记录消费者的消费位置。

#### 游标特性

- 持久化存储在 Ledger 中
- 记录最后确认的消息 ID
- 支持消息回溯（重置消费位置）

#### 游标操作

```python
# 重置到最早位置
consumer.seek(earliest=True)

# 重置到最新位置
consumer.seek(latest=True)

# 重置到指定时间
consumer.seek(timestamp=int(time.time() * 1000) - 3600000)  # 1小时前

# 重置到指定消息 ID
consumer.seek(message_id=msg_id)
```

---

## 3. 存储模型

### 3.1 Ledger

Ledger 是 BookKeeper 中的基本存储单元。

#### Ledger 特性

- **不可变**：一旦关闭不可修改
- **追加写入**：只能顺序追加
- **分段存储**：单个 Topic 由多个 Ledger 组成

```
Topic
├── Ledger 1 (segment-1) ─── 已关闭，只读
├── Ledger 2 (segment-2) ─── 已关闭，只读
└── Ledger 3 (segment-3) ─── 当前活跃，可写入
```

#### Ledger 配置

| 参数 | 说明 | 默认值 |
|------|------|--------|
| ledgerSize | 单个 Ledger 大小阈值 | 100MB |
| ledgerTime | Ledger 时长阈值 | 4小时 |
| ensembleSize | 写入副本数 | 3 |
| writeQuorum | 写入确认数 | 2 |
| ackQuorum | 确认数 | 2 |

---

### 3.2 BookKeeper

Apache BookKeeper 是 Pulsar 的底层存储系统。

#### 核心概念

```
┌─────────────────────────────────────┐
│            BookKeeper 集群           │
├─────────────────────────────────────┤
│  ┌─────────┐ ┌─────────┐ ┌─────────┐│
│  │ Bookie  │ │ Bookie  │ │ Bookie  ││
│  │  (节点1) │ │  (节点2) │ │  (节点3) ││
│  └─────────┘ └─────────┘ └─────────┘│
└─────────────────────────────────────┘
```

- **Bookie**：BookKeeper 的存储节点
- **Entry**：单个消息记录
- **Ledger**：Entry 的集合

#### 写入流程

```
Producer → Broker → Bookie 1 (复制副本1)
                  → Bookie 2 (复制副本2)
                  → Bookie 3 (复制副本3)
                  ← 确认 (Quorum 达成)
                  ← 返回确认给 Producer
```

#### Quorum 机制

- **Ensemble (E)**：参与写入的 Bookie 数量
- **Write Quorum (WQ)**：需要成功写入的副本数
- **Ack Quorum (AQ)**：需要确认的副本数

示例配置：E=3, WQ=2, AQ=2
- 数据写入 3 个 Bookie
- 任意 2 个写入成功即可返回
- 保证至少 2 个副本持久化

---

## 4. 服务组件

### 4.1 Broker

Broker 是 Pulsar 的服务层组件，负责消息传递。

#### Broker 职责

- 接收生产者消息
- 投递消息给消费者
- Topic 负载均衡
- 消息协议转换
- 管理 Topic 和分区

#### Broker 特性

- **无状态**：Broker 不存储数据
- **可水平扩展**：动态增减节点
- **自动故障转移**：Broker 故障后 Topic 自动迁移

#### Broker 与 Topic

```
┌─────────────────────────────────┐
│           Broker 1              │
│   Topic-A, Topic-B, Topic-C     │
├─────────────────────────────────┤
│           Broker 2              │
│   Topic-D, Topic-E, Topic-F     │
├─────────────────────────────────┤
│           Broker 3              │
│   Topic-G, Topic-H, Topic-I     │
└─────────────────────────────────┘
```

---

### 4.2 ZooKeeper

ZooKeeper 提供 Pulsar 集群的协调服务。

#### ZooKeeper 存储

| 路径 | 内容 |
|------|------|
| /cluster | 集群配置信息 |
| /brokers | Broker 注册信息 |
| /loadbalance | 负载均衡状态 |
| /namespace | 命名空间策略 |
| /bookies | Bookie 列表 |

#### ZooKeeper 功能

- **服务发现**：Broker 和 Bookie 注册
- **配置管理**：存储集群配置
- **领导选举**：Broker 选举
- **协调服务**：分布式协调

---

## 5. 多租户

### 5.1 Tenant（租户）

租户是 Pulsar 中顶层的资源隔离单位。

#### 租户特性

- 资源配额限制
- 命名空间管理
- 权限隔离

#### 租户操作

```bash
# 创建租户
pulsar-admin tenants create my-tenant \
  --admin-roles admin \
  --allowed-clusters us-west,us-east

# 查看租户列表
pulsar-admin tenants list

# 删除租户
pulsar-admin tenants delete my-tenant
```

---

### 5.2 Namespace（命名空间）

命名空间是租户内的逻辑分组单元。

#### 命名空间特性

- Topic 的管理单元
- 策略配置的单位
- 资源配额设置

#### 命名空间策略

| 策略 | 说明 |
|------|------|
| messageTTL | 消息生存时间 |
| retention | 消息保留策略 |
| backlogQuota | 积压配额 |
| maxProducers | 最大生产者数 |
| maxConsumers | 最大消费者数 |
| replicationClusters | 复制集群列表 |

#### 命名空间操作

```bash
# 创建命名空间
pulsar-admin namespaces create my-tenant/my-namespace

# 设置消息保留
pulsar-admin namespaces set-retention my-tenant/my-namespace \
  --size 10G \
  --time 7d

# 设置消息 TTL
pulsar-admin namespaces set-message-ttl my-tenant/my-namespace \
  --ttl 86400
```

---

## 6. Schema

### 6.1 Schema 类型

Pulsar 支持多种 Schema 类型：

| 类型 | 说明 |
|------|------|
| Primitive | 原始类型（String, Bytes, Int64 等） |
| Avro | Avro 结构化 Schema |
| JSON | JSON Schema |
| Protobuf | Protocol Buffer Schema |
| KeyValue | 键值对 Schema |

### 6.2 Schema 使用

```python
from pulsar import Schema

# 使用 String Schema
producer = client.create_producer(
    topic,
    schema=Schema.STRING
)

# 使用 Avro Schema
from pulsar.schema import AvroSchema, Record

class User(Record):
    name = String()
    age = Integer()

producer = client.create_producer(
    topic,
    schema=AvroSchema(User)
)
```

### 6.3 Schema 兼容性

| 策略 | 说明 |
|------|------|
| Backward | 新 Schema 可以读取旧数据 |
| Forward | 旧 Schema 可以读取新数据 |
| Full | 双向兼容 |
| Always Compatible | 总是兼容（无检查） |

---

## 7. 安全模型

### 7.1 认证

支持多种认证方式：

- **TLS 客户端证书**
- **Token 认证**
- **JWT 认证**
- **Athenz 认证**

### 7.2 授权

基于角色的访问控制：

```
Tenant
└── Namespace
    └── Topic
        └── 权限配置
            ├── produce (生产权限)
            ├── consume (消费权限)
            └── functions (函数权限)
```

---

## 总结

Pulsar 核心概念层次：

1. **应用层**：Producer、Consumer、Message
2. **逻辑层**：Topic、Subscription、Schema
3. **管理层**：Tenant、Namespace、Policy
4. **服务层**：Broker
5. **存储层**：BookKeeper、Ledger、Cursor
6. **协调层**：ZooKeeper