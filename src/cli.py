import argparse
import asyncio
import websockets
import json
import httpx
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import threading
import time
import queue

# Global variables
results_queue = queue.Queue()
test_running = threading.Event()
total_requests_sent = 0

async def receive_data(total_requests):
    global total_requests_sent
    while test_running.is_set():
        try:
            async with websockets.connect("ws://localhost:8765") as websocket:
                while test_running.is_set() and total_requests_sent < total_requests:
                    message = await websocket.recv()
                    result = json.loads(message)
                    results_queue.put(result)
                    total_requests_sent += 1
                    print(f"Total requests sent: {total_requests_sent}")
        except websockets.exceptions.ConnectionClosed:
            await asyncio.sleep(1)  # Wait before trying to reconnect

async def start_load_test(url, num_requests, concurrent_users, qps, headers, payload):
    async with httpx.AsyncClient() as client:
        response = await client.post("http://localhost:8000/start_test", json={
            'url': url,
            'num_requests': num_requests,
            'concurrent_users': concurrent_users,
            'qps': qps,
            'headers': headers,
            'payload': payload
        })
        return response.status_code == 200

async def stop_load_test():
    async with httpx.AsyncClient() as client:
        response = await client.post("http://localhost:8000/stop_test")
        return response.status_code == 200

def parse_headers(headers_string):
    headers = {}
    for line in headers_string.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            headers[key.strip()] = value.strip()
    return headers

def display_results(results, show_graphs=True):
    if show_graphs:
        # Response Time Chart
        fig_rt, ax_rt = plt.subplots(figsize=(10, 5))
        response_times = [r['response_time'] for r in results]
        ax_rt.plot(response_times)
        ax_rt.set_title("Response Times")
        ax_rt.set_xlabel("Request Number")
        ax_rt.set_ylabel("Response Time (s)")
        plt.show()
        plt.close(fig_rt)

        # Status Code Chart
        fig_sc, ax_sc = plt.subplots(figsize=(10, 5))
        status_codes = [r.get('status_code', 0) for r in results]
        ax_sc.hist(status_codes, bins=20)
        ax_sc.set_title("Status Codes Distribution")
        ax_sc.set_xlabel("Status Code")
        ax_sc.set_ylabel("Frequency")
        plt.show()
        plt.close(fig_sc)

        # Response Time Distribution Chart
        fig_rtd, ax_rtd = plt.subplots(figsize=(10, 5))
        sns.histplot(response_times, kde=True, ax=ax_rtd)
        ax_rtd.set_title("Response Time Distribution")
        ax_rtd.set_xlabel("Response Time (s)")
        ax_rtd.set_ylabel("Frequency")
        plt.show()
        plt.close(fig_rtd)

    # Performance Metrics Summary
    total_requests = len(results)
    successful_requests = sum(1 for r in results if r.get('status_code', 0) < 400 and r.get('success', True))
    error_rate = (total_requests - successful_requests) / total_requests if total_requests > 0 else 0
    avg_response_time = sum(r['response_time'] for r in results) / total_requests if total_requests > 0 else 0
    max_response_time = max(r['response_time'] for r in results) if results else 0
    min_response_time = min(r['response_time'] for r in results) if results else 0

    print("\n### Performance Metrics Summary ###")
    print(f"Total Requests: {total_requests}")
    print(f"Successful Requests: {successful_requests}")
    print(f"Error Rate: {error_rate:.2%}")
    print(f"Average Response Time: {avg_response_time:.3f} s")
    print(f"Max Response Time: {max_response_time:.3f} s")
    print(f"Min Response Time: {min_response_time:.3f} s")

def main():
    parser = argparse.ArgumentParser(description="Advanced Load Tester CLI")
    parser.add_argument("--url", type=str, required=True, help="Enter website URL")
    parser.add_argument("--num_requests", type=int, default=100, help="Number of requests")
    parser.add_argument("--concurrent_users", type=int, default=10, help="Concurrent users")
    parser.add_argument("--qps", type=int, default=1, help="Queries per second (QPS)")
    parser.add_argument("--headers", type=str, default="", help="Custom Headers (one per line, e.g., 'Content-Type: application/json')")
    parser.add_argument("--payload", type=str, default="", help="Custom Payload (JSON format)")
    parser.add_argument("--graph", action='store_true', help="Print graphs or not")

    args = parser.parse_args()

    url = args.url
    num_requests = args.num_requests
    concurrent_users = args.concurrent_users
    qps = args.qps
    headers_string = args.headers
    headers = parse_headers(headers_string)
    payload = args.payload
    # show_graphs = args.graph

    test_running.set()

    # Start the WebSocket receiver in a separate thread
    threading.Thread(target=lambda: asyncio.run(receive_data(num_requests)), daemon=True).start()

    # Call the FastAPI to start the load test
    if asyncio.run(start_load_test(url, num_requests, concurrent_users, qps, headers, payload)):
        print("Load test started successfully!")
    else:
        print("Failed to start load test")
        test_running.clear()
        return

    # Monitor the number of requests sent
    while total_requests_sent < num_requests:
        time.sleep(1)

    test_running.clear()
    if asyncio.run(stop_load_test()):
        print("Test stopped automatically after reaching the total number of requests.")
    else:
        print("Failed to stop load test")

    # Display and update charts
    results = []
    while not results_queue.empty():
        results.append(results_queue.get())

    if results:
        display_results(results)
    else:
        print("No results to display.")

if __name__ == "__main__":
    main()