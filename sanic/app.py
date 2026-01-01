from sanic import Sanic, response, Request
from dataclasses import dataclass, asdict
from typing import Optional, Dict
import traceback
from sanic.exceptions import SanicException

app = Sanic("DeviceManager")

# 允许所有 Host (默认行为，但显式确认一下)
app.config.HOST = "0.0.0.0" 

@dataclass
class Device:
    id: str
    name: str
    type: str
    status: str = "offline"

# In-memory storage
devices: Dict[str, Device] = {}

@app.on_request
async def print_request(request):
    print(f"Incoming: {request.method} {request.path}")
    print(f"Raw Headers: {request.headers}")
    print(f"Host Header: {request.host}")
    # 打印更多 Body 相关信息
    try:
        print(f"Content-Length: {request.headers.get('content-length')}")
        print(f"Transfer-Encoding: {request.headers.get('transfer-encoding')}")
        # print(f"Body: {request.body}") 
    except:
        pass

@app.exception(Exception)
async def catch_all(request, exception):
    print(f"Caught exception: {exception}")
    traceback.print_exc()
    status_code = 500
    if isinstance(exception, SanicException):
        status_code = exception.status_code
    return response.json({"error": f"Server Error: {str(exception)}"}, status=status_code)

@app.get("/ping")
async def ping(request: Request):
    return response.text("pong")

@app.post("/devices")
async def create_device(request: Request):
    """Create a new device"""
    print("Inside create_device handler")
    try:
        data = request.json
        print(f"Payload: {data}")
        
        if not data:
            return response.json({"error": "Invalid JSON payload"}, status=400)
        
        device_id = data.get("id")
        if not device_id:
            return response.json({"error": "Missing device ID"}, status=400)
            
        if device_id in devices:
            return response.json({"error": "Device already exists"}, status=409)
            
        device = Device(
            id=device_id,
            name=data.get("name", "Unknown"),
            type=data.get("type", "generic"),
            status=data.get("status", "offline")
        )
        devices[device_id] = device
        return response.json(asdict(device), status=201)
    except Exception as e:
        traceback.print_exc()
        return response.json({"error": str(e)}, status=500)

@app.get("/devices")
async def list_devices(request: Request):
    """List all devices"""
    return response.json([asdict(d) for d in devices.values()])

@app.get("/devices/<device_id:str>")
async def get_device(request: Request, device_id: str):
    """Get a device by ID"""
    if device_id not in devices:
        return response.json({"error": "Device not found"}, status=404)
    return response.json(asdict(devices[device_id]))

@app.put("/devices/<device_id:str>")
async def update_device(request: Request, device_id: str):
    """Update a device"""
    if device_id not in devices:
        return response.json({"error": "Device not found"}, status=404)
    
    try:
        data = request.json
    except:
        return response.json({"error": "Bad JSON"}, status=400)

    if not data:
        return response.json({"error": "Invalid JSON"}, status=400)
        
    device = devices[device_id]
    if "name" in data:
        device.name = data["name"]
    if "type" in data:
        device.type = data["type"]
    if "status" in data:
        device.status = data["status"]
        
    return response.json(asdict(device))

@app.delete("/devices/<device_id:str>")
async def delete_device(request: Request, device_id: str):
    """Delete a device"""
    if device_id not in devices:
        return response.json({"error": "Device not found"}, status=404)
    
    del devices[device_id]
    return response.empty(status=204)

if __name__ == "__main__":
    # 使用 single_process=True 方便调试
    app.run(host="0.0.0.0", port=8001, debug=True, access_log=True, single_process=True)
