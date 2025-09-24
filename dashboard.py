#!/usr/bin/env python3
"""
Speed Test Dashboard

A web-based dashboard to visualize internet speed test results.
"""

from flask import Flask, render_template, jsonify, send_from_directory, request, Response
import json
import os
import pandas as pd
import subprocess
import time
from datetime import datetime, timedelta
from collections import deque
from functools import wraps

app = Flask(__name__)

# Configuration
CONFIG = {
    'log_file': 'speed_log.csv',
    'report_file': 'speed_report.json',
    'port': 8050
}

# Global queue to store real-time test progress
progress_queue = deque()
test_in_progress = False # Flag to indicate if a test is currently running

# Ensure the data directory exists
os.makedirs('static', exist_ok=True)
def load_speed_data():
    """Load and process speed test data from CSV using pandas."""
    try:
        df = pd.read_csv(CONFIG['log_file'], quotechar='"', skipinitialspace=True)
        
        # Ensure all required columns are present
        required_columns = {
            'Timestamp': 'timestamp',
            'Download_Speed_Mbps': 'download_mbps',
            'Upload_Speed_Mbps': 'upload_mbps',
            'Ping_ms': 'ping_ms',
            'Download_Compliance_Percent': 'download_percent',
            'Upload_Compliance_Percent': 'upload_percent'
        }
        
        # Check for missing required columns
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Missing columns in CSV: {', '.join(missing_columns)}")
            # Try to continue with available columns
        
        # Rename columns that exist in the CSV
        rename_columns = {k: v for k, v in required_columns.items() if k in df.columns}
        
        # Add optional columns if they exist
        optional_columns = {
            'Server_Host': 'server_host',
            'Server_Location': 'server_location',
            'Client_IP': 'client_ip',
            'Error': 'error'
        }
        
        for old_col, new_col in optional_columns.items():
            if old_col in df.columns:
                rename_columns[old_col] = new_col
        
        df = df.rename(columns=rename_columns)
        
        # If server_host is present, ensure it's not empty
        if 'server_host' in df.columns:
            df['server_host'] = df['server_host'].fillna('Unknown')
        
        # Convert data types
        numeric_cols = ['download_mbps', 'upload_mbps', 'ping_ms',
                       'download_percent', 'upload_percent']
        
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Convert timestamp to datetime and sort
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        # Calculate moving averages for the charts
        window_size = min(6, len(df))  # Use a smaller window if we don't have much data
        df['download_ma'] = df['download_mbps'].rolling(window=window_size, min_periods=1).mean()
        df['upload_ma'] = df['upload_mbps'].rolling(window=window_size, min_periods=1).mean()
        
        # Format for JSON serialization
        df['time_str'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
        
        return df
        
    except FileNotFoundError:
        print(f"Log file not found: {CONFIG['log_file']}")
        return pd.DataFrame()
    except pd.errors.EmptyDataError:
        print(f"Log file is empty: {CONFIG['log_file']}")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error loading data: {e}")
        return pd.DataFrame()

def get_summary_stats():
    """Calculate summary statistics from the speed test data"""
    df = load_speed_data()
    
    if df.empty:
        return {}
    
    # Get the most recent test
    latest_test = df.iloc[-1].to_dict()
    
    # Calculate statistics for the last 24 hours
    one_day_ago = datetime.now() - timedelta(days=1)
    recent_data = df[df['timestamp'] >= one_day_ago]
    
    # Calculate averages
    avg_download = recent_data['download_mbps'].mean()
    avg_upload = recent_data['upload_mbps'].mean()
    avg_ping = recent_data['ping_ms'].mean()
    
    # Calculate minimums and maximums
    min_download = recent_data['download_mbps'].min()
    max_download = recent_data['download_mbps'].max()
    min_upload = recent_data['upload_mbps'].min()
    max_upload = recent_data['upload_mbps'].max()
    
    # Get contracted speeds (you can update these values as needed)
    contracted_download = 1100  # Update this with your actual contracted download speed
    contracted_upload = 35     # Update this with your actual contracted upload speed
    
    # Calculate compliance percentages
    download_compliance = (recent_data['download_mbps'].mean() / contracted_download) * 100
    upload_compliance = (recent_data['upload_mbps'].mean() / contracted_upload) * 100
    
    # Prepare the summary data
    summary = {
        'latest_test': {
            'timestamp': latest_test.get('timestamp'),
            'download_mbps': latest_test.get('download_mbps'),
            'upload_mbps': latest_test.get('upload_mbps'),
            'ping_ms': latest_test.get('ping_ms'),
            'server': latest_test.get('server_host', 'Unknown')
        },
        'averages_24h': {
            'download_mbps': round(avg_download, 2),
            'upload_mbps': round(avg_upload, 2),
            'ping_ms': round(avg_ping, 2)
        },
        'min_max_24h': {
            'min_download_mbps': round(min_download, 2),
            'max_download_mbps': round(max_download, 2),
            'min_upload_mbps': round(min_upload, 2),
            'max_upload_mbps': round(max_upload, 2)
        },
        'compliance': {
            'download_percent': round(download_compliance, 2),
            'upload_percent': round(upload_compliance, 2)
        },
        'contracted_speeds': {
            'download_mbps': contracted_download,
            'upload_mbps': contracted_upload
        },
        'test_count_24h': len(recent_data)
    }
    
    return summary

@app.route('/')
def dashboard():
    """Render the main dashboard page"""
    df = load_speed_data()
    
    # Get the latest test result
    latest_test = df.iloc[-1].to_dict() if not df.empty else {}
    
    # Get summary statistics
    summary = get_summary_stats()
    
    return render_template('dashboard.html', 
                         latest_test=latest_test,
                         summary=summary)

@app.route('/api/speed-data')
def speed_data():
    """API endpoint for speed test data"""
    try:
        print("Loading speed data...")
        df = load_speed_data()
        print(f"Loaded {len(df)} rows")
        
        if df.empty:
            print("No data available")
            return jsonify({'error': 'No data available'})
        
        # Convert timestamp to datetime if it's not already
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        # Make sure we have the required columns with fallbacks
        if 'download_mbps' not in df.columns and 'Download_Speed_Mbps' in df.columns:
            df['download_mbps'] = df['Download_Speed_Mbps']
        if 'upload_mbps' not in df.columns and 'Upload_Speed_Mbps' in df.columns:
            df['upload_mbps'] = df['Upload_Speed_Mbps']
        if 'ping_ms' not in df.columns and 'Ping_ms' in df.columns:
            df['ping_ms'] = df['Ping_ms']
        if 'server_host' not in df.columns and 'Server_Host' in df.columns:
            df['server_host'] = df['Server_Host']
        
        # Calculate moving averages
        window_size = min(6, len(df))
        df['download_ma'] = df['download_mbps'].rolling(window=window_size, min_periods=1).mean()
        df['upload_ma'] = df['upload_mbps'].rolling(window=window_size, min_periods=1).mean()
        
        # Get data for the last 7 days
        week_ago = datetime.now() - timedelta(days=7)
        recent_data = df[df['timestamp'] >= week_ago]
        
        if recent_data.empty:
            print("No recent data available (last 7 days)")
            return jsonify({'error': 'No recent data available'})
        
        # Create the response dictionary with required fields
        response = {
            'timestamps': recent_data['timestamp'].astype(str).tolist(),
            'download': recent_data['download_mbps'].round(2).fillna(0).tolist(),
            'upload': recent_data['upload_mbps'].round(2).fillna(0).tolist(),
            'ping': recent_data['ping_ms'].round(2).fillna(0).tolist(),
            'download_ma': recent_data['download_ma'].round(2).fillna(0).tolist(),
            'upload_ma': recent_data['upload_ma'].round(2).fillna(0).tolist()
        }
        
        # Add optional fields if they exist
        if 'server_host' in recent_data.columns:
            response['server_host'] = recent_data['server_host'].fillna('Unknown').tolist()
        
        print(f"Returning response with {len(response.get('timestamps', []))} data points")
        return jsonify(response)
        
    except Exception as e:
        import traceback
        error_msg = f"Error in speed_data: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return jsonify({'error': str(e)})

@app.route('/api/summary')
def summary():
    """API endpoint for summary statistics"""
    return jsonify(get_summary_stats())

# Serve static files
@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/api/run-test', methods=['POST'])
def run_test():
    """
    Run a speed test in a separate process and return initial status.
    Progress updates are streamed via /api/test-progress.
    """
    global progress_queue, test_in_progress
    progress_queue.clear() # Clear previous progress
    test_in_progress = True # Set flag to indicate test is running

    def generate_progress_and_set_flag():
        global test_in_progress
        process = subprocess.Popen(
            ['python3', 'speed-test-script.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        for line in iter(process.stdout.readline, ''):
            stripped_line = line.strip()
            print(f"SCRIPT_OUTPUT: {stripped_line}", flush=True) # Print to Flask terminal for debugging
            progress_queue.append(stripped_line)
            # Yield for SSE stream
            yield f"data: {json.dumps({'message': stripped_line})}\n\n"
        
        process.wait()
        if process.returncode != 0:
            error_message = f"Speed test script failed with exit code {process.returncode}"
            print(f"SCRIPT_ERROR: {error_message}", flush=True) # Print error to Flask terminal
            progress_queue.append(f"ERROR: {error_message}")
            yield f"data: {json.dumps({'error': error_message})}\n\n"
        else:
            final_message = "STATUS: Test complete. Reloading data..."
            print(f"SCRIPT_STATUS: {final_message}", flush=True) # Print final status to Flask terminal
            progress_queue.append(final_message)
            yield f"data: {json.dumps({'message': final_message})}\n\n"
            # After script finishes, trigger a data reload on the frontend
            # This is handled by the frontend calling loadData() after the SSE stream closes.
        
        test_in_progress = False # Reset flag when test is complete
        yield f"data: {json.dumps({'event': 'test_complete'})}\n\n" # Send a final event

    # Start the background task
    from threading import Thread
    thread = Thread(target=lambda: list(generate_progress_and_set_flag())) # Consume generator in thread
    thread.start()
    print("STATUS: Speed test initiated. Check /api/test-progress for updates.", flush=True)
    return jsonify({'status': 'Speed test initiated. Check /api/test-progress for updates.'})

def add_cors_headers(response):
    """Add CORS headers to the response."""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

@app.route('/api/test-progress')
def test_progress():
    """Streams real-time progress updates for the speed test."""
    def stream_events():
        global test_in_progress
        try:
            while test_in_progress or progress_queue:
                if progress_queue:
                    message = progress_queue.popleft()
                    yield f"data: {json.dumps({'message': message})}\n\n"
                else:
                    time.sleep(0.5) # Wait for new messages
            # Send a final event when done
            yield f"data: {json.dumps({'event': 'complete'})}\n\n"
        except GeneratorExit:
            print("Client disconnected")
        except Exception as e:
            print(f"Error in stream_events: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    response = app.response_class(
        stream_events(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'  # Disable buffering for nginx
        }
    )
    return add_cors_headers(response)

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Create the dashboard template if it doesn't exist
    dashboard_path = os.path.join('templates', 'dashboard.html')
    if not os.path.exists(dashboard_path):
        with open(dashboard_path, 'w') as f:
            f.write("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Internet Speed Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/moment"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-moment"></script>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <style>
        .card {
            @apply bg-white rounded-lg shadow-md p-6 mb-6;
        }
        .stat-card {
            @apply bg-white rounded-lg shadow p-4 text-center;
        }
        .stat-value {
            @apply text-3xl font-bold text-blue-600;
        }
        .stat-label {
            @apply text-gray-500 text-sm;
        }
        .chart-container {
            @apply bg-white rounded-lg shadow-md p-4 mb-6;
            height: 300px;
        }
    </style>
</head>
<body class="bg-gray-100">
    <div class="container mx-auto px-4 py-8">
        <header class="mb-8">
            <h1 class="text-3xl font-bold text-gray-800">Internet Speed Dashboard</h1>
            <p class="text-gray-600">Monitoring your connection quality</p>
        </header>

        <!-- Stats Overview -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <div class="stat-card">
                <div class="stat-value" id="current-download">--</div>
                <div class="stat-label">Current Download (Mbps)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="current-upload">--</div>
                <div class="stat-label">Current Upload (Mbps)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="current-ping">--</div>
                <div class="stat-label">Ping (ms)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="compliance">--</div>
                <div class="stat-label">SLA Compliance (Last 24h)</div>
            </div>
        </div>

        <!-- Speed Chart -->
        <div class="card">
            <h2 class="text-xl font-semibold mb-4">Download & Upload Speeds (Last 7 Days)</h2>
            <div class="chart-container">
                <canvas id="speedChart"></canvas>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- Speed Percentage Chart -->
            <div class="card">
                <h2 class="text-xl font-semibold mb-4">% of Contracted Speed</h2>
                <div class="chart-container">
                    <canvas id="percentageChart"></canvas>
                </div>
            </div>

            <!-- Ping Chart -->
            <div class="card">
                <h2 class="text-xl font-semibold mb-4">Ping Latency (ms)</h2>
                <div class="chart-container">
                    <canvas id="pingChart"></canvas>
                </div>
            </div>
        </div>

        <!-- Summary Stats -->
        <div class="card mt-6">
            <h2 class="text-xl font-semibold mb-4">Performance Summary</h2>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                    <h3 class="font-medium text-gray-700">Download</h3>
                    <p>Average: <span id="avg-download" class="font-semibold">--</span> Mbps</p>
                    <p>Min: <span id="min-download" class="font-semibold">--</span> Mbps</p>
                    <p>Max: <span id="max-download" class="font-semibold">--</span> Mbps</p>
                </div>
                <div>
                    <h3 class="font-medium text-gray-700">Upload</h3>
                    <p>Average: <span id="avg-upload" class="font-semibold">--</span> Mbps</p>
                    <p>Min: <span id="min-upload" class="font-semibold">--</span> Mbps</p>
                    <p>Max: <span id="max-upload" class="font-semibold">--</span> Mbps</p>
                </div>
                <div>
                    <h3 class="font-medium text-gray-700">Compliance</h3>
                    <p>Download: <span id="comp-download" class="font-semibold">--</span>%</p>
                    <p>Upload: <span id="comp-upload" class="font-semibold">--</span>%</p>
                    <p>Tests: <span id="test-count" class="font-semibold">--</span></p>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Global chart references
        let speedChart, percentageChart, pingChart;
        
        // Initialize the dashboard when the page loads
        document.addEventListener('DOMContentLoaded', function() {
            loadData();
            
            // Refresh data every 5 minutes
            setInterval(loadData, 5 * 60 * 1000);
        });
        
        // Load data from the API
        async function loadData() {
            try {
                // Load speed data
                const speedResponse = await fetch('/api/speed-data');
                const speedData = await speedResponse.json();
                
                // Load summary data
                const summaryResponse = await fetch('/api/summary');
                const summaryData = await summaryResponse.json();
                
                // Update the UI with the latest data
                updateUI(speedData, summaryData);
                
                // Render charts
                renderCharts(speedData);
                
            } catch (error) {
                console.error('Error loading data:', error);
            }
        }
        
        // Update the UI with the latest data
        function updateUI(speedData, summaryData) {
            // Update current stats
            if (speedData.download && speedData.download.length > 0) {
                const lastIndex = speedData.download.length - 1;
                document.getElementById('current-download').textContent = speedData.download[lastIndex];
                document.getElementById('current-upload').textContent = speedData.upload[lastIndex];
                document.getElementById('current-ping').textContent = speedData.ping[lastIndex];
                
                // Calculate 24h compliance (simplified)
                const recentDownloads = speedData.download_percent.slice(-24);
                const recentUploads = speedData.upload_percent.slice(-24);
                const avgCompliance = (recentDownloads.reduce((a, b) => a + b, 0) / recentDownloads.length).toFixed(1);
                document.getElementById('compliance').textContent = `${avgCompliance}%`;
            }
            
            // Update summary stats
            if (summaryData.tests) {
                document.getElementById('avg-download').textContent = summaryData.average_download || '--';
                document.getElementById('min-download').textContent = summaryData.min_download || '--';
                document.getElementById('max-download').textContent = summaryData.max_download || '--';
                
                document.getElementById('avg-upload').textContent = summaryData.average_upload || '--';
                document.getElementById('min-upload').textContent = summaryData.min_upload || '--';
                document.getElementById('max-upload').textContent = summaryData.max_upload || '--';
                
                document.getElementById('comp-download').textContent = summaryData.compliance_download || '--';
                document.getElementById('comp-upload').textContent = summaryData.compliance_upload || '--';
                document.getElementById('test-count').textContent = summaryData.tests || '--';
            }
        }
        
        // Render charts
        function renderCharts(data) {
            const ctx1 = document.getElementById('speedChart').getContext('2d');
            const ctx2 = document.getElementById('percentageChart').getContext('2d');
            const ctx3 = document.getElementById('pingChart').getContext('2d');
            
            // Destroy existing charts if they exist
            if (speedChart) speedChart.destroy();
            if (percentageChart) percentageChart.destroy();
            if (pingChart) pingChart.destroy();
            
            // Speed Chart
            speedChart = new Chart(ctx1, {
                type: 'line',
                data: {
                    labels: data.timestamps,
                    datasets: [
                        {
                            label: 'Download (Mbps)',
                            data: data.download_ma,
                            borderColor: 'rgb(59, 130, 246)',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            borderWidth: 2,
                            tension: 0.3,
                            fill: true,
                            pointRadius: 0
                        },
                        {
                            label: 'Upload (Mbps)',
                            data: data.upload_ma,
                            borderColor: 'rgb(16, 185, 129)',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            borderWidth: 2,
                            tension: 0.3,
                            fill: true,
                            pointRadius: 0
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            type: 'time',
                            time: {
                                unit: 'day',
                                tooltipFormat: 'MMM D, HH:mm',
                                displayFormats: {
                                    hour: 'MMM D, HH:mm',
                                    day: 'MMM D'
                                }
                            },
                            grid: {
                                display: false
                            }
                        },
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Mbps'
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                        },
                    },
                    interaction: {
                        mode: 'nearest',
                        axis: 'x',
                        intersect: false
                    }
                }
            });
            
            // Percentage Chart
            percentageChart = new Chart(ctx2, {
                type: 'line',
                data: {
                    labels: data.timestamps,
                    datasets: [
                        {
                            label: 'Download % of Contracted',
                            data: data.download_percent,
                            borderColor: 'rgb(59, 130, 246)',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            borderWidth: 2,
                            tension: 0.3,
                            fill: true,
                            pointRadius: 0
                        },
                        {
                            label: 'Upload % of Contracted',
                            data: data.upload_percent,
                            borderColor: 'rgb(16, 185, 129)',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            borderWidth: 2,
                            tension: 0.3,
                            fill: true,
                            pointRadius: 0
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            type: 'time',
                            time: {
                                unit: 'day',
                                tooltipFormat: 'MMM D, HH:mm'
                            },
                            grid: {
                                display: false
                            }
                        },
                        y: {
                            beginAtZero: true,
                            max: 120,
                            title: {
                                display: true,
                                text: '% of Contracted Speed'
                            },
                            ticks: {
                                callback: function(value) {
                                    return value + '%';
                                }
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                            callbacks: {
                                label: function(context) {
                                    return context.dataset.label + ': ' + context.parsed.y.toFixed(1) + '%';
                                }
                            }
                        },
                        annotation: {
                            annotations: {
                                line1: {
                                    type: 'line',
                                    yMin: 80,
                                    yMax: 80,
                                    borderColor: 'rgb(75, 192, 192)',
                                    borderWidth: 2,
                                    borderDash: [6, 6],
                                    label: {
                                        content: '80% Threshold',
                                        enabled: true,
                                        position: 'right'
                                    }
                                }
                            }
                        }
                    }
                }
            });
            
            // Ping Chart
            pingChart = new Chart(ctx3, {
                type: 'line',
                data: {
                    labels: data.timestamps,
                    datasets: [{
                        label: 'Ping (ms)',
                        data: data.ping,
                        borderColor: 'rgb(245, 158, 11)',
                        backgroundColor: 'rgba(245, 158, 11, 0.1)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true,
                        pointRadius: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            type: 'time',
                            time: {
                                unit: 'day',
                                tooltipFormat: 'MMM D, HH:mm'
                            },
                            grid: {
                                display: false
                            }
                        },
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'ms'
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                        },
                    }
                }
            });
        }
    </script>
</body>
</html>""")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=CONFIG['port'], debug=True)
