import streamlit as st
import asyncio
import websockets
import json
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from collections import deque
import httpx
import threading
import time
import queue

# Global variables
results_queue = queue.Queue()
test_running = threading.Event()

async def receive_data():
    while test_running.is_set():
        try:
            async with websockets.connect("ws://localhost:8765") as websocket:
                while test_running.is_set():
                    message = await websocket.recv()
                    result = json.loads(message)
                    results_queue.put(result)
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

def main():
    st.title("Advanced Load Tester")

    # Test Configuration
    st.header("Test Configuration")
    url = st.text_input("Enter website URL", "https://example.com")
    num_requests = st.number_input("Number of requests", min_value=1, value=100)
    concurrent_users = st.number_input("Concurrent users", min_value=1, value=10)
    qps = st.number_input("Queries per second (QPS)", min_value=1, value=1)
    
    # Custom Headers
    headers_string = st.text_area("Custom Headers (one per line, e.g., 'Content-Type: application/json')")
    headers = parse_headers(headers_string)
    
    # Custom Payload
    payload = st.text_area("Custom Payload (JSON format)")
    
    # Test Configuration Presets
    presets = {
        "Light Load": {"num_requests": 50, "concurrent_users": 5, "qps": 1},
        "Medium Load": {"num_requests": 200, "concurrent_users": 20, "qps": 5},
        "Heavy Load": {"num_requests": 500, "concurrent_users": 50, "qps": 10}
    }
    selected_preset = st.selectbox("Load Preset", ["Custom"] + list(presets.keys()))
    if selected_preset != "Custom":
        num_requests = presets[selected_preset]["num_requests"]
        concurrent_users = presets[selected_preset]["concurrent_users"]
        qps = presets[selected_preset]["qps"]

    start_button = st.button("Start Load Test")
    stop_button = st.button("Stop Test")

    # Create placeholders for charts and results
    response_time_chart = st.empty()
    status_code_chart = st.empty()
    response_time_dist_chart = st.empty()
    results_count = st.empty()
    performance_metrics = st.empty()
    
    if start_button:
        test_running.set()
        
        # Start the WebSocket receiver in a separate thread
        threading.Thread(target=lambda: asyncio.run(receive_data()), daemon=True).start()

        # Call the FastAPI to start the load test
        if asyncio.run(start_load_test(url, num_requests, concurrent_users, qps, headers, payload)):
            st.success("Load test started!")
        else:
            st.error("Failed to start load test")
            test_running.clear()
            return

    if stop_button:
        test_running.clear()
        if asyncio.run(stop_load_test()):
            st.warning("Test stopped by user.")
        else:
            st.error("Failed to stop load test")

    # Display and update charts
    results = []
    while True:
        while not results_queue.empty():
            results.append(results_queue.get())

        if results:
            # Response Time Chart
            fig_rt, ax_rt = plt.subplots(figsize=(10, 5))
            response_times = [r['response_time'] for r in results]
            ax_rt.plot(response_times)
            ax_rt.set_title("Response Times")
            ax_rt.set_xlabel("Request Number")
            ax_rt.set_ylabel("Response Time (s)")
            response_time_chart.pyplot(fig_rt)
            plt.close(fig_rt)

            # Status Code Chart
            fig_sc, ax_sc = plt.subplots(figsize=(10, 5))
            status_codes = [r.get('status_code', 0) for r in results]
            ax_sc.hist(status_codes, bins=20)
            ax_sc.set_title("Status Codes Distribution")
            ax_sc.set_xlabel("Status Code")
            ax_sc.set_ylabel("Frequency")
            status_code_chart.pyplot(fig_sc)
            plt.close(fig_sc)

            # Response Time Distribution Chart
            fig_rtd, ax_rtd = plt.subplots(figsize=(10, 5))
            sns.histplot(response_times, kde=True, ax=ax_rtd)
            ax_rtd.set_title("Response Time Distribution")
            ax_rtd.set_xlabel("Response Time (s)")
            ax_rtd.set_ylabel("Frequency")
            response_time_dist_chart.pyplot(fig_rtd)
            plt.close(fig_rtd)

            # Performance Metrics Summary
            total_requests = len(results)
            successful_requests = sum(1 for r in results if r.get('status_code', 0) < 400 and r.get('success', True))
            error_rate = (total_requests - successful_requests) / total_requests if total_requests > 0 else 0
            avg_response_time = sum(r['response_time'] for r in results) / total_requests if total_requests > 0 else 0
            max_response_time = max(r['response_time'] for r in results) if results else 0
            min_response_time = min(r['response_time'] for r in results) if results else 0
            
            performance_metrics.markdown(f"""
            ### Performance Metrics Summary
            - Total Requests: {total_requests}
            - Successful Requests: {successful_requests}
            - Error Rate: {error_rate:.2%}
            - Average Response Time: {avg_response_time:.3f} s
            - Max Response Time: {max_response_time:.3f} s
            - Min Response Time: {min_response_time:.3f} s
            """)

        # Display current results count
        results_count.write(f"Number of requests processed: {len(results)}")

        # Add a small delay to prevent excessive updates
        time.sleep(0.1)

        # Check if the test is still running
        if not test_running.is_set() and results_queue.empty():
            break

        # Use st.empty() to rerun the script
        st.empty()

    # Export Results
    if results:
        df = pd.DataFrame(results)
        csv = df.to_csv(index=False)
        st.download_button(
            label="Download Results CSV",
            data=csv,
            file_name="load_test_results.csv",
            mime="text/csv"
        )

if __name__ == "__main__":
    main()