# Internet Speed Test Monitor

This project provides a solution to monitor internet speed, log results, and visualize them through a web-based dashboard.

## Project Structure

-   [`dashboard.py`](dashboard.py): Flask application that serves the web dashboard and API endpoints.
-   [`speed-test-script.py`](speed-test-script.py): Python script responsible for performing speed tests using `speedtest-cli`, logging results to a CSV file, and generating a summary report.
-   [`speed_log.csv`](speed_log.csv): Stores historical speed test data in a comma-separated values format.
-   [`speed_report.json`](speed_report.json): Contains aggregated summary statistics of the speed test results.
-   [`templates/dashboard.html`](templates/dashboard.html): The main HTML template for the web dashboard, featuring data visualizations powered by Chart.js and styled with Tailwind CSS.
-   `static/`: (Currently empty) Intended for serving static assets like custom CSS or JavaScript files.

## Key Functionalities

1.  **Automated Speed Testing**: The `speed-test-script.py` executes internet speed tests (download, upload, ping) and records the results.
2.  **Data Persistence**: All speed test results are logged into `speed_log.csv` for historical tracking and analysis.
3.  **Performance Reporting**: A summary report (`speed_report.json`) is generated, providing insights into average, minimum, maximum speeds, and compliance with contracted ISP speeds.
4.  **Interactive Web Dashboard**: `dashboard.py` hosts a Flask web application that presents the speed test data in an intuitive and interactive dashboard.
5.  **RESTful API**: The Flask application exposes several API endpoints:
    *   `/api/speed-data`: Delivers recent speed test data for dynamic charting.
    *   `/api/summary`: Provides the latest summary statistics from the generated report.
    *   `/api/run-test` (POST): Allows users to manually trigger a new speed test directly from the dashboard.
6.  **Rich Data Visualization**: The `dashboard.html` leverages Chart.js to render various graphs, including:
    *   Download and Upload Speed over time.
    *   Percentage of Contracted Speed (Download and Upload).
    *   Ping Latency.
    The dashboard also displays current and overall summary statistics.

## Data Flow and Interactions

1.  **Speed Test Execution**: `speed-test-script.py` runs, performs a speed test, appends the results to `speed_log.csv`, and updates `speed_report.json`.
2.  **Backend Data Processing**: `dashboard.py` reads and processes the raw data from `speed_log.csv` (using pandas) and the summary data from `speed_report.json`.
3.  **API Exposure**: The processed data is made available to the frontend through the `/api/speed-data` and `/api/summary` API endpoints.
4.  **Frontend Data Fetching**: The `dashboard.html` (client-side JavaScript) periodically fetches data from these API endpoints.
5.  **User-Initiated Tests**: A "Run Speed Test" button on the dashboard triggers a POST request to `/api/run-test`, which then executes `speed-test-script.py` on the server.
6.  **Dynamic UI Updates**: The fetched data is used to update the dashboard's charts and statistical displays in real-time.

## Setup and Usage

### Running the Dashboard

To run the Flask dashboard:

```bash
python3 dashboard.py
```

The dashboard will be accessible in your web browser at `http://127.0.0.1:8050`.

### Running Speed Tests Manually

To run a single speed test and log the results:

```bash
python3 speed-test-script.py
```

To generate and display a report:

```bash
python3 speed-test-script.py --report
```

### Running Speed Tests as a Daemon

To run speed tests continuously in the background (e.g., every 5 minutes):

```bash
python3 speed-test-script.py --daemon --interval 300
```

### Scheduling with Cron (Example)

To schedule the speed test script to run automatically, you can use `crontab`.

1.  Open your crontab editor:
    ```bash
    crontab -e
    ```

2.  Add one of the following lines to schedule the script. **Ensure the path to `python3` and `speed-test-script.py` is correct for your system.**

    *   **Run Script Every Hour**:
        ```cron
        0 * * * * /usr/local/bin/python3 /Users/nicorosen/code_projects/python/speed-test-monitor/speed-test-script.py
        ```

    *   **Run Script Every Minute (for testing)**:
        ```cron
        * * * * * /usr/local/bin/python3 /Users/nicorosen/code_projects/python/speed-test-monitor/speed-test-script.py
        ```

    *Note: The path `/usr/local/bin/python3` is a common location for Python 3. You might need to adjust this based on your Python installation. You can find your Python 3 path by running `which python3` in your terminal.*
