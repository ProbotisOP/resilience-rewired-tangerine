"""
Interactive charts for Resilience Rewired, built on Apache ECharts (streamlit-echarts).

Every chart gets the same simple interactions: tooltips on hover, legend toggling, a range slider on
long time axes, Save PNG, and optional click events that return the clicked point to Python.

No JavaScript is ever sent to the browser. Streamlit in Snowflake runs under a Content Security
Policy that blocks eval(), so JsCode formatters render as raw text there. Labels use ECharts string
templates or text pre-formatted in Python; clicks use the component's built-in point selection.
"""

from typing import Any, Dict, Iterable, List, Optional, Sequence

from streamlit_echarts import st_echarts

ORANGE = "#FF6A13"
ORANGE_SOFT = "#FFB37A"
TEAL = "#2EC4B6"
BLUE = "#4EA8DE"
RED = "#EF476F"
YELLOW = "#FFD166"
GREY = "#8A939E"
TEXT = "#E8EAED"
MUTED = "#9AA3AD"
GRID = "rgba(255,255,255,0.07)"
PALETTE = [ORANGE, TEAL, BLUE, YELLOW, RED, "#B388EB", GREY]

CAD = "${value}"  # ECharts fills {value} with the comma-grouped tick, e.g. $12,000


def money_text(value: Optional[float], decimals: int = 0) -> str:
    return "–" if value is None else f"{'-' if value < 0 else ''}${abs(value):,.{decimals}f}"


def _category_labels(labels: Sequence, budget_px: int = 900) -> Dict[str, Any]:
    """Tilt and thin category labels so they never overlap: flat when they fit, 35° when crowded, 45° when dense."""
    texts = [str(v) for v in labels]
    if not texts:
        return {}
    longest = max(len(t) for t in texts)
    needed = len(texts) * (longest * 7 + 12)
    if needed <= budget_px:
        return {"rotate": 0, "interval": 0, "hideOverlap": True}
    rotate = 35 if len(texts) <= 24 else 45
    return {"rotate": rotate, "interval": 0 if len(texts) <= 24 else "auto", "hideOverlap": True,
            "width": 120, "overflow": "truncate", "margin": 10}


def _base(title: Optional[str] = None, subtitle: Optional[str] = None) -> Dict[str, Any]:
    opts: Dict[str, Any] = {
        "backgroundColor": "transparent",
        "color": PALETTE,
        "textStyle": {"color": TEXT, "fontFamily": "Inter, -apple-system, Segoe UI, sans-serif"},
        "animationDuration": 600,
        "animationEasing": "cubicOut",
        "legend": {"type": "scroll", "top": 4, "left": "center", "right": 190, "textStyle": {"color": MUTED},
                   "icon": "roundRect", "pageTextStyle": {"color": MUTED}, "pageIconColor": ORANGE,
                   "itemWidth": 14, "itemHeight": 8},
        "grid": {"left": 12, "right": 44, "top": 48, "bottom": 18, "containLabel": True},
        "tooltip": {"trigger": "axis", "backgroundColor": "rgba(24,26,30,0.96)", "borderColor": "#3A4149",
                    "textStyle": {"color": TEXT}, "axisPointer": {"type": "line", "lineStyle": {"color": "#5A626C"}}},
        # Only "Save PNG": no box-zoom, chart-type switch or brush, so a click never leaves the chart in a strange state.
        "toolbox": {"orient": "vertical", "right": 2, "top": 60, "itemSize": 13, "itemGap": 9,
                    "iconStyle": {"borderColor": MUTED}, "emphasis": {"iconStyle": {"borderColor": ORANGE}},
                    "feature": {"saveAsImage": {"title": "Save PNG", "backgroundColor": "#1A1D21"}}},
    }
    # Header rows, top to bottom: title, subtitle, legend (full width), then the plot. The toolbox runs
    # down the right edge beside the plot, so it can never collide with a title or legend at any width.
    if title:
        opts["title"] = {"text": title, "subtext": subtitle or "", "left": 4, "top": 0, "itemGap": 6,
                         "textStyle": {"color": TEXT, "fontSize": 14, "fontWeight": 600},
                         "subtextStyle": {"color": MUTED, "fontSize": 11}}
        legend_top = 50 if subtitle else 30
    elif subtitle:
        opts["title"] = {"text": "", "subtext": subtitle, "left": 4, "top": 16, "subtextStyle": {"color": MUTED, "fontSize": 11}}
        legend_top = 46
    else:
        legend_top = 26
    opts["legend"].update({"top": legend_top, "left": 4, "right": 8})
    opts["grid"]["top"] = legend_top + 34
    return opts


def _axis(kind: str, name: str = "", data: Optional[Sequence] = None, money: bool = False, **extra) -> Dict[str, Any]:
    axis: Dict[str, Any] = {
        "type": kind, "name": name,
        "nameTextStyle": {"color": "#C9CED4", "fontSize": 12, "fontWeight": 600},
        "axisLine": {"lineStyle": {"color": "#3A4149"}}, "axisLabel": {"color": MUTED, "hideOverlap": True},
        "splitLine": {"lineStyle": {"color": GRID}},
    }
    if data is not None:
        axis["data"] = list(data)
        if kind == "category":
            axis["axisLabel"].update(_category_labels(axis["data"]))
    if money:
        axis["axisLabel"]["formatter"] = CAD
    axis.update(extra)
    return axis


def _zoom(n_points: int) -> List[Dict[str, Any]]:
    """Range slider only (no scroll-wheel zoom), so scrolling the page never zooms a chart by accident."""
    start = 0 if n_points <= 36 else max(0, 100 - 3600 / n_points)
    return [
        {"type": "slider", "start": start, "end": 100, "height": 18, "bottom": 4,
         "borderColor": "#3A4149", "fillerColor": "rgba(255,106,19,0.18)",
         "handleStyle": {"color": ORANGE}, "textStyle": {"color": MUTED},
         "dataBackground": {"lineStyle": {"color": GREY}, "areaStyle": {"color": "rgba(138,147,158,0.15)"}}},
    ]


def _plain(item: Any) -> Any:
    return item.get("value") if isinstance(item, dict) else item


def _clear_axis_names(opts: Dict[str, Any]) -> None:
    """Make axis titles readable and keep them clear of labels, legend and toolbox.

    Y titles sit above the axis, left-aligned (room is added above the plot). X titles sit centred
    under the tick labels (room is added below the plot, more when labels are tilted).
    Then line the vertical toolbox up with the plot's top edge and keep room for it on the right."""
    def as_list(a):
        return a if isinstance(a, list) else ([a] if a else [])

    grid = opts.get("grid")
    y_axes, x_axes = as_list(opts.get("yAxis")), as_list(opts.get("xAxis"))
    if grid is not None and any(isinstance(a, dict) and a.get("name") and a.get("nameLocation") != "middle" for a in y_axes):
        grid["top"] = grid.get("top", 48) + 20
        for i, a in enumerate(y_axes):
            if a.get("name") and a.get("nameLocation") != "middle":
                a["nameTextStyle"] = dict(a.get("nameTextStyle", {}), align="right" if i else "left")
                a["nameGap"] = 14
    for a in x_axes:
        if isinstance(a, dict) and a.get("name") and a.get("nameLocation") != "middle":
            rotated = bool(a.get("axisLabel", {}).get("rotate"))
            a.update({"nameLocation": "middle", "nameGap": 62 if rotated else 30})
            if grid is not None:
                grid["bottom"] = grid.get("bottom", 18) + (52 if rotated else 26)
    if grid is not None and opts.get("toolbox", {}).get("orient") == "vertical":
        opts["toolbox"]["top"] = grid["top"]
        grid["right"] = max(grid.get("right", 0), 48)


def _render(opts, height: int, key: str, clickable: bool, names: Optional[Sequence] = None,
            raw: Optional[List[List[Any]]] = None):
    """Draw the chart. With clickable, return the clicked point as {name, seriesName, value, dataIndex, data}.

    Clicks come from the component's built-in point selection (series and point index only), so the
    point's data is looked up here in Python instead of being shaped by a JavaScript handler.
    """
    _clear_axis_names(opts)
    if not clickable:
        st_echarts(options=opts, height=f"{height}px", key=key, theme="dark")
        return None
    result = st_echarts(options=opts, height=f"{height}px", key=key, theme="dark",
                        on_select="rerun", selection_mode=["points"])
    points = ((result or {}).get("selection") or {}).get("points") or []
    if not points:
        return None
    si, pi = int(points[0].get("series_index") or 0), points[0].get("point_index")
    series = opts.get("series") or []
    if pi is None or si >= len(series):
        return None
    pi = int(pi)
    data = raw[si] if raw is not None and si < len(raw) else [_plain(d) for d in series[si].get("data", [])]
    if pi >= len(data):
        return None
    name = names[pi] if names is not None and pi < len(names) else points[0].get("name")
    return {"name": name, "seriesName": series[si].get("name"), "value": data[pi], "dataIndex": pi, "data": data[pi]}


def signed_money(value: float) -> str:
    """Delta text Streamlit colours correctly: the sign must be the first character."""
    return f"{'-' if value < 0 else '+'}${abs(value):,.2f}"


def mark_line(value: float, label: str, color: str = GREY, axis: str = "yAxis") -> Dict[str, Any]:
    return {axis: value, "name": label, "lineStyle": {"color": color, "type": "dashed", "width": 1.5},
            "label": {"formatter": label, "color": color, "position": "insideEndTop"}}


def line_chart(
    x: Sequence,
    series: List[Dict[str, Any]],
    key: str,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    y_name: str = "CAD",
    money: bool = True,
    height: int = 380,
    zoom: bool = True,
    mark_lines: Iterable[Dict[str, Any]] = (),
    right_axis: Optional[Dict[str, Any]] = None,
    mark_areas: Iterable[Dict[str, Any]] = (),
    clickable: bool = False,
    x_name: str = "",
):
    """Line/area chart. Each series: {name, data, color?, area?, dashed?, step?, axis? (0|1), bar?}."""
    opts = _base(title, subtitle)
    opts["xAxis"] = _axis("category", x_name, data=x, boundaryGap=any(s.get("bar") for s in series))
    y_axes = [_axis("value", y_name, money=money, scale=False)]
    if right_axis:
        y_axes.append(_axis("value", right_axis.get("name", ""), money=right_axis.get("money", False),
                            splitLine={"show": False}, position="right"))
    opts["yAxis"] = y_axes
    if zoom:
        opts["dataZoom"] = _zoom(len(x))
        opts["toolbox"]["feature"] = {"restore": {"title": "Reset zoom"}, **opts["toolbox"]["feature"]}
        opts["grid"]["bottom"] = 40
    built = []
    for i, s in enumerate(series):
        color = s.get("color", PALETTE[i % len(PALETTE)])
        item: Dict[str, Any] = {
            "name": s["name"], "type": "bar" if s.get("bar") else "line", "data": list(s["data"]),
            "yAxisIndex": s.get("axis", 0), "smooth": s.get("smooth", False), "showSymbol": len(x) <= 24,
            "symbolSize": 6, "itemStyle": {"color": color},
            "lineStyle": {"width": s.get("width", 2.5), "color": color, "type": "dashed" if s.get("dashed") else "solid"},
        }
        if s.get("points"):
            item["markPoint"] = {"symbol": "pin", "symbolSize": 44, "data": s["points"],
                                 "label": {"color": "#111", "fontSize": 10, "fontWeight": 700}}
        if s.get("step"):
            item["step"] = "end"
            item["smooth"] = False
        if s.get("bar"):
            item["barMaxWidth"] = 14
            item["itemStyle"]["borderRadius"] = [3, 3, 0, 0]
        if s.get("area"):
            item["areaStyle"] = {"color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                                           "colorStops": [{"offset": 0, "color": color + "66"},
                                                          {"offset": 1, "color": color + "05"}]}}
        built.append(item)
    marks = list(mark_lines)
    if marks and built:
        # Alternate label ends so reference lines with close values don't print on top of each other.
        for i, m in enumerate(marks):
            if i % 2 and isinstance(m.get("label"), dict):
                m["label"] = dict(m["label"], position="insideStartTop")
        built[0]["markLine"] = {"symbol": "none", "silent": True, "data": marks}
    areas = list(mark_areas)
    if areas and built:
        built[0]["markArea"] = {"silent": True, "data": areas}
    opts["series"] = built
    return _render(opts, height, key, clickable, names=list(x))


def bar_chart(
    categories: Sequence,
    series: List[Dict[str, Any]],
    key: str,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    y_name: str = "",
    money: bool = False,
    horizontal: bool = False,
    stacked: bool = False,
    height: int = 360,
    mark_lines: Iterable[Dict[str, Any]] = (),
    clickable: bool = False,
    value_suffix: str = "",
    highlight: Optional[str] = None,
    x_name: str = "",
):
    """Bar chart. x_name titles the category axis, y_name the value axis. Each series: {name, data, color?, axis? (0|1), line? (render as line overlay)}."""
    opts = _base(title, subtitle)
    cat_axis = _axis("category", x_name, data=categories, axisTick={"alignWithLabel": True})
    if horizontal:
        cat_axis["axisLabel"].update({"rotate": 0, "interval": 0, "hideOverlap": False, "width": 210,
                                      "overflow": "truncate"})
    elif not cat_axis["axisLabel"].get("rotate"):
        cat_axis["axisLabel"].update({"width": 90, "overflow": "break"})
    val_axis = _axis("value", y_name, money=money)
    if value_suffix:
        val_axis["axisLabel"]["formatter"] = "{value}" + value_suffix
    opts["xAxis"], opts["yAxis"] = (val_axis, cat_axis) if horizontal else (cat_axis, val_axis)
    if any(s.get("axis") == 1 for s in series) and not horizontal:
        right = series[[s.get("axis") for s in series].index(1)]
        right_axis = _axis("value", right.get("axis_name", ""), money=bool(right.get("money")), splitLine={"show": False})
        if right.get("suffix") and not right.get("money"):
            right_axis["axisLabel"]["formatter"] = "{value}" + right["suffix"]
        opts["yAxis"] = [val_axis, right_axis]
    opts["tooltip"]["axisPointer"] = {"type": "shadow"}
    built, raw = [], []
    for i, s in enumerate(series):
        color = s.get("color", PALETTE[i % len(PALETTE)])
        values = list(s["data"])
        raw.append(values)
        data: List[Any] = values
        if highlight is not None and not s.get("line"):
            data = [{"value": v, "itemStyle": {"color": ORANGE if c == highlight else color + "AA",
                                               "borderColor": "#FFFFFF" if c == highlight else None,
                                               "borderWidth": 1.5 if c == highlight else 0}}
                    for c, v in zip(categories, values)]
        if s.get("labels") and money:
            # Pre-formatted per-bar text: a template cannot add the $ and thousands separators.
            data = [dict(d if isinstance(d, dict) else {"value": d},
                         label={"formatter": money_text(_plain(d))}) for d in data]
        item = {"name": s["name"], "type": "line" if s.get("line") else "bar", "data": data,
                "itemStyle": {"color": color, "borderRadius": ([0, 4, 4, 0] if horizontal else [4, 4, 0, 0])},
                "barMaxWidth": 38}
        if s.get("axis") == 1:
            item["yAxisIndex"] = 1
        if s.get("line"):
            item.update({"smooth": False, "symbolSize": 7, "lineStyle": {"width": 2.5, "color": color}})
        if stacked:
            item["stack"] = "total"
        if s.get("labels"):
            item["label"] = {"show": True, "position": "right" if horizontal else "top", "color": TEXT, "fontSize": 11}
            if not money:
                item["label"]["formatter"] = "{c}" + value_suffix
            if horizontal:
                opts["grid"]["right"] = 96  # labels of bars ending at the right edge need room before the toolbox
        built.append(item)
    marks = list(mark_lines)
    if marks and built:
        for i, m in enumerate(marks):
            if i % 2 and isinstance(m.get("label"), dict):
                m["label"] = dict(m["label"], position="insideStartTop")
        built[0]["markLine"] = {"symbol": "none", "silent": True, "data": marks}
    opts["series"] = built
    return _render(opts, height, key, clickable, names=list(categories), raw=raw)


def scatter_chart(
    groups: List[Dict[str, Any]],
    key: str,
    x_name: str,
    y_name: str,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    height: int = 460,
    x_money: bool = True,
    y_money: bool = True,
    x_log: bool = False,
    y_log: bool = False,
    tooltip_fields: Sequence[str] = ("Account", "x", "y"),
    highlight_point: Optional[Sequence[float]] = None,
    clickable: bool = True,
):
    """Scatter; hover for details, click a dot to open the account. Each group: {name, data: [[x, y, account_id, extra], ...], color?, size?}."""
    opts = _base(title, subtitle)
    opts["tooltip"] = {"trigger": "item", "backgroundColor": "rgba(24,26,30,0.96)", "borderColor": "#3A4149",
                       "textStyle": {"color": TEXT}}
    # Tooltip rows come from named dimensions holding pre-formatted text (no formatter function needed).
    dimensions = [{"name": "x", "type": "float"}, {"name": "y", "type": "float"},
                  {"name": "Account", "type": "ordinal"}, {"name": x_name, "type": "ordinal"},
                  {"name": y_name, "type": "ordinal"}, {"name": "Note", "type": "ordinal"}]
    encode = {"x": 0, "y": 1, "tooltip": [2, 3, 4, 5], "itemName": 2}

    def shown(point: Sequence[Any]) -> List[Any]:
        x, y = point[0], point[1]
        return [x, y, f"#{point[2]}" if len(point) > 2 else "",
                money_text(x) if x_money else x, money_text(y) if y_money else y,
                point[3] if len(point) > 3 and point[3] is not None else "Click to open this account"]

    opts["xAxis"] = _axis("log" if x_log else "value", x_name, money=x_money, scale=True)
    opts["yAxis"] = _axis("log" if y_log else "value", y_name, money=y_money, scale=True)
    series, raw = [], []
    for i, g in enumerate(groups):
        color = g.get("color", PALETTE[i % len(PALETTE)])
        raw.append(list(g["data"]))
        series.append({"name": g["name"], "type": "scatter", "data": [shown(p) for p in g["data"]],
                       "dimensions": dimensions, "encode": encode, "symbolSize": g.get("size", 6),
                       "large": len(g["data"]) > 2000, "itemStyle": {"color": color, "opacity": g.get("opacity", 0.7)},
                       "emphasis": {"itemStyle": {"opacity": 1, "borderColor": "#fff", "borderWidth": 1}}})
    if highlight_point is not None:
        raw.append([list(highlight_point)])
        series.append({"name": "Selected account", "type": "effectScatter", "data": [shown(highlight_point)],
                       "dimensions": dimensions, "encode": encode,
                       "symbolSize": 16, "rippleEffect": {"scale": 3, "brushType": "stroke"},
                       "itemStyle": {"color": "#FFFFFF", "borderColor": ORANGE, "borderWidth": 3}, "z": 10})
    opts["series"] = series
    return _render(opts, height, key, clickable, raw=raw)


def gauge_chart(value: float, key: str, title: str, max_value: float = 24, suffix: str = " mo",
                bands: Sequence = ((3, RED), (6, YELLOW), (24, TEAL)), height: int = 230,
                display: Optional[str] = None):
    """Half-ring gauge; bands are (upper bound, colour) pairs on the 0..max_value scale."""
    shown = min(max(value, 0), max_value)
    stops = [[min(b / max_value, 1.0), c] for b, c in bands]
    opts = {
        "backgroundColor": "transparent",
        "series": [{
            "type": "gauge", "startAngle": 200, "endAngle": -20, "min": 0, "max": max_value, "radius": "95%",
            "center": ["50%", "58%"], "splitNumber": 4,
            "axisLine": {"lineStyle": {"width": 14, "color": stops}},
            "pointer": {"width": 4, "length": "52%", "itemStyle": {"color": TEXT}},
            "anchor": {"show": True, "size": 12, "itemStyle": {"color": ORANGE}},
            "axisTick": {"show": False}, "splitLine": {"length": 10, "lineStyle": {"color": "#1A1D21", "width": 2}},
            "axisLabel": {"color": MUTED, "distance": 18, "fontSize": 10},
            "title": {"offsetCenter": [0, "62%"], "color": MUTED, "fontSize": 12},
            "detail": {"valueAnimation": True, "offsetCenter": [0, "36%"], "fontSize": 22, "fontWeight": 700,
                       "color": TEXT, "formatter": display if display else "{value}" + suffix},
            "data": [{"value": round(shown, 1), "name": title}],
        }],
    }
    st_echarts(options=opts, height=f"{height}px", key=key, theme="dark")


def heatmap_chart(x_labels: Sequence[str], y_labels: Sequence[str], values: List[List[float]], key: str,
                  title: Optional[str] = None, subtitle: Optional[str] = None, x_name: str = "", y_name: str = "",
                  max_value: float = 24, height: int = 380, marker: Optional[Sequence[int]] = None, clickable: bool = True):
    """values[y][x]. Colour scale red (0) → teal (max_value+). marker = [x_index, y_index] to outline."""
    raw = [[xi, yi, round(float(values[yi][xi]), 1)] for yi in range(len(y_labels)) for xi in range(len(x_labels))]

    def cell(xi: int, yi: int, v: float) -> Dict[str, Any]:
        runway = "120+ months (no shortfall)" if v >= 120 else f"{v} months"
        item: Dict[str, Any] = {"value": [xi, yi, v],
                                "name": f"{x_name} {x_labels[xi]} · {y_name} {y_labels[yi]} → runway {runway}"}
        if v >= 120:
            item["label"] = {"formatter": "∞"}
        return item

    opts = _base(title, subtitle)
    opts.pop("legend")
    opts["tooltip"] = {"trigger": "item", "backgroundColor": "rgba(24,26,30,0.96)", "borderColor": "#3A4149",
                       "textStyle": {"color": TEXT}, "formatter": "{b}<br/>Click to load this scenario"}
    opts["grid"].update({"left": 70, "bottom": 96, "containLabel": False, "right": 20})
    opts["xAxis"] = _axis("category", x_name, data=x_labels, splitArea={"show": False}, nameLocation="middle", nameGap=26)
    if opts["xAxis"]["axisLabel"].get("rotate"):
        opts["xAxis"]["nameGap"] = 46
        opts["grid"]["bottom"] = 116
    opts["yAxis"] = _axis("category", y_name, data=y_labels, nameLocation="middle", nameGap=52)
    opts["yAxis"]["axisLabel"].update({"rotate": 0, "interval": 0})
    opts["visualMap"] = {"min": 0, "max": max_value, "calculable": True, "orient": "horizontal", "left": "center",
                         "bottom": 0, "itemHeight": 260, "textStyle": {"color": MUTED},
                         "inRange": {"color": [RED, ORANGE, YELLOW, TEAL]}, "text": [f"{max_value}+ mo", "0 mo"]}
    series = [{"type": "heatmap", "data": [cell(*d) for d in raw],
               "label": {"show": len(x_labels) <= 12, "color": "#111", "fontSize": 10},
               "itemStyle": {"borderColor": "#15171A", "borderWidth": 1},
               "emphasis": {"itemStyle": {"borderColor": "#FFFFFF", "borderWidth": 2}}}]
    if marker is not None:
        series[0]["markPoint"] = {"symbol": "rect", "symbolSize": 26, "silent": True,
                                  "itemStyle": {"color": "transparent", "borderColor": "#FFFFFF", "borderWidth": 2.5},
                                  "data": [{"coord": [int(marker[0]), int(marker[1])]}]}
    opts["series"] = series
    return _render(opts, height, key, clickable, raw=[raw])


def donut_chart(items: List[Dict[str, Any]], key: str, title: Optional[str] = None, height: int = 300,
                money: bool = True, clickable: bool = False):
    """Donut. items: [{name, value, color?}]."""
    opts = _base(title)
    opts["tooltip"] = {"trigger": "item", "backgroundColor": "rgba(24,26,30,0.96)", "borderColor": "#3A4149",
                       "textStyle": {"color": TEXT}}
    opts["legend"] = {"orient": "vertical", "right": 4, "top": "middle", "textStyle": {"color": MUTED}}
    opts["toolbox"].update({"orient": "horizontal", "top": 0, "right": 6})  # the legend owns the right edge here
    opts["series"] = [{
        "type": "pie", "radius": ["48%", "74%"], "center": ["36%", "55%"], "avoidLabelOverlap": True,
        "itemStyle": {"borderColor": "#1A1D21", "borderWidth": 2, "borderRadius": 5},
        "label": {"show": False}, "emphasis": {"label": {"show": True, "fontWeight": 700, "color": TEXT,
                                                         "formatter": "{b}\n{d}%"}, "scale": True},
        "tooltip": {"formatter": "{b}: " + ("${c}" if money else "{c}") + " ({d}%)"},
        "data": [{"name": it["name"], "value": round(float(it["value"]), 2),
                  **({"itemStyle": {"color": it["color"]}} if it.get("color") else {})} for it in items],
    }]
    return _render(opts, height, key, clickable)


def band_chart(x: Sequence, actual: Sequence, forecast: Sequence, lower: Sequence, upper: Sequence, key: str,
               title: Optional[str] = None, subtitle: Optional[str] = None, extra: Optional[List[Dict[str, Any]]] = None,
               height: int = 380, split_label: Optional[str] = None):
    """Actual history, a model forecast and its prediction band (lower..upper), plus optional comparison lines."""
    opts = _base(title, subtitle)
    opts["xAxis"] = _axis("category", "Month", data=x, boundaryGap=False)
    opts["yAxis"] = _axis("value", "Average daily balance ($)", money=True)
    band_base = [None if v is None else round(v, 2) for v in lower]
    band_width = [None if (lo is None or hi is None) else round(hi - lo, 2) for lo, hi in zip(lower, upper)]
    series = [
        {"name": "Range low", "type": "line", "data": band_base, "stack": "band", "symbol": "none",
         "lineStyle": {"opacity": 0}, "tooltip": {"show": False}, "legendHoverLink": False},
        {"name": "80% prediction range", "type": "line", "data": band_width, "stack": "band", "symbol": "none",
         "lineStyle": {"opacity": 0}, "areaStyle": {"color": "rgba(78,168,222,0.22)"}, "tooltip": {"show": False}},
        {"name": "Observed", "type": "line", "data": [None if v is None else round(v, 2) for v in actual],
         "itemStyle": {"color": TEAL}, "lineStyle": {"width": 2.5, "color": TEAL}, "symbolSize": 5},
        {"name": "Forecast (MODEL ESTIMATE)", "type": "line", "data": [None if v is None else round(v, 2) for v in forecast],
         "itemStyle": {"color": BLUE}, "lineStyle": {"width": 2.5, "type": "dashed", "color": BLUE}, "symbolSize": 6},
    ]
    for e in extra or []:
        series.append({"name": e["name"], "type": "line", "data": e["data"], "symbol": "none",
                       "itemStyle": {"color": e.get("color", ORANGE)},
                       "lineStyle": {"width": 2, "type": "dotted", "color": e.get("color", ORANGE)}})
    if split_label:
        series[2]["markLine"] = {"symbol": "none", "silent": True, "data": [
            {"xAxis": split_label, "label": {"formatter": "forecast starts", "color": MUTED},
             "lineStyle": {"color": GREY, "type": "dashed"}},
            {"yAxis": 0, "label": {"formatter": "$0", "color": RED}, "lineStyle": {"color": RED, "type": "dashed"}}]}
    opts["legend"]["data"] = [s["name"] for s in series if s["name"] != "Range low"]
    opts["series"] = series
    _render(opts, height, key, False)
