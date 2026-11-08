"""Shared Apache ECharts options and Streamlit renderer."""

import streamlit as st
from streamlit_echarts import st_echarts

from config.settings import THEME


TEXT = THEME["text_main"]
MUTED = THEME["text_muted"]
GRID = "rgba(141,153,174,.16)"
SURFACE = THEME["dark_navy"]


def base_options(*, zoom: bool = False, toolbox: bool = True) -> dict:
    """Return shared dark Tangerine styling and interactive chart controls."""
    options = {
        "backgroundColor": "transparent",
        "animation": True,
        "animationDuration": 420,
        "animationDurationUpdate": 320,
        "animationEasing": "cubicOut",
        "animationEasingUpdate": "cubicOut",
        "textStyle": {"color": TEXT, "fontFamily": "Inter, Segoe UI, sans-serif"},
        "tooltip": {
            "trigger": "axis",
            "confine": True,
            "backgroundColor": SURFACE,
            "borderColor": THEME["primary_orange"],
            "textStyle": {"color": TEXT},
            "axisPointer": {"type": "cross", "label": {"backgroundColor": THEME["card_bg"]}},
        },
        "legend": {
            "type": "scroll",
            "top": 4,
            "textStyle": {"color": MUTED},
            "pageTextStyle": {"color": MUTED},
        },
        "grid": {
            "left": 16,
            "right": 24,
            "top": 48,
            "bottom": 24,
            "containLabel": True,
        },
        "aria": {"enabled": True},
    }
    if toolbox:
        options["toolbox"] = {
            "right": 8,
            "top": 4,
            "itemSize": 14,
            "iconStyle": {"borderColor": MUTED},
            "emphasis": {"iconStyle": {"borderColor": THEME["primary_orange"]}},
            "feature": {
                "dataZoom": {"yAxisIndex": "none"},
                "restore": {},
                "saveAsImage": {"name": "resilience-rewired-chart", "pixelRatio": 2},
            },
        }
    if zoom:
        options["grid"]["bottom"] = 66
        options["dataZoom"] = [
            {"type": "inside", "xAxisIndex": [0], "filterMode": "none"},
            {
                "type": "slider",
                "xAxisIndex": [0],
                "bottom": 10,
                "height": 16,
                "borderColor": "transparent",
                "backgroundColor": "rgba(141,153,174,.12)",
                "fillerColor": "rgba(255,91,0,.22)",
                "handleStyle": {"color": THEME["primary_orange"]},
                "textStyle": {"color": MUTED},
            },
        ]
    return options


def axis_style() -> dict:
    return {
        "axisLine": {"lineStyle": {"color": "rgba(141,153,174,.32)"}},
        "axisTick": {"show": False},
        "axisLabel": {"color": MUTED, "hideOverlap": True},
        "splitLine": {"lineStyle": {"color": GRID}},
    }


def render_chart(options: dict, *, key: str, height: int = 400):
    """Render ECharts while keeping a stable instance through Streamlit reruns."""
    for series in options.get("series", []):
        if isinstance(series, dict):
            series.setdefault("universalTransition", True)
    return st_echarts(
        options=options,
        height=f"{height}px",
        width="100%",
        key=key,
        renderer="canvas",
        replace_merge="series",
    )
