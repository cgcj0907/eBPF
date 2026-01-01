# Swap RPCLI and RPCQI Monitoring Scripts

The user identified that the scripts `RPCLI_monitor.py` and `RPCQI_monitor.py` are named inversely to their intended functions.
- Currently: `RPCQI` handles Client-side metrics (RTT, SYN), and `RPCLI` handles Server/Quality metrics (Congestion).
- Goal: Swap them so `RPCLI` handles Client metrics and `RPCQI` handles Quality metrics.

## Implementation Steps

1.  **Stop Services**
    - Stop running Python monitoring scripts (`RPCQI_monitor.py`, `tcpcong.py`/`RPCLI_monitor.py`).
    - Stop Vector agent.

2.  **Rename Scripts (Swap)**
    - Rename `bpf/RPCQI_monitor.py` (RTT/SYN) -> `bpf/RPCLI_monitor.py`.
    - Rename `bpf/RPCLI_monitor.py` (Congestion) -> `bpf/RPCQI_monitor.py`.

3.  **Update Script Internals**
    - **`RPCLI_monitor.py` (RTT/SYN)**:
        - Change Log Path: `logs/rpcqi.log` -> `logs/rpcli.log`.
        - Change Alert Subject: "RPCQI Health" -> "RPCLI Health".
    - **`RPCQI_monitor.py` (Congestion)**:
        - Change Log Path: `logs/tcpcong.log` -> `logs/rpcqi.log`.
        - Change Alert Subject: "TCP Congestion" -> "RPCQI Health".

4.  **Migrate ClickHouse Tables**
    - Rename `rpcqi_log` (RTT Schema) -> `rpcli_log`.
    - Rename `rpcli_summary` (Congestion Schema) -> `rpcqi_summary`.

5.  **Update Vector Configuration (`vector/tcpcong.toml`)**
    - Configure `rpcli_source` to read `rpcli.log` and write to `rpcli_log` (JSON format).
    - Configure `rpcqi_source` to read `rpcqi.log` and write to `rpcqi_summary` (Key-Value format).

6.  **Restart Services**
    - Start Vector with updated config.
    - Start `RPCLI_monitor.py` and `RPCQI_monitor.py` in background.
    - Verify logs and ClickHouse data insertion.
