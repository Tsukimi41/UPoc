from __future__ import annotations

import colorsys
import os
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db, init_db
from app.models import Cap, Checkin, Event, NotificationSubscription, Theme

GRID_WIDTH = 40
GRID_HEIGHT = 25
TOTAL_PIXELS = GRID_WIDTH * GRID_HEIGHT
DEFAULT_EVENT_ID = "default"
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")

COLOR_LABELS = {
    "red": "赤",
    "orange": "オレンジ",
    "yellow": "黄",
    "green": "緑",
    "cyan": "シアン",
    "blue": "青",
    "purple": "紫",
    "pink": "ピンク",
    "brown": "茶",
    "gray": "グレー",
    "black": "黒",
    "white": "白",
}

COLOR_PALETTE = {
    "red": "#e53935",
    "orange": "#fb8c00",
    "yellow": "#fdd835",
    "green": "#43a047",
    "cyan": "#00acc1",
    "blue": "#1e88e5",
    "purple": "#8e24aa",
    "pink": "#d81b60",
    "brown": "#6d4c41",
    "gray": "#757575",
    "black": "#212121",
    "white": "#f5f5f5",
}

THEME_POOL = [
    {
        "id": "chofu-water",
        "title": "調布の水辺",
        "description": "多摩川や野川の水景をイメージした爽やかなテーマ",
        "votes": 0,
    },
    {
        "id": "gegege",
        "title": "鬼太郎と仲間たち",
        "description": "調布のゆかりキャラクターをドット絵で表現",
        "votes": 0,
    },
    {
        "id": "station",
        "title": "調布駅前の風景",
        "description": "駅前広場のにぎわいを街の色で表現",
        "votes": 0,
    },
    {
        "id": "season",
        "title": "季節の花火",
        "description": "季節イベントに合わせた夜空の色合い",
        "votes": 0,
    },
]


class CapInput(BaseModel):
    hex: Optional[str] = Field(default=None, description="Hex color like #RRGGBB")
    rgb: Optional[List[int]] = Field(default=None, description="RGB list [0-255,0-255,0-255]")
    nickname: Optional[str] = Field(default=None)
    user_id: Optional[str] = Field(default=None)
    source: Optional[str] = Field(default=None, description="camera / manual / demo")
    checkin_token: Optional[str] = Field(default=None)


class CheckinInput(BaseModel):
    nickname: Optional[str] = Field(default=None)
    user_id: Optional[str] = Field(default=None)
    source: Optional[str] = Field(default=None, description="qr / tablet / event")


class NotificationSubscriptionInput(BaseModel):
    channel: str = Field(description="email / line / sms / other")
    contact: str
    user_id: Optional[str] = Field(default=None)


class AdminResetInput(BaseModel):
    reset_themes: bool = Field(default=False)
    clear_notifications: bool = Field(default=False)


class ConnectionManager:
    def __init__(self) -> None:
        self.active: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        for websocket in list(self.active):
            try:
                await websocket.send_json(message)
            except WebSocketDisconnect:
                self.disconnect(websocket)


manager = ConnectionManager()

app = FastAPI(title="Cap Art MVP", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    db = SessionLocal()
    try:
        seed_defaults(db)
    finally:
        db.close()


@app.get("/")
async def root() -> FileResponse:
    return FileResponse("static/index.html")


@app.get("/live")
async def live_page() -> FileResponse:
    return FileResponse("static/live.html")


@app.get("/checkin")
async def checkin_page() -> FileResponse:
    return FileResponse("static/checkin.html")


@app.get("/rewards")
async def rewards_page() -> FileResponse:
    return FileResponse("static/rewards.html")


def normalize_hex(value: str) -> str:
    value = value.strip().lower()
    if value.startswith("#"):
        value = value[1:]
    if len(value) == 3:
        value = "".join(char * 2 for char in value)
    if len(value) != 6 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("invalid hex")
    return f"#{value}"


def hex_to_rgb(value: str) -> List[int]:
    value = normalize_hex(value)[1:]
    return [int(value[i : i + 2], 16) for i in (0, 2, 4)]


def parse_color(payload: CapInput) -> List[int]:
    if payload.rgb is not None:
        if len(payload.rgb) != 3:
            raise ValueError("rgb must have 3 values")
        rgb = [int(max(0, min(255, channel))) for channel in payload.rgb]
        return rgb
    if payload.hex:
        return hex_to_rgb(payload.hex)
    return [random.randint(0, 255) for _ in range(3)]


def rgb_to_hsv(rgb: List[int]) -> List[float]:
    r, g, b = [channel / 255 for channel in rgb]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return [h * 360, s, v]


def classify_color(hsv: List[float]) -> str:
    h, s, v = hsv
    if v < 0.15:
        return "black"
    if v > 0.9 and s < 0.15:
        return "white"
    if s < 0.2:
        return "gray"
    if h < 15 or h >= 350:
        return "red"
    if h < 35:
        return "orange"
    if h < 70:
        return "yellow"
    if h < 160:
        return "green"
    if h < 200:
        return "cyan"
    if h < 260:
        return "blue"
    if h < 290:
        return "purple"
    if h < 350:
        return "pink"
    return "red"


def index_to_xy(index: int) -> List[int]:
    pos = index - 1
    return [pos % GRID_WIDTH, pos // GRID_WIDTH]


def build_color_stats(caps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counts: Dict[str, int] = {}
    for cap in caps:
        name = cap["color"]["name"]
        counts[name] = counts.get(name, 0) + 1
    total = len(caps)
    stats: List[Dict[str, Any]] = []
    for name, count in counts.items():
        stats.append(
            {
                "name": name,
                "label": COLOR_LABELS.get(name, name),
                "hex": COLOR_PALETTE.get(name, "#999999"),
                "count": count,
                "ratio": count / total if total else 0,
            }
        )
    stats.sort(key=lambda item: item["count"], reverse=True)
    return stats


def build_leaderboard(db: Session) -> List[Dict[str, Any]]:
    rows = (
        db.query(Cap.nickname, func.count(Cap.id).label("count"))
        .group_by(Cap.nickname)
        .order_by(func.count(Cap.id).desc())
        .limit(10)
        .all()
    )
    leaderboard = [
        {"nickname": row.nickname, "count": row.count}
        for row in rows
        if row.nickname
    ]
    return leaderboard


def suggest_theme(color_stats: List[Dict[str, Any]]) -> Dict[str, Any]:
    top_colors = [stat["name"] for stat in color_stats[:3]]
    palette = [
        {
            "name": stat["name"],
            "label": stat["label"],
            "hex": stat["hex"],
        }
        for stat in color_stats[:4]
    ]
    if not top_colors:
        return {
            "summary": "まだキャップが集まっていません。",
            "topColors": [],
            "suggestedThemes": [],
            "palette": [],
        }
    if "blue" in top_colors and "green" in top_colors:
        themes = [
            "水辺の調布風景",
            "初夏のけやき並木",
            "夜の調布花火",
        ]
    elif "red" in top_colors or "orange" in top_colors:
        themes = [
            "夕焼けの街並み",
            "鬼太郎の決めポーズ",
            "秋の祭り提灯",
        ]
    elif "yellow" in top_colors:
        themes = [
            "春の菜の花畑",
            "調布の商店街パレード",
            "子どもたちの笑顔",
        ]
    else:
        themes = [
            "季節のグラデーション",
            "調布の四季",
            "みんなのメッセージ",
        ]
    summary = f"直近のトップカラーは{', '.join(COLOR_LABELS.get(c, c) for c in top_colors)}です。"
    return {
        "summary": summary,
        "topColors": top_colors,
        "suggestedThemes": themes,
        "palette": palette,
    }


def sanitize_nickname(value: Optional[str]) -> str:
    if not value:
        return "ゲスト"
    blocked = {"<", ">", "&", '"', "'"}
    cleaned = "".join(char for char in value.strip() if char.isprintable() and char not in blocked)
    if not cleaned:
        return "ゲスト"
    return cleaned[:20]


def sanitize_user_id(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    blocked = {"<", ">", "&", '"', "'"}
    cleaned = "".join(char for char in value.strip() if char.isprintable() and char not in blocked)
    if not cleaned:
        return None
    return cleaned[:40]


def sanitize_channel(value: str) -> str:
    allowed = {"email", "line", "sms", "push", "other"}
    cleaned = value.strip().lower()
    if cleaned not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported channel")
    return cleaned


def sanitize_contact(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Contact is required")
    return cleaned[:200]


def cap_to_dict(cap: Cap) -> Dict[str, Any]:
    return {
        "index": cap.index,
        "x": cap.x,
        "y": cap.y,
        "color": {
            "name": cap.color_name,
            "label": cap.color_label,
            "hex": cap.color_hex,
            "palette": cap.color_palette,
        },
        "nickname": cap.nickname,
        "source": cap.source,
        "timestamp": cap.created_at.isoformat() if cap.created_at else None,
        "userId": cap.user_id,
        "checkinToken": cap.checkin_token,
    }


def theme_to_dict(theme: Theme) -> Dict[str, Any]:
    return {
        "id": theme.id,
        "title": theme.title,
        "description": theme.description,
        "votes": theme.votes,
        "active": theme.is_active,
    }


def event_to_dict(event: Event) -> Dict[str, Any]:
    return {
        "id": event.id,
        "title": event.title,
        "status": event.status,
        "total": event.total_pixels,
        "startedAt": event.started_at.isoformat() if event.started_at else None,
        "completedAt": event.completed_at.isoformat() if event.completed_at else None,
    }


def checkin_to_dict(checkin: Checkin) -> Dict[str, Any]:
    return {
        "token": checkin.token,
        "nickname": checkin.nickname,
        "userId": checkin.user_id,
        "source": checkin.source,
        "createdAt": checkin.created_at.isoformat() if checkin.created_at else None,
        "usedAt": checkin.used_at.isoformat() if checkin.used_at else None,
    }


def subscription_to_dict(subscription: NotificationSubscription) -> Dict[str, Any]:
    return {
        "id": subscription.id,
        "channel": subscription.channel,
        "contact": subscription.contact,
        "userId": subscription.user_id,
        "createdAt": subscription.created_at.isoformat() if subscription.created_at else None,
    }


def seed_defaults(db: Session) -> None:
    event = db.query(Event).filter(Event.id == DEFAULT_EVENT_ID).first()
    if not event:
        event = Event(
            id=DEFAULT_EVENT_ID,
            title="UPoc 2026",
            status="active",
            total_pixels=TOTAL_PIXELS,
            started_at=datetime.now(timezone.utc),
        )
        db.add(event)
    if db.query(Theme).count() == 0:
        for theme in THEME_POOL:
            db.add(
                Theme(
                    id=theme["id"],
                    title=theme["title"],
                    description=theme["description"],
                    votes=theme["votes"],
                    is_active=True,
                )
            )
    db.commit()


def get_event(db: Session) -> Optional[Event]:
    return db.query(Event).filter(Event.id == DEFAULT_EVENT_ID).first()


def build_state_snapshot(db: Session) -> Dict[str, Any]:
    caps = db.query(Cap).order_by(Cap.index).all()
    cap_items = [cap_to_dict(cap) for cap in caps]
    progress = len(cap_items)
    color_stats = build_color_stats(cap_items)
    themes = db.query(Theme).order_by(Theme.id).all()
    event = get_event(db)
    return {
        "caps": cap_items,
        "progress": progress,
        "total": TOTAL_PIXELS,
        "remaining": TOTAL_PIXELS - progress,
        "width": GRID_WIDTH,
        "height": GRID_HEIGHT,
        "colorStats": color_stats,
        "leaderboard": build_leaderboard(db),
        "themes": [theme_to_dict(theme) for theme in themes],
        "suggestions": suggest_theme(color_stats),
        "event": event_to_dict(event) if event else None,
    }


def require_admin(x_admin_token: Optional[str] = Header(default=None)) -> None:
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="Admin token not configured")
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/api/state")
def get_state(db: Session = Depends(get_db)) -> Dict[str, Any]:
    return build_state_snapshot(db)


@app.get("/api/caps/{cap_index}")
def get_cap(cap_index: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    cap = db.query(Cap).filter(Cap.index == cap_index).first()
    if not cap:
        raise HTTPException(status_code=404, detail="Cap not found")
    return cap_to_dict(cap)


@app.post("/api/caps")
async def add_cap(payload: CapInput, db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        rgb = parse_color(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    hsv = rgb_to_hsv(rgb)
    color_name = classify_color(hsv)
    color_hex = "#{:02x}{:02x}{:02x}".format(*rgb)
    nickname = sanitize_nickname(payload.nickname)
    user_id = sanitize_user_id(payload.user_id)
    progress = db.query(func.count(Cap.id)).scalar() or 0
    if progress >= TOTAL_PIXELS:
        raise HTTPException(status_code=409, detail="Art already completed")

    index = progress + 1
    x, y = index_to_xy(index)
    cap = Cap(
        index=index,
        x=x,
        y=y,
        color_name=color_name,
        color_label=COLOR_LABELS.get(color_name, color_name),
        color_hex=color_hex,
        color_palette=COLOR_PALETTE.get(color_name, color_hex),
        nickname=nickname,
        source=payload.source or "manual",
        user_id=user_id,
        checkin_token=payload.checkin_token,
        created_at=datetime.now(timezone.utc),
    )
    db.add(cap)
    db.commit()
    db.refresh(cap)

    event = get_event(db)
    if event and index >= event.total_pixels:
        event.status = "completed"
        event.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(event)

    leaderboard = build_leaderboard(db)
    caps = db.query(Cap).order_by(Cap.index).all()
    cap_items = [cap_to_dict(item) for item in caps]
    color_stats = build_color_stats(cap_items)

    await manager.broadcast(
        {
            "type": "cap_added",
            "cap": cap_to_dict(cap),
            "progress": index,
            "remaining": TOTAL_PIXELS - index,
            "total": TOTAL_PIXELS,
            "leaderboard": leaderboard,
            "colorStats": color_stats,
            "suggestions": suggest_theme(color_stats),
            "event": event_to_dict(event) if event else None,
        }
    )
    return {
        "cap": cap_to_dict(cap),
        "progress": index,
        "remaining": TOTAL_PIXELS - index,
        "total": TOTAL_PIXELS,
        "leaderboard": leaderboard,
        "colorStats": color_stats,
    }


@app.get("/api/leaderboard")
def get_leaderboard(db: Session = Depends(get_db)) -> Dict[str, Any]:
    return {"leaderboard": build_leaderboard(db)}


@app.get("/api/color-stats")
def get_color_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    caps = db.query(Cap).order_by(Cap.index).all()
    cap_items = [cap_to_dict(cap) for cap in caps]
    return {"colorStats": build_color_stats(cap_items)}


@app.get("/api/suggestions")
def get_suggestions(db: Session = Depends(get_db)) -> Dict[str, Any]:
    caps = db.query(Cap).order_by(Cap.index).all()
    cap_items = [cap_to_dict(cap) for cap in caps]
    color_stats = build_color_stats(cap_items)
    return suggest_theme(color_stats)


@app.get("/api/themes")
def get_themes(db: Session = Depends(get_db)) -> Dict[str, Any]:
    themes = db.query(Theme).order_by(Theme.id).all()
    return {"themes": [theme_to_dict(theme) for theme in themes]}


@app.post("/api/themes/{theme_id}/vote")
async def vote_theme(theme_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    theme = db.query(Theme).filter(Theme.id == theme_id).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    theme.votes += 1
    db.commit()
    db.refresh(theme)

    themes = db.query(Theme).order_by(Theme.id).all()
    payload = {"themes": [theme_to_dict(item) for item in themes]}
    await manager.broadcast({"type": "theme_voted", "themes": payload["themes"]})
    return payload


@app.post("/api/checkins")
def create_checkin(
    payload: CheckinInput,
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    nickname = sanitize_nickname(payload.nickname)
    user_id = sanitize_user_id(payload.user_id)
    token = uuid.uuid4().hex
    checkin = Checkin(
        token=token,
        nickname=nickname,
        user_id=user_id,
        source=payload.source or "qr",
        created_at=datetime.now(timezone.utc),
    )
    db.add(checkin)
    db.commit()
    db.refresh(checkin)
    return {
        "token": token,
        "url": f"{request.base_url}checkin/{token}",
        "checkin": checkin_to_dict(checkin),
    }


@app.post("/api/checkins/{token}/confirm")
def confirm_checkin(token: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    checkin = db.query(Checkin).filter(Checkin.token == token).first()
    if not checkin:
        raise HTTPException(status_code=404, detail="Checkin not found")
    if not checkin.used_at:
        checkin.used_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(checkin)
    return {"checkin": checkin_to_dict(checkin)}


@app.post("/api/notifications")
def create_notification(
    payload: NotificationSubscriptionInput,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    channel = sanitize_channel(payload.channel)
    contact = sanitize_contact(payload.contact)
    user_id = sanitize_user_id(payload.user_id)
    subscription = NotificationSubscription(
        channel=channel,
        contact=contact,
        user_id=user_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return {"subscription": subscription_to_dict(subscription)}


@app.get("/api/users/{user_id}/summary")
def get_user_summary(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    cleaned_user_id = sanitize_user_id(user_id)
    if not cleaned_user_id:
        raise HTTPException(status_code=400, detail="Invalid user id")
    total = db.query(func.count(Cap.id)).filter(Cap.user_id == cleaned_user_id).scalar() or 0
    latest = (
        db.query(Cap)
        .filter(Cap.user_id == cleaned_user_id)
        .order_by(Cap.index.desc())
        .first()
    )
    return {
        "userId": cleaned_user_id,
        "nickname": latest.nickname if latest else "",
        "total": total,
        "latest": cap_to_dict(latest) if latest else None,
    }


@app.get("/api/admin/summary")
def admin_summary(
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> Dict[str, Any]:
    caps = db.query(Cap).order_by(Cap.index).all()
    cap_items = [cap_to_dict(cap) for cap in caps]
    progress = len(cap_items)
    latest_caps = (
        db.query(Cap)
        .order_by(Cap.index.desc())
        .limit(5)
        .all()
    )
    themes = db.query(Theme).order_by(Theme.id).all()
    color_stats = build_color_stats(cap_items)
    return {
        "progress": progress,
        "total": TOTAL_PIXELS,
        "remaining": TOTAL_PIXELS - progress,
        "event": event_to_dict(get_event(db)) if get_event(db) else None,
        "latestCaps": [cap_to_dict(cap) for cap in latest_caps],
        "leaderboard": build_leaderboard(db),
        "colorStats": color_stats,
        "themes": [theme_to_dict(theme) for theme in themes],
        "suggestions": suggest_theme(color_stats),
    }


@app.get("/api/admin/caps")
def admin_caps(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> Dict[str, Any]:
    safe_limit = max(1, min(limit, 200))
    caps = (
        db.query(Cap)
        .order_by(Cap.index.desc())
        .offset(max(offset, 0))
        .limit(safe_limit)
        .all()
    )
    return {"caps": [cap_to_dict(cap) for cap in caps]}


@app.get("/api/admin/notifications")
def admin_notifications(
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> Dict[str, Any]:
    subscriptions = (
        db.query(NotificationSubscription)
        .order_by(NotificationSubscription.id.desc())
        .limit(200)
        .all()
    )
    return {"subscriptions": [subscription_to_dict(item) for item in subscriptions]}


@app.post("/api/admin/reset")
async def admin_reset(
    payload: AdminResetInput,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> Dict[str, Any]:
    db.query(Cap).delete()
    db.query(Checkin).delete()
    if payload.clear_notifications:
        db.query(NotificationSubscription).delete()
    if payload.reset_themes:
        for theme in db.query(Theme).all():
            theme.votes = 0
    event = get_event(db)
    if event:
        event.status = "active"
        event.started_at = datetime.now(timezone.utc)
        event.completed_at = None
        event.total_pixels = TOTAL_PIXELS
    db.commit()

    snapshot = build_state_snapshot(db)
    await manager.broadcast({"type": "state", "state": snapshot})
    return snapshot


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    db = SessionLocal()
    try:
        snapshot = build_state_snapshot(db)
        await websocket.send_json({"type": "state", "state": snapshot})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    finally:
        db.close()
