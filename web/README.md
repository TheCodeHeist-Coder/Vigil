# web

The four screens, in React and Vite. Run with `pnpm install` then `pnpm dev`, and open <http://localhost:5173>.

| Page | Path | Use |
| --- | --- | --- |
| Bench | `#/` | Start a unit, follow each step, and see every alert and decision. Mark bench zones here. |
| Camera | `#/camera` | Streams the camera to `ingest` over WebRTC |
| Phone | `#/phone` | Voice and vibration for the operator. Use Chrome on Android, and tap to arm. |
| Supervisor | `#/supervisor` | Results, incidents, manual search, and manual edits with approval |

On this laptop, plain `http://localhost:5173` is enough, because browsers allow the camera on localhost. A phone reaches the laptop by IP address, which needs HTTPS, so `dev.sh` also serves `https://<laptop-ip>:5174`. Accept the certificate warning once on the phone.
