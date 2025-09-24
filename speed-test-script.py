#!/usr/bin/env python3
"""
Internet Speed Test Monitor

This script measures internet speeds using the official Speedtest CLI by Ookla and compares them 
against contracted ISP speeds. Results are logged to a CSV file for analysis.
"""

import csv
import os
import json
import argparse
import time
import subprocess
from datetime import datetime
from typing import Tuple, Dict, Any, Optional

# Configuration
CONFIG = {
    'contracted_speeds': {
        'download_mbps': 1100,  # Update with your contracted download speed
        'upload_mbps': 35      # Update with your contracted upload speed
    },
    'log_file': 'speed_log.csv',
    'report_file': 'speed_report.json',
    'min_test_interval': 300,  # 5 minutes between tests when running in daemon mode
    'speedtest_cmd': 'speedtest',  # Using official Speedtest CLI
}

def run_command(cmd: list, timeout: int = 120) -> Tuple[bool, str, str]:
    """Run a shell command with timeout and return (success, stdout, stderr)"""
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(timeout=timeout)
        return process.returncode == 0, stdout, stderr
    except subprocess.TimeoutExpired:
        process.kill()
        return False, "", f"Command timed out after {timeout} seconds"
    except Exception as e:
        return False, "", str(e)

def measure_speed() -> Tuple[float, float, Dict[str, Any]]:
    """
    Measure internet speeds using the official Speedtest CLI
    
    Returns:
        Tuple containing (download_speed, upload_speed, test_metadata)
    """
    max_retries = 2
    retry_delay = 3  # seconds
    
    # Check if speedtest command is available
    try:
        subprocess.run([CONFIG['speedtest_cmd'], '--version'], 
                      capture_output=True, check=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        raise Exception("Speedtest CLI not found. Please install it first: https://www.speedtest.net/apps/cli")
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            print(f"STATUS: Starting speed test (attempt {attempt + 1}/{max_retries})...")
            
            # Run the official Speedtest CLI with JSON output
            cmd = [
                CONFIG['speedtest_cmd'],
                '--format=json',
                '--progress=no',
                '--accept-license',
                '--accept-gdpr'
            ]
            print(f"STATUS: Running command: {' '.join(cmd)}")
            
            success, stdout, stderr = run_command(cmd, timeout=300)  # 5 minute timeout
            
            if not success:
                raise Exception(f"Command failed: {stderr}")
                
            # Parse the JSON output
            try:
                result = json.loads(stdout)
                
                # Extract metrics from the result
                download_speed = result.get('download', {}).get('bandwidth', 0) / 125000  # Convert from bps to Mbps
                upload_speed = result.get('upload', {}).get('bandwidth', 0) / 125000  # Convert from bps to Mbps
                ping = result.get('ping', {}).get('latency', 0)
                jitter = result.get('ping', {}).get('jitter', 0)
                packet_loss = result.get('packetLoss', 0)
                
                print(f"STATUS: Download: {download_speed:.2f} Mbps")
                print(f"STATUS: Upload: {upload_speed:.2f} Mbps")
                print(f"STATUS: Ping: {ping:.2f} ms")
                print(f"STATUS: Jitter: {jitter:.2f} ms")
                print(f"STATUS: Packet Loss: {packet_loss}%")
                
                # Get server info
                server_info = result.get('server', {})
                server_location = f"{server_info.get('name', 'Unknown')}, {server_info.get('location', 'Unknown')}, {server_info.get('country', 'Unknown')}"
                
                # Get client info
                client_info = result.get('interface', {})
                isp_info = result.get('isp', '')
                
                return download_speed, upload_speed, {
                    'server': {
                        'name': server_info.get('name', 'Unknown'),
                        'sponsor': server_info.get('sponsor', 'Unknown'),
                        'country': server_info.get('country', 'Unknown'),
                        'location': server_info.get('location', 'Unknown'),
                        'host': f"{server_info.get('host', '')}:{server_info.get('port', '')}",
                        'distance': server_info.get('distance', 0),
                        'lat': server_info.get('lat'),
                        'lon': server_info.get('lon')
                    },
                    'client': {
                        'ip': client_info.get('externalIp', ''),
                        'isp': isp_info,
                        'country': result.get('client', {}).get('country', ''),
                        'lat': result.get('client', {}).get('lat'),
                        'lon': result.get('client', {}).get('lon')
                    },
                    'timestamp': datetime.now().isoformat(),
                    'ping': ping,
                    'jitter': jitter,
                    'packet_loss': packet_loss,
                    'result_url': result.get('result', {}).get('url', '')
                }
                    
            except json.JSONDecodeError as e:
                raise Exception(f"Failed to parse JSON output: {e}")
                
        except Exception as e:
            last_error = str(e)
            print(f"ERROR: {last_error}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            continue
    
    raise Exception(f"Failed to measure speed after {max_retries} attempts. Last error: {last_error}")

def log_speed(download_speed: float, upload_speed: float, test_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Log speed test results to a CSV file
    
    Args:
        download_speed: Measured download speed in Mbps
        upload_speed: Measured upload speed in Mbps
        test_metadata: Additional test metadata from speed test
        
    Returns:
        Dictionary containing the logged data
    """
    # Extract server and client information with fallbacks
    server_info = test_metadata.get('server', {})
    client_info = test_metadata.get('client', {})
    
    # Format server location
    server_location = server_info.get('name', 'Unknown')
    if 'location' in server_info and server_info['location'] != 'Unknown':
        server_location = f"{server_info['location']}, {server_info.get('country', 'Unknown')}"
    
    # Create log entry with all available data
    log_entry = {
        'timestamp': test_metadata.get('timestamp', datetime.now().isoformat()),
        'download_mbps': round(download_speed, 2),
        'upload_mbps': round(upload_speed, 2),
        'ping_ms': round(test_metadata.get('ping', 0), 2),
        'jitter_ms': round(test_metadata.get('jitter', 0), 2),
        'packet_loss': test_metadata.get('packet_loss', 0),
        'server_host': server_info.get('host', 'unknown'),
        'server_name': server_info.get('name', 'unknown'),
        'server_sponsor': server_info.get('sponsor', 'unknown'),
        'server_country': server_info.get('country', 'unknown'),
        'server_location': server_location,
        'server_lat': server_info.get('lat'),
        'server_lon': server_info.get('lon'),
        'server_distance_km': round(server_info.get('distance', 0), 2) if 'distance' in server_info else None,
        'client_ip': client_info.get('ip', 'unknown'),
        'client_isp': client_info.get('isp', 'unknown'),
        'client_lat': client_info.get('lat'),
        'client_lon': client_info.get('lon'),
        'download_percent': round((download_speed / CONFIG['contracted_speeds']['download_mbps']) * 100, 2)
        if CONFIG['contracted_speeds']['download_mbps'] > 0 else 0,
        'upload_percent': round((upload_speed / CONFIG['contracted_speeds']['upload_mbps']) * 100, 2)
        if CONFIG['contracted_speeds']['upload_mbps'] > 0 else 0,
        'error': test_metadata.get('error', '')
    }
    
    # Ensure log directory exists
    log_dir = os.path.dirname(os.path.abspath(CONFIG['log_file']))
    if log_dir:  # Only create directory if path is not empty
        os.makedirs(log_dir, exist_ok=True)
    
    # Define the field order for the CSV
    fieldnames = [
        'timestamp', 'download_mbps', 'upload_mbps', 'ping_ms', 'jitter_ms', 'packet_loss',
        'server_host', 'server_name', 'server_sponsor', 'server_country', 'server_location',
        'server_lat', 'server_lon', 'server_distance_km', 'client_ip', 'client_isp',
        'client_lat', 'client_lon', 'download_percent', 'upload_percent', 'error'
    ]
    
    # Write to CSV
    file_exists = os.path.isfile(CONFIG['log_file'])
    with open(CONFIG['log_file'], 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        
        # Create a clean row with all fields in the right order
        clean_row = {field: log_entry.get(field, '') for field in fieldnames}
        writer.writerow(clean_row)
    
    return log_entry

def print_summary(log_entry: Dict[str, Any]):
    """Print a summary of the speed test results"""
    print("\n=== Speed Test Results ===")
    print(f"Time: {log_entry.get('timestamp', 'N/A')}")
    print(f"Server: {log_entry.get('server_name', 'Unknown')} ({log_entry.get('server_location', 'Unknown')})")
    print(f"Ping: {log_entry.get('ping_ms', 0):.2f} ms")
    print(f"Jitter: {log_entry.get('jitter_ms', 0):.2f} ms")
    print(f"Packet Loss: {log_entry.get('packet_loss', 0)}%")
    print(f"Download: {log_entry.get('download_mbps', 0):.2f} Mbps "
          f"({log_entry.get('download_percent', 0):.2f}% of contracted)")
    print(f"Upload: {log_entry.get('upload_mbps', 0):.2f} Mbps "
          f"({log_entry.get('upload_percent', 0):.2f}% of contracted)")
    
    if log_entry.get('server_distance_km'):
        print(f"Server Distance: {log_entry['server_distance_km']:.2f} km")
    
    # Show client info if available
    if log_entry.get('client_ip') and log_entry['client_ip'] != 'unknown':
        print(f"\nClient IP: {log_entry['client_ip']}")
        if log_entry.get('client_isp') and log_entry['client_isp'] != 'unknown':
            print(f"ISP: {log_entry['client_isp']}")
    
    # Show result URL if available
    if log_entry.get('result_url'):
        print(f"\nDetailed Results: {log_entry['result_url']}")
    
    # Show any errors if present
    if log_entry.get('error'):
        print(f"\nERROR: {log_entry['error']}")
    
    print("=" * 40 + "\n")

def run_test():
    """Run a single speed test and log the results"""
    try:
        print(f"STATUS: Running speed test at {datetime.now()}...")
        download_speed, upload_speed, test_metadata = measure_speed()
        log_entry = log_speed(download_speed, upload_speed, test_metadata)
        print_summary(log_entry)
        print("STATUS: Speed test completed successfully!")
        return True
    except Exception as e:
        print(f"ERROR: Speed test failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Internet Speed Test Monitor')
    parser.add_argument('--daemon', action='store_true', help='Run in daemon mode (continuous testing)')
    parser.add_argument('--interval', type=int, default=300, 
                       help='Test interval in seconds (default: 300)')
    parser.add_argument('--report', action='store_true', help='Generate and display a report')
    
    args = parser.parse_args()
    
    if args.daemon:
        print(f"Starting speed test daemon with {args.interval}s interval. Press Ctrl+C to stop.")
        while True:
            run_test()
            print(f"Next test in {args.interval} seconds...")
            time.sleep(args.interval)
    elif args.report:
        # Generate and display report
        report = generate_report()
        print("\n=== Speed Test Report ===")
        print(f"Generated at: {report.get('generated_at')}")
        print(f"Total tests: {report.get('total_tests', 0)}")
        print(f"Average Download: {report.get('avg_download', 0):.2f} Mbps")
        print(f"Average Upload: {report.get('avg_upload', 0):.2f} Mbps")
        print(f"Average Ping: {report.get('avg_ping', 0):.2f} ms")
    else:
        # Run a single test
        run_test()

if __name__ == "__main__":
    main()
