import subprocess
import time
import requests
import pytest
import sys
import os
import signal

# 绝对路径配置
PROJECT_ROOT = "/root/ebpf_rust"
SANIC_APP_PATH = os.path.join(PROJECT_ROOT, "sanic", "app.py")
SANIC_PYTHON = os.path.join(PROJECT_ROOT, "sanic", "bin", "python")

PROXY_BIN_DIR = os.path.join(PROJECT_ROOT, "rust", "proxy_final", "target", "debug")
PROXY_BIN = os.path.join(PROXY_BIN_DIR, "proxy_final")

# 端口配置
BACKEND_PORT = 8001
PROXY_PORT = 8080

BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
PROXY_URL = f"http://127.0.0.1:{PROXY_PORT}"

@pytest.fixture(scope="module")
def env_setup():
    # 1. 启动 Sanic 后端
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
            requests.get(f"{BACKEND_URL}/ping")
            print("Backend is ready.")
            break
        except requests.exceptions.ConnectionError:
            time.sleep(0.5)
    else:
        pytest.fail("Backend failed to start")

    # 2. 编译并启动 Rust 代理
    print(f"Starting Rust proxy on port {PROXY_PORT} -> {BACKEND_PORT}...")
    
    # 确保已编译
    if not os.path.exists(PROXY_BIN):
         subprocess.run(["cargo", "build"], cwd=os.path.join(PROJECT_ROOT, "rust", "proxy_final"), check=True)

    proxy_proc = subprocess.Popen(
        [PROXY_BIN, "--proxy-addr", f"0.0.0.0:{PROXY_PORT}", "--backend-addr", f"127.0.0.1:{BACKEND_PORT}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid
    )

    # 等待代理启动 (通过尝试连接代理端口)
    for _ in range(20):
        try:
            # 尝试通过代理访问后端 Ping
            requests.get(f"{PROXY_URL}/ping")
            print("Proxy is ready.")
            break
        except requests.exceptions.ConnectionError:
            time.sleep(0.5)
    else:
        # 打印代理日志以便调试
        stdout, stderr = proxy_proc.communicate()
        print(f"Proxy failed to start.\nStdout: {stdout}\nStderr: {stderr}")
        os.killpg(os.getpgid(backend_proc.pid), signal.SIGTERM)
        pytest.fail("Proxy failed to start")

    yield

    # 打印后端日志，查看 400 错误原因
    try:
        outs, errs = backend_proc.communicate(timeout=2)
        print("\n=== Sanic Backend Output ===")
        print(outs.decode() if outs else "")
        print(errs.decode() if errs else "")
        print("============================\n")
    except subprocess.TimeoutExpired:
        pass

    # 清理
    print("Shutting down processes...")
    os.killpg(os.getpgid(proxy_proc.pid), signal.SIGTERM)
    os.killpg(os.getpgid(backend_proc.pid), signal.SIGTERM)
    proxy_proc.wait()
    backend_proc.wait()

def test_proxy_create_device(env_setup):
    """测试通过代理创建设备"""
    payload = {
        "id": "proxy_dev01",
        "name": "Proxy Sensor",
        "type": "proxy_type",
        "status": "online"
    }
    # 注意：请求发送给 PROXY_URL
    response = requests.post(f"{PROXY_URL}/devices", json=payload)
    assert response.status_code == 201, f"Proxy Create Failed: {response.text}"
    data = response.json()
    assert data["id"] == "proxy_dev01"

def test_proxy_get_device(env_setup):
    """测试通过代理获取设备"""
    response = requests.get(f"{PROXY_URL}/devices/proxy_dev01")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Proxy Sensor"

def test_proxy_list_devices(env_setup):
    """测试通过代理获取列表"""
    response = requests.get(f"{PROXY_URL}/devices")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1

def test_proxy_update_device(env_setup):
    """测试通过代理更新设备"""
    payload = {"status": "maintenance"}
    response = requests.put(f"{PROXY_URL}/devices/proxy_dev01", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "maintenance"

def test_proxy_delete_device(env_setup):
    """测试通过代理删除设备"""
    response = requests.delete(f"{PROXY_URL}/devices/proxy_dev01")
    assert response.status_code == 204
    
    # 验证删除
    response = requests.get(f"{PROXY_URL}/devices/proxy_dev01")
    assert response.status_code == 404
