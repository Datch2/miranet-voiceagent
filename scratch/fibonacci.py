import subprocess
import time
import os
import sys

# IP configurations for both active clients
CLIENTS = {
    "RT000002": {
        "ip": "146.190.222.105",
        "name": "Cliente 1 - Router RT000002",
        "fib_index": 0,
        "next_check": 0.0
    },
    "RT000001": {
        "ip": "147.182.138.56",
        "name": "Cliente 2 - Router RT000001",
        "fib_index": 0,
        "next_check": 0.0
    }
}

# Fibonacci sequence for exponential backoff retries (in seconds)
FIBONACCI_SEQ = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
MAX_FIB = len(FIBONACCI_SEQ) - 1

# OIDs
OID_UPTIME = ".1.3.6.1.2.1.1.3.0"
# ssCpuIdle (CPU Idle percentage)
OID_CPU_IDLE = ".1.3.6.1.4.1.2021.11.11.0"
# ifOperStatus of the primary interface
OID_IF_STATUS = ".1.3.6.1.2.1.2.2.1.8.1"

# Log path inside the linux server
LOG_DIR = "/root/miranet-voiceagent/logs"
LOG_FILE = os.path.join(LOG_DIR, "network.log")

def log_message(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}\n"
    print(log_line, end="")
    try:
        # Create directory if it doesn't exist
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print(f"Error writing to log file: {e}", file=sys.stderr)

def query_snmp_value(ip, oid):
    """
    Executes native snmpget to retrieve SNMP metric values.
    """
    try:
        # snmpget -v 2c -c miranet -t 1 -r 0 <ip> <oid>
        res = subprocess.run(
            ["snmpget", "-v", "2c", "-c", "miranet", "-t", "1", "-r", "0", ip, oid],
            capture_output=True,
            text=True,
            timeout=1.5
        )
        if res.returncode == 0:
            # Parse output, e.g. "iso.3.6.1.2.1.1.3.0 = Timeticks: (5712) 0:00:57.12"
            parts = res.stdout.strip().split(" = ")
            if len(parts) == 2:
                val = parts[1].split(": ")
                return val[1].replace('"', '').strip() if len(val) == 2 else parts[1].strip()
    except Exception:
        pass
    return None

def check_client(client_id, info):
    ip = info["ip"]
    start_time = time.perf_counter()
    
    # Query Uptime to check basic connectivity and measure latency
    uptime = query_snmp_value(ip, OID_UPTIME)
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    
    if uptime is not None:
        # Target is UP, query CPU and Interface metrics
        cpu_idle_str = query_snmp_value(ip, OID_CPU_IDLE)
        cpu_usage = 15.0  # default/base CPU usage
        if cpu_idle_str and cpu_idle_str.isdigit():
            cpu_usage = 100.0 - float(cpu_idle_str)
            
        if_status_str = query_snmp_value(ip, OID_IF_STATUS)
        # 1 means UP, 2 means DOWN
        if_status = "UP" if if_status_str == "1" or "up" in if_status_str.lower() else "DOWN"
        
        # Reset Fibonacci backoff on success
        info["fib_index"] = 0
        interval = 2.0  # standard interval
        info["next_check"] = time.time() + interval
        
        log_message(f"Router: {client_id} | IP: {ip} | Status: UP | Latency: {latency_ms}ms | CPU: {cpu_usage:.1f}% | Interface: {if_status}")
    else:
        # Target is DOWN, apply Fibonacci Backoff interval
        fib_sec = FIBONACCI_SEQ[info["fib_index"]]
        log_message(f"Router: {client_id} | IP: {ip} | Status: DOWN | Latency: Timeout | CPU: N/A | Interface: DOWN (Retrying in {fib_sec}s)")
        
        # Advance Fibonacci sequence
        if info["fib_index"] < MAX_FIB:
            info["fib_index"] += 1
            
        info["next_check"] = time.time() + fib_sec

def main():
    log_message("MIRANET VOICEAGENT - FIBONACCI POLLING MONITOR STARTED")
    log_message(f"Monitoring: {list(CLIENTS.keys())}")
    log_message(f"Writing logs to: {LOG_FILE}")
    
    try:
        while True:
            now = time.time()
            for client_id, info in CLIENTS.items():
                if now >= info["next_check"]:
                    check_client(client_id, info)
            time.sleep(0.1)
    except KeyboardInterrupt:
        log_message("Monitor stopped by user.")

if __name__ == "__main__":
    main()
