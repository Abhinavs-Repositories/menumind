// Base URL of the MenuMind backend.
//
// Override per environment with EXPO_PUBLIC_API_URL:
//   - Web / iOS simulator:  http://localhost:8000
//   - Physical phone (Expo Go): http://<your-computer-LAN-IP>:8000
//   - Production: your deployed Hugging Face Space URL
export const API_URL = (
  process.env.EXPO_PUBLIC_API_URL ?? 'https://seahawk-menumind-api.hf.space'
).replace(/\/+$/, '');
