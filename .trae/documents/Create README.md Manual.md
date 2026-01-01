I will create a comprehensive `README.md` file in the project root (`/root/ebpf_rust/README.md`) to document the system usage, architecture, and configuration.

The README will include:

1. **Project Overview**: Explanation of the RPCLI (Client) and RPCQI (Quality) monitoring systems.
2. **Architecture**: How eBPF, Vector, and ClickHouse work together.
3. **Installation & Prerequisites**: Required tools (bcc, vector, clickhouse).
4. **Quick Start Guide**:

   * Step 1: Create ClickHouse Tables (SQL for both Standard and Proxy tables).

   * Step 2: Start Vector Aggregator (Command to load all `.toml` configs).

   * Step 3: Start eBPF Monitors (Commands for default and proxy modes).
5. **Data Visualization**:

   * Ready-to-use SQL queries for Grafana (RTT, Success Rate, Congestion States) for both Standard and Proxy datasets.
6. **Testing**: Instructions on running `test_syn.py` to verify the pipeline.

