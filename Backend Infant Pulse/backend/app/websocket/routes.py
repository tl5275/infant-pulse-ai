from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder

router = APIRouter()


@router.websocket("/ws/vitals")
async def vitals_websocket(websocket: WebSocket) -> None:
    manager = websocket.app.state.websocket_manager
    await manager.connect(websocket)
    await websocket.send_json(
        {
            "event": "connected",
            "data": {"message": "Subscribed to Infant Pulse live vitals stream"},
        }
    )

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)


@router.websocket("/ws/live")
async def live_websocket(websocket: WebSocket) -> None:
    manager = websocket.app.state.live_websocket_manager
    request_telemetry_service = websocket.app.state.request_telemetry_service
    await manager.connect(websocket)
    await websocket.send_json(jsonable_encoder(request_telemetry_service.generate_overview()))

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)
