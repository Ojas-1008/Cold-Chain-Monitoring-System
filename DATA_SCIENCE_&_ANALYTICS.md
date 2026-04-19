# 📊 Data Science & Analytics in Cold Chain Monitoring

This document explains the core Data Science and Analytics concepts implemented in this project. Even though the project focuses on IoT and logistics, the "brain" of the system relies on statistical methods and data processing techniques to ensure cargo safety.

---

## 🚀 1. Real-Time Stream Processing
In Data Science, "Stream Processing" refers to analyzing data as it arrives, rather than waiting for a large batch.

*   **How it works here:** The `subscriber.py` script acts as a stream processor. It listens to MQTT messages (the stream) and instantly calculates metrics.
*   **Concepts used:**
    *   **Rolling Window (Windowing):** We maintain a `sensor_history` list for each sensor, keeping only the last 12 readings. This allows us to calculate moving averages without needing years of history in memory.
    *   **Low-latency Filtering:** Comparing every incoming temperature against a safety threshold in real-time.

## 📈 2. Feature Engineering & Heuristic Scoring
Feature engineering is the process of creating new pieces of information (features) from raw data to make better decisions.

*   **The "Health Score":** We created a custom formula to represent the "safety status" of a shipment in a single number (0 to 1.0).
    *   **The Formula:** `Health = (Battery % * 0.8) + (20 points if NOT in breach)`
    *   **Why?** A high temperature is dangerous, but a high temperature *with a dying battery* is a critical failure waiting to happen. This "Hybrid Score" helps operators prioritize which truck to check first.

## 🔍 3. Statistical Anomaly Detection
Detecting "outliers" or "anomalies" is a fundamental Data Science task. This project uses two levels of detection:

### A. Threshold-Based (Heuristic)
*   **Logic:** If `temp > max_limit` (High Breach) OR `temp < min_limit` (Low Breach), it's an anomaly.
*   **Refinement:** To avoid "false positives" (noise in the sensor), we use a **Stability Counter**. An alert only triggers if the temperature is breached (in either direction) 3 times in a row (`MAX_FAILURES = 3`).

### B. Z-Score Analysis (Advanced)
Found in the `notebooks/explore.ipynb`, the Z-score measures how many standard deviations a data point is from the mean.
*   **The Logic:** `Z = (Value - Mean) / Standard Deviation`
*   **Why use it?** If a sensor suddenly jumps 10 degrees, even if it's still "within the safe zone," it might be a sign of a failing cooling unit. The Z-score flags these statistical "weirdnesses."

## 📅 4. Time-Series Analytics
Since our data is indexed by time, we use specific Time-Series techniques.

*   **Resampling:** In the dashboard and notebooks, we use `resample('1min').mean()`. This "smooths out" the data by taking the average of every 60 seconds, making it easier to see long-term trends rather than jittery sensor noise.
*   **Duration Tracking:** We calculate the **Total Breach Time**. It's not just *that* it got hot, but *for how long*. 
    *   *Calculation:* `(Number of breach readings * Sensor Interval) / 60 = X minutes`.

## 💾 5. Data Persistence & Time-Series DB
Standard databases (like SQL) can struggle with millions of sensor readings.
*   **InfluxDB:** We use a dedicated Time-Series Database. It is optimized for "Write-Heavy" workloads and provides high-speed temporal queries (e.g., "Give me the average temp for last Tuesday").

## 🔮 6. Predictive Analytics (New!)
We don't just want to know what happened; we want to know what *will* happen.
*   **Time-to-Breach Prediction (Improved):** We use a **Smoothed Linear Trend** instead of just two data points.
    *   **The Logic:** We calculate the "Slope" across the last 5 readings (~25 seconds of history). This filters out one-off sensor jitters.
    *   **The Safety Margin (Confidence):** We intentionally multiply our prediction by **0.9 (90%)**. This is a **Conservative Heuristic**—it's safer to tell a driver they have 9 minutes left when they have 10, than to tell them they have 11 and have the cargo spoil.
    *   **Defensibility:** This mirrors industrial **Predictive Maintenance**. While we can't predict random "Black Swan" events (like an engine exploding), we provide a high-confidence forecast for gradual environmental failures.

*   **Estimated Battery Life (EBD):** Uses the same trend logic but applied to battery discharge rates. It predicts how many **hours** the sensor can continue operating before dying.

## 🖥️ 7. Descriptive Analytics (The Dashboard)
The Streamlit dashboard (`dashboard/app.py`) provides **Descriptive Analytics**—explaining what happened in the past and what is happening now.
*   **Risk Level Comparison:** A bar chart that aggregates breaches by **Product Category**. This helps managers see which products (e.g., vaccines vs. meat) are suffering from the most shipping failures.
*   **Aggregations:** Using Pandas to find the `min`, `max`, and `avg` for every sensor instantly.
*   **Trend Visualization:** Using `Plotly` to map out the "Life Cycle" of a shipment.
*   **Safety Zones:** Visualizing "Safe" vs "Danger" zones using horizontal lines on charts, giving immediate spatial context to numerical data.

---

## 🛠️ Key Data Tools Used
*   **Pandas:** The "Swiss Army Knife" for data manipulation. Used for cleaning, grouping, and calculating stats.
*   **Plotly:** For interactive, zoomable data visualizations.
*   **NumPy:** Used for mathematical calculations like Z-scores.
*   **InfluxDB Client:** To bridge the gap between IoT hardware and Data Science software.

---

## 🚀 8. Future Roadmap: Industry 4.0 Enhancements
To take this system to a professional "Big Pharma" level, the following Data Science concepts could be added:
*   **Mean Kinetic Temperature (MKT):** A weighted average that accounts for the accelerated degradation of products at higher temperatures.
*   **Cumulative Stability Budgets:** Moving from "Is it hot now?" to "What is the total time spent outside the safety zone across the entire trip?"
*   **Degree-Minute Integration:** Calculating the "Area Under the Curve" to measure the total heat energy absorbed by the cargo.
