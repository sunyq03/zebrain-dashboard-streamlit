"""本周关键结论 / 异常分析 的纯计算逻辑（无 UI 依赖）。

dashboard.py（看板）与 send_email.py（邮件预警）共用同一套口径，
保证页面与邮件结论完全一致。

核心概念：
- 趋势类指标（到课率/完课率/参与率）随学期自然下滑，
  以「全周期平均每周变化」为基准，看本周降幅是否好于常态。
- 首次 3 星率以「全周期均值」为基准。
- 完成时长不评级。
"""
import re


# ── 取数器 ────────────────────────────────────────────────────────────────
def get_week_stat(week):
    return (week or {}).get("weekStat", {}) or {}


def get_exam_stat(week):
    return ((week or {}).get("outline", {}) or {}).get("userOutlineTableStatVO", {}) or {}


def get_day_entries(week):
    return (week or {}).get("days", []) or []


def pct_val(v):
    try:
        return float(v) if v else None
    except (TypeError, ValueError):
        return None


def _day_code(label):
    m = re.match(r"\s*(D\d+)", label or "")
    return m.group(1) if m else (label or "")


def _clean_qtype(name):
    """'点击单选/多选-exam-V2' → '点击单选/多选'。"""
    if not name:
        return "题目"
    return re.split(r"[-（(]", name)[0].strip() or name


# ── 课程六大指标（D1-D4 / 整周聚合共用）──────────────────────────────────
COURSE_METRICS = [
    ("到课率", "attendanceRate", "pct"),
    ("完课率", "completionRate", "pct"),
    ("到课完课率", "classFinishRate", "pct"),
    ("完课留存率", "retentionRate", "pct"),
    ("完成时长", "completeTime", "min"),
    ("首次 3 星率", "firstThreeStarPercentage", "pct"),
]

SRC_GETTER = {"week": get_week_stat, "exam": get_exam_stat}


def build_kpis(exam_label):
    """关键指标卡定义：(名称, 字段, 类型, 数据源, 健康灯模式)。
    数据源 week=整周课程、exam=周测，UI 会据此把课程指标 / 周测指标分组展示。"""
    return [
        # —— 整周课程 ——
        ("整周到课率", "attendanceRate", "pct", "week", "trend"),
        ("整周完课率", "completionRate", "pct", "week", "trend"),
        ("整周到课完课率", "classFinishRate", "pct", "week", "trend"),
        # —— 周测 ——
        (f"{exam_label}参与率", "examAttendanceRate", "pct", "exam", "trend"),
        (f"{exam_label}完成率", "examCompletionRate", "pct", "exam", "trend"),
        (f"{exam_label}参与完成率", "examClassFinishRate", "pct", "exam", "trend"),
        (f"{exam_label}首次3星率", "firstThreeStarPercentage", "pct", "exam", "mean"),
        (f"{exam_label}完成时长", "completeTime", "min", "exam", "none"),
    ]


# ── 基准统计 ────────────────────────────────────────────────────────────
def field_mean(weeks, field, getter):
    vals = [pct_val(getter(w).get(field)) for w in weeks]
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def avg_weekly_delta(weeks, field, getter):
    """全周期「每周变化值」的均值（自然衰减时为负=平均每周降幅）。"""
    seq = [pct_val(getter(w).get(field)) for w in weeks]
    deltas = [seq[i] - seq[i - 1] for i in range(1, len(seq))
              if seq[i] is not None and seq[i - 1] is not None]
    return sum(deltas) / len(deltas) if deltas else None


def trend_streak(weeks, sel_index, field, getter):
    """从 sel_index 往前数，连续「差于常态」（环比 < 全周期平均每周变化）的周数。
    用于连续异常升级：连续多周差于常态 → 升级红灯。"""
    avg = avg_weekly_delta(weeks, field, getter)
    if avg is None:
        return 0
    streak = 0
    i = sel_index
    while i >= 1:
        cur = pct_val(getter(weeks[i]).get(field))
        prev = pct_val(getter(weeks[i - 1]).get(field))
        if cur is None or prev is None:
            break
        if (cur - prev) < avg:
            streak += 1
            i -= 1
        else:
            break
    return streak


STREAK_ESCALATE = 2  # 连续 ≥ 该周数差于常态 → 升级为红灯


def light(weeks, fld, kind, mode, cur, prev, getter):
    """健康灯：🟢/🟡/🔴/⚪。"""
    cf = pct_val(cur)
    if mode == "none" or kind == "min" or cf is None:
        return "⚪"
    if mode == "trend":
        pf = pct_val(prev)
        avg = avg_weekly_delta(weeks, fld, getter)
        if pf is None or avg is None:
            return "⚪"
        return "🟢" if (cf - pf) >= avg else "🟡"
    mean = field_mean(weeks, fld, getter)
    if mean is None:
        return "⚪"
    diff = cf - mean
    if diff >= 0:
        return "🟢"
    if diff >= -3:
        return "🟡"
    return "🔴"


def short_delta(cur, prev, kind):
    cf, pf = pct_val(cur), pct_val(prev)
    if cf is None or pf is None:
        return None
    d = cf - pf
    return f"{d/60:+.1f} 分钟" if kind == "min" else f"{d:+.1f}%"


def fmt_metric(v, kind):
    f = pct_val(v)
    if f is None:
        return "—"
    return f"{f/60:.1f} 分钟" if kind == "min" else f"{f:.1f}%"


# ── 根因归因：异常指标主要由哪一节课（D几）拖累 ──────────────────────────
def culprit_day(sel_week, prev_week, field):
    """返回 (课节label, 环比delta, 当前值) —— 该指标本周环比降幅最大的课节。"""
    if not prev_week:
        return None
    prev_days = {_day_code(d.get("label")): d for d in get_day_entries(prev_week)}
    worst = None
    for d in get_day_entries(sel_week):
        code = _day_code(d.get("label"))
        cur = pct_val((d.get("stat") or {}).get(field))
        pv = prev_days.get(code)
        prev = pct_val((pv.get("stat") if pv else {} or {}).get(field)) if pv else None
        if cur is None or prev is None:
            continue
        delta = cur - prev
        if worst is None or delta < worst[1]:
            worst = (d.get("label") or code, delta, cur)
    return worst


# ── 课节层级异常扫描（coverage）──────────────────────────────────────────
DAY_DROP_THRESHOLD = -5.0  # 课节某指标环比降幅超过该值视为异常


def day_anomalies(sel_week, prev_week, top_n=4):
    if not prev_week:
        return []
    prev_days = {_day_code(d.get("label")): d for d in get_day_entries(prev_week)}
    found = []
    for d in get_day_entries(sel_week):
        code = _day_code(d.get("label"))
        pv = prev_days.get(code)
        if not pv:
            continue
        for name, fld, kind in COURSE_METRICS:
            if kind != "pct":
                continue
            cur = pct_val((d.get("stat") or {}).get(fld))
            prev = pct_val((pv.get("stat") or {}).get(fld))
            if cur is None or prev is None:
                continue
            delta = cur - prev
            if delta <= DAY_DROP_THRESHOLD:
                found.append({
                    "day": d.get("label") or code, "metric": name,
                    "delta": delta, "cur": cur,
                    "text": f"{code} {name} 环比 {delta:+.1f}%（→ {cur:.1f}%）",
                })
    found.sort(key=lambda x: x["delta"])
    return found[:top_n]


# ── Top 低分题 / 最薄弱知识点 ────────────────────────────────────────────
def top_low_questions(sel_week, threshold=70.0, top_n=3):
    qs = sel_week.get("questions") or []
    rows = []
    for i, q in enumerate(qs):
        r = pct_val(q.get("firstThreeStarPercentage"))
        if r is None or r >= threshold:
            continue
        qvo = q.get("questionVO") or {}
        name = qvo.get("text") or f"第{i + 1}题"
        qtype = _clean_qtype(q.get("questionTypeName"))
        rows.append({
            "name": name,
            "type": qtype,
            "rate": r,
            "label": f"{name} · {qtype}",
        })
    rows.sort(key=lambda x: x["rate"])
    return rows[:top_n]


def weak_knowledge(sel_week, top_n=3, min_students=0):
    ks = sel_week.get("knowledge") or []
    rows = []
    for k in ks:
        name = k.get("knowledgeName")
        rate = pct_val(k.get("firstTimeThreeStarRate"))
        n = k.get("firstTimeAnswerStudentNum") or 0
        if not name or rate is None or n < min_students:
            continue
        rows.append({"name": name, "rate": rate, "n": int(n)})
    rows.sort(key=lambda x: x["rate"])
    return rows[:top_n]


def term_weak_knowledge(weeks, top_n=10):
    """全学期反复薄弱知识点：跨所有周次按知识点聚合周测首次 3 星率
    （按作答人次加权平均），按平均率从低到高排序。"""
    agg = {}
    for w in weeks:
        for k in w.get("knowledge") or []:
            name = k.get("knowledgeName")
            rate = pct_val(k.get("firstTimeThreeStarRate"))
            n = k.get("firstTimeAnswerStudentNum") or 0
            if not name or rate is None:
                continue
            a = agg.setdefault(name, {"rate_n": 0.0, "n": 0, "weeks": 0, "min": rate, "min_week": w["week"]})
            a["rate_n"] += rate * n
            a["n"] += n
            a["weeks"] += 1
            if rate < a["min"]:
                a["min"] = rate
                a["min_week"] = w["week"]
    rows = []
    for name, a in agg.items():
        if a["n"] <= 0:
            continue
        rows.append({
            "name": name,
            "avg": a["rate_n"] / a["n"],
            "weeks": a["weeks"],
            "n": int(a["n"]),
            "min": a["min"],
            "min_week": a["min_week"],
        })
    rows.sort(key=lambda x: x["avg"])
    return rows[:top_n]


# ── 建议规则 ────────────────────────────────────────────────────────────
def _advice_for(field, culprit_label=None):
    code = _day_code(culprit_label) if culprit_label else None
    suffix = f"，重点排查 {code}" if code else ""
    rules = {
        "attendanceRate": f"核对开课提醒与推送触达，关注开课节奏{suffix}",
        "completionRate": f"检查课程时长/难度与卡点环节{suffix}",
        "examAttendanceRate": "加强周测前的提醒与动员，关注「到课→完成」漏斗流失",
        "examCompletionRate": "排查周测时长/难度，关注中途流失环节",
        "examClassFinishRate": "关注「参与→完成」转化，排查弃考与中断",
        "firstThreeStarPercentage": "复盘高频错题与薄弱知识点（见下方），针对性补讲",
    }
    return rules.get(field)


# ── 主入口：产出结构化结论 ──────────────────────────────────────────────
def compute_insights(weeks, sel_week, prev_week, exam_label):
    """返回 dict：kpis / highlights / concerns / day_anomalies /
    top_low_questions / weak_knowledge。dashboard 与 email 共用。"""
    kpis_def = build_kpis(exam_label)
    cur_exam = get_exam_stat(sel_week)
    prev_exam = get_exam_stat(prev_week) if prev_week else {}
    cur_week = get_week_stat(sel_week)
    prev_week_stat = get_week_stat(prev_week) if prev_week else {}
    src_cur = {"week": cur_week, "exam": cur_exam}
    src_prev = {"week": prev_week_stat, "exam": prev_exam}

    # 当前周在 weeks 中的下标（用于连续异常检测）
    sel_index = next((i for i, w in enumerate(weeks) if w.get("week") == sel_week.get("week")), len(weeks) - 1)

    # 各 trend 指标的连续「差于常态」周数
    streaks = {}
    for name, fld, kind, src, mode in kpis_def:
        if mode == "trend":
            streaks[fld] = trend_streak(weeks, sel_index, fld, SRC_GETTER[src])

    kpis = []
    for name, fld, kind, src, mode in kpis_def:
        getter = SRC_GETTER[src]
        cur = src_cur[src].get(fld)
        prev = src_prev[src].get(fld)
        lt = light(weeks, fld, kind, mode, cur, prev, getter)
        streak = streaks.get(fld, 0)
        # 连续异常升级：trend 指标黄灯且连续 ≥STREAK_ESCALATE 周差于常态 → 红灯
        if mode == "trend" and lt == "🟡" and streak >= STREAK_ESCALATE:
            lt = "🔴"
        kpis.append({
            "name": name, "field": fld, "kind": kind, "mode": mode, "src": src,
            "value": cur, "value_str": fmt_metric(cur, kind),
            "delta_str": short_delta(cur, prev, kind),
            "light": lt, "streak": streak,
        })

    highlights, concerns = [], []
    for name, fld, kind, src, mode in kpis_def:
        if kind == "min":
            continue
        getter = SRC_GETTER[src]
        cur = pct_val(src_cur[src].get(fld))
        prev = pct_val(src_prev[src].get(fld))
        if cur is None:
            continue
        if mode == "trend":
            avg = avg_weekly_delta(weeks, fld, getter)
            if prev is None or avg is None:
                continue
            d = cur - prev
            if d >= avg + 1:
                highlights.append({"rank": d - avg,
                    "text": f"{name} 本周环比 {d:+.1f}%，好于常态（平均 {avg:+.1f}%/周）"})
            elif d < avg:
                # 归因到课节（仅整周到课/完课有 D1-D4 拆解）
                culprit = culprit_day(sel_week, prev_week, fld) if src == "week" else None
                attr = ""
                if culprit and culprit[1] < 0:
                    attr = f"，主要由 {_day_code(culprit[0])} 拖累（{culprit[2]:.1f}%，环比 {culprit[1]:+.1f}%）"
                streak = streaks.get(fld, 0)
                escalate = streak >= STREAK_ESCALATE
                streak_note = f"🔴 **已连续 {streak} 周差于常态**，" if escalate else ""
                advice = _advice_for(fld, culprit[0] if culprit else None)
                if escalate and advice:
                    advice = f"已连续下滑，建议尽快介入：{advice}"
                concerns.append({"rank": (d - avg) - (100 if escalate else 0), "field": fld,
                    "text": f"{streak_note}{name} 本周环比 {d:+.1f}%，差于常态降幅（平均 {avg:+.1f}%/周）{attr}",
                    "advice": advice,
                    "name": name, "delta_str": f"{d:+.1f}%", "delta_dir": "down",
                    "baseline_str": f"常态 {avg:+.1f}%/周",
                    "attr": attr.lstrip("，") if attr else "",
                    "streak": streak, "escalate": escalate})
        else:  # mean
            mean = field_mean(weeks, fld, getter)
            if prev is not None:
                d = cur - prev
                if d >= 1.0:
                    highlights.append({"rank": d, "text": f"{name} 环比上升 {d:+.1f}%（{cur:.1f}%）"})
                elif d <= -1.0:
                    concerns.append({"rank": d, "field": fld,
                        "text": f"{name} 环比下降 {d:.1f}%（{cur:.1f}%）",
                        "advice": _advice_for(fld),
                        "name": name, "delta_str": f"{d:.1f}%", "delta_dir": "down",
                        "baseline_str": f"当前 {cur:.1f}%", "attr": "",
                        "streak": 0, "escalate": False})
            if mean is not None and cur - mean <= -3:
                concerns.append({"rank": cur - mean, "field": fld,
                    "text": f"{name} 低于全周期均值（{cur:.1f}% vs 均值 {mean:.1f}%）",
                    "advice": _advice_for(fld),
                    "name": name, "delta_str": f"{cur - mean:.1f}%", "delta_dir": "down",
                    "baseline_str": f"均值 {mean:.1f}%", "attr": "",
                    "streak": 0, "escalate": False})

    low_qs = top_low_questions(sel_week)
    if low_qs:
        concerns.append({"rank": 0, "field": "low_q",
            "text": f"本周{exam_label}有 {len(top_low_questions(sel_week, top_n=999))} 道低分题"
                    f"（首次 3 星率 <70%）",
            "advice": "见下方「Top 低分题 / 薄弱知识点」，优先补讲"})

    concerns.sort(key=lambda x: x["rank"])
    highlights.sort(key=lambda x: -x["rank"])

    return {
        "kpis": kpis,
        "highlights": highlights,
        "concerns": concerns,
        "day_anomalies": day_anomalies(sel_week, prev_week),
        "top_low_questions": low_qs,
        "weak_knowledge": weak_knowledge(sel_week),
        "term_weak_knowledge": term_weak_knowledge(weeks),
    }
