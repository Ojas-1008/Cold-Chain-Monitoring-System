# 📊 Data Science & Analytics in Cold Chain Monitoring

This document outlines the core Data Science and Analytics concepts implemented in this system. While the project is built on IoT architecture, its "intelligence" is derived from statistical processing and predictive modeling to ensure the integrity of temperature-sensitive cargo.

---

## 🚀 1. Real-Time Stream Processing
In Data Science, "Stream Processing" refers to analyzing data as it arrives (in motion) rather than processing it in batch (at rest).

*   **Implementation:** The `subscriber/subscriber.py` script acts as our real-time engine. It processes every MQTT packet as it arrives from the field.
*   **Concepts Used:**
    *   **Rolling Window (Windowing):** We maintain a `sensor_history` buffer of the last **12 readings** (representing 60 seconds of history). This allows the system to calculate **Moving Averages (Rolling Mean)**, smoothing out sensor jitter without memory overhead.
    *   **Low-Latency Filtering:** Real-time threshold comparison happens in <5ms, allowing for instant alerting.

## 📉 2. Predictive Analytics (The "Forecast" Engine)
We move beyond reactive monitoring ("it's hot now") to proactive prevention ("it will be hot soon").

### A. Time-to-Breach (TTB) Prediction
*   **The Logic:** Instead of simple linear regression, we use a **Smoothed Slope Analysis** over the last 5 readings (~25 seconds).
*   **Formula:** `Slope = (Temp_now - Temp_5_intervals_ago) / 4`
*   **Confidence Interval (Safety Margin):** We apply a **0.9 (90%) Conservative Multiplier**. It is safer to alert a driver they have 9 minutes left when they have 10, then to overshoot and spoil the cargo.
*   **Visual Logic:** The dashboard highlights this as `⚠️ BREACH IN Xm` if the prediction falls below a 2-hour threshold.

### B. Estimated Battery Life (EBD)
*   **The Logic:** Tracks the **Discharge Rate** of the sensor.
*   **Calculation:** `Hours Remaining = Current Battery / (Rate of Drop * 720 readings/hour)`.
*   **Use Case:** Critical for logistics management—identifying which sensors need maintenance before they go "dark" mid-transit.

## 🛡️ 3. Statistical Anomaly Detection
The system distinguishes between "Environmental Noise" and "Actual Failures."

### A. Threshold-Based (Heuristic)
*   **Multi-Step Validation:** To prevent "false positives" (e.g., a door opens briefly), we use a **Stability Counter**. An alert only triggers if a breach persists for `MAX_FAILURES = 3` consecutive readings.

### B. Z-Score Analysis (Exploratory)
*   **Implementation:** Located in `notebooks/explore.ipynb`.
*   **The Math:** `Z = (Value - Mean) / Standard Deviation`.
*   **Purpose:** Identifying "Outliers" that are within the safe zone but statistically abnormal. For example, if a freezer suddenly jumps from -18C to -12C, it might still be "safe," but the Z-score will flag it as a potential cooling system failure.

## 🌡️ 4. Feature Engineering: The "Health Score"
Feature engineering converts raw data into actionable insights. We created a **Synthetic Metric** to represent the total status of a shipment.

*   **The Formula:** `Health = ((Battery % * 0.8) + (20 if NOT in breach)) / 100`
*   **Weighting:** 80% is allocated to hardware stability (battery) and 20% to environmental compliance. A sensor with a high temperature *and* a low battery represents a catastrophic failure risk.

## 🖥️ 5. Descriptive & Visual Analytics
The Dashboard (`dashboard/app.py`) translates complex time-series data into human-readable views.

*   **Safety Zone Overlays:** Using `Plotly` to overlay horizontal `dash` lines representing the specific safety limits for different product types (e.g., Vaccines vs. Meat).
*   **Category Risk Analysis:** A dynamic bar chart that aggregates breaches by **Product Category**, helping managers identify which logistics lines are most susceptible to failure.
*   **Temporal Resampling:** In exploratory views, we use `.resample('1min').mean()` to visualize long-term trends without the "hairiness" of raw 5-second sensor data.

## 📋 6. Post-Shipment Analytics (Reporting)
When a shipment is finalized, the system generates a **Performance Summary**.

*   **KPIs Tracked:**
    *   **Average Trip Temperature:** Overall mean of the shipment.
    *   **Total Breach Duration:** Calculation: `(Breach Readings * 5 seconds) / 60`.
    *   **Binary Verdict:** Automatic `PASS/FAIL` based on whether any sustained breaches occurred.

---

## 🚀 Future Roadmap: Industry 4.0
Future versions of the analytics engine could include:
1.  **Mean Kinetic Temperature (MKT):** A weighted average that accounts for the fact that higher temperatures accelerate degradation faster than a simple linear average suggests.
2.  **Cumulative Stability Budgets:** Tracking the total "Stress" on a vaccine across the entire cold chain (multiple shipments).
3.  **Predictive Routing:** Integrating GPS data to predict if weather patterns will cause a breach at the current truck speed.

---
*Created for the Cold Chain Monitoring System — Version 2.0*
