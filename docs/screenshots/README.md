# Screenshots and GIFs

This directory holds the visual assets referenced by the top-level README.

## Expected files

| File | Content |
| --- | --- |
| `dashboard.gif` | One full experiment: RUN -> fault -> anomaly -> postmortem -> compare |
| `dashboard.png` | Optional still of the default dashboard layout |

## Recording a demo GIF

1. Start the real stack with `./run_demo.sh` (or `.\run_demo.ps1`).
2. Open <http://localhost:5173> at roughly 1440x900 and let the first baseline
   settle.
3. Use a recorder such as ScreenToGif, Peek or `ffmpeg` with `x11grab`.
4. Select `latency` as the fault, `payments` as the target, toggle **Apply
   fixes** off, press **RUN**, and stop recording after the postmortem and
   compare panel update.
5. Keep the file under ~8 MB so GitHub renders it inline. Prefer 12-15 fps and
   a cropped region over the full screen.

If the real stack is not available, record `http://localhost:5173/?mock=1`
instead and label the GIF as "scripted replay".

Do not include `.env`, tokens, hostnames or any other local secrets in the
recording.
