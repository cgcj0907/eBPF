import subprocess
import time
import requests
import pytest
import sys
import os
import signal

# 绝对路径配置
PROJECT_ROOT = "/root/ebpf_rust"
APP_PATH = os.path.join(PROJECT_ROOT, "sanic", "app.py")
PYTHON_EXE = os.path.join(PROJECT_ROOT, "sanic", "bin", "python")
BASE_URL = "http://127.0.0.1:8001"

@pytest.fixture(scope="module")
def sanic_server():
    print(f"Starting Sanic server from {APP_PATH}...")
    # 启动 Sanic 服务
    process = subprocess.Popen(
        [PYTHON_EXE, APP_PATH], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid # 创建新的进程组，方便清理
    )
    
    # 简单的健康检查重试循环
    for i in range(10):
        try:
            requests.get(f"{BASE_URL}/devices")
            break
        except requests.exceptions.ConnectionError:
            time.sleep(0.5)
    else:
        # 如果超时，打印日志并退出
        stdout, stderr = process.communicate()
        print(f"Server failed to start.\nStdout: {stdout}\nStderr: {stderr}")
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        pytest.fail("Server failed to start")

    yield process
    
    # 停止服务
    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    process.wait()

def test_create_device(sanic_server):
    payload = {
        "id": "dev001",
        "name": "Sensor 1",
        "type": "temp",
        "status": "online"
    }
    response = requests.post(f"{BASE_URL}/devices", json=payload)
    assert response.status_code == 201, f"Failed to create: {response.text}"
    data = response.json()
    assert data["id"] == "dev001"
    assert data["name"] == "Sensor 1"

def test_get_device(sanic_server):
    response = requests.get(f"{BASE_URL}/devices/dev001")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "dev001"

def test_list_devices(sanic_server):
    response = requests.get(f"{BASE_URL}/devices")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

def test_update_device(sanic_server):
    payload = {"status": "offline"}
    response = requests.put(f"{BASE_URL}/devices/dev001", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "offline"

def test_delete_device(sanic_server):
    response = requests.delete(f"{BASE_URL}/devices/dev001")
    assert response.status_code == 204
    
    # 确认已删除
    response = requests.get(f"{BASE_URL}/devices/dev001")
    assert response.status_code == 404
