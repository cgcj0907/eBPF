# TCP Congestion & Quality Monitor (eBPF + ClickHouse)

A comprehensive monitoring system for TCP network quality, utilizing **eBPF (BCC)** for kernel-level metrics collection, **Vector** for log aggregation, and **ClickHouse** for high-performance storage and analytics.

## 🌟 System Overview

This project consists of two main monitoring subsystems:

1.  **RPCLI (Client Monitor)**: Monitors TCP connection establishment from the client side.
    *   **Metrics**: Round Trip Time (RTT), SYN Received, Established Connections, Connection Success Rate.
    *   **Use Case**: Detecting connectivity issues, high latency, or SYN flood attacks.
2.  **RPCQI (Quality Monitor)**: Monitors TCP congestion control and quality from the server side.
    *   **Metrics**: Congestion States (Open, Loss, CWR, Recovery), Disorder, Retransmissions.
    *   **Use Case**: Analyzing network congestion, packet loss, and link quality.

## 📂 Directory Structure

```text
/root/ebpf_rust/
├── bpf/
│   ├── RPCLI_monitor.py      # Client-side metrics monitor (Python/BCC)
│   ├── RPCQI_monitor.py      # Quality/Congestion monitor (Python/BCC)
│   ├── email_alert.py        # Email alerting module
│   └── ...
├── vector/
│   ├── rpcli.toml            # Vector config for Default RPCLI
│   ├── rpcqi.toml            # Vector config for Default RPCQI
│   ├── rpcli_proxy.toml      # Vector config for Proxy RPCLI
│   └── rpcqi_proxy.toml      # Vector config for Proxy RPCQI
├── logs/                     # Log output directory
└── python/tests/             # Test scripts (e.g., test_syn.py)
```

## 🚀 Quick Start

### 1. Database Setup (ClickHouse)

Run the following commands to create the necessary tables in ClickHouse.

**Default Tables (General Services):**
```bash
curl -u default:password -X POST 'http://localhost:8123/' --data-binary '
CREATE TABLE IF NOT EXISTS rpcli_log (timestamp DateTime, port UInt16, avg_rtt_us Float64, syn_recv UInt64, established UInt64, retrans UInt64, success_rate Float64) ENGINE = MergeTree() ORDER BY timestamp;
CREATE TABLE IF NOT EXISTS rpcqi_summary (ts DateTime, AvgOpen Float64, AvgLoss Float64, AvgCWR Float64, AvgRecover Float64, AvgDisorder Float64, AvgChanges Float64, connections UInt32) ENGINE = MergeTree() ORDER BY ts;'
```

**Proxy Tables (Reverse Proxy / Port 8080):**
```bash
curl -u default:password -X POST 'http://localhost:8123/' --data-binary '
CREATE TABLE IF NOT EXISTS rpcli_log_proxy (timestamp DateTime, port UInt16, avg_rtt_us Float64, syn_recv UInt64, established UInt64, retrans UInt64, success_rate Float64) ENGINE = MergeTree() ORDER BY timestamp;
CREATE TABLE IF NOT EXISTS rpcqi_summary_proxy (ts DateTime, AvgOpen Float64, AvgLoss Float64, AvgCWR Float64, AvgRecover Float64, AvgDisorder Float64, AvgChanges Float64, connections UInt32) ENGINE = MergeTree() ORDER BY ts;'
```

### 2. Start Data Pipeline (Vector)

Vector aggregates logs from the monitors and writes them to ClickHouse. Run this command to load all configurations:

```bash
nohup /root/.vector/bin/vector \
  --config /root/ebpf_rust/vector/rpcli.toml \
  --config /root/ebpf_rust/vector/rpcqi.toml \
  --config /root/ebpf_rust/vector/rpcli_proxy.toml \
  --config /root/ebpf_rust/vector/rpcqi_proxy.toml \
  > /root/ebpf_rust/logs/vector.log 2>&1 &
```

### 3. Start eBPF Monitors

You can run multiple instances of the monitors for different purposes.

**Option A: Monitor Default Traffic (Sanic Port 8001/8081)**
```bash
# Client Metrics (Port 8001)
nohup python3 /root/ebpf_rust/bpf/RPCLI_monitor.py -p 8001 --json-log /root/ebpf_rust/logs/rpcli.log > /root/ebpf_rust/logs/rpcli.out 2>&1 &

# Quality Metrics (Port 8081, interval 5s)
nohup python3 /root/ebpf_rust/bpf/RPCQI_monitor.py -p 8001 5 --log-file /root/ebpf_rust/logs/rpcqi.log > /root/ebpf_rust/logs/rpcqi.out 2>&1 &
```

**Option B: Monitor Proxy Traffic (Port 8080)**
Using the `-p` flag separates the logs and storage.
```bash
# Client Metrics (Port 8080)
nohup python3 /root/ebpf_rust/bpf/RPCLI_monitor.py -p 8080 --json-log /root/ebpf_rust/logs/rpcli_proxy.log > /root/ebpf_rust/logs/rpcli_proxy.out 2>&1 &

# Quality Metrics (Port 8080, interval 5s)
nohup python3 /root/ebpf_rust/bpf/RPCQI_monitor.py -p 8080 5 --log-file /root/ebpf_rust/logs/rpcqi_proxy.log > /root/ebpf_rust/logs/rpcqi_proxy.out 2>&1 &
```

---

## 📊 Grafana Visualization

Use these SQL queries in Grafana (Time Series panel) to visualize the data.

### 🔹 Default Services

**1. Average RTT (Latency)**
```sql
SELECT
    timestamp AS time,
    avg_rtt_us AS "Average RTT (us)",
    port AS "Server Port"
FROM rpcli_log
WHERE timestamp >= now() - INTERVAL 24 HOUR
ORDER BY time ASC
```

**2. Connection Success Rate**
```sql
SELECT
    CASE 
        WHEN success_rate = 100 THEN '100% Success'
        WHEN success_rate >= 90 THEN '90-99% Success'
        WHEN success_rate >= 70 THEN '70-89% Success'
        ELSE '<70% Success'
    END AS category,
    COUNT(*) AS cnt
FROM rpcli_log
WHERE timestamp >= now() - INTERVAL 24 HOUR
GROUP BY category;
```

**3. Congestion States (Network Quality)**
```sql
SELECT
    ts AS time,
    AvgOpen AS "Open",
    AvgLoss AS "Loss",
    AvgRecover AS "Recover"
FROM rpcqi_summary
WHERE ts >= now() - INTERVAL 24 HOUR
ORDER BY time ASC
```

### 🔹 Proxy Services (Port 8080)

**1. Proxy Average RTT**
```sql
SELECT
    timestamp AS time,
    avg_rtt_us AS "Average RTT (us)",
    port AS "Server Port"
FROM rpcli_log_proxy
WHERE timestamp >= now() - INTERVAL 24 HOUR
ORDER BY time ASC
```

**2. Proxy Success Rate**
```sql
SELECT
    CASE 
        WHEN success_rate = 100 THEN '100% Success'
        WHEN success_rate >= 90 THEN '90-99% Success'
        WHEN success_rate >= 70 THEN '70-89% Success'
        ELSE '<70% Success'
    END AS category,
    COUNT(*) AS cnt
FROM rpcli_log_proxy
WHERE timestamp >= now() - INTERVAL 24 HOUR
GROUP BY category;
```

**3. Proxy Congestion States**
```sql
SELECT
    ts AS time,
    AvgOpen AS "Open",
    AvgLoss AS "Loss",
    AvgRecover AS "Recover"
FROM rpcqi_summary_proxy
WHERE ts >= now() - INTERVAL 24 HOUR
ORDER BY time ASC
```

## 🧪 Testing

Use the provided test scripts to generate traffic and verify the pipeline.

### 1. SYN Flood / Half-Open Test
Generates incomplete TCP connections (SYN only) to simulate traffic or attacks.
```bash
# Uses system Python (requires scapy)
/usr/bin/python3 /root/ebpf_rust/python/tests/test_syn.py -p 8080
```

### 2. End-to-End Proxy Test (Real Traffic)
Starts the backend, the proxy, and sends real HTTP CRUD requests. This generates **healthy** traffic (high success rate).
```bash
# Uses Sanic virtual environment (requires requests, pytest)
/root/ebpf_rust/sanic/bin/python -m pytest -v -s /root/ebpf_rust/python/tests/test_proxy_e2e.py
```

After running the tests, check the `*_proxy` tables in ClickHouse to see the generated data.
