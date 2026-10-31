# web

The four screens, in React and Vite. Run with `pnpm install` then `pnpm dev`, and open `https://<laptop-ip>:5173`.

| Page | Path | Use |
| --- | --- | --- |
| Operator | `#/` | Live bench, steps, alerts, verdicts and timers. Draw zones here. |
| Camera | `#/camera` | Streams the camera to `ingest` over WebRTC |
| Phone | `#/phone` | Voice and vibration for the operator. Use Chrome on Android, and tap to arm. |
| Supervisor | `#/supervisor` | Results, incidents, manual search, and manual edits with approval |

The dev server uses a self-signed certificate because a phone's camera needs HTTPS. Accept the browser warning once.
