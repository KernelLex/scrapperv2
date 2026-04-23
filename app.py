"""
app.py — Streamlit lead-research dashboard for ethical B2B prospecting.

Run with:
    streamlit run app.py
"""

import io
import os
import time
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from database   import init_db, create_session, save_leads, get_leads, update_tag, list_sessions, delete_session
from extractor  import extract_leads
from scoring    import score_leads, apply_filters
from search     import run_searches
from utils      import deduplicate_leads, get_logger

warnings.filterwarnings("ignore")
load_dotenv()
logger = get_logger("app")

# ─── Page Config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="LeadScope — B2B Prospect Research",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* ── Import fonts ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Root variables ── */
:root {
    --bg-primary:    #0f1117;
    --bg-secondary:  #1a1d27;
    --bg-card:       #1e2130;
    --bg-elevated:   #252840;
    --accent-blue:   #4f8ef7;
    --accent-purple: #9b59f7;
    --accent-green:  #2ecc71;
    --accent-amber:  #f39c12;
    --accent-red:    #e74c3c;
    --text-primary:  #e8eaf0;
    --text-secondary:#9ea3b4;
    --text-muted:    #5c6170;
    --border:        rgba(255,255,255,0.08);
    --radius:        12px;
    --shadow:        0 4px 24px rgba(0,0,0,0.4);
}

/* ── Global reset ── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    color: var(--text-primary);
}

/* ── App background ── */
.stApp {
    background: linear-gradient(135deg, #0d0f1a 0%, #111726 50%, #0d1320 100%);
    min-height: 100vh;
}

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: var(--bg-secondary) !important;
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 {
    color: var(--text-primary) !important;
}

/* ── Cards / metric containers ── */
.metric-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px 24px;
    box-shadow: var(--shadow);
    transition: transform 0.2s ease, border-color 0.2s ease;
}
.metric-card:hover {
    transform: translateY(-2px);
    border-color: var(--accent-blue);
}
.metric-value {
    font-size: 2.2rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.metric-label {
    font-size: 0.82rem;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-top: 4px;
}

/* ── Hero header ── */
.hero-header {
    text-align: center;
    padding: 48px 0 32px;
}
.hero-title {
    font-size: 3rem;
    font-weight: 700;
    background: linear-gradient(135deg, #4f8ef7 0%, #9b59f7 50%, #2ecc71 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.02em;
    margin-bottom: 8px;
}
.hero-subtitle {
    color: var(--text-secondary);
    font-size: 1.05rem;
    font-weight: 400;
}

/* ── Section labels ── */
.section-label {
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--accent-blue);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 8px;
}

/* ── Pill badges ── */
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
}
.badge-hot    { background: rgba(231,76,60,0.2);  color: #f97060; border: 1px solid rgba(231,76,60,0.4); }
.badge-warm   { background: rgba(243,156,18,0.2); color: #f5b942; border: 1px solid rgba(243,156,18,0.4); }
.badge-skip   { background: rgba(92,97,112,0.2);  color: #9ea3b4; border: 1px solid rgba(92,97,112,0.4); }
.badge-none   { background: rgba(79,142,247,0.1); color: #7aabff; border: 1px solid rgba(79,142,247,0.3); }

/* ── Score badges ── */
.score-high { color: #2ecc71; font-weight: 600; }
.score-med  { color: #f39c12; font-weight: 600; }
.score-low  { color: #9ea3b4; }

/* ── Dataframe overrides ── */
[data-testid="stDataFrame"] {
    border-radius: var(--radius);
    overflow: hidden;
    border: 1px solid var(--border);
}

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple)) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 10px 24px !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 4px 12px rgba(79,142,247,0.3) !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(79,142,247,0.5) !important;
}

/* ── Progress bar ── */
.stProgress > div > div {
    background: linear-gradient(90deg, var(--accent-blue), var(--accent-purple)) !important;
}

/* ── Info/warning boxes ── */
.stInfo, .stWarning, .stSuccess, .stError {
    border-radius: var(--radius) !important;
}

/* ── Input fields ── */
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] select {
    background: var(--bg-elevated) !important;
    color: var(--text-primary) !important;
    border-color: var(--border) !important;
    border-radius: 8px !important;
}

/* ── Expander ── */
[data-testid="stExpander"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
}

/* ── Divider ── */
hr { border-color: var(--border) !important; }

/* ── Tooltip-style URL links in dataframe ── */
a { color: var(--accent-blue); }
</style>
""", unsafe_allow_html=True)


# ─── DB Initialisation ────────────────────────────────────────────────────────

@st.cache_resource
def get_db():
    return init_db()


conn = get_db()


# ─── Session State Defaults ───────────────────────────────────────────────────

def _init_state():
    defaults = {
        "leads":         [],
        "search_done":   False,
        "session_id":    None,
        "active_tab":    "search",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


# ─── Helper: truncated clickable URL ─────────────────────────────────────────

def _short(url: str, max_len: int = 34) -> str:
    if not url:
        return "—"
    return url if len(url) <= max_len else url[:max_len] + "…"


# ─── Hero ─────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="hero-header">
    <div class="hero-title">🔭 LeadScope</div>
    <div class="hero-subtitle">
        Ethical B2B prospect research · powered by public search data
    </div>
</div>
""", unsafe_allow_html=True)

st.divider()


# ─── Sidebar — Search Configuration ──────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🎯 Search Configuration")
    st.markdown("<div class='section-label'>Target</div>", unsafe_allow_html=True)

    city   = st.text_input("📍 City", value="Bangalore", key="city_input",
                            placeholder="e.g. Bangalore, Mumbai, Delhi")
    sector = st.text_input("💼 Sector", value="wedding photographers", key="sector_input",
                            placeholder="e.g. bridal makeup artists")

    st.divider()
    st.markdown("### 🔧 Filters")

    max_results         = st.slider("Max results", 10, 200, 50, step=10)
    must_have_instagram = st.toggle("Must have Instagram", value=False)
    must_have_contact   = st.toggle("Must have phone or email", value=False)
    weak_presence_only  = st.toggle("Weak digital presence only", value=False)

    st.markdown("<div class='section-label'>Follower Range (Instagram)</div>",
                unsafe_allow_html=True)
    col_min, col_max = st.columns(2)
    with col_min:
        min_followers = st.number_input("Min", value=0, min_value=0, step=100, key="min_f")
    with col_max:
        max_followers = st.number_input("Max", value=50000, min_value=0, step=1000, key="max_f")

    fetch_pages = st.toggle("Fetch landing pages (slower, richer data)", value=True)

    st.divider()
    with st.expander("🔑 Optional API Keys (boosts quota)", expanded=False):
        st.markdown(
            "<div style='font-size:0.8rem;color:#9ea3b4;margin-bottom:8px;'>" 
            "🟢 <b>By default, DuckDuckGo is used — completely free, no key needed.</b><br>"
            "Add keys below only if you want Google-level results or higher quota."
            "</div>",
            unsafe_allow_html=True,
        )
        serpapi_key = st.text_input(
            "SerpAPI Key", value=os.getenv("SERPAPI_KEY", ""), type="password",
            help="serpapi.com — 100 free searches/month after signup",
            placeholder="Leave blank to use DuckDuckGo (free)",
        )
        gcse_key = st.text_input(
            "Google CSE API Key", value=os.getenv("GCSE_API_KEY", ""), type="password",
            help="console.cloud.google.com → Custom Search JSON API",
            placeholder="Leave blank to use DuckDuckGo (free)",
        )
        gcse_cx = st.text_input(
            "Google CSE CX", value=os.getenv("GCSE_CX", ""),
            help="Custom Search Engine ID from programmablesearchengine.google.com",
            placeholder="Only needed with Google CSE Key",
        )

    st.divider()
    run_btn = st.button("🚀 Find Leads", use_container_width=True, key="run_btn")


# ─── Run Pipeline ─────────────────────────────────────────────────────────────

if run_btn:
    if not city.strip() or not sector.strip():
        st.error("Please enter both a city and a sector.")
    else:
        st.session_state.leads        = []
        st.session_state.search_done  = False
        st.session_state.session_id   = None

        prog_bar = st.progress(0, text="Initialising …")
        status   = st.empty()

        def _progress(pct: float, msg: str):
            prog_bar.progress(min(pct, 1.0), text=msg)
            status.info(msg)

        try:
            # ─ 1. Search
            _progress(0.05, "🔍 Running search queries …")
            raw_results = run_searches(
                sector        = sector.strip(),
                city          = city.strip(),
                max_results   = max_results,
                serpapi_key   = serpapi_key or None,
                gcse_key      = gcse_key or None,
                gcse_cx       = gcse_cx or None,
                progress_callback = lambda p, m: _progress(0.05 + p * 0.35, m),
            )

            if not raw_results:
                st.warning(
                    "No results returned. DuckDuckGo may be temporarily rate-limiting — "
                    "wait 30 seconds and try again, or try a different sector/city query."
                )
                st.stop()

            # ─ 2. Extract
            _progress(0.40, "🔎 Extracting contact details …")
            leads = extract_leads(
                raw_results,
                fetch_pages = fetch_pages,
                progress_callback = lambda p, m: _progress(0.40 + p * 0.35, m),
            )

            # ─ 3. Deduplicate
            _progress(0.76, "🧹 Removing duplicates …")
            leads = deduplicate_leads(leads)

            # ─ 4. Score
            _progress(0.82, "📊 Scoring leads …")
            leads = score_leads(leads)

            # ─ 5. Filter
            _progress(0.88, "🎯 Applying filters …")
            leads = apply_filters(
                leads,
                must_have_instagram = must_have_instagram,
                must_have_contact   = must_have_contact,
                weak_presence_only  = weak_presence_only,
                min_followers       = int(min_followers),
                max_followers       = int(max_followers),
            )

            # ─ 6. Persist
            _progress(0.94, "💾 Saving to database …")
            session_id = create_session(conn, sector.strip(), city.strip())
            save_leads(conn, leads, session_id)

            st.session_state.leads       = leads
            st.session_state.search_done = True
            st.session_state.session_id  = session_id

            _progress(1.0, f"✅ Done! {len(leads)} leads found.")
            time.sleep(0.5)
            prog_bar.empty()
            status.empty()

        except ValueError as e:
            prog_bar.empty()
            status.empty()
            st.error(str(e))
        except Exception as e:
            prog_bar.empty()
            status.empty()
            st.error(f"Unexpected error: {e}")
            logger.exception("Pipeline error")


# ─── Main Tabs ────────────────────────────────────────────────────────────────

tab_results, tab_history, tab_tagger, tab_about = st.tabs(
    ["📋 Results", "📚 History", "🏷️ Tag Leads", "ℹ️ About"]
)


# ══════════════════════════════════════════════════════════════════
#  TAB 1 — Results
# ══════════════════════════════════════════════════════════════════

with tab_results:
    leads = st.session_state.get("leads", [])

    if not leads:
        st.markdown("""
        <div style='text-align:center; padding: 80px 0; color: #5c6170;'>
            <div style='font-size:4rem; margin-bottom:16px;'>🔭</div>
            <div style='font-size:1.2rem; color:#9ea3b4;'>
                No results yet — configure your search in the sidebar and click
                <strong style='color:#4f8ef7;'>Find Leads</strong>.
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # ── Metrics Row
        total        = len(leads)
        with_ig      = sum(1 for l in leads if l.get("instagram_url"))
        with_contact = sum(1 for l in leads if l.get("phone") or l.get("email"))
        avg_quality  = round(sum(l.get("quality_score", 0) for l in leads) / max(total, 1), 1)

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{total}</div>
                <div class="metric-label">Leads Found</div>
            </div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{with_ig}</div>
                <div class="metric-label">Have Instagram</div>
            </div>""", unsafe_allow_html=True)
        with m3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{with_contact}</div>
                <div class="metric-label">Have Contact Info</div>
            </div>""", unsafe_allow_html=True)
        with m4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{avg_quality}</div>
                <div class="metric-label">Avg Quality Score</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Sort Controls
        sc1, sc2, sc3 = st.columns([2, 2, 1])
        with sc1:
            sort_col = st.selectbox("Sort by", [
                "quality_score", "dp_score", "name", "has_instagram",
                "has_phone", "has_email", "followers_approx"
            ], key="sort_col")
        with sc2:
            sort_dir = st.radio("Direction", ["Descending", "Ascending"],
                                horizontal=True, key="sort_dir")
        with sc3:
            st.markdown("<br>", unsafe_allow_html=True)
            # CSV Export
            df_export = pd.DataFrame(leads)
            csv_bytes = df_export.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇ Export CSV",
                data=csv_bytes,
                file_name=f"leads_{sector.replace(' ','_')}_{city}_{datetime.now():%Y%m%d_%H%M}.csv",
                mime="text/csv",
                use_container_width=True,
                key="csv_export",
            )

        # ── Build display DataFrame
        DISPLAY_COLS = [
            "name", "sector", "city", "instagram_url", "website_url",
            "phone", "email", "description", "source_url",
            "dp_score", "quality_score", "tag", "followers_approx",
        ]
        df = pd.DataFrame(leads)[DISPLAY_COLS]
        df = df.sort_values(sort_col, ascending=(sort_dir == "Ascending")).reset_index(drop=True)

        # Rename for display
        df.columns = [
            "Name", "Sector", "City", "Instagram", "Website",
            "Phone", "Email", "Bio", "Source",
            "DP Score", "Quality", "Tag", "Followers ≈"
        ]

        st.dataframe(
            df,
            use_container_width=True,
            height=520,
            column_config={
                "Instagram": st.column_config.LinkColumn("Instagram", display_text="🔗 View"),
                "Website":   st.column_config.LinkColumn("Website",   display_text="🌐 Open"),
                "Source":    st.column_config.LinkColumn("Source",    display_text="↗ Source"),
                "Bio":       st.column_config.TextColumn("Bio", max_chars=80),
                "DP Score":  st.column_config.NumberColumn("DP Score",  format="%d ⚡"),
                "Quality":   st.column_config.NumberColumn("Quality",   format="%d ⭐"),
                "Followers ≈": st.column_config.NumberColumn("Followers ≈", format="%d"),
                "Tag":       st.column_config.TextColumn("Tag"),
            },
            hide_index=True,
        )

        # ── Quality Distribution
        with st.expander("📊 Score Distribution", expanded=False):
            score_df = pd.DataFrame({
                "Quality Score": [l.get("quality_score", 0) for l in leads],
                "DP Score":      [l.get("dp_score", 0) for l in leads],
            })
            c1, c2 = st.columns(2)
            with c1:
                st.bar_chart(score_df["Quality Score"].value_counts().sort_index(),
                             color="#4f8ef7")
            with c2:
                st.bar_chart(score_df["DP Score"].value_counts().sort_index(),
                             color="#9b59f7")

        # ── Per-lead accordion detail view
        with st.expander("🔍 Detailed Lead Cards", expanded=False):
            page_size = 10
            total_pages = max(1, (len(leads) + page_size - 1) // page_size)
            page_num = st.number_input("Page", min_value=1, max_value=total_pages,
                                       value=1, key="detail_page")
            start = (page_num - 1) * page_size
            for lead in leads[start:start + page_size]:
                qual = lead.get("quality_score", 0)
                dp   = lead.get("dp_score", 0)
                tag  = lead.get("tag", "Untagged")
                tag_badge = {
                    "Hot": "badge badge-hot", "Warm": "badge badge-warm",
                    "Skip": "badge badge-skip",
                }.get(tag, "badge badge-none")
                qs_cls = "score-high" if qual >= 6 else "score-med" if qual >= 3 else "score-low"
                dp_cls = "score-high" if dp  >= 5 else "score-med" if dp  >= 3 else "score-low"

                st.markdown(f"""
<div class="metric-card" style="margin-bottom:12px;">
  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
    <span style="font-size:1.1rem; font-weight:600;">{lead.get('name','—')}</span>
    <span class="{tag_badge}">{tag}</span>
  </div>
  <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; font-size:0.87rem; color:var(--text-secondary);">
    <div>📍 {lead.get('city','—')} &nbsp;·&nbsp; 💼 {lead.get('sector','—')}</div>
    <div>⭐ Quality: <span class="{qs_cls}">{qual}</span> &nbsp;·&nbsp; ⚡ DP: <span class="{dp_cls}">{dp}</span></div>
    <div>👥 {lead.get('followers_approx') or '—'} followers</div>
    <div>📱 {lead.get('phone') or '—'}</div>
    <div>📧 {lead.get('email') or '—'}</div>
    <div>🌐 <a href="{lead.get('website_url','#')}" target="_blank">Website</a> &nbsp;·&nbsp;
         📸 <a href="{lead.get('instagram_url','#')}" target="_blank">Instagram</a></div>
  </div>
  <div style="font-size:0.82rem; color:var(--text-muted); margin-top:8px;">{lead.get('description','')[:220]}</div>
  <div style="font-size:0.78rem; color:var(--text-muted); margin-top:6px;">
    🔗 <a href="{lead.get('source_url','')}" target="_blank" style="color:var(--text-muted);">Source</a>
  </div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
#  TAB 2 — History
# ══════════════════════════════════════════════════════════════════

with tab_history:
    sessions = list_sessions(conn)
    if not sessions:
        st.info("No past search sessions yet.")
    else:
        st.markdown(f"**{len(sessions)} past session(s)**")
        for s in sessions:
            with st.expander(
                f"🗂 {s['sector'].title()} in {s['city'].title()} — "
                f"{s['result_count']} leads  ·  {s['created_at'][:16]}",
                expanded=False,
            ):
                h_leads = get_leads(conn, session_id=s["id"])
                if h_leads:
                    df_h = pd.DataFrame(h_leads)[[
                        "name", "instagram_url", "phone", "email",
                        "dp_score", "quality_score", "tag"
                    ]]
                    df_h.columns = ["Name", "Instagram", "Phone", "Email",
                                    "DP Score", "Quality", "Tag"]
                    st.dataframe(df_h, use_container_width=True, hide_index=True)

                    csv_h = pd.DataFrame(h_leads).to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "⬇ Export Session CSV",
                        csv_h,
                        file_name=f"session_{s['id']}.csv",
                        mime="text/csv",
                        key=f"export_s_{s['id']}",
                    )
                del_col, _ = st.columns([1, 4])
                with del_col:
                    if st.button("🗑 Delete Session", key=f"del_s_{s['id']}"):
                        delete_session(conn, s["id"])
                        st.rerun()


# ══════════════════════════════════════════════════════════════════
#  TAB 3 — Tag Leads
# ══════════════════════════════════════════════════════════════════

with tab_tagger:
    st.markdown("### 🏷️ Tag Leads for Outreach")

    session_id = st.session_state.get("session_id")
    if not session_id:
        all_sess = list_sessions(conn)
        if all_sess:
            sess_opts = {
                f"{s['sector']} · {s['city']} · {s['created_at'][:16]}": s["id"]
                for s in all_sess
            }
            chosen = st.selectbox("Choose session to tag", list(sess_opts.keys()), key="tag_sess")
            session_id = sess_opts[chosen]
        else:
            st.info("Run a search first to generate leads.")
            st.stop()

    tag_filter = st.selectbox("Filter by tag", ["All", "Untagged", "Hot", "Warm", "Skip"],
                              key="tag_filter")
    tag_leads = get_leads(conn, session_id=session_id,
                          tag=None if tag_filter == "All" else tag_filter)

    if not tag_leads:
        st.info("No leads match this filter.")
    else:
        st.markdown(f"**{len(tag_leads)} lead(s)**")
        for lead in tag_leads:
            with st.container():
                c1, c2, c3, c4 = st.columns([3, 1, 1, 2])
                with c1:
                    ig = lead.get("instagram_url", "")
                    ig_link = f"[📸 IG]({ig})" if ig else "—"
                    st.markdown(
                        f"**{lead.get('name','—')}** &nbsp;·&nbsp; "
                        f"📱 `{lead.get('phone') or '—'}` &nbsp;·&nbsp; {ig_link} &nbsp;·&nbsp; "
                        f"⭐ {lead.get('quality_score',0)} &nbsp;·&nbsp; ⚡ {lead.get('dp_score',0)}"
                    )
                with c2:
                    new_tag = st.selectbox(
                        "Tag", ["Untagged", "Hot", "Warm", "Skip"],
                        index=["Untagged", "Hot", "Warm", "Skip"].index(
                            lead.get("tag", "Untagged")
                            if lead.get("tag", "Untagged") in ["Untagged", "Hot", "Warm", "Skip"]
                            else "Untagged"
                        ),
                        key=f"tag_{lead['id']}",
                        label_visibility="collapsed",
                    )
                with c3:
                    notes = st.text_input(
                        "Notes", value=lead.get("notes", ""),
                        key=f"notes_{lead['id']}",
                        label_visibility="collapsed",
                        placeholder="Notes …",
                    )
                with c4:
                    if st.button("💾 Save", key=f"save_{lead['id']}"):
                        update_tag(conn, lead["id"], new_tag, notes)
                        st.success("Saved!", icon="✅")
                st.divider()


# ══════════════════════════════════════════════════════════════════
#  TAB 4 — About
# ══════════════════════════════════════════════════════════════════

with tab_about:
    st.markdown("""
## 🔭 LeadScope — Ethical B2B Prospect Research

LeadScope helps you discover potential B2B clients by searching **publicly available**
information from public search results, Instagram snippets, and business websites.

### ✅ 100% Free — No API Keys Required

LeadScope uses **DuckDuckGo** as its default search engine — completely free, no signup,
no quota limits. Optionally add SerpAPI or Google CSE keys in the sidebar for
Google-specific results or a higher daily quota.

| Search Backend | Cost | Requires Key? |
|----------------|------|---------------|
| DuckDuckGo     | Free | ❌ No          |
| SerpAPI        | Free tier (100/mo) | ✅ Yes (signup) |
| Google CSE     | Free tier (100/day) | ✅ Yes (signup) |

### How It Works

1. **Search** — 8 varied query templates are fired against your chosen search backend.
2. **Extract** — Snippets and (optionally) landing pages are parsed for phones, emails,
   Instagram handles, and descriptions using BeautifulSoup.
3. **Score** — Each lead gets a DP Score (digital presence weakness) and Quality Score
   (actionability).
4. **Filter** — Narrow by Instagram, contact info, follower range, weak presence, etc.
5. **Tag** — Mark leads as Hot 🔥 / Warm 🤝 / Skip ⏭ for your outreach workflow.
6. **Export** — Download leads as CSV at any time.

### Scoring Guide

| DP Score | Meaning |
|----------|---------|
| 7+       | Very weak online presence — prime opportunity |
| 4–6      | Some gaps — could benefit from services |
| 0–3      | Reasonably established digital presence |

| Quality Score | Meaning |
|--------------|---------||
| 8+           | Excellent — multiple contact channels |
| 4–7          | Good — some contact info available |
| 0–3          | Limited — minimal actionable data |

### Ethical Use

- ✅ Only **publicly listed** data is used
- ✅ No Instagram private API or account credentials
- ✅ Rate-limited — polite to target servers
- ✅ Intended for **manual, personalised outreach** — not spam

### Source Code

🔗 [github.com/KernelLex/scrapperv2](https://github.com/KernelLex/scrapperv2)
""")
