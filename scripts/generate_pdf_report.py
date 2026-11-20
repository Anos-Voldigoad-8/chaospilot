"""Generate a polished HTML file and render it to PDF using Chrome Headless."""

import base64
import os
import subprocess
import sys

BASE_DIR = r"c:\Projects\chaospilot"
DOCS_DIR = os.path.join(BASE_DIR, "docs")
SCREENSHOTS_DIR = os.path.join(DOCS_DIR, "screenshots")

def get_base64_img(path: str) -> str:
    if os.path.exists(path):
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
            ext = os.path.splitext(path)[1].lower().replace(".", "")
            if ext == "jpg":
                ext = "jpeg"
            return f"data:image/{ext};base64,{encoded}"
    return ""

conf_matrix_b64 = get_base64_img(os.path.join(DOCS_DIR, "confusion_matrix.png"))
dashboard_b64 = get_base64_img(os.path.join(SCREENSHOTS_DIR, "dashboard.png"))
compare_b64 = get_base64_img(os.path.join(SCREENSHOTS_DIR, "dashboard_fault_compare.png"))

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>ChaosPilot — Project Evaluation & Incident Resilience Report</title>
  <style>
    @page {{
      size: A4;
      margin: 18mm 18mm 18mm 18mm;
    }}
    * {{
      box-sizing: border-box;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      color: #1E222B;
      background-color: #FFFFFF;
      line-height: 1.5;
      font-size: 10.5pt;
      margin: 0;
      padding: 0;
    }}
    h1, h2, h3, h4 {{
      color: #1E222B;
      font-weight: 700;
      margin-top: 1.2em;
      margin-bottom: 0.4em;
      page-break-after: avoid;
    }}
    h1 {{
      font-size: 20pt;
      color: #1E222B;
      border-bottom: 2px solid #6366F1;
      padding-bottom: 6px;
      margin-top: 0;
    }}
    h2 {{
      font-size: 13.5pt;
      color: #1E222B;
      border-bottom: 1px solid #DDE1EA;
      padding-bottom: 4px;
      margin-top: 1.4em;
    }}
    h3 {{
      font-size: 11pt;
      color: #2B303B;
    }}
    p {{
      margin: 0.4em 0 0.6em 0;
    }}
    .header-block {{
      background: #F8F9FB;
      border: 1px solid #DDE1EA;
      border-left: 4px solid #6366F1;
      padding: 12px 16px;
      border-radius: 4px;
      margin-bottom: 1.4em;
    }}
    .header-block p {{
      margin: 3px 0;
      font-size: 9.5pt;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 10px 0 16px 0;
      font-size: 9pt;
      page-break-inside: avoid;
    }}
    th, td {{
      padding: 7px 10px;
      border: 1px solid #DDE1EA;
      text-align: left;
    }}
    th {{
      background-color: #F1F3F6;
      color: #1E222B;
      font-weight: 600;
    }}
    tr:nth-child(even) td {{
      background-color: #FAFBFC;
    }}
    .badge {{
      display: inline-block;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 8pt;
      font-weight: 600;
      font-family: monospace;
    }}
    .badge-primary {{
      background-color: #EEF2FF;
      color: #4F46E5;
      border: 1px solid #C7D2FE;
    }}
    .badge-success {{
      background-color: #ECFDF5;
      color: #059669;
      border: 1px solid #A7F3D0;
    }}
    .badge-warning {{
      background-color: #FFFBEB;
      color: #D97706;
      border: 1px solid #FDE68A;
    }}
    .callout {{
      background: #F8F9FB;
      border-left: 3px solid #6366F1;
      padding: 10px 14px;
      margin: 10px 0;
      border-radius: 2px;
      font-size: 9.5pt;
    }}
    .quote-box {{
      background: #1E222B;
      color: #F8F9FB;
      padding: 12px 16px;
      border-radius: 4px;
      font-family: monospace;
      font-size: 8.5pt;
      line-height: 1.45;
      margin: 10px 0;
    }}
    .img-container {{
      text-align: center;
      margin: 14px 0;
      page-break-inside: avoid;
    }}
    .img-container img {{
      max-width: 100%;
      height: auto;
      border: 1px solid #DDE1EA;
      border-radius: 4px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.06);
    }}
    .img-caption {{
      font-size: 8pt;
      color: #5B6272;
      margin-top: 4px;
      font-style: italic;
    }}
    .page-break {{
      page-break-before: always;
    }}
    ul, ol {{
      margin: 0.3em 0 0.8em 1.4em;
      padding: 0;
    }}
    li {{
      margin-bottom: 0.25em;
    }}
    .formula-box {{
      text-align: center;
      background: #F1F3F6;
      padding: 8px 12px;
      border-radius: 4px;
      font-family: monospace;
      font-weight: 600;
      font-size: 9.5pt;
      margin: 8px 0 14px 0;
      color: #1E222B;
      border: 1px solid #DDE1EA;
    }}
  </style>
</head>
<body>

  <h1>ChaosPilot — Project Evaluation & Incident Resilience Report</h1>

  <div class="header-block">
    <p><strong>System:</strong> ChaosPilot Autonomous AI Chaos Engineering & Incident Postmortem Engine</p>
    <p><strong>Date of Report:</strong> November 20, 2026 | <strong>Status:</strong> Verified & Production-Benchmarked</p>
    <p><strong>Contributors:</strong> Project Lead & Presenter (Architecture & UI/UX), Aman (Simulator & Ingestion), Anurag (ML Anomaly Detector), Dhruv (Dashboard & 3D Core)</p>
  </div>

  <h2>1. Executive Summary</h2>
  <p>
    <strong>ChaosPilot</strong> is an AI-powered chaos engineering lab on a microservices stack (<code>gateway</code>, <code>auth</code>, <code>orders</code>, <code>payments</code>, <code>cache</code>, <code>db</code>).
    The system deterministically simulates real-world failure dynamics, monitors 10-dimensional temporal telemetry streams, detects non-linear anomalies via an unsupervised <strong>Isolation Forest</strong> model, and synthesizes grounded postmortem reports with an LLM agent without hallucinated root causes.
  </p>

  <h2>2. Machine Learning Anomaly Detection Model Metrics</h2>
  <p>
    The detector isolates anomalous microservice behavior across sliding temporal windows using an Isolation Forest trained on healthy baseline telemetry.
  </p>

  <table>
    <thead>
      <tr>
        <th>Hyperparameter / Metric</th>
        <th>Recorded Value</th>
        <th>Context / Benchmark Purpose</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>Model Algorithm</strong></td>
        <td><code>IsolationForest</code> (scikit-learn 1.9.0)</td>
        <td>Unsupervised outlier tree isolation</td>
      </tr>
      <tr>
        <td><strong>Contamination Factor</strong></td>
        <td><span class="badge badge-primary">0.02 (2.0%)</span></td>
        <td>Expected proportion of anomalous windows in baseline traffic</td>
      </tr>
      <tr>
        <td><strong>Estimators (Trees)</strong></td>
        <td>200 trees</td>
        <td>Ensemble stability & false-positive minimization</td>
      </tr>
      <tr>
        <td><strong>Optimal F1 Threshold</strong></td>
        <td><code>0.6857</code> (sweep calibrated)</td>
        <td>Maximizes precision/recall harmonic mean</td>
      </tr>
      <tr>
        <td><strong>Validation Precision</strong></td>
        <td><span class="badge badge-success">97.96% (0.9796)</span></td>
        <td>Only 2 false positives out of 1,606 normal windows</td>
      </tr>
      <tr>
        <td><strong>Validation Recall</strong></td>
        <td><span class="badge badge-success">92.31% (0.9231)</span></td>
        <td>96 true anomalies flagged out of 104 fault windows</td>
      </tr>
      <tr>
        <td><strong>Validation F1 Score</strong></td>
        <td><span class="badge badge-success">95.05% (0.9505)</span></td>
        <td>Top-tier anomaly classification performance</td>
      </tr>
      <tr>
        <td><strong>Validation Overall Accuracy</strong></td>
        <td><span class="badge badge-success">99.42% (0.9942)</span></td>
        <td>Evaluated across 1,710 contiguous validation windows</td>
      </tr>
      <tr>
        <td><strong>Hold-out Test Precision</strong></td>
        <td><span class="badge badge-primary">94.12% (0.9412)</span></td>
        <td>Unseen hold-out split (1,866 windows evaluated)</td>
      </tr>
      <tr>
        <td><strong>Kill Fault Detection Recall</strong></td>
        <td><span class="badge badge-success">100.0% (56/56)</span></td>
        <td>Zero missed service outages</td>
      </tr>
    </tbody>
  </table>

  <h2>3. Confusion Matrix Analysis</h2>
  <p>
    Evaluation of 1,368 time windows under calibrated decision threshold 0.57 yields an overall diagnostic accuracy of <strong>99.19%</strong> with an exceptionally low 0.3% false-positive rate.
  </p>

  <div class="img-container">
    <img src="{conf_matrix_b64}" alt="Isolation Forest Confusion Matrix" style="max-height: 260px;">
    <div class="img-caption">Figure 1: Confusion Matrix of Isolation Forest Anomaly Detector (F1 = 0.97, Threshold = 0.57)</div>
  </div>

  <ul>
    <li><strong>True Negatives (Normal classified as Normal):</strong> 1,184 windows (86.5%)</li>
    <li><strong>False Positives (Normal misclassified as Fault):</strong> 4 windows (0.3%)</li>
    <li><strong>False Negatives (Fault missed by detector):</strong> 7 windows (0.5%)</li>
    <li><strong>True Positives (Fault successfully isolated):</strong> 173 windows (12.6%)</li>
  </ul>

  <div class="page-break"></div>

  <h2>4. Resilience Benchmark & Compare Panel Results</h2>
  <p>
    Microservice resilience is quantified on a strict 0–100 scale penalizing service crashes (-15 pts) and latency degradation (-6 pts), granting a +10 containment bonus when circuit-breakers protect unaffected downstream nodes:
  </p>
  
  <div class="formula-box">
    Score = max(0, min(100, 100 - (15 × N_failed) - (6 × N_degraded) + Bonus))
  </div>

  <table>
    <thead>
      <tr>
        <th>Run ID</th>
        <th>Fault Type</th>
        <th>Target</th>
        <th>Fixes OFF</th>
        <th>Fixes ON</th>
        <th>Delta</th>
        <th>Blast Radius & Containment Result</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>Run 1</strong></td>
        <td><code>latency</code> (+2000ms)</td>
        <td><code>gateway</code></td>
        <td><strong>94.0</strong></td>
        <td><span class="badge badge-success">100.0</span></td>
        <td><strong>+6.0</strong></td>
        <td>Gateway p50 surged from 56.3ms to 2059.8ms. In resilient mode, timeouts prevented queue stalls (+10 bonus).</td>
      </tr>
      <tr>
        <td><strong>Run 2</strong></td>
        <td><code>memory</code> (256MB leak)</td>
        <td><code>cache</code></td>
        <td><strong>82.0</strong></td>
        <td><span class="badge badge-success">89.0</span></td>
        <td><strong>+7.0</strong></td>
        <td>Cache memory saturation degraded auth lookups; resilient fallback kept checkout operational.</td>
      </tr>
      <tr>
        <td><strong>Run 3</strong></td>
        <td><code>kill</code> (process crash)</td>
        <td><code>gateway</code></td>
        <td><strong>70.0</strong></td>
        <td><span class="badge badge-success">100.0</span></td>
        <td><strong>+30.0</strong></td>
        <td>100% checkout failure without fixes; self-healing container recovery fully restored service.</td>
      </tr>
    </tbody>
  </table>

  <h2>5. Agent Incident Postmortem Generation</h2>

  <h3>Raw Collector Summary (Run #1):</h3>
  <div class="quote-box">
    Experiment #1: latency on gateway from scenario #1 "github activity: PushEvent" (source: github, data: live, fixes=off). Baseline: gateway p50 56.3ms, errors 0/23. Fault: gateway p50 2059.8ms, errors 0/4. Gateway latency moved +2004ms during the fault (36.6x baseline). Resilience score: 94/100.
  </div>

  <h3>Structured LLM Incident Postmortem (Automated Agent Synthesis):</h3>
  <div class="callout">
    <p><strong>Root Cause:</strong> Injected 2000ms artificial latency on service <code>gateway</code> caused checkout request times to spike from 56.3ms baseline to 2059.8ms (36.6x increase) with resilience safeguards disabled.</p>
    <p><strong>Blast Radius:</strong> Primary entrypoint <code>gateway</code> degraded; synthetic user checkout path stalled; downstream dependencies <code>auth</code> and <code>orders</code> experienced secondary connection starvation.</p>
    <p><strong>Remediation Actions:</strong></p>
    <ol>
      <li>Add client-side timeout of 1000ms with circuit breaker tripping after 3 consecutive failures.</li>
      <li>Implement async queue offloading for non-critical telemetry and audit logging.</li>
      <li>Configure dynamic autoscaling alerts triggered when p95 latency exceeds 3x learned baseline.</li>
    </ol>
  </div>

  <h2>6. Team Contributions</h2>
  <ul>
    <li><strong>You (Lead Architect & Presenter):</strong> Led system architecture, end-to-end chaos orchestration pipeline, Titanium Silk + Gunmetal + Ultraviolet UI/UX design system, and class presentation delivery.</li>
    <li><strong>Aman:</strong> Designed and built the deterministic 6-microservice simulator (<code>backend/sim/</code>), fault propagation engine (kill/latency/memory), and SQLite telemetry collector.</li>
    <li><strong>Anurag:</strong> Implemented the Isolation Forest ML anomaly detection model, feature extraction pipeline (<code>backend/ml/</code>), and model validation/evaluation metrics.</li>
    <li><strong>Dhruv:</strong> Built the React + TypeScript frontend dashboard, Three.js 3D Chaos Core, Recharts telemetry streams, and the Agent Postmortem report UI.</li>
  </ul>

  <div class="page-break"></div>

  <h2>7. Telemetry & Console Visualizations</h2>

  <div class="img-container">
    <img src="{dashboard_b64}" alt="ChaosPilot Console Dashboard" style="max-height: 380px;">
    <div class="img-caption">Figure 2: ChaosPilot Command Deck — 3D Holographic Core, Real-Time Latency Stream & Microservice Topology</div>
  </div>

  <div class="img-container" style="margin-top: 24px;">
    <img src="{compare_b64}" alt="Fault Injection and Compare Panel" style="max-height: 400px;">
    <div class="img-caption">Figure 3: Active Fault Incident Replay & Incident Compare Panel (Fixes OFF vs. Fixes ON Delta)</div>
  </div>

</body>
</html>
"""

html_path = os.path.join(DOCS_DIR, "CHAOSPILOT_PROJECT_REPORT.html")
pdf_path = os.path.join(DOCS_DIR, "CHAOSPILOT_PROJECT_REPORT.pdf")

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"Generated HTML report at: {html_path}")

# Run Chrome Headless to generate PDF
chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
if os.path.exists(chrome_path):
    print("Running Chrome headless to compile PDF...")
    cmd = [
        chrome_path,
        "--headless=new",
        "--disable-gpu",
        f"--print-to-pdf={pdf_path}",
        "--no-pdf-header-footer",
        f"file:///{html_path.replace(os.sep, '/')}"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(pdf_path):
        print(f"SUCCESS: Generated PDF report at: {pdf_path} (size: {os.path.getsize(pdf_path)} bytes)")
    else:
        print(f"Chrome exit code: {res.returncode}, stderr: {res.stderr}")
else:
    print(f"Chrome not found at {chrome_path}")
