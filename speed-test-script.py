import speedtest
from datetime import datetime
import csv
import os

def measure_speed():
    st = speedtest.Speedtest()
    st.get_best_server()
    download_speed = st.download() / 10**6  # Convert to Mbps
    upload_speed = st.upload() / 10**6  # Convert to Mbps
    return download_speed, upload_speed

def log_speed(download_speed, upload_speed):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_file = os.path.join(os.path.dirname(__file__), 'speed_log.csv')
    with open(log_file, 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, download_speed, upload_speed])

def main():
    download_speed, upload_speed = measure_speed()
    log_speed(download_speed, upload_speed)

if __name__ == "__main__":
    main()