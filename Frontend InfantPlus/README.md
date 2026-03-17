# InfantPlus NICU Dashboard

A Next.js + Tailwind CSS hackathon frontend that simulates a production-grade NICU monitoring system with realtime telemetry, predictive vitals overlays, alerts, a digital twin room map, and a simplified parent view.

## Stack

- Next.js pages router
- React 18
- Tailwind CSS
- Recharts
- Mock WebSocket simulator with auto reconnect

## Run

1. Install Node.js 18 or newer.
2. Install dependencies:
   npm install
3. Start the dev server:
   npm run dev
4. Open the URL shown by Next.js in your terminal.

## Routes

- `/` NICU command center dashboard
- `/baby/NICU-101` bedside detail page
- `/parent?id=NICU-101` simplified parent view

## Notes

- Telemetry polling refreshes the dashboard every 2 seconds.
- Configure `NEXT_PUBLIC_API_URL` for the environment you are targeting.
- Periodic anomalies are injected to exercise alert states and risk escalation.
