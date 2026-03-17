# Infant Pulse AI 🚀

Real-time NICU monitoring system with:

- ECG + SpO2 + HR + BP monitoring
- ML-based anomaly detection
- Real-time dashboard (Next.js)
- FastAPI backend with WebSocket streaming

## Structure

- Backend: /Backend Infant Pulse
- Frontend: /Frontend InfantPlus
- ML Models: /ml_model

## Run Locally

### Backend
cd "Backend Infant Pulse"
pip install -r requirements.txt
uvicorn app:app --reload

### Frontend
cd "Frontend InfantPlus"
npm install
npm run dev

## Deployment

- Backend: Render
- Frontend: Render 
- https://infant-pulse-ai.onrender.com/
