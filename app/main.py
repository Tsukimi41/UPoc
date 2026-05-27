from __future__ import annotations

import asyncio
import colorsys
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

GRID_WIDTH = 40
GRID_HEIGHT = 25
TOTAL_PIXELS = GRID_WIDTH * GRID_HEIGHT

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
    source: Optional[str] = Field(default=None, description="camera / manual / demo")


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


class AppState:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.caps: List[Dict[str, Any]] = []
        self.contributions: Dict[str, int] = {}
        self.themes: List[Dict[str, Any]] = [theme.copy() for theme in THEME_POOL]


state = AppState()
manager = ConnectionManager()

app = FastAPI(title="Cap Art MVP", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root() -> FileResponse:
    return FileResponse("static/index.html")


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


def build_leaderboard(contributions: Dict[str, int]) -> List[Dict[str, Any]]:
    ranking = [
        {"nickname": name, "count": count}
        for name, count in contributions.items()
        if name
    ]
    ranking.sort(key=lambda item: item["count"], reverse=True)
    return ranking[:10]


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
    blocked = {"<", ">", "&", "\"", "'"}
    cleaned = "".join(char for char in value.strip() if char.isprintable() and char not in blocked)
    if not cleaned:
        return "ゲスト"
    return cleaned[:20]


async def build_state_snapshot() -> Dict[str, Any]:
    async with state.lock:
        caps = list(state.caps)
        contributions = dict(state.contributions)
        themes = [theme.copy() for theme in state.themes]
    color_stats = build_color_stats(caps)
    return {
        "caps": caps,
        "progress": len(caps),
        "total": TOTAL_PIXELS,
        "remaining": TOTAL_PIXELS - len(caps),
        "width": GRID_WIDTH,
        "height": GRID_HEIGHT,
        "colorStats": color_stats,
        "leaderboard": build_leaderboard(contributions),
        "themes": themes,
        "suggestions": suggest_theme(color_stats),
    }


@app.get("/api/state")
async def get_state() -> Dict[str, Any]:
    return await build_state_snapshot()


@app.get("/api/caps/{cap_index}")
async def get_cap(cap_index: int) -> Dict[str, Any]:
    async with state.lock:
        if cap_index < 1 or cap_index > len(state.caps):
            raise HTTPException(status_code=404, detail="Cap not found")
        return state.caps[cap_index - 1]


@app.post("/api/caps")
async def add_cap(payload: CapInput) -> Dict[str, Any]:
    try:
        rgb = parse_color(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    hsv = rgb_to_hsv(rgb)
    color_name = classify_color(hsv)
    color_hex = "#{:02x}{:02x}{:02x}".format(*rgb)
    nickname = sanitize_nickname(payload.nickname)

    async with state.lock:
        if len(state.caps) >= TOTAL_PIXELS:
            raise HTTPException(status_code=409, detail="Art already completed")
        index = len(state.caps) + 1
        x, y = index_to_xy(index)
        cap = {
            "index": index,
            "x": x,
            "y": y,
            "color": {
                "name": color_name,
                "label": COLOR_LABELS.get(color_name, color_name),
                "hex": color_hex,
                "palette": COLOR_PALETTE.get(color_name, color_hex),
            },
            "nickname": nickname,
            "source": payload.source or "manual",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        state.caps.append(cap)
        state.contributions[nickname] = state.contributions.get(nickname, 0) + 1
        progress = len(state.caps)
        remaining = TOTAL_PIXELS - progress
        contributions = dict(state.contributions)
        caps_snapshot = list(state.caps)

    leaderboard = build_leaderboard(contributions)
    color_stats = build_color_stats(caps_snapshot)
    await manager.broadcast(
        {
            "type": "cap_added",
            "cap": cap,
            "progress": progress,
            "remaining": remaining,
            "total": TOTAL_PIXELS,
            "leaderboard": leaderboard,
            "colorStats": color_stats,
            "suggestions": suggest_theme(color_stats),
        }
    )
    return {
        "cap": cap,
        "progress": progress,
        "remaining": remaining,
        "total": TOTAL_PIXELS,
        "leaderboard": leaderboard,
        "colorStats": color_stats,
    }


@app.get("/api/leaderboard")
async def get_leaderboard() -> Dict[str, Any]:
    async with state.lock:
        contributions = dict(state.contributions)
    return {"leaderboard": build_leaderboard(contributions)}


@app.get("/api/color-stats")
async def get_color_stats() -> Dict[str, Any]:
    async with state.lock:
        caps = list(state.caps)
    return {"colorStats": build_color_stats(caps)}


@app.get("/api/suggestions")
async def get_suggestions() -> Dict[str, Any]:
    async with state.lock:
        caps = list(state.caps)
    color_stats = build_color_stats(caps)
    return suggest_theme(color_stats)


@app.get("/api/themes")
async def get_themes() -> Dict[str, Any]:
    async with state.lock:
        themes = [theme.copy() for theme in state.themes]
    return {"themes": themes}


@app.post("/api/themes/{theme_id}/vote")
async def vote_theme(theme_id: str) -> Dict[str, Any]:
    async with state.lock:
        for theme in state.themes:
            if theme["id"] == theme_id:
                theme["votes"] += 1
                break
        else:
            raise HTTPException(status_code=404, detail="Theme not found")
        themes = [theme.copy() for theme in state.themes]
    await manager.broadcast({"type": "theme_voted", "themes": themes})
    return {"themes": themes}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        snapshot = await build_state_snapshot()
        await websocket.send_json({"type": "state", "state": snapshot})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
