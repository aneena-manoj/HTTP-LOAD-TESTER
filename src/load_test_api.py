from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import asyncio
import websockets
import httpx
import json
import time

app = FastAPI()

# Global variables for storing results
results = []
stop_test = False

class TestParams(BaseModel):
    url: str
    num_requests: int
    concurrent_users: int
    qps: int
    headers: dict = {}
    payload: str = ""

class LoadTester:
    def __init__(self, websocket_url: str):
        self.websocket_url = websocket_url

    async def send_request(self, method: str, url: str, headers: dict, payload: str):
        global stop_test
        if stop_test:
            return
        
        start_time = time.time()
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(method, url, headers=headers, data=payload)
                elapsed_time = time.time() - start_time
                result = {
                    'status_code': response.status_code,
                    'response_time': elapsed_time,
                    'success': True
                }
            except httpx.RequestError as e:
                elapsed_time = time.time() - start_time
                result = {
                    'error': str(e),
                    'response_time': elapsed_time,
                    'success': False
                }
        await self.stream_result(result)

    async def stream_result(self, result):
        global results
        results.append(result)
        async with websockets.connect(self.websocket_url) as websocket:
            await websocket.send(json.dumps(result))

    async def run_test(self, method: str, url: str, num_requests: int, concurrent_users: int, qps: int, headers: dict, payload: str):
        global stop_test
        stop_test = False
        tasks = []
        delay = 1 / qps
        for _ in range(num_requests):
            if stop_test:
                break
            tasks.append(self.send_request(method, url, headers, payload))
            await asyncio.sleep(delay / concurrent_users)

        for i in range(0, len(tasks), concurrent_users):
            if stop_test:
                break
            batch = tasks[i:i+concurrent_users]
            await asyncio.gather(*batch)

async def run_load_test(url: str, num_requests: int, concurrent_users: int, qps: int, headers: dict, payload: str):
    tester = LoadTester("ws://localhost:8765")
    await tester.run_test(
        method='POST' if payload else 'GET',
        url=url,
        num_requests=num_requests,
        concurrent_users=concurrent_users,
        qps=qps,
        headers=headers,
        payload=payload
    )

@app.post("/start_test")
async def start_test(params: TestParams, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_load_test, params.url, params.num_requests, params.concurrent_users, params.qps, params.headers, params.payload)
    return {"message": "Load test started"}

@app.post("/stop_test")
async def stop_test():
    global stop_test
    stop_test = True
    return {"message": "Load test stopped"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)