import time
import random
import sys
from scapy.all import IP, TCP, send, conf

# 目标配置
TARGET_IP = "127.0.0.1"
TARGET_PORT = 8080

# 模拟的业务操作列表
OPERATIONS = [
    "CREATE (POST /devices)",
    "READ   (GET /devices)",
    "UPDATE (PUT /devices)",
    "DELETE (DELETE /devices)"
]

def send_syn_flood():
    # 确保使用 Layer 3 socket
    conf.L3socket = conf.L3socket or conf.use_pcap
    
    print(f"Starting SYN Half-Open Connect Test to {TARGET_IP}:{TARGET_PORT}")
    print("Simulating unsuccessful connections for CRUD operations...\n")

    for op in OPERATIONS:
        # 随机源端口，模拟不同的客户端连接
        src_port = random.randint(1024, 65535)
        
        # 构造 SYN 包
        # flags="S" 表示 SYN
        ip_layer = IP(dst=TARGET_IP)
        tcp_layer = TCP(sport=src_port, dport=TARGET_PORT, flags="S", seq=random.randint(1000, 9000))
        packet = ip_layer / tcp_layer
        
        print(f"[:] Simulating {op}")
        print(f"    Sending SYN packet (Sport: {src_port} -> Dport: {TARGET_PORT})...")
        
        # 发送包 (verbose=0 不打印 scapy 内部日志)
        send(packet, verbose=0)
        
        # 暂停一下，方便观察日志
        time.sleep(1)

    print("\nTest finished. Check RPCQI_monitor logs for SYN_RECV counts and low Success Rate.")

if __name__ == "__main__":
    # 简单的权限检查（Scapy 发包通常需要 root）
    try:
        send_syn_flood()
    except PermissionError:
        print("Error: This script requires root privileges to send raw packets.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
