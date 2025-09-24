#!/usr/bin/env python3
"""
Internet Speed Test Monitor

This script measures internet speeds and compares them against contracted ISP speeds.
Results are logged to a CSV file for analysis.
"""

import speedtest
import csv
import os
import json
import argparse
import time
from datetime import datetime
from typing import Tuple, Dict, Any

# Configuration
CONFIG = {
    'contracted_speeds': {
        'download_mbps': 1100,  # Update with your contracted download speed
        'upload_mbps': 35      # Update with your contracted upload speed
    },
    'log_file': 'speed_log.csv',
    'report_file': 'speed_report.json',
    'min_test_interval': 300  # 5 minutes between tests when running in daemon mode
}

def measure_speed() -> Tuple[float, float, Dict[str, Any]]:
    """
    Measure internet speeds using speedtest.net
    
    Returns:
        Tuple containing (download_speed, upload_speed, test_metadata)
    """
    try:
        st = speedtest.Speedtest()
        print("STATUS: Finding best server...")
        st.get_best_server()
        print(f"STATUS: Best server found: {st.results.server['sponsor']} ({st.results.server['name']}, {st.results.server['country']})")
        
        print("STATUS: Testing download speed...")
        download_speed = st.download() / 10**6  # Convert to Mbps
        print("STATUS: Download test complete.")
        
        print("STATUS: Testing upload speed...")
        upload_speed = st.upload() / 10**6  # Convert to Mbps
        print("STATUS: Upload test complete.")
        
        # Collect additional test metadata
        test_metadata = {
            'server': st.results.server,
            'client': st.results.client,
            'timestamp': datetime.now().isoformat(),
            'ping': st.results.ping
        }
        
        return download_speed, upload_speed, test_metadata
        
    except speedtest.SpeedtestException as e:
        print(f"ERROR: Speed test failed: {e}")
        return 0, 0, {'error': str(e)}
    except Exception as e:
        print(f"ERROR: An unexpected error occurred: {e}")
        return 0, 0, {'error': str(e)}

def log_speed(download_speed: float, upload_speed: float, test_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Log speed test results to a CSV file
    
    Args:
        download_speed: Measured download speed in Mbps
        upload_speed: Measured upload speed in Mbps
        test_metadata: Additional test metadata
        
    Returns:
        Dictionary containing the logged data
    """
    log_entry = {
        'timestamp': test_metadata.get('timestamp', datetime.now().isoformat()),
        'download_mbps': round(download_speed, 2),
        'upload_mbps': round(upload_speed, 2),
        'ping_ms': round(test_metadata.get('ping', 0), 2),
        'server_host': test_metadata.get('server', {}).get('host', 'unknown'),
        'server_location': f"{test_metadata.get('server', {}).get('name', 'Unknown')}, "
                         f"{test_metadata.get('server', {}).get('country', 'Unknown')}",
        'client_ip': test_metadata.get('client', {}).get('ip', 'unknown'),
        'download_percent': round((download_speed / CONFIG['contracted_speeds']['download_mbps']) * 100, 2)
        if CONFIG['contracted_speeds']['download_mbps'] > 0 else 0,
        'upload_percent': round((upload_speed / CONFIG['contracted_speeds']['upload_mbps']) * 100, 2)
        if CONFIG['contracted_speeds']['upload_mbps'] > 0 else 0,
        'error': test_metadata.get('error', '')
    }
    
    # Ensure log directory exists
    os.makedirs(os.path.dirname(os.path.abspath(CONFIG['log_file'])), exist_ok=True)
    
    # Write to CSV
    file_exists = os.path.isfile(CONFIG['log_file'])
    with open(CONFIG['log_file'], 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=log_entry.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(log_entry)
    
    return log_entry

def generate_report() -> Dict[str, Any]:
    """
    Generate a summary report from the log file
    
    Returns:
        Dictionary containing report data
    """
    if not os.path.exists(CONFIG['log_file']):
        return {"error": "No log file found"}
    
    report = {
        'generated_at': datetime.now().isoformat(),
        'contracted_speeds': CONFIG['contracted_speeds'],
        'tests': 0,
        'average_download': 0,
        'average_upload': 0,
        'min_download': float('inf'),
        'min_upload': float('inf'),
        'max_download': 0,
        'max_upload': 0,
        'compliance_download': 0,  # Percentage of tests meeting download speed
        'compliance_upload': 0     # Percentage of tests meeting upload speed
    }
    
    download_speeds = []
    upload_speeds = []
    compliant_downloads = 0
    compliant_uploads = 0
    
    # Read the log file
    with open(CONFIG['log_file'], 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                dl = float(row.get('download_mbps', 0))
                ul = float(row.get('upload_mbps', 0))
                
                download_speeds.append(dl)
                upload_speeds.append(ul)
                
                if dl >= CONFIG['contracted_speeds']['download_mbps'] * 0.8:  # 80% of contracted speed
                    compliant_downloads += 1
                if ul >= CONFIG['contracted_speeds']['upload_mbps'] * 0.8:    # 80% of contracted speed
                    compliant_uploads += 1
                    
            except (ValueError, KeyError):
                continue
    
    # Calculate statistics
    if download_speeds:
        report.update({
            'tests': len(download_speeds),
            'average_download': round(sum(download_speeds) / len(download_speeds), 2),
            'average_upload': round(sum(upload_speeds) / len(upload_speeds), 2),
            'min_download': round(min(download_speeds), 2),
            'min_upload': round(min(upload_speeds), 2),
            'max_download': round(max(download_speeds), 2),
            'max_upload': round(max(upload_speeds), 2),
            'compliance_download': round((compliant_downloads / len(download_speeds)) * 100, 2),
            'compliance_upload': round((compliant_uploads / len(upload_speeds)) * 100, 2),
            'last_test': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    
    # Save report to file
    with open(CONFIG['report_file'], 'w') as f:
        json.dump(report, f, indent=2)
    
    return report

def print_summary(log_entry: Dict[str, Any]):
    """Print a summary of the speed test results"""
    print("\n=== Speed Test Results ===")
    print(f"Time: {log_entry['timestamp']}")
    print(f"Server: {log_entry['server_location']}")
    print(f"Ping: {log_entry['ping_ms']} ms")
    print(f"Download: {log_entry['download_mbps']} Mbps ({log_entry['download_percent']}% of contracted)")
    print(f"Upload: {log_entry['upload_mbps']} Mbps ({log_entry['upload_percent']}% of contracted)")
    print("=" * 25 + "\n")

def main():
    parser = argparse.ArgumentParser(description='Internet Speed Test Monitor')
    parser.add_argument('--daemon', action='store_true', help='Run in daemon mode (continuous testing)')
    parser.add_argument('--interval', type=int, default=300, 
                       help='Test interval in seconds (default: 300)')
    parser.add_argument('--report', action='store_true', help='Generate and display a report')
    
    args = parser.parse_args()
    
    if args.report:
        report = generate_report()
        print("\n=== Speed Test Report ===")
        print(f"Generated at: {report['generated_at']}")
        print(f"Tests performed: {report['tests']}")
        print(f"\nContracted Speeds: {report['contracted_speeds']['download_mbps']} Mbps down / "
              f"{report['contracted_speeds']['upload_mbps']} Mbps up")
        print("\nDownload Statistics:")
        print(f"  Average: {report['average_download']} Mbps")
        print(f"  Minimum: {report['min_download']} Mbps")
        print(f"  Maximum: {report['max_download']} Mbps")
        print(f"  Compliance: {report['compliance_download']}% of tests >= 80% of contracted speed")
        print("\nUpload Statistics:")
        print(f"  Average: {report['average_upload']} Mbps")
        print(f"  Minimum: {report['min_upload']} Mbps")
        print(f"  Maximum: {report['max_upload']} Mbps")
        print(f"  Compliance: {report['compliance_upload']}% of tests >= 80% of contracted speed")
        print("=" * 25 + "\n")
        return
    
    if args.daemon:
        print(f"Starting speed test daemon with {args.interval} second interval...")
        print(f"Press Ctrl+C to stop\n")
        
        try:
            while True:
                run_test()
                time.sleep(max(args.interval, CONFIG['min_test_interval']))
        except KeyboardInterrupt:
            print("\nStopping speed test daemon...")
    else:
        run_test()

def run_test():
    """Run a single speed test and log the results"""
    print(f"STATUS: Running speed test at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
    download_speed, upload_speed, test_metadata = measure_speed()
    
    if download_speed > 0 or upload_speed > 0:
        log_entry = log_speed(download_speed, upload_speed, test_metadata)
        print_summary(log_entry)
        
        # Generate report after each test
        generate_report()
        print("STATUS: Speed test completed successfully!")
    else:
        print("ERROR: Speed test failed. Check your internet connection.")

if __name__ == "__main__":
    main()