import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from matplotlib.colors import LinearSegmentedColormap
import weekly_insights as wi

# ── 全局语义色（好 / 警示 / 差 / 中性）：全站状态类元素统一用这一套 ──────────
C_GOOD = "#2a9d3f"      # 好 / 上升（正向）
C_GOOD_BG = "#e9f6ee"
C_WARN = "#d9930a"      # 警示 / 偏离常态
C_WARN_BG = "#fdf4e3"
C_BAD = "#c0392b"       # 差 / 下滑（负向）/ 连续异常
C_BAD_BG = "#fdecea"
C_NEUTRAL = "#6b7280"   # 中性 / 不评级
C_MUTED = "#9ca3af"     # 次要文字
C_INK = "#111827"       # 主文字
C_LINE = "#e5e7eb"      # 边框线
C_AI = "#4f46e5"        # AI 分析统一强调色（靛蓝）
C_AI_BG = "#eef0fd"

# 表格用「单色顺序色阶」（浅→深=该列内由低到高），刻意避开红/黄/绿——
# 因为红/黄/绿在本看板已专门表示「健康状态(差/警示/好)」。表格底色只表达
# “该指标在各周中的相对高低/分布”，不含好坏判定，故用中性的青蓝单色避免误读。
SOFT_CMAP = LinearSegmentedColormap.from_list(
    "soft_seq",
    ["#f1f5f7", "#dbe9ec", "#bcd8da", "#93c2c2", "#6aa9a6"],
)
# 缺失值（未开放该指标的课节）用浅灰底，避免默认的刺眼黑色块
SOFT_CMAP.set_bad(color="#f3f4f6")


def style_heatmap(df, pct_cols, fmt, height=None):
    """统一的表格样式：柔和色阶 + 白色细网格 + 居中 + 深色文字。"""
    styler = (
        df.style
        .background_gradient(cmap=SOFT_CMAP, subset=pct_cols, axis=0)
        .format(fmt, na_rep="—")
        .set_properties(**{
            "color": "#374151",
            "font-size": "13px",
            "text-align": "center",
            "border": "2px solid #ffffff",
            "padding": "6px 8px",
        })
        .set_table_styles([
            {"selector": "th",
             "props": [("background-color", "#f8fafc"), ("color", "#475569"),
                       ("font-weight", "600"), ("font-size", "12px"),
                       ("text-align", "center"), ("border", "2px solid #ffffff"),
                       ("padding", "8px")]},
        ])
    )
    # 按内容自适应宽度，不再横向铺满整页
    if height is not None:
        st.dataframe(styler, use_container_width=False, height=height, hide_index=True)
    else:
        st.dataframe(styler, use_container_width=False, hide_index=True)

DATA_FILE = Path(__file__).parent / "data" / "latest.json"
WEEK_NAMES_FILE = Path(__file__).parent / "week_names.json"
QUESTION_ANALYSIS_FILE = Path(__file__).parent / "question_analysis.json"
AI_ANALYSIS_FILE = Path(__file__).parent / "ai_analysis.json"
WEEKLY_SUMMARY_FILE = Path(__file__).parent / "weekly_summary.json"
COURSE_SUMMARY_FILE = Path(__file__).parent / "course_summary.json"
OVERALL_SUMMARY_FILE = Path(__file__).parent / "overall_summary.json"

st.set_page_config(page_title="周测数据报表", layout="wide")

if not DATA_FILE.exists():
    st.warning("暂无数据，请先运行 `./venv/bin/python fetch_data.py`")
    st.stop()

raw = json.loads(DATA_FILE.read_text())
fetched_at = raw.get("fetched_at", "")[:19].replace("T", " ")
stages = raw.get("stages", [])
if not stages:
    st.warning("数据为空")
    st.stop()

WEEK_NAMES = json.loads(WEEK_NAMES_FILE.read_text()) if WEEK_NAMES_FILE.exists() else {}
QUESTION_ANALYSIS = json.loads(QUESTION_ANALYSIS_FILE.read_text()) if QUESTION_ANALYSIS_FILE.exists() else {}
AI_ANALYSIS = json.loads(AI_ANALYSIS_FILE.read_text()) if AI_ANALYSIS_FILE.exists() else {}
WEEKLY_SUMMARY = json.loads(WEEKLY_SUMMARY_FILE.read_text()) if WEEKLY_SUMMARY_FILE.exists() else {}
COURSE_SUMMARY = json.loads(COURSE_SUMMARY_FILE.read_text()) if COURSE_SUMMARY_FILE.exists() else {}
OVERALL_SUMMARY = json.loads(OVERALL_SUMMARY_FILE.read_text()) if OVERALL_SUMMARY_FILE.exists() else {}

def week_full(stage_name: str, week: str) -> str:
    """W1 -> 'W1 · 语义推理之排除法'，找不到映射则原样返回"""
    name = WEEK_NAMES.get(stage_name, {}).get(week)
    return f"{week} · {name}" if name else week

def week_name_only(stage_name: str, week: str) -> str:
    """W1 -> '语义推理之排除法'，找不到返回空字符串"""
    return WEEK_NAMES.get(stage_name, {}).get(week, "")

def get_expert_qa(qid) -> dict | None:
    """按题目 ID 获取专家分析（若 question_analysis.json 里有）"""
    if qid is None:
        return None
    return QUESTION_ANALYSIS.get(str(qid))

def get_ai_qa(qid) -> dict | None:
    """按题目 ID 获取 AI 教研分析（若 ai_analysis.json 里有）"""
    if qid is None:
        return None
    return AI_ANALYSIS.get(str(qid))

# ── 工具函数 ──────────────────────────────────────────────────────────────
def get_stat(week):
    return week.get("outline", {}).get("userOutlineTableStatVO", {})

def pct(v):
    if v is None: return "—"
    try: return f"{float(v):.1f}%" if float(v) > 0 else "—"
    except: return "—"

def pct_val(v):
    try: return float(v) if v else None
    except: return None

def sec_to_min(v):
    if v is None: return "—"
    try: return f"{float(v)/60:.2f} 分钟"
    except: return "—"

def num(v):
    return f"{int(v):,}" if v is not None else "—"

# ── 整周 / D1-D4 系统课 相关 ────────────────────────────────────────────────
def get_week_stat(week):
    """整周聚合数据（D1-D4：率取均值、时长累计）。"""
    return (week or {}).get("weekStat", {}) or {}

def get_day_entries(week):
    """D1-D4 系统课每节课 [{label, episodeId, stat}]。"""
    return (week or {}).get("days", []) or []

# 系统课/整周 六大指标：(显示名, 字段, 类型 pct|min)
COURSE_METRICS = [
    ("到课率", "attendanceRate", "pct"),
    ("完课率", "completionRate", "pct"),
    ("到课完课率", "classFinishRate", "pct"),
    ("完课留存率", "retentionRate", "pct"),
    ("完成时长", "completeTime", "min"),
    ("首次 3 星率", "firstThreeStarPercentage", "pct"),
]

# 周测六大指标（周测的到课/完课用 exam* 字段）
EXAM_METRICS = [
    ("参与率（到课）", "examAttendanceRate", "pct"),
    ("参与完成率", "examClassFinishRate", "pct"),
    ("完课率", "examCompletionRate", "pct"),
    ("首次 3 星率", "firstThreeStarPercentage", "pct"),
    ("完成时长", "completeTime", "min"),
]

def fmt_metric(v, kind):
    if v is None: return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "—"
    return f"{f/60:.1f} 分钟" if kind == "min" else f"{f:.1f}%"

def metric_delta_str(cur, prev, kind):
    """环比文案：率用 %，时长用分钟。"""
    cf, pf = pct_val(cur), pct_val(prev)
    if cf is None or pf is None:
        return None
    d = cf - pf
    return f"{d/60:+.2f} 分钟 环比" if kind == "min" else f"{d:+.1f}% 环比"

# ── 题目分析渲染（周测 / 系统课 共用）──────────────────────────────────────
def render_question_analysis(questions, knowledge, week_label, stage_name, title_label):
    """渲染单份题目数据（题目概览卡片 + 低分题分析）。
    周测与系统课 D1-D4 共用：缺失字段（错因/知识点名）会自动降级。"""
    knowledge = knowledge or []
    kn_map = {}
    for k in knowledge:
        ep = k.get("episodeId") or k.get("id")
        name = k.get("knowledgeName") or k.get("name") or k.get("chapterName") or ""
        if ep:
            kn_map[ep] = name

    if not questions:
        st.info("暂无题目数据，请重新运行 fetch_data.py 拉取。")
        return

    valid_rates = [pct_val(q.get("firstThreeStarPercentage")) for q in questions]
    valid_rates = [r for r in valid_rates if r is not None]
    week_mean_rate = sum(valid_rates) / len(valid_rates) if valid_rates else None

    enriched = []
    for i, q in enumerate(questions):
        rate = pct_val(q.get("firstThreeStarPercentage"))
        qid = q.get("questionId")
        avg_time = q.get("answerTimeMedian") or q.get("questionAverageAnswerTime")
        qvo = q.get("questionVO") or {}
        q_type = q.get("questionTypeName") or qvo.get("questionTypeName") or ""
        kn_vos = q.get("knowledgeVOs") or []
        kn_name = kn_vos[0].get("keypointText", "") if kn_vos else (q.get("chapterTypeLabel") or "")
        preview_url = qvo.get("previewImageUrl") or ""
        q_name = qvo.get("text") or f"第 {i + 1} 题"
        wrong_raw = q.get("nonThreeStarWrongOptionsRate") or []
        enriched.append({
            "idx": i, "seq": i + 1, "qid": qid, "rate": rate, "name": q_name,
            "avg_time": avg_time, "q_type": q_type, "kn_name": kn_name,
            "preview_url": preview_url, "wrong_raw": wrong_raw,
            "expert": get_expert_qa(qid),
        })

    # 🔍 题目卡片网格
    expert_count = sum(1 for e in enriched if e["expert"])
    st.subheader(f"📒 题目概览 — {title_label}（共 {len(questions)} 题）")
    if expert_count:
        st.caption(f"📌 标记 = 该题有教研专家分析（{expert_count} 题），点击卡片底部 “教学分析” 展开。")
    cols = st.columns(4)

    for e in enriched:
        rate = e["rate"]
        if rate is not None and rate >= 90:
            rate_bg = C_GOOD_BG; rate_fg = C_GOOD; tag = "优"
        elif rate is not None and rate >= 70:
            rate_bg = C_WARN_BG; rate_fg = C_WARN; tag = "良"
        else:
            rate_bg = C_BAD_BG; rate_fg = C_BAD; tag = "需关注"

        badge = "📌" if e["expert"] else ""
        rate_str = f"{rate:.1f}%" if rate is not None else "—"
        time_str = f"{e['avg_time']:.1f} 秒" if e["avg_time"] else "—"
        img_html = (
            f'<div style="width:100%;aspect-ratio:4/3;background:#fafafa;border-radius:10px 10px 0 0;overflow:hidden;display:flex;align-items:center;justify-content:center">'
            f'<img src="{e["preview_url"]}" style="width:100%;height:100%;object-fit:contain;display:block" loading="lazy" />'
            f'</div>'
            if e["preview_url"]
            else '<div style="width:100%;aspect-ratio:4/3;background:#fafafa;border-radius:10px 10px 0 0;display:flex;align-items:center;justify-content:center;color:#999;font-size:12px">无预览图</div>'
        )

        footer_html = '<div style="height:42px"></div>'
        if e["expert"]:
            ex = e["expert"]
            parts = []
            if ex.get("design"):
                parts.append(
                    f"<div style='margin-top:8px'>"
                    f"<div style='font-size:11px;font-weight:600;color:#1d4ed8;margin-bottom:2px'>📐 设计说明</div>"
                    f"<div style='font-size:12px;color:#374151;background:#eef5ff;border-left:3px solid #4C9BE8;padding:6px 8px;border-radius:4px;line-height:1.6'>{ex['design']}</div>"
                    f"</div>"
                )
            if ex.get("analysis"):
                parts.append(
                    f"<div style='margin-top:8px'>"
                    f"<div style='font-size:11px;font-weight:600;color:#b45309;margin-bottom:2px'>📊 重点分析</div>"
                    f"<div style='font-size:12px;color:#374151;background:#fff5e6;border-left:3px solid #E76F51;padding:6px 8px;border-radius:4px;line-height:1.6;white-space:pre-wrap'>{ex['analysis']}</div>"
                    f"</div>"
                )
            footer_html = (
                f"<details style='margin-top:10px;border-top:1px dashed #e5e7eb;padding-top:8px'>"
                f"<summary style='cursor:pointer;font-size:12px;color:#b45309;font-weight:600;list-style:none;user-select:none;padding:2px 0'>"
                f"📌 教学分析 <span style='float:right;color:#9ca3af;font-size:10px'>点击展开 ▾</span>"
                f"</summary>"
                f"{''.join(parts)}"
                f"</details>"
            )

        kn_safe = e["kn_name"] or "—"
        card_html = (
            f'<div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;margin-bottom:14px;box-shadow:0 1px 3px rgba(0,0,0,0.04);overflow:hidden;display:flex;flex-direction:column">'
            f'{img_html}'
            f'<div style="padding:10px 12px 10px 12px;display:flex;flex-direction:column;flex:1">'
            f'<div style="min-height:116px">'
            f'<div style="font-weight:600;font-size:14px;margin-bottom:6px">'
            f'{e["name"]} {badge}'
            f'<span style="float:right;font-size:11px;background:{rate_bg};color:{rate_fg};padding:1px 6px;border-radius:4px">{tag}</span>'
            f'</div>'
            f'<div style="display:flex;gap:14px;font-size:12px;color:#374151;margin-bottom:4px">'
            f'<div>正确率 <span style="background:{rate_bg};color:{rate_fg};padding:1px 6px;border-radius:4px;font-weight:600">{rate_str}</span></div>'
            f'<div>答题时长 <span style="color:#111;font-weight:600">{time_str}</span></div>'
            f'</div>'
            f'<div style="font-size:11px;color:#6b7280;margin-top:6px">知识点：{kn_safe}</div>'
            f'<div style="font-size:11px;color:#9ca3af;margin-top:2px">ID {e["qid"]}　·　{e["q_type"]}</div>'
            f'</div>'
            f'{footer_html}'
            f'</div>'
            f'</div>'
        )
        with cols[e["idx"] % 4]:
            st.markdown(card_html, unsafe_allow_html=True)

    # 📉 低数据题目分析（首次 3 星率 < 70%）
    low_items = [e for e in enriched if e["rate"] is not None and e["rate"] < 70]
    if low_items:
        st.divider()
        st.subheader(f"📉 低数据题目分析（首次 3 星率 < 70%，共 {len(low_items)} 题）")
        st.caption(
            "参考 Excel 阈值规则：70% 以下需关注；50–60% 可保留 1 道，多了影响体验；< 50% 建议修改。"
            "结合错因分布、答题时长与本周均值给出归因建议。"
        )

        def parse_wrong_options(raw_list):
            correct = None
            wrong = []
            for line in raw_list:
                if not isinstance(line, str):
                    continue
                line = line.strip()
                if line.startswith("正确答案"):
                    correct = line.split(":", 1)[1].strip() if ":" in line else line
                elif ":" in line:
                    opt, p = line.rsplit(":", 1)
                    wrong.append((opt.strip(), p.strip()))
            return correct, wrong

        for e in low_items:
            rate = e["rate"]
            if rate < 50:
                severity = "🔴 建议修改"; sev_bg = C_BAD_BG; sev_fg = C_BAD
            elif rate < 60:
                severity = "🟠 建议复盘"; sev_bg = "#fdebd8"; sev_fg = "#9a3412"
            else:
                severity = "🟡 需关注"; sev_bg = C_WARN_BG; sev_fg = C_WARN

            rate_str = f"{rate:.1f}%"
            time_str = f"{e['avg_time']:.1f} 秒" if e["avg_time"] else "—"

            correct, wrong = parse_wrong_options(e["wrong_raw"])
            wrong_rows = ""
            if correct:
                wrong_rows += (
                    f"<tr><td style='padding:3px 8px;color:#1f7a3a;font-weight:600'>✓ 正确答案</td>"
                    f"<td style='padding:3px 8px;color:#1f7a3a;font-weight:600'>{correct}</td>"
                    f"<td style='padding:3px 8px;color:#9ca3af;font-size:11px'>—</td></tr>"
                )
            for i, (opt, p) in enumerate(wrong[:5]):
                flag = "（主要错因）" if i == 0 else ""
                wrong_rows += (
                    f"<tr><td style='padding:3px 8px;color:#b42318'>✗ 错误选项</td>"
                    f"<td style='padding:3px 8px;color:#374151'>{opt}</td>"
                    f"<td style='padding:3px 8px;color:#b42318;font-weight:600'>{p} <span style='color:#9ca3af;font-size:11px;font-weight:400'>{flag}</span></td></tr>"
                )
            wrong_html = (
                f"<div style='margin-top:10px'>"
                f"<div style='font-size:12px;font-weight:600;color:#374151;margin-bottom:4px'>📊 错因分布</div>"
                f"<table style='font-size:12px;border-collapse:collapse;width:100%;background:#fff;border:1px solid #e5e7eb;border-radius:4px'>{wrong_rows}</table>"
                f"</div>"
            ) if wrong_rows else ""

            bullets = []
            if week_mean_rate is not None:
                delta = rate - week_mean_rate
                if delta <= -10:
                    bullets.append(f"明显低于本周均值（{week_mean_rate:.1f}%），落差 <b>{abs(delta):.1f}%</b>。")
                elif delta <= -5:
                    bullets.append(f"低于本周均值（{week_mean_rate:.1f}%）<b>{abs(delta):.1f}%</b>。")
            if e["avg_time"]:
                if e["avg_time"] >= 30:
                    bullets.append(f"答题时长 <b>{e['avg_time']:.1f} 秒</b> 明显偏长，可能题面信息量大或解题路径复杂。")
                elif e["avg_time"] >= 20:
                    bullets.append(f"答题时长 <b>{e['avg_time']:.1f} 秒</b> 偏长。")
            if wrong and len(wrong) > 0:
                try:
                    top_pct = float(wrong[0][1].rstrip("%"))
                    if top_pct >= 50:
                        bullets.append(f"主要错因集中在选项 <b>{wrong[0][0]}</b>（{wrong[0][1]}），是典型干扰项，建议教研复盘。")
                except (ValueError, AttributeError):
                    pass
            insight_inner = "".join(f"<li style='margin-bottom:2px'>{b}</li>" for b in bullets) or "<li>数据特征不显著，建议人工复看。</li>"
            insight_html = (
                f"<div style='margin-top:10px'>"
                f"<div style='font-size:12px;font-weight:600;color:#374151;margin-bottom:4px'>🔍 自动洞察</div>"
                f"<ul style='margin:0;padding-left:18px;font-size:12px;color:#374151;line-height:1.7'>{insight_inner}</ul>"
                f"</div>"
            )

            expert_block = ""
            if e["expert"]:
                ex = e["expert"]
                parts = []
                if ex.get("design"):
                    parts.append(
                        f"<div style='margin-top:6px'>"
                        f"<div style='font-size:11px;font-weight:600;color:#1d4ed8;margin-bottom:2px'>📐 设计说明</div>"
                        f"<div style='font-size:12px;color:#374151;background:#eef5ff;border-left:3px solid #4C9BE8;padding:6px 8px;border-radius:4px;line-height:1.6'>{ex['design']}</div>"
                        f"</div>"
                    )
                if ex.get("analysis"):
                    parts.append(
                        f"<div style='margin-top:6px'>"
                        f"<div style='font-size:11px;font-weight:600;color:#b45309;margin-bottom:2px'>📊 重点分析</div>"
                        f"<div style='font-size:12px;color:#374151;background:#fff5e6;border-left:3px solid #E76F51;padding:6px 8px;border-radius:4px;line-height:1.6;white-space:pre-wrap'>{ex['analysis']}</div>"
                        f"</div>"
                    )
                expert_block = (
                    f"<details style='margin-top:10px;border-top:1px dashed #e5e7eb;padding-top:8px' open>"
                    f"<summary style='cursor:pointer;font-size:12px;color:#b45309;font-weight:600;list-style:none;user-select:none'>"
                    f"📌 教研专家分析 <span style='float:right;color:#9ca3af;font-size:10px'>点击收起 ▴</span>"
                    f"</summary>"
                    f"{''.join(parts)}"
                    f"</details>"
                )

            ai_block = ""
            ai_data = get_ai_qa(e["qid"])
            if ai_data and ai_data.get("analysis"):
                ai_block = (
                    f"<details style='margin-top:10px;border-top:1px dashed {C_LINE};padding-top:8px' open>"
                    f"<summary style='cursor:pointer;font-size:12px;color:{C_AI};font-weight:600;list-style:none;user-select:none'>"
                    f"🤖 AI 教研分析（Claude Sonnet 4.6） <span style='float:right;color:{C_MUTED};font-size:10px'>点击收起 ▴</span>"
                    f"</summary>"
                    f"<div style='margin-top:6px;font-size:12px;color:#374151;background:{C_AI_BG};border-left:3px solid {C_AI};padding:8px 10px;border-radius:4px;line-height:1.7;white-space:pre-wrap'>{ai_data['analysis']}</div>"
                    f"<div style='margin-top:4px;font-size:10px;color:{C_MUTED};text-align:right'>生成于 {ai_data.get('generated_at', '—')}</div>"
                    f"</details>"
                )

            header_html = (
                f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>"
                f"<div style='font-weight:700;font-size:15px;color:#111'>{e['name']}</div>"
                f"<div style='background:{sev_bg};color:{sev_fg};padding:3px 10px;border-radius:4px;font-size:12px;font-weight:600'>{severity}</div>"
                f"</div>"
                f"<div style='display:flex;gap:18px;font-size:12px;color:#374151;flex-wrap:wrap;margin-bottom:4px'>"
                f"<div>正确率 <span style='background:{sev_bg};color:{sev_fg};padding:1px 6px;border-radius:4px;font-weight:600'>{rate_str}</span></div>"
                f"<div>答题时长 <span style='font-weight:600;color:#111'>{time_str}</span></div>"
                f"<div>知识点 <span style='font-weight:600;color:#111'>{e['kn_name'] or '—'}</span></div>"
                f"</div>"
                f"<div style='font-size:11px;color:#9ca3af;margin-bottom:6px'>ID {e['qid']}　·　{e['q_type']}</div>"
            )

            right_html = (
                f"<div style='padding:0 4px'>"
                f"{header_html}"
                f"{wrong_html}"
                f"{insight_html}"
                f"{ai_block}"
                f"{expert_block}"
                f"</div>"
            )

            outer = st.container(border=True)
            with outer:
                img_col, txt_col = st.columns([1, 3])
                with img_col:
                    if e["preview_url"]:
                        st.image(e["preview_url"], use_container_width=True)
                    else:
                        st.caption("无预览图")
                with txt_col:
                    st.markdown(right_html, unsafe_allow_html=True)


# ── 可视化组件（整周 / 周测 共用）──────────────────────────────────────────
def cmp_table_html(metrics, cur_stat, prev_stat, sel_label, prev_label, title):
    """本周 vs 上周 数据对比表。metrics=[(label, field, kind pct|min)]。"""
    def cell(field, kind):
        cur_v = pct_val(cur_stat.get(field))
        prev_v = pct_val(prev_stat.get(field))
        is_time = kind == "min"
        if is_time:
            cur_disp = f"{cur_v/60:.2f} 分钟" if cur_v else "—"
            prev_disp = f"{prev_v/60:.2f} 分钟" if prev_v else "—"
        else:
            cur_disp = f"{cur_v:.1f}%" if cur_v is not None else "—"
            prev_disp = f"{prev_v:.1f}%" if prev_v is not None else "—"
        if cur_v is not None and prev_v is not None:
            d = cur_v - prev_v
            if is_time:
                delta_disp = f"{d/60:+.2f} 分钟"
                color = C_BAD if d > 0 else (C_GOOD if d < 0 else C_NEUTRAL)
            else:
                delta_disp = f"{d:+.1f}%"
                color = C_GOOD if d > 0 else (C_BAD if d < 0 else C_NEUTRAL)
            arrow = "↑" if d > 0 else ("↓" if d < 0 else "→")
            delta_html = f"<span style='color:{color};font-weight:600'>{arrow} {delta_disp}</span>"
        else:
            delta_html = f"<span style='color:{C_MUTED}'>—</span>"
        return prev_disp, cur_disp, delta_html

    head_cells = "".join(
        f"<th style='text-align:center;padding:8px 10px;font-size:12px;color:{C_NEUTRAL};font-weight:600;border-bottom:2px solid {C_LINE}'>{label}</th>"
        for label, _, _ in metrics
    )
    prev_row = ""; cur_row = ""; delta_row = ""
    for label, field, kind in metrics:
        p, c, d = cell(field, kind)
        prev_row += f"<td style='text-align:center;padding:6px 10px;font-size:13px;color:{C_NEUTRAL}'>{p}</td>"
        cur_row += f"<td style='text-align:center;padding:6px 10px;font-size:15px;font-weight:700;color:{C_INK}'>{c}</td>"
        delta_row += f"<td style='text-align:center;padding:6px 10px;font-size:13px'>{d}</td>"
    return (
        f"<div style='border:1px solid {C_LINE};border-radius:8px;padding:12px 14px;background:#fff;height:100%;box-sizing:border-box'>"
        f"<div style='font-weight:700;font-size:14px;color:{C_INK};margin-bottom:10px'>{title}</div>"
        f"<div style='font-size:11px;color:{C_MUTED};margin-bottom:8px'>{sel_label} 本周　vs　{prev_label} 上周</div>"
        f"<table style='width:100%;border-collapse:collapse'>"
        f"<thead><tr><th style='text-align:left;padding:6px 6px;font-size:11px;color:{C_NEUTRAL};font-weight:600;border-bottom:2px solid {C_LINE}'></th>{head_cells}</tr></thead>"
        f"<tbody>"
        f"<tr><td style='text-align:left;padding:6px 6px;font-size:12px;color:{C_MUTED}'>上周</td>{prev_row}</tr>"
        f"<tr><td style='text-align:left;padding:6px 6px;font-size:12px;color:#374151;font-weight:600'>本周</td>{cur_row}</tr>"
        f"<tr style='border-top:1px dashed {C_LINE}'><td style='text-align:left;padding:6px 6px;font-size:12px;color:{C_MUTED}'>环比</td>{delta_row}</tr>"
        f"</tbody></table>"
        f"</div>"
    )


def ai_box_html(title, summary_text):
    """统一的 AI 分析框样式（全站一致：靛蓝强调色）。summary_text 为纯文本。"""
    if not summary_text:
        return None
    return (
        f"<div style='background:{C_AI_BG};border-left:4px solid {C_AI};padding:12px 16px;border-radius:6px;height:100%;box-sizing:border-box'>"
        f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>"
        f"<div style='font-weight:700;font-size:15px;color:{C_AI}'>{title}</div>"
        f"<div style='font-size:11px;color:{C_MUTED}'>Claude Sonnet 4.6</div>"
        f"</div>"
        f"<div style='font-size:13px;color:#374151;line-height:1.8;white-space:pre-wrap'>{summary_text}</div>"
        f"</div>"
    )


def ai_summary_html(summary_data, title, fg=None, bg=None, border=None):
    if not (summary_data and summary_data.get("summary")):
        return None
    return ai_box_html(title, summary_data["summary"]
    )


# 趋势型字段（按"每周变化"判健康）/ 均值型字段（按"全周期均值"判健康）
_TREND_FIELDS = {"attendanceRate", "completionRate", "classFinishRate",
                 "examAttendanceRate", "examCompletionRate", "examClassFinishRate"}
_MEAN_FIELDS = {"firstThreeStarPercentage", "retentionRate"}
_BASELINE_GRAY = "#9aa5b1"


def add_baseline_traces(fig, weeks_list, x_vals, fld, kind, getter):
    """在趋势图上叠加「常态」参考，口径与健康灯一致：
       趋势型 → 逐周「常态预期」虚线（= 上周实际值 + 全周期平均每周变化）；
                本周点在虚线上方 = 好于常态（降幅小于平均 / 逆势上升）。
       均值型 → 全周期均值线 + [均值-3%, 均值] 的 🟡 参考带。
       时长 / 其它 → 不加（不评级）。
    在添加真实折线之前调用，使参考线位于其下方。"""
    if kind == "min":
        return
    seq = [pct_val(getter(w).get(fld)) for w in weeks_list]
    if fld in _TREND_FIELDS:
        avg = wi.avg_weekly_delta(weeks_list, fld, getter)
        if avg is None:
            return
        # 逐周常态预期 = 上周实际 + 平均每周变化（缺口不外推，避免退化成首末连线）
        exp = [round(seq[i - 1] + avg, 2) if i >= 1 and seq[i - 1] is not None else None
               for i in range(len(seq))]
        if not any(v is not None for v in exp):
            return
        fig.add_trace(go.Scatter(
            x=x_vals, y=exp, mode="lines",
            line=dict(color=_BASELINE_GRAY, width=1.5, dash="dot"),
            connectgaps=False, name="常态预期", showlegend=False,
            hovertemplate="常态预期 %{y:.1f}（上周值+平均周变化）<extra></extra>"))
    elif fld in _MEAN_FIELDS:
        mean = wi.field_mean(weeks_list, fld, getter)
        if mean is None:
            return
        fig.add_hrect(y0=mean - 3, y1=mean, fillcolor=C_WARN, opacity=0.08, line_width=0)
        fig.add_hline(y=mean, line=dict(color=_BASELINE_GRAY, width=1.5, dash="dot"),
                      annotation_text=f"均值 {mean:.1f}", annotation_position="top left",
                      annotation_font=dict(size=10, color=C_NEUTRAL))


def _baseline_caption():
    st.caption("灰色虚线 = **常态预期**：趋势型 = 上周实际值 + 全周期平均每周变化，"
               "本周点在虚线**上方=好于常态**（降幅小于平均/逆势上升）；"
               "均值型为全周期均值线（浅黄带为 🟡 偏低区）。")


def render_trend_grid(metrics, weeks_list, sel_week_label, stat_getter, stage_name, palette):
    """每个指标一张趋势折线图，2 列网格，当前周高亮。"""
    df = pd.DataFrame([{
        "周次": w["week"],
        "课程名称": week_name_only(stage_name, w["week"]) or "—",
        "_stage": w.get("examType") == "EXAM",  # 阶段测点
        **{
            lbl: (round(pct_val(stat_getter(w).get(fld)) / 60, 2)
                  if kind == "min" and pct_val(stat_getter(w).get(fld)) is not None
                  else pct_val(stat_getter(w).get(fld)))
            for lbl, fld, kind in metrics
        },
    } for w in weeks_list])
    is_stage = list(df["_stage"])
    is_sel = [w == sel_week_label for w in df["周次"]]
    has_stage = any(is_stage)
    STAGE_COLOR = "#475569"  # 中性石板色：标记阶段测，避免与“红=差”的状态语义混淆
    grid = st.columns(2)
    for i, (lbl, fld, kind) in enumerate(metrics):
        color = palette[i % len(palette)]
        unit = "分钟" if kind == "min" else "%"
        symbols = ["diamond" if s else ("circle-open" if sel else "circle")
                   for s, sel in zip(is_stage, is_sel)]
        sizes = [13 if s else (10 if sel else 5) for s, sel in zip(is_stage, is_sel)]
        mcolors = [STAGE_COLOR if s else color for s in is_stage]
        lwidths = [2 if (s or sel) else 0 for s, sel in zip(is_stage, is_sel)]
        kinds = ["阶段测" if s else "周测" for s in is_stage]
        fig = go.Figure()
        add_baseline_traces(fig, weeks_list, list(df["周次"]), fld, kind, stat_getter)
        fig.add_trace(go.Scatter(
            x=df["周次"], y=df[lbl],
            mode="lines+markers", line=dict(color=color, width=2),
            marker=dict(size=sizes, symbol=symbols, color=mcolors,
                        line=dict(width=lwidths, color=mcolors)),
            customdata=list(zip(df["课程名称"], kinds)),
            hovertemplate=f"<b>%{{x}} · %{{customdata[0]}}</b>（%{{customdata[1]}}）<br>{lbl}: %{{y}} {unit}<extra></extra>",
        ))
        fig.update_layout(title=f"{lbl}趋势", xaxis_title="周次", yaxis_title=f"{lbl}（{unit}）",
                          hovermode="closest", height=280, margin=dict(t=40, b=30))
        with grid[i % 2]:
            st.plotly_chart(fig, use_container_width=True)
    _baseline_caption()
    if has_stage:
        st.caption("◆ 深灰菱形为**阶段测**（W12/24/36/48，难度与普通周测不同，仅作区分标记，非好坏判定）。")


def render_full_period_table(metrics, weeks_list, stat_getter, stage_name, extra_cols=None):
    """全周期数据表：每周一行，率列色阶 + 均值行。extra_cols=[(列名, field, 'int'|'min')]。"""
    extra_cols = extra_cols or []
    def col_name(label, kind):
        return f"{label}（分钟）" if kind == "min" else f"{label} (%)"
    rows = []
    for w in weeks_list:
        s = stat_getter(w)
        row = {"周次": w["week"], "课程名称": week_name_only(stage_name, w["week"]) or "—"}
        for label, field, kind in metrics:
            v = pct_val(s.get(field))
            row[col_name(label, kind)] = (None if v is None else (round(v/60, 2) if kind == "min" else round(v, 1)))
        for cname, field, typ in extra_cols:
            v = s.get(field)
            try:
                row[cname] = float(v) if v is not None else None
            except (TypeError, ValueError):
                row[cname] = None
        rows.append(row)
    df = pd.DataFrame(rows)
    numeric_cols = [c for c in df.columns if c not in {"周次", "课程名称"}]
    mean_row = {"周次": "均值", "课程名称": "—"}
    for c in numeric_cols:
        vals = df[c].dropna()
        mean_row[c] = round(vals.mean(), 2) if len(vals) else None
    df = pd.concat([df, pd.DataFrame([mean_row])], ignore_index=True)
    pct_cols = [col_name(l, k) for l, _, k in metrics if k == "pct"]
    fmt = {}
    for l, _, k in metrics:
        fmt[col_name(l, k)] = "{:.2f}" if k == "min" else "{:.1f}"
    for cname, _, typ in extra_cols:
        fmt[cname] = "{:,.0f}" if typ == "int" else "{:.2f}"
    style_heatmap(df, pct_cols, fmt, height=min(600, 40 * len(df) + 40))


def _day_code(label):
    """从 'D1 基础路线推演' 提取 'D1'。"""
    import re as _re
    m = _re.match(r"\s*(D\d+)", label or "")
    return m.group(1) if m else (label or "")


def course_compare_table_html(day_entries, prev_week):
    """各节课（D1-D4）课程指标表：每格大字为本周值，下方小字为对比上周
    【同节次】（D1↔D1…）的环比，与邮件口径一致。"""
    prev_days = {}
    for pdd in (prev_week or {}).get("days") or []:
        prev_days[_day_code(pdd.get("label"))] = pdd.get("stat") or {}

    def fmt(v, kind):
        if v is None:
            return "—"
        return f"{v/60:.1f} 分钟" if kind == "min" else f"{v:.1f}%"

    def cell(s, ps, fld, kind):
        cur, prev = pct_val(s.get(fld)), pct_val(ps.get(fld))
        disp = fmt(cur, kind)
        valcolor = C_INK if cur is not None else C_MUTED
        if cur is None or prev is None or abs(cur - prev) < 1e-9:
            sub = f"<div style='font-size:11px;color:{C_MUTED};margin-top:2px'>—</div>"
        else:
            d = cur - prev
            good = (d > 0) if kind != "min" else (d < 0)
            color = C_GOOD if good else C_BAD
            arrow = "↑" if d > 0 else "↓"
            dv = f"{d/60:+.1f} 分钟" if kind == "min" else f"{d:+.1f}%"
            sub = f"<div style='font-size:11px;color:{color};margin-top:2px'>{arrow} {dv}</div>"
        return (f"<div style='font-size:14px;font-weight:700;color:{valcolor}'>{disp}</div>"
                f"{sub}")

    td = f"padding:8px 12px;border:1px solid {C_LINE};text-align:center"
    head = (f"<th style='{td};background:#f8fafc;color:#475569;font-size:13px'>节次</th>"
            + "".join(f"<th style='{td};background:#f8fafc;color:#475569;font-size:13px'>{l}</th>"
                      for l, _, _ in COURSE_METRICS))
    body = ""
    for d in day_entries:
        s = d.get("stat") or {}
        ps = prev_days.get(_day_code(d.get("label")), {})
        cells = "".join(f"<td style='{td}'>{cell(s, ps, fld, kind)}</td>"
                        for _, fld, kind in COURSE_METRICS)
        body += (f"<tr><td style='{td};text-align:left'><b>{d.get('label', '')}</b></td>"
                 f"{cells}</tr>")
    return (f"<table style='border-collapse:collapse;background:#fff'>"
            f"<tr>{head}</tr>{body}</table>")


def render_episode_trend_grid(metrics, weeks_list, sel_week_label, stage_name, palette):
    """系统课各指标趋势：把每周 D1-D4 连成一条折线（锯齿形），当前周高亮。
    x 轴按 周次→D1..D4 顺序排列，呈现整段趋势。"""
    xs, week_of_point, course_of_point, day_of_point = [], [], [], []
    per_metric = {fld: [] for _, fld, _ in metrics}
    for w in weeks_list:
        cname = week_name_only(stage_name, w["week"]) or "—"
        for d in get_day_entries(w):
            code = _day_code(d.get("label"))
            xs.append(f"{w['week']}·{code}")
            week_of_point.append(w["week"])
            course_of_point.append(cname)
            day_of_point.append(d.get("label") or code)
            s = d.get("stat") or {}
            for _, fld, kind in metrics:
                v = pct_val(s.get(fld))
                per_metric[fld].append(round(v / 60, 2) if (kind == "min" and v is not None) else v)
    if not xs:
        st.info("暂无可绘制的系统课趋势数据。")
        return
    grid = st.columns(2)
    for i, (lbl, fld, kind) in enumerate(metrics):
        color = palette[i % len(palette)]
        unit = "分钟" if kind == "min" else "%"
        y = per_metric[fld]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=xs, y=y, mode="lines+markers",
            line=dict(color=color, width=1.6), connectgaps=True,
            marker=dict(
                size=[9 if wk == sel_week_label else 4 for wk in week_of_point],
                symbol=["circle-open" if wk == sel_week_label else "circle" for wk in week_of_point],
                line=dict(width=[2 if wk == sel_week_label else 0 for wk in week_of_point], color=color),
                color=color,
            ),
            customdata=list(zip(course_of_point, day_of_point)),
            hovertemplate=f"<b>%{{customdata[0]}} · %{{customdata[1]}}</b><br>{lbl}: %{{y}} {unit}<extra></extra>",
        ))
        fig.update_layout(
            title=f"{lbl}趋势（每周 D1-D4）", yaxis_title=f"{lbl}（{unit}）",
            hovermode="closest", height=300, margin=dict(t=40, b=60),
            xaxis=dict(title="周次 · 课节", tickangle=-90, tickfont=dict(size=8)),
        )
        with grid[i % 2]:
            st.plotly_chart(fig, use_container_width=True)


PALETTE = ["#4C9BE8", "#2A9D8F", "#8E7CC3", "#E9C46A", "#F4A261", "#E76F51"]

# 周测可视化口径（4 指标）
EXAM_VIZ_METRICS = [
    ("参与率", "examAttendanceRate", "pct"),
    ("参与完成率", "examClassFinishRate", "pct"),
    ("首次 3 星率", "firstThreeStarPercentage", "pct"),
    ("完成时长", "completeTime", "min"),
]


# ── 顶部标题区 ────────────────────────────────────────────────────────────
stage_names = [s["stage"] for s in stages]
col_title, col_stage = st.columns([3, 1])
with col_stage:
    sel_stage_name = st.selectbox("级别", stage_names, key="global_stage")

sel_stage = next(s for s in stages if s["stage"] == sel_stage_name)


def _week_has_data(w):
    """该周是否已上线、有数据（整周或周测任一有指标即视为已上线）。"""
    if any(get_week_stat(w).get(f[1]) is not None for f in COURSE_METRICS):
        return True
    s = get_stat(w)
    return any(s.get(f[1]) is not None for f in EXAM_VIZ_METRICS)


# 只展示已上线、有数据的周次（未上线的未来周次全是空数据，直接过滤掉）
all_weeks = sel_stage.get("weeks", [])
weeks = [w for w in all_weeks if _week_has_data(w)]
n_weeks = len(weeks)

st.title(f"思维课程数据看板 — {sel_stage_name}")
if weeks:
    st.caption(
        f"已上线 {weeks[0]['week']}–{weeks[-1]['week']} 共 {n_weeks} 周"
        f"（未上线周次暂不展示）　　数据更新：{fetched_at}"
    )
else:
    st.caption(f"数据更新：{fetched_at}")

if not weeks:
    st.warning(f"{sel_stage_name} 暂无已上线的周次数据。")
    st.stop()

# 周次显示名（带课程名）与短名（仅 W 编号）的双向映射
week_short_list = [w["week"] for w in weeks]
week_full_list = [week_full(sel_stage_name, w) for w in week_short_list]
full_to_short = dict(zip(week_full_list, week_short_list))

# 全局周次选择（三个模块联动；默认最新一周）
sel_week_full = st.selectbox("📆 选择周次（三个模块联动）", week_full_list, index=len(week_full_list)-1, key="global_week")
sel_week_label = full_to_short[sel_week_full]
sel_idx = next(i for i, w in enumerate(weeks) if w["week"] == sel_week_label)
sel_week = weeks[sel_idx]
prev_week = weeks[sel_idx - 1] if sel_idx > 0 else None
prev_label_full = week_full(sel_stage_name, prev_week["week"]) if prev_week else "—"
stat = get_stat(sel_week)
prev_stat = get_stat(prev_week) if prev_week else {}
wk = get_week_stat(sel_week)
prev_wk = get_week_stat(prev_week) if prev_week else {}
cur_course_name = week_name_only(sel_stage_name, sel_week_label)
exam_label = "阶段测" if sel_week.get("examType") == "EXAM" else "周测"

# ══════════════════════════════════════════════════════════════════════════
# 置顶 — 本周关键结论（看板视角：一屏看清最新一周状态 + 根因 + 建议）
# ══════════════════════════════════════════════════════════════════════════
insights = wi.compute_insights(weeks, sel_week, prev_week, exam_label)

st.markdown(f"## 🎯 本周关键结论 · {sel_week_label}" + (f" · {cur_course_name}" if cur_course_name else ""))
if exam_label == "阶段测":
    st.caption("📌 本周为**阶段测**（W12/24/36/48），下列测评指标为阶段测成绩。")

LIGHT_COLOR = {"🟢": C_GOOD, "🟡": C_WARN, "🔴": C_BAD, "⚪": C_NEUTRAL}


def _kpi_cards_html(title, items):
    """统一卡片网格：固定宽度、左对齐、语义色圆点 + 大数值 + 环比。"""
    if not items:
        return ""
    cards = ""
    for k in items:
        dot = LIGHT_COLOR.get(k["light"], C_NEUTRAL)
        val = k["value_str"]
        val_color = C_INK if val != "—" else C_MUTED
        ds = k["delta_str"]
        if ds:
            neg = ds.strip().startswith("-")
            arrow = "↓" if neg else "↑"
            if k["mode"] == "none":          # 不评级指标：环比只示意方向，不判好坏
                dcolor = C_NEUTRAL
            elif k["kind"] == "min":         # 时长：增加视为负向
                dcolor = C_GOOD if neg else C_BAD
            else:                             # 率：上升为正向
                dcolor = C_BAD if neg else C_GOOD
            delta_html = f"<div style='font-size:12px;font-weight:600;color:{dcolor};margin-top:3px'>{arrow} {ds}</div>"
        else:
            delta_html = f"<div style='font-size:12px;color:{C_MUTED};margin-top:3px'>—</div>"
        cards += (
            f"<div style='flex:0 0 154px;border:1px solid {C_LINE};border-radius:10px;"
            f"padding:11px 13px;background:#fff'>"
            f"<div style='font-size:12px;color:{C_NEUTRAL};display:flex;align-items:center;gap:6px;white-space:nowrap'>"
            f"<span style='width:8px;height:8px;border-radius:50%;background:{dot};display:inline-block;flex:0 0 8px'></span>"
            f"{k['name']}</div>"
            f"<div style='font-size:23px;font-weight:700;color:{val_color};margin-top:6px;line-height:1.1'>{val}</div>"
            f"{delta_html}</div>"
        )
    return (
        f"<div style='background:#fafbfc;border:1px solid {C_LINE};border-radius:12px;"
        f"padding:10px 12px 12px;margin-bottom:10px'>"
        f"<div style='margin:0 0 8px;font-size:13px;font-weight:700;color:{C_INK}'>{title}</div>"
        f"<div style='display:flex;flex-wrap:wrap;gap:10px'>{cards}</div>"
        f"</div>"
    )


# 课程指标 / 周测指标分组展示（src: week=整周课程, exam=周测）
_course_kpis = [k for k in insights["kpis"] if k["src"] == "week"]
_exam_kpis = [k for k in insights["kpis"] if k["src"] == "exam"]
st.markdown(
    _kpi_cards_html("📚 整周课程", _course_kpis) + _kpi_cards_html(f"📝 {exam_label}", _exam_kpis),
    unsafe_allow_html=True,
)

with st.expander("ℹ️ 健康灯基准逻辑"):
    st.markdown(
        "- **整周到课/完课/到课完课率、周测参与/完成/参与完成率**（基准 = 全周期「平均每周变化」）："
        "这类指标随学期自然下滑，因此不看绝对值，只看**本周降幅是否好于常态**。\n"
        "  - 🟢 本周环比 **≥** 平均每周变化（降得比平时少、或逆势上升）\n"
        "  - 🟡 本周环比 **<** 平均每周变化（降得比平时多）\n"
        "- **首次 3 星率**（基准 = 全周期均值）：🟢 ≥ 均值　🟡 低于均值 3% 内　🔴 低于均值 3% 以上\n"
        "- **完成时长**：⚪ 不评级\n"
        "- **连续异常升级**：到课率/完课率/参与率若**连续 2 周及以上**差于常态，🟡 自动升级为 🔴（持续下滑比单周波动更值得介入）。\n"
        "- 卡片下方箭头为**环比上周**（↑ 升 / ↓ 降）。\n"
        "- **关于配色**：红/黄/绿**只用于健康状态**（差/警示/好）。下方深度分析表格的**青蓝底色深浅**仅表示"
        "「该指标在各周中的相对高低」，**不代表好坏**，请勿与健康灯混淆。"
    )

def _concern_card_html(c):
    """结构化需关注卡：指标名 + 环比badge + 常态基准 + 根因 + 建议，扫读更快。"""
    name = c.get("name")
    if not name:  # 无结构化字段（如“低分题”汇总）→ 退回纯文本
        adv = (f"<div style='margin-top:4px;font-size:12px;color:{C_WARN}'>💡 {c['advice']}</div>"
               if c.get("advice") else "")
        return (f"<div style='border:1px solid {C_LINE};border-left:3px solid {C_WARN};border-radius:8px;"
                f"padding:8px 11px;margin-bottom:8px;background:#fff'>"
                f"<div style='font-size:13px;color:#374151'>{c['text']}</div>{adv}</div>")
    escalate = c.get("escalate")
    accent = C_BAD if escalate else C_WARN
    tag = (f"<span style='font-size:11px;font-weight:700;color:#fff;background:{C_BAD};"
           f"border-radius:4px;padding:1px 6px;margin-left:6px'>连续{c.get('streak')}周</span>"
           if escalate else "")
    delta_badge = (f"<span style='font-size:12px;font-weight:700;color:{C_BAD};"
                   f"background:{C_BAD_BG};border-radius:5px;padding:1px 7px'>↓ {c.get('delta_str','')}</span>")
    attr = (f"<div style='margin-top:3px;color:{C_NEUTRAL};font-size:12px'>· {c['attr']}</div>"
            if c.get("attr") else "")
    adv = (f"<div style='margin-top:5px;font-size:12px;color:{C_WARN}'>💡 {c['advice']}</div>"
           if c.get("advice") else "")
    return (
        f"<div style='border:1px solid {C_LINE};border-left:3px solid {accent};border-radius:8px;"
        f"padding:8px 11px;margin-bottom:8px;background:#fff'>"
        f"<div style='display:flex;align-items:center;gap:8px;flex-wrap:wrap'>"
        f"<b style='font-size:13px;color:{C_INK}'>{name}</b>{delta_badge}{tag}"
        f"<span style='font-size:11px;color:{C_MUTED}'>{c.get('baseline_str','')}</span></div>"
        f"{attr}{adv}</div>"
    )


# 需关注（含根因 + 建议）/ 本周亮点
_cc, _ch = st.columns(2)
with _cc:
    st.markdown("**⚠️ 需关注**")
    if insights["concerns"]:
        st.markdown("".join(_concern_card_html(c) for c in insights["concerns"][:4]),
                    unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='color:{C_GOOD}'>✅ 暂无明显异常，核心指标平稳</div>",
                    unsafe_allow_html=True)
with _ch:
    st.markdown("**✅ 本周亮点**")
    if insights["highlights"]:
        for h in insights["highlights"][:4]:
            st.markdown(f"- {h['text']}")
    else:
        st.markdown("- 本周各指标较上周无显著提升")

# 🔬 本周诊断详情（课节异常 / Top低分题 / 薄弱知识点）—— 收进 expander，保持第一屏清爽
_lq, _wk = insights["top_low_questions"], insights["weak_knowledge"]
with st.expander("🔬 本周诊断详情（课节异常 · Top低分题 · 薄弱知识点）"):
    if insights["day_anomalies"]:
        st.markdown("**🔎 课节异常**　<span style='color:%s;font-size:12px'>D1-D4 环比骤降 ≥5%%</span>" % C_MUTED,
                    unsafe_allow_html=True)
        badges = "".join(
            f"<span style='display:inline-block;margin:2px 8px 6px 0;padding:3px 10px;"
            f"background:{C_BAD_BG};color:{C_BAD};border-radius:12px;font-size:12px;font-weight:600'>{a['text']}</span>"
            for a in insights["day_anomalies"]
        )
        st.markdown(badges, unsafe_allow_html=True)
    else:
        st.caption("✅ 课节层级未发现环比骤降 ≥5% 的异常。")

    _q1, _q2 = st.columns(2)
    with _q1:
        st.markdown(f"**📉 Top 低分题**　<span style='color:{C_MUTED};font-size:12px'>{exam_label}，首次 3 星率 &lt;70%</span>",
                    unsafe_allow_html=True)
        if _lq:
            for q in _lq:
                st.markdown(f"- {q['label']}　<b style='color:{C_BAD}'>{q['rate']:.1f}%</b>", unsafe_allow_html=True)
            st.caption("完整逐题分析见下方「周测数据 → 逐题分析」。")
        else:
            st.markdown("- 本周无低分题 ✅")
    with _q2:
        st.markdown(f"**🧩 相对薄弱知识点**　<span style='color:{C_MUTED};font-size:12px'>首次 3 星率最低 3 个</span>",
                    unsafe_allow_html=True)
        if _wk:
            for k in _wk:
                st.markdown(f"- {k['name']}　<b style='color:{C_WARN}'>{k['rate']:.1f}%</b>　<span style='color:{C_MUTED}'>(n={k['n']})</span>",
                            unsafe_allow_html=True)
        else:
            st.markdown("- 暂无知识点数据")

# AI 整周综合速读（默认收起，保持第一屏聚焦在结论）
_ai = (OVERALL_SUMMARY.get(sel_stage_name) or {}).get(sel_week_label)
if _ai and _ai.get("summary"):
    with st.expander("🤖 AI 速读 · 整周综合（D1-4 课程 + 周测）", expanded=False):
        st.markdown(ai_box_html("🤖 整周综合速读", _ai["summary"]), unsafe_allow_html=True)
elif OVERALL_SUMMARY:
    st.caption("💡 本周整周综合 AI 速读待生成，可运行 `./venv/bin/python generate_weekly_summary.py`。")

st.divider()
st.markdown("#### 📊 深度分析")
tabs = st.tabs(["📅 整周数据", "📚 D1-4课程数据", "📝 周测数据"])

# ══════════════════════════════════════════════════════════════════════════
# 模块一 — 整周数据（整周聚合口径）
# ══════════════════════════════════════════════════════════════════════════
with tabs[0]:
    st.markdown("#### 一、整体情况")
    if cur_course_name:
        st.caption(f"📖 当前周课程：**{sel_week_label} · {cur_course_name}**")
    if wk.get("_source") == "aggregate":
        st.caption("⚠️ 该周无官方整周数据，下列为 D1-D4 估算（率取均值、时长累计）。")
    elif wk:
        st.caption("Z 站官方整周口径（计算维度：当周/按时）。")
    if any(wk.get(f[1]) is not None for f in COURSE_METRICS):
        wcols = st.columns(6)
        for col, (label, field, kind) in zip(wcols, COURSE_METRICS):
            with col:
                st.metric(
                    label,
                    fmt_metric(wk.get(field), kind),
                    delta=metric_delta_str(wk.get(field), prev_wk.get(field), kind),
                    delta_color="inverse" if kind == "min" else "normal",
                )
    else:
        st.info("本周暂无系统课（D1-D4）数据，可能该周还未开课。")

    # ── 整周：本周 vs 上周 数据对比 + AI 整体分析 ──────────────────────────
    has_wk_cur = any(wk.get(f[1]) is not None for f in COURSE_METRICS)
    if sel_idx == 0:
        if has_wk_cur:
            st.info("ℹ️ 本周是该学期第一周，整周数据无上周可对比。")
    elif has_wk_cur and any(prev_wk.get(f[1]) is not None for f in COURSE_METRICS):
        prev_label_short = prev_week["week"]
        prev_course = week_name_only(sel_stage_name, prev_label_short)
        prev_label = f"{prev_label_short} · {prev_course}" if prev_course else prev_label_short

        def wk_cmp_cell(field, kind):
            cur_v = pct_val(wk.get(field))
            prev_v = pct_val(prev_wk.get(field))
            is_time = kind == "min"
            if is_time:
                cur_disp = f"{cur_v/60:.2f} 分钟" if cur_v else "—"
                prev_disp = f"{prev_v/60:.2f} 分钟" if prev_v else "—"
            else:
                cur_disp = f"{cur_v:.1f}%" if cur_v is not None else "—"
                prev_disp = f"{prev_v:.1f}%" if prev_v is not None else "—"
            if cur_v is not None and prev_v is not None:
                d = cur_v - prev_v
                if is_time:
                    delta_disp = f"{d/60:+.2f} 分钟"
                    color = "#b42318" if d > 0 else ("#1f7a3a" if d < 0 else "#6b7280")
                else:
                    delta_disp = f"{d:+.1f}%"
                    color = "#1f7a3a" if d > 0 else ("#b42318" if d < 0 else "#6b7280")
                arrow = "↑" if d > 0 else ("↓" if d < 0 else "→")
                delta_html = f"<span style='color:{color};font-weight:600'>{arrow} {delta_disp}</span>"
            else:
                delta_html = "<span style='color:#9ca3af'>—</span>"
            return prev_disp, cur_disp, delta_html

        head_cells = "".join(
            f"<th style='text-align:center;padding:8px 10px;font-size:12px;color:#6b7280;font-weight:600;border-bottom:2px solid #e5e7eb'>{label}</th>"
            for label, _, _ in COURSE_METRICS
        )
        prev_row = ""; cur_row = ""; delta_row = ""
        for label, field, kind in COURSE_METRICS:
            p, c, d = wk_cmp_cell(field, kind)
            prev_row += f"<td style='text-align:center;padding:6px 10px;font-size:13px;color:#6b7280'>{p}</td>"
            cur_row += f"<td style='text-align:center;padding:6px 10px;font-size:15px;font-weight:700;color:#111'>{c}</td>"
            delta_row += f"<td style='text-align:center;padding:6px 10px;font-size:13px'>{d}</td>"
        wk_cmp_html = (
            f"<div style='border:1px solid #e5e7eb;border-radius:8px;padding:12px 14px;background:#fff;height:100%;box-sizing:border-box'>"
            f"<div style='font-weight:700;font-size:14px;color:#111;margin-bottom:10px'>📊 整周数据对比</div>"
            f"<div style='font-size:11px;color:#9ca3af;margin-bottom:8px'>{sel_week_label} 本周　vs　{prev_label} 上周</div>"
            f"<table style='width:100%;border-collapse:collapse'>"
            f"<thead><tr><th style='text-align:left;padding:6px 6px;font-size:11px;color:#6b7280;font-weight:600;border-bottom:2px solid #e5e7eb'></th>{head_cells}</tr></thead>"
            f"<tbody>"
            f"<tr><td style='text-align:left;padding:6px 6px;font-size:12px;color:#9ca3af'>上周</td>{prev_row}</tr>"
            f"<tr><td style='text-align:left;padding:6px 6px;font-size:12px;color:#374151;font-weight:600'>本周</td>{cur_row}</tr>"
            f"<tr style='border-top:1px dashed #e5e7eb'><td style='text-align:left;padding:6px 6px;font-size:12px;color:#9ca3af'>环比</td>{delta_row}</tr>"
            f"</tbody></table>"
            f"</div>"
        )

        wk_summary = (COURSE_SUMMARY.get(sel_stage_name) or {}).get(sel_week_label)
        wk_summary_html = ai_box_html("🤖 整周 AI 分析（D1-D4 系统课）",
                                      wk_summary.get("summary") if wk_summary else None)

        col_c, col_a = st.columns([6, 6], gap="medium")
        with col_c:
            st.markdown(wk_cmp_html, unsafe_allow_html=True)
        with col_a:
            if wk_summary_html:
                st.markdown(wk_summary_html, unsafe_allow_html=True)
            else:
                st.caption("💡 该周整周 AI 分析待生成，可运行 `./venv/bin/python generate_weekly_summary.py` 更新。")

    st.divider()
    st.markdown("#### 二、细节情况")
    if any(get_week_stat(w).get(f[1]) is not None for w in weeks for f in COURSE_METRICS):
        st.markdown("**📈 各指标趋势**")
        df_course = pd.DataFrame([{
            "周次": w["week"],
            "课程名称": week_name_only(sel_stage_name, w["week"]) or "—",
            **{
                lbl: (round(pct_val(get_week_stat(w).get(fld)) / 60, 2)
                      if kind == "min" and pct_val(get_week_stat(w).get(fld)) is not None
                      else pct_val(get_week_stat(w).get(fld)))
                for lbl, fld, kind in COURSE_METRICS
            },
        } for w in weeks])
        palette = ["#4C9BE8", "#2A9D8F", "#8E7CC3", "#E9C46A", "#F4A261", "#E76F51"]
        grid = st.columns(2)
        for i, (lbl, fld, kind) in enumerate(COURSE_METRICS):
            color = palette[i % len(palette)]
            unit = "分钟" if kind == "min" else "%"
            fig = go.Figure()
            add_baseline_traces(fig, weeks, list(df_course["周次"]), fld, kind, get_week_stat)
            fig.add_trace(go.Scatter(
                x=df_course["周次"], y=df_course[lbl],
                mode="lines+markers", line=dict(color=color, width=2),
                marker=dict(
                    size=[10 if w == sel_week_label else 5 for w in df_course["周次"]],
                    symbol=["circle-open" if w == sel_week_label else "circle" for w in df_course["周次"]],
                    color=color,
                ),
                customdata=df_course["课程名称"],
                hovertemplate=f"<b>%{{x}} · %{{customdata}}</b><br>{lbl}: %{{y}} {unit}<extra></extra>",
            ))
            fig.update_layout(title=f"{lbl}趋势", xaxis_title="周次", yaxis_title=f"{lbl}（{unit}）",
                              hovermode="closest", height=260, margin=dict(t=40, b=30))
            with grid[i % 2]:
                st.plotly_chart(fig, use_container_width=True)
        _baseline_caption()
        st.markdown("**📋 全周期整周数据**")
        render_full_period_table(COURSE_METRICS, weeks, get_week_stat, sel_stage_name)
    else:
        st.info("暂无整周趋势数据。")

# ══════════════════════════════════════════════════════════════════════════
# 模块二 — 系统课题目数据（D1-D4）
# ══════════════════════════════════════════════════════════════════════════
with tabs[1]:
    day_entries = get_day_entries(sel_week)
    if day_entries:
        # ───────────────────────── 板块一：课程数据 ─────────────────────────
        st.markdown("### 📗 课程数据")
        st.markdown("**一、各节课课程指标（到课 / 完课 / 正确率等）**")
        st.markdown(course_compare_table_html(day_entries, prev_week), unsafe_allow_html=True)
        st.caption("每格下方小字为对比上周同节次（D1↔D1…）环比；课程内容逐周不同，仅供趋势参考。")

        st.markdown("**二、各指标趋势（全周期 · 每周 D1-D4 连线）**")
        st.caption("每周由 D1 到 D4 连成一段，整体呈现各指标随周次/课节的变化趋势；当前周用空心大点高亮。")
        render_episode_trend_grid(COURSE_METRICS, weeks, sel_week_label, sel_stage_name, PALETTE)

        st.divider()
        # ───────────────────────── 板块二：题目数据 ─────────────────────────
        st.markdown("### 📕 题目数据")
        st.markdown("**一、各节课题目概览**")
        _ov = []
        for _d in day_entries:
            _qs = _d.get("questions") or []
            _rates = [pct_val(q.get("firstThreeStarPercentage")) for q in _qs]
            _rates = [r for r in _rates if r is not None]
            _ov.append({
                "节次": _d["label"],
                "题目数": len(_qs),
                # 与「课程数据」表口径一致：用节课整体首次3星率（_d["stat"]），而非题目平均
                "首次 3 星率 (%)": pct_val((_d.get("stat") or {}).get("firstThreeStarPercentage")),
                "低分题数 (<70%)": sum(1 for r in _rates if r < 70),
            })
        _df_ov = pd.DataFrame(_ov)
        style_heatmap(_df_ov, ["首次 3 星率 (%)"],
                      {"首次 3 星率 (%)": "{:.1f}", "题目数": "{:.0f}", "低分题数 (<70%)": "{:.0f}"})

        st.markdown("**二、逐题分析**")
        _day_labels = [d.get("label") or f"D{i+1}" for i, d in enumerate(day_entries)]
        _sel_day = st.selectbox("选择课节（D1-D4）", _day_labels, key="sc_day")
        _dsel = day_entries[_day_labels.index(_sel_day)]
        render_question_analysis(
            _dsel.get("questions") or [],
            _dsel.get("chapters") or [],
            f"{sel_week_label} {_sel_day}",
            sel_stage_name,
            f"{week_full(sel_stage_name, sel_week_label)} · {_sel_day}",
        )
    else:
        st.info("本周暂无 D1-D4 系统课数据，可能该周还未开课。")

# ══════════════════════════════════════════════════════════════════════════
# 模块三 — 周测数据（D5 每周挑战）
# ══════════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.markdown("#### 一、整体情况")
    if cur_course_name:
        st.caption(f"📖 当前周课程：**{sel_week_label} · {cur_course_name}**")
    if sel_week.get("examType") == "EXAM":
        st.info("📌 本周为**阶段测**（每 12 周一次：W12 / W24 / W36 / W48），下列数据为阶段测成绩。")

    metrics = [
        ("参与率", "examAttendanceRate"),
        ("参与完成率", "examClassFinishRate"),
        ("首次 3 星率", "firstThreeStarPercentage"),
        ("完成时长", "completeTime"),
    ]

    cols = st.columns(4)
    for col, (label, field) in zip(cols, metrics):
        cur = pct_val(stat.get(field))
        prev_val = pct_val(prev_stat.get(field)) if prev_stat else None
        delta = round(cur - prev_val, 1) if cur is not None and prev_val is not None else None
        is_time = field == "completeTime"

        with col:
            cur_str = (sec_to_min(cur) if cur else "—") if is_time else (f"{cur:.1f}%" if cur is not None else "—")
            if delta is not None:
                delta_str = f"{delta/60:+.2f} 分钟 环比" if is_time else f"{delta:+.1f}% 环比"
            else:
                delta_str = None
            st.metric(label, cur_str, delta=delta_str,
                      delta_color="inverse" if is_time else "normal")

    # ── 本周 vs 上周：数据对比 + AI 整体分析（两部分） ──────────────────────
    if sel_idx == 0:
        st.info("ℹ️ 本周是该学期第一周，无上周数据可对比。")
    elif prev_week is not None:
        prev_label_short = prev_week["week"]
        prev_course = week_name_only(sel_stage_name, prev_label_short)
        prev_label = f"{prev_label_short} · {prev_course}" if prev_course else prev_label_short

        # ① 数据对比表
        def cmp_cell(field, is_time=False):
            cur_v = pct_val(stat.get(field))
            prev_v = pct_val(prev_stat.get(field))
            if is_time:
                cur_disp = f"{cur_v/60:.2f} 分钟" if cur_v else "—"
                prev_disp = f"{prev_v/60:.2f} 分钟" if prev_v else "—"
            else:
                cur_disp = f"{cur_v:.1f}%" if cur_v is not None else "—"
                prev_disp = f"{prev_v:.1f}%" if prev_v is not None else "—"
            if cur_v is not None and prev_v is not None:
                d = cur_v - prev_v
                if is_time:
                    # 时长增加是负面（红），减少是正面（绿）
                    delta_disp = f"{d/60:+.2f} 分钟"
                    color = "#b42318" if d > 0 else ("#1f7a3a" if d < 0 else "#6b7280")
                    arrow = "↑" if d > 0 else ("↓" if d < 0 else "→")
                else:
                    delta_disp = f"{d:+.1f}%"
                    color = "#1f7a3a" if d > 0 else ("#b42318" if d < 0 else "#6b7280")
                    arrow = "↑" if d > 0 else ("↓" if d < 0 else "→")
                delta_html = f"<span style='color:{color};font-weight:600'>{arrow} {delta_disp}</span>"
            else:
                delta_html = "<span style='color:#9ca3af'>—</span>"
            return prev_disp, cur_disp, delta_html

        cmp_metrics = [
            ("参与率", "examAttendanceRate", False),
            ("参与完成率", "examClassFinishRate", False),
            ("首次 3 星率", "firstThreeStarPercentage", False),
            ("完成时长", "completeTime", True),
        ]
        head_cells = "".join(
            f"<th style='text-align:center;padding:8px 10px;font-size:12px;color:#6b7280;font-weight:600;border-bottom:2px solid #e5e7eb'>{label}</th>"
            for label, _, _ in cmp_metrics
        )
        prev_row = ""; cur_row = ""; delta_row = ""
        for label, field, is_time in cmp_metrics:
            p, c, d = cmp_cell(field, is_time)
            prev_row += f"<td style='text-align:center;padding:6px 10px;font-size:13px;color:#6b7280'>{p}</td>"
            cur_row += f"<td style='text-align:center;padding:6px 10px;font-size:15px;font-weight:700;color:#111'>{c}</td>"
            delta_row += f"<td style='text-align:center;padding:6px 10px;font-size:13px'>{d}</td>"

        cmp_html = (
            f"<div style='border:1px solid #e5e7eb;border-radius:8px;padding:12px 14px;background:#fff;height:100%;box-sizing:border-box'>"
            f"<div style='font-weight:700;font-size:14px;color:#111;margin-bottom:10px'>📊 数据对比</div>"
            f"<div style='font-size:11px;color:#9ca3af;margin-bottom:8px'>{sel_week_label} 本周　vs　{prev_label} 上周</div>"
            f"<table style='width:100%;border-collapse:collapse'>"
            f"<thead><tr><th style='text-align:left;padding:6px 6px;font-size:11px;color:#6b7280;font-weight:600;border-bottom:2px solid #e5e7eb'></th>{head_cells}</tr></thead>"
            f"<tbody>"
            f"<tr><td style='text-align:left;padding:6px 6px;font-size:12px;color:#9ca3af'>上周</td>{prev_row}</tr>"
            f"<tr><td style='text-align:left;padding:6px 6px;font-size:12px;color:#374151;font-weight:600'>本周</td>{cur_row}</tr>"
            f"<tr style='border-top:1px dashed #e5e7eb'><td style='text-align:left;padding:6px 6px;font-size:12px;color:#9ca3af'>环比</td>{delta_row}</tr>"
            f"</tbody></table>"
            f"</div>"
        )

        # ② AI 整体分析
        summary_data = (WEEKLY_SUMMARY.get(sel_stage_name) or {}).get(sel_week_label)
        summary_html = ai_box_html(f"🤖 {exam_label} AI 分析（D5 测评）",
                                   summary_data.get("summary") if summary_data else None)

        # 左右并排：数据对比表（窄）+ AI 分析（宽），节省纵向空间
        col_cmp, col_ai = st.columns([5, 7], gap="medium")
        with col_cmp:
            st.markdown(cmp_html, unsafe_allow_html=True)
        with col_ai:
            if summary_html:
                st.markdown(summary_html, unsafe_allow_html=True)
            elif WEEKLY_SUMMARY:
                st.caption("💡 当前周次 AI 分析正在生成中，可手动运行 `./venv/bin/python generate_weekly_summary.py` 更新。")

    st.divider()
    st.markdown("#### 二、细节情况")
    st.markdown("**📈 各指标趋势**")
    render_trend_grid(EXAM_VIZ_METRICS, weeks, sel_week_label, get_stat, sel_stage_name,
                      ["#4C9BE8", "#2A9D8F", "#E76F51", "#F4A261"])

    st.markdown("**📋 全周期周测数据**")
    st.caption("率列按各自最低→最高独立着色（浅红→浅绿）；完成时长 / 总学生数 / 参与人数为参考，不着色。")
    render_full_period_table(
        EXAM_VIZ_METRICS, weeks, get_stat, sel_stage_name,
        extra_cols=[("总学生数", "totalStudentsNum", "int"), ("参与人数", "attendanceStudentsNum", "int")],
    )

    _term_kp = insights.get("term_weak_knowledge") or []
    if _term_kp:
        st.markdown("**🧩 全学期反复薄弱知识点 Top10**")
        st.caption(
            f"跨 {sel_stage_name} 全部已上线周次，按知识点的周测首次 3 星率（按作答人次加权平均）从低到高排序，"
            "用于定位需要在课程里持续强化的知识点。"
        )
        _kp_rows = [{
            "知识点": k["name"],
            "平均首次 3 星率 (%)": round(k["avg"], 1),
            "最低首次 3 星率 (%)": round(k["min"], 1),
            "最低出现周次": k["min_week"],
            "出现周数": k["weeks"],
            "累计作答人次": k["n"],
        } for k in _term_kp]
        _df_kp = pd.DataFrame(_kp_rows)
        style_heatmap(
            _df_kp, ["平均首次 3 星率 (%)", "最低首次 3 星率 (%)"],
            {"平均首次 3 星率 (%)": "{:.1f}", "最低首次 3 星率 (%)": "{:.1f}",
             "出现周数": "{:.0f}", "累计作答人次": "{:,.0f}"},
            height=min(440, 40 * len(_df_kp) + 40),
        )

    st.divider()
    st.markdown("**🔍 逐题分析**")
    render_question_analysis(
        sel_week.get("questions") or [],
        sel_week.get("knowledge") or [],
        sel_week_label,
        sel_stage_name,
        week_full(sel_stage_name, sel_week_label),
    )
