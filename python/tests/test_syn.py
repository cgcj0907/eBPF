import time
import random
import sys
import argparse
import subprocess
import os
import signal
import urllib.request
import urllib.error
import time
import random
from scapy.all import IP, TCP, send, conf

# 绝对路径配置 (复用 test_proxy_e2e.py 的配置)
PROJECT_ROOT = "/root/ebpf_rust"
SANIC_APP_PATH = os.path.join(PROJECT_ROOT, "sanic", "app.py")
SANIC_PYTHON = os.path.join(PROJECT_ROOT, "sanic", "bin", "python")
PROXY_BIN_DIR = os.path.join(PROJECT_ROOT, "rust", "proxy_final", "target", "debug")
PROXY_BIN = os.path.join(PROXY_BIN_DIR, "proxy_final")

# 端口配置
BACKEND_PORT = 8001
DEFAULT_TARGET_PORT = 8080 # Proxy Port
DEFAULT_TARGET_IP = "127.0.0.1"

BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
PROXY_URL = f"http://127.0.0.1:{DEFAULT_TARGET_PORT}"

# 模拟的业务操作列表
OPERATIONS = [
    "CREATE (POST /devices)",
    "READ   (GET /devices)",
    "UPDATE (PUT /devices)",
    "DELETE (DELETE /devices)"
]

def setup_services():
    """启动 Sanic 后端和 Rust 代理"""
    print(f"Starting Sanic backend on port {BACKEND_PORT}...")
    backend_proc = subprocess.Popen(
        [SANIC_PYTHON, SANIC_APP_PATH],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid
    )

    # 等待后端启动
    for _ in range(20):
        try:
            with urllib.request.urlopen(f"{BACKEND_URL}/ping") as response:
                if response.status == 200:
                    print("Backend is ready.")
                    break
        except (urllib.error.URLError, ConnectionResetError):
            time.sleep(0.5)
    else:
        print("Backend failed to start")
        os.killpg(os.getpgid(backend_proc.pid), signal.SIGTERM)
        sys.exit(1)

    print(f"Starting Rust proxy on port {DEFAULT_TARGET_PORT} -> {BACKEND_PORT}...")
    
    # 确保已编译
    if not os.path.exists(PROXY_BIN):
         subprocess.run(["cargo", "build"], cwd=os.path.join(PROJECT_ROOT, "rust", "proxy_final"), check=True)

    proxy_proc = subprocess.Popen(
        [PROXY_BIN, "--proxy-addr", f"0.0.0.0:{DEFAULT_TARGET_PORT}", "--backend-addr", f"127.0.0.1:{BACKEND_PORT}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid
    )

    # 等待代理启动
    for _ in range(20):
        try:
            with urllib.request.urlopen(f"{PROXY_URL}/ping") as response:
                if response.status == 200:
                    print("Proxy is ready.")
                    break
        except (urllib.error.URLError, ConnectionResetError):
            time.sleep(0.5)
    else:
        print("Proxy failed to start")
        os.killpg(os.getpgid(backend_proc.pid), signal.SIGTERM)
        os.killpg(os.getpgid(proxy_proc.pid), signal.SIGTERM)
        sys.exit(1)
        
    return backend_proc, proxy_proc

def teardown_services(backend_proc, proxy_proc):
    """清理服务进程"""
    print("Shutting down processes...")
    if proxy_proc:
        os.killpg(os.getpgid(proxy_proc.pid), signal.SIGTERM)
        proxy_proc.wait()
    if backend_proc:
        os.killpg(os.getpgid(backend_proc.pid), signal.SIGTERM)
        backend_proc.wait()

def send_syn_flood(target_ip, target_port):
    # 确保使用 Layer 3 socket
    conf.L3socket = conf.L3socket or conf.use_pcap
    
    print(f"Starting SYN Half-Open Connect Test to {target_ip}:{target_port}")
    print("Simulating unsuccessful connections for CRUD operations...\n")

    for op in OPERATIONS:
        # 随机源端口，模拟不同的客户端连接
        src_port = random.randint(1024, 65535)
        
        # 构造 SYN 包
        # flags="S" 表示 SYN
        ip_layer = IP(dst=target_ip)
        tcp_layer = TCP(sport=src_port, dport=target_port, flags="S", seq=random.randint(1000, 9000))
        packet = ip_layer / tcp_layer
        
        print(f"[:] Simulating {op}")
        print(f"    Sending SYN packet (Sport: {src_port} -> Dport: {target_port})...")
        
        # 发送包 (verbose=0 不打印 scapy 内部日志)
        send(packet, verbose=0)
        
        # 暂停一下，方便观察日志
        time.sleep(1)

    print("\nTest finished. Check RPCQI_monitor logs for SYN_RECV counts and low Success Rate.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SYN Flood Test Script")
    parser.add_argument("-p", "--port", type=int, default=DEFAULT_TARGET_PORT, help="Target port")
    parser.add_argument("--ip", type=str, default=DEFAULT_TARGET_IP, help="Target IP")
    args = parser.parse_args()

    # 1. 启动服务
    backend_proc, proxy_proc = setup_services()

    # 2. 执行测试 (简单的权限检查)
    try:
        send_syn_flood(args.ip, args.port)
    except PermissionError:
        print("Error: This script requires root privileges to send raw packets.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # 3. 清理服务
        teardown_services(backend_proc, proxy_proc)
