import pytest

from app.main import (
    normalize_hex,
    hex_to_rgb,
    parse_color,
    rgb_to_hsv,
    classify_color,
    sanitize_nickname,
    sanitize_user_id,
    CapInput,
)


def test_normalize_hex_short():
    assert normalize_hex("#abc") == "#aabbcc"


def test_normalize_hex_plain():
    assert normalize_hex("fff") == "#ffffff"


def test_normalize_hex_invalid():
    with pytest.raises(ValueError):
        normalize_hex("#ggg")


def test_hex_to_rgb():
    assert hex_to_rgb("#00ff00") == [0, 255, 0]


def test_parse_color_rgb():
    payload = CapInput(rgb=[10, 20, 30])
    assert parse_color(payload) == [10, 20, 30]


def test_parse_color_hex():
    payload = CapInput(hex="#ff0000")
    assert parse_color(payload) == [255, 0, 0]


def test_rgb_to_hsv_and_classify():
    black = [0, 0, 0]
    hsv_black = rgb_to_hsv(black)
    assert classify_color(hsv_black) == "black"

    white = [255, 255, 255]
    hsv_white = rgb_to_hsv(white)
    assert classify_color(hsv_white) == "white"

    red = [255, 0, 0]
    hsv_red = rgb_to_hsv(red)
    assert classify_color(hsv_red) == "red"

    gray = [128, 128, 128]
    hsv_gray = rgb_to_hsv(gray)
    assert classify_color(hsv_gray) == "gray"

    blue = [0, 0, 255]
    hsv_blue = rgb_to_hsv(blue)
    assert classify_color(hsv_blue) == "blue"


def test_sanitize_nickname_and_user_id():
    assert sanitize_nickname(None) == "ゲスト"
    assert sanitize_nickname(" <bad> name ") == "bad name"
    long_name = "a" * 50
    assert len(sanitize_nickname(long_name)) <= 20

    assert sanitize_user_id(None) is None
    assert sanitize_user_id(" user123 ") == "user123"
    assert sanitize_user_id("<x>") == "x"
