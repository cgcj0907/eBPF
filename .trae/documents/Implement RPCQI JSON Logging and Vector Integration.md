I will implement the JSON logging and ClickHouse integration as follows:

### 1. Modify `bpf/RPCQI_monitor.py`

I will update the script to log metrics to a file in **NDJSON** (Newline Delimited JSON) format. This allows Vector to easily parse each line as a structured event.

* **Log File**: `/root/ebpf_rust/logs/rpcqi.log`

* **Format**: `{"timestamp": "...", "port": 8001, "avg_rtt_us": 12.3, ...}`

* **Logic**: Inside the main loop, I will iterate through the collected `port_data` and write one JSON line per port per interval.

### 2. Update `vector/tcpcong.toml`

I will add a new pipeline to the existing Vector configuration to handle RPCQI logs.

* **Source**: Read from `/root/ebpf_rust/logs/rpcqi.log`.

* **Transform**: Use `parse_json` to decode the log lines.

* **Sink**: Write to ClickHouse table `rpcqi_log`.

### 3. Create ClickHouse Table

I will create the `rpcqi_log` table in ClickHouse to store the metrics.

**SQL Schema:**

```sql
CREATE TABLE IF NOT EXISTS default.rpcqi_log (
    timestamp DateTime,
    port UInt16,
    avg_rtt_us Float64,
    syn_recv UInt64,
    established UInt64,
    retrans UInt64,
    success_rate Float64
) ENGINE = MergeTree()
ORDER BY (timestamp, port);
```

### Execution Plan

1. **Edit** **`bpf/RPCQI_monitor.py`** to add JSON logging.
2. **Edit** **`vector/tcpcong.toml`** to add the RPCQI pipeline.
3. **Run ClickHouse Client** to create the table.

