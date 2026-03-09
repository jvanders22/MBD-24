import streamlit as st
import pandas as pd
import os, urllib.request, io, re, zipfile
from datetime import datetime, date, timedelta

st.set_page_config(page_title="Debita Outreach", layout="wide", page_icon="📊")

# ── Config ─────────────────────────────────────────────────────────────────────
SHEET_ID      = "1t6GEkF2DyvWKbT0Bm80-Tp1N5_nCByGbPJqvKdWi_3U"
SHEET_URL     = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
MASTER_FILE   = "/Users/joshvanderspuy/Desktop/NEITEC/Buy Side/Family Office/04_Active_Tracking/DEBITA_OUTREACH_MASTER.xlsx"
TRACKING_FILE = "/Users/joshvanderspuy/Desktop/NEITEC/Buy Side/Family Office/05_Tools/debita_tracking.csv"

STAGES = ["Contacted", "Responded", "Meeting", "Committed", "Pass"]

PASS_KW = ["not interested","not in scope","not in their","not something","retired",
           "no interest","dont look","only works in europe","not in charge","not part of",
           "only semi","refocusing","eif only","not a direct fit","not allocating"]
MEETING_KW = ["set up call","calendly","had a call","meeting","signed up","kyc","nda",
              "send him deck","sent over docs","sent deck","setting up call",
              "lets have a convo","should have call","setting up call"]

SENIOR_TITLES = ["cio","chief investment","managing partner","managing director",
                 "founder","president","ceo","cfo","portfolio manager",
                 "head of","partner","principal"]
MID_TITLES    = ["director","senior","vice president"," vp ","associate director"]

# ── Normalisation ──────────────────────────────────────────────────────────────

def norm_company(s):
    s = re.sub(r'\b(inc|llc|ltd|limited|corp|sa|gmbh|ag|lp|llp)\b\.?', '', str(s).lower())
    s = re.sub(r'[^\w\s]', ' ', s)
    return ' '.join(s.split())

def norm_name(s):
    s = re.sub(r'\b(cfa|caia|phd|mba|fia|acsi|cpa|jr|sr)\b', '', str(s).lower())
    s = re.sub(r'[^\w\s]', ' ', s)
    return ' '.join(s.split())

# ── Stage derivation ───────────────────────────────────────────────────────────

def derive_stage(situation):
    sit = str(situation).strip().lower() if pd.notna(situation) else ""
    if not sit:                                            return "Contacted"
    if any(k in sit for k in PASS_KW):                   return "Pass"
    if any(k in sit for k in MEETING_KW):                return "Meeting"
    return "Responded"

# ── Follow-up logic ────────────────────────────────────────────────────────────

def count_followups(situation):
    s = str(situation).lower()
    if re.search(r'3rd follow|third follow|completed 3', s):                  return 3
    if re.search(r'2nd follow|follow.{0,5}up twice|twice|completed 2', s):   return 2
    if re.search(r'follow.{0,5}up|followed up', s):                          return 1
    return 0

def followup_action(row):
    if row.get("Stage") != "Contacted": return None
    is_cold = str(row.get("ColdStatus", "")).upper() == "COLD"
    n = count_followups(row.get("Situation", ""))
    if is_cold:
        return "Final follow-up" if n == 2 else None
    if n == 0: return "1st follow-up"
    if n == 1: return "2nd follow-up"
    if n == 2: return "Final follow-up"
    return "Mark cold"

# ── Priority scoring ───────────────────────────────────────────────────────────

def priority_score(row):
    score = 0
    title = str(row.get("Title", "")).lower()
    if any(t in title for t in SENIOR_TITLES): score += 40
    elif any(t in title for t in MID_TITLES):  score += 20
    d = days_since(row.get("Last_Contact"))
    if d: score += min(d, 30)
    if pd.notna(row.get("Follow_Up_Date")): score += 20
    return score

def seniority_badge(row):
    title = str(row.get("Title", "")).lower()
    if any(t in title for t in SENIOR_TITLES): return "⭐"
    return ""

# ── Helpers ────────────────────────────────────────────────────────────────────

def days_since(ts):
    if pd.isna(ts): return None
    return (datetime.now() - pd.Timestamp(ts)).days

def fmt_date(ts):
    if pd.isna(ts): return "—"
    return pd.Timestamp(ts).strftime("%d %b")

def stage_icon(stage):
    return {"Contacted":"📤","Responded":"💬","Meeting":"🤝",
            "Committed":"✅","Pass":"❌"}.get(stage,"")

# ── Data loading ───────────────────────────────────────────────────────────────

def load_sheet():
    """Load LinkedIn outreach tracker (Google Sheet)."""
    req = urllib.request.Request(SHEET_URL, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=10).read().decode("utf-8")
    df  = pd.read_csv(io.StringIO(raw))
    df.columns = df.columns.str.strip()

    out = pd.DataFrame()
    out["Name"]      = df["Name"].astype(str).str.strip()
    out["Company"]   = df["Company"].astype(str).str.strip()
    out["Title"]     = df.get("What They Do", pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    out["Situation"] = df.get("Situation",    pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    out["Next_Step"] = df.get("Next Step",    pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    out["Deal_Type"] = df.get("Deal Type",    pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    out["ColdStatus"]= df.get("status - cold hot warm - to prioritise",
                               pd.Series(dtype=str)).fillna("").astype(str).str.strip().str.upper()

    out["Last_Contact"]   = pd.to_datetime(df.get("Date Contacted"),        dayfirst=True, errors="coerce")
    out["Follow_Up_Date"] = pd.to_datetime(df.get("Follow-up Date (last)"), dayfirst=True, errors="coerce")

    out["Stage"]  = out["Situation"].apply(derive_stage)
    out["Source"] = "outreach"

    out = out[out["Name"].notna() & (out["Name"] != "") & (out["Name"] != "nan")]
    return out.reset_index(drop=True)


def load_master():
    """Load HOT/WARM/COLD target list (Excel)."""
    df = pd.read_excel(MASTER_FILE, sheet_name="ALL")
    out = pd.DataFrame()
    out["Name"]       = df["Name"].astype(str).str.strip()
    out["Company"]    = df["Company"].astype(str).str.strip()
    out["Title"]      = df.get("Title",      pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    out["Category"]   = df.get("Category",   pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    out["Type"]       = df.get("Type",       pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    out["Location"]   = df.get("Location",   pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    out["Est_Ticket"] = df.get("Est_Ticket", pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    out["Why_Fit"]    = df.get("Why_Fit",    pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    out["LinkedIn"]   = df.get("LinkedIn_Person", pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    out["Email"]      = df.get("Email",      pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    out["Source"]     = "master"
    return out.reset_index(drop=True)


def load_tracking():
    if os.path.exists(TRACKING_FILE):
        t = pd.read_csv(TRACKING_FILE)
        for col in ["Meeting_Date", "Notes_Local", "Stage_Override"]:
            if col not in t.columns: t[col] = ""
        t["Meeting_Date"] = pd.to_datetime(t["Meeting_Date"], errors="coerce")
        return t
    return pd.DataFrame(columns=["Name","Company","Meeting_Date","Notes_Local","Stage_Override"])


def save_tracking(df):
    cols = ["Name","Company","Meeting_Date","Notes_Local","Stage_Override"]
    df[[c for c in cols if c in df.columns]].to_csv(TRACKING_FILE, index=False)


def already_contacted(master_row, sheet_companies):
    """Check if a master lead has already been contacted (by company match)."""
    c = norm_company(master_row["Company"])
    return c in sheet_companies


def load_all():
    sheet   = load_sheet()
    master  = load_master()
    tracking = load_tracking()

    # Apply tracking overrides to sheet
    if not tracking.empty:
        sheet = sheet.merge(
            tracking[["Name","Company","Meeting_Date","Notes_Local","Stage_Override"]],
            on=["Name","Company"], how="left"
        )
        mask = sheet["Stage_Override"].notna() & (sheet["Stage_Override"] != "")
        sheet.loc[mask, "Stage"] = sheet.loc[mask, "Stage_Override"]
    else:
        sheet["Meeting_Date"]   = pd.NaT
        sheet["Notes_Local"]    = ""
        sheet["Stage_Override"] = ""
    sheet["Notes_Local"] = sheet["Notes_Local"].fillna("")

    # Mark which master leads are already in outreach
    sheet_companies = set(sheet["Company"].apply(norm_company))
    master["Contacted"] = master.apply(
        lambda r: already_contacted(r, sheet_companies), axis=1
    )

    return sheet, master

# ── Session state ──────────────────────────────────────────────────────────────

if "sheet" not in st.session_state:
    with st.spinner("Loading data..."):
        try:
            s, m = load_all()
            st.session_state.sheet  = s
            st.session_state.master = m
        except Exception as e:
            st.error(f"Failed to load: {e}")
            st.stop()

sheet  = st.session_state.sheet
master = st.session_state.master

# Derived subsets
contacted    = len(sheet)
responded_df = sheet[sheet["Stage"] == "Responded"]
meeting_df   = sheet[sheet["Stage"] == "Meeting"]
committed_df = sheet[sheet["Stage"] == "Committed"]
pass_df      = sheet[sheet["Stage"] == "Pass"]

master_hot  = master[(master["Category"] == "HOT")  & ~master["Contacted"]]
master_warm = master[(master["Category"] == "WARM") & ~master["Contacted"]]
master_cold = master[(master["Category"] == "COLD") & ~master["Contacted"]]

# ── Sidebar ────────────────────────────────────────────────────────────────────

LOGO = "/Users/joshvanderspuy/Desktop/NEITEC/Buy Side/Investor Docs/Debita Logo.png"
if os.path.exists(LOGO):
    st.sidebar.image(LOGO, use_column_width=True)
else:
    st.sidebar.title("Debita")

st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Navigate",
    ["📊 Overview", "⚡ Today", "🤝 Active Pipeline", "🎯 To Contact", "📋 All Outreach"],
    label_visibility="collapsed"
)
st.sidebar.markdown("---")

# Sidebar mini-metrics
response_rate = round(len(responded_df) / contacted * 100, 1) if contacted else 0
meeting_rate  = round(len(meeting_df)   / contacted * 100, 1) if contacted else 0
st.sidebar.markdown(f"**Contacted** {contacted}")
st.sidebar.markdown(f"**Responded** {len(responded_df) + len(meeting_df)}  ·  {response_rate}%")
st.sidebar.markdown(f"**Meetings** {len(meeting_df)}  ·  {meeting_rate}%")
st.sidebar.markdown(f"🔥 **HOT to contact** {len(master_hot)}")
st.sidebar.markdown("---")

if st.sidebar.button("🔄 Sync"):
    del st.session_state["sheet"]
    del st.session_state["master"]
    st.rerun()

# ── Contact card (Active Pipeline) ─────────────────────────────────────────────

def contact_card(row, widget_key, df_idx):
    lc = days_since(row.get("Last_Contact"))
    fu = fmt_date(row.get("Follow_Up_Date"))
    md = fmt_date(row.get("Meeting_Date"))

    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown(f"**{row['Name']}**")
        if row.get("Title"): st.caption(row["Title"] + "  ·  " + row.get("Company",""))
        else: st.caption(row.get("Company",""))
        if row.get("Situation"):  st.info(row["Situation"])
        if row.get("Next_Step"):  st.success(f"Next: {row['Next_Step']}")
        if row.get("Notes_Local"): st.warning(row["Notes_Local"])
    with c2:
        if lc is not None: st.caption(f"📤 {lc}d ago")
        if fu != "—":       st.caption(f"📅 {fu}")
        if md != "—":       st.caption(f"🤝 {md}")

    with st.expander("Edit"):
        ec1, ec2 = st.columns(2)
        with ec1:
            new_stage = st.selectbox("Stage", STAGES,
                index=STAGES.index(row["Stage"]) if row["Stage"] in STAGES else 0,
                key=f"stage_{widget_key}")
        with ec2:
            mt_val = row["Meeting_Date"].date() if pd.notna(row.get("Meeting_Date")) else None
            meeting_date = st.date_input("Meeting date", value=mt_val, key=f"mt_{widget_key}")
        notes = st.text_area("Notes", value=str(row.get("Notes_Local","")),
                             height=60, key=f"notes_{widget_key}")
        if st.button("Save", key=f"save_{widget_key}"):
            st.session_state.sheet.at[df_idx,"Stage_Override"] = new_stage
            st.session_state.sheet.at[df_idx,"Stage"]          = new_stage
            st.session_state.sheet.at[df_idx,"Meeting_Date"]   = pd.Timestamp(meeting_date) if meeting_date else pd.NaT
            st.session_state.sheet.at[df_idx,"Notes_Local"]    = notes
            save_tracking(st.session_state.sheet)
            st.success("Saved!")
            st.rerun()
    st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

if page == "📊 Overview":
    st.title("Outreach Overview")

    # ── Funnel KPIs ──
    total_targets = len(master) + len(sheet[~sheet["Company"].apply(norm_company).isin(
        set(master["Company"].apply(norm_company)))])

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("🎯 Target List",   len(master))
    k2.metric("📤 Contacted",     contacted)
    k3.metric("💬 Responded",     len(responded_df) + len(meeting_df))
    k4.metric("🤝 Meetings",      len(meeting_df))
    k5.metric("📈 Response Rate", f"{response_rate}%")
    k6.metric("📈 Meeting Rate",  f"{meeting_rate}%")

    st.markdown("---")

    # ── Two-column layout ──
    left, right = st.columns([3, 2])

    with left:
        st.subheader("Outreach Funnel")

        funnel_data = {
            "Contacted":  contacted,
            "Responded":  len(responded_df),
            "Meeting":    len(meeting_df),
            "Committed":  len(committed_df),
            "Pass":       len(pass_df),
        }
        funnel_df = pd.DataFrame({
            "Stage": list(funnel_data.keys()),
            "Count": list(funnel_data.values())
        })
        st.bar_chart(funnel_df.set_index("Stage"), horizontal=True, height=220)

        st.markdown("---")
        st.subheader("Follow-up Queue")

        contacted_rows = sheet[sheet["Stage"] == "Contacted"].copy()
        contacted_rows["_action"] = contacted_rows.apply(followup_action, axis=1)
        fu_counts = contacted_rows["_action"].value_counts()

        stale_cut_ov = pd.Timestamp(datetime.now() - timedelta(days=14))
        fu_active_count = sheet[
            sheet["Follow_Up_Date"].notna()
            & (sheet["Follow_Up_Date"] <= pd.Timestamp(date.today()))
            & (sheet["Follow_Up_Date"] >= stale_cut_ov)
            & (~sheet["Stage"].isin(["Committed","Pass"]))
        ]
        qc1, qc2, qc3, qc4 = st.columns(4)
        qc1.metric("📅 Due This Week", len(fu_active_count))
        qc2.metric("1st Follow-up",   fu_counts.get("1st follow-up", 0))
        qc3.metric("2nd Follow-up",   fu_counts.get("2nd follow-up", 0))
        qc4.metric("Final Follow-up", fu_counts.get("Final follow-up", 0))

    with right:
        st.subheader("Target List Status")

        tc1, tc2, tc3 = st.columns(3)
        tc1.metric("🔥 HOT",  len(master_hot),  delta=f"{len(master[master['Category']=='HOT'])} total")
        tc2.metric("🌡️ WARM", len(master_warm), delta=f"{len(master[master['Category']=='WARM'])} total")
        tc3.metric("❄️ COLD", len(master_cold), delta=f"{len(master[master['Category']=='COLD'])} total")

        st.markdown("---")
        st.subheader("Active Meetings")
        if meeting_df.empty:
            st.caption("No meetings scheduled.")
        for _, row in meeting_df.head(8).iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([3,1])
                c1.markdown(f"**{row['Name']}** — {row['Company']}")
                c1.caption(row.get("Situation","")[:80])
                md = fmt_date(row.get("Meeting_Date"))
                c2.caption(f"📅 {md}" if md != "—" else "Date TBC")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: TODAY
# ══════════════════════════════════════════════════════════════════════════════

elif page == "⚡ Today":
    st.title("Today's Actions")

    today_ts  = pd.Timestamp(date.today())
    stale_cut = pd.Timestamp(datetime.now() - timedelta(days=14))

    base_fu_mask = (
        sheet["Follow_Up_Date"].notna()
        & (sheet["Follow_Up_Date"] <= today_ts)
        & (~sheet["Stage"].isin(["Committed","Pass"]))
    )
    # Active = overdue within last 14 days (genuinely needs action)
    fu_active = sheet[base_fu_mask & (sheet["Follow_Up_Date"] >= stale_cut)]
    # Stale   = older than 14 days (probably already handled, sheet not cleaned yet)
    fu_stale  = sheet[base_fu_mask & (sheet["Follow_Up_Date"] < stale_cut)]

    going_cold_mask = (
        (sheet["Stage"] == "Responded")
        & sheet["Last_Contact"].notna()
        & (sheet["Last_Contact"] <= pd.Timestamp(datetime.now() - timedelta(days=14)))
    )
    going_cold = sheet[going_cold_mask]

    contacted_rows = sheet[sheet["Stage"] == "Contacted"].copy()
    contacted_rows["_action"] = contacted_rows.apply(followup_action, axis=1)
    fu_queue = {
        "1st follow-up":   contacted_rows[contacted_rows["_action"] == "1st follow-up"],
        "2nd follow-up":   contacted_rows[contacted_rows["_action"] == "2nd follow-up"],
        "Final follow-up": contacted_rows[contacted_rows["_action"] == "Final follow-up"],
        "Mark cold":       contacted_rows[contacted_rows["_action"] == "Mark cold"],
    }
    needs_action = sum(len(v) for k, v in fu_queue.items() if k != "Mark cold")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("🤝 Meetings",        len(meeting_df))
    m2.metric("📅 Due This Week",   len(fu_active))
    m3.metric("📬 Need Follow-up",  needs_action)
    m4.metric("🧊 Going Cold",      len(going_cold))
    m5.metric("Mark Cold",          fu_queue["Mark cold"].shape[0])

    st.divider()
    left, right = st.columns([3, 2])

    with left:
        # Active follow-up dates (last 14 days)
        if not fu_active.empty:
            st.subheader(f"📅 Follow-up Dates Due ({len(fu_active)})")
            for _, row in fu_active.sort_values("Follow_Up_Date").iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([3,1])
                    c1.markdown(f"**{row['Name']}** — {row['Company']}")
                    c1.caption(f"`{row['Stage']}`" + (f"  ·  {row['Situation']}" if row.get('Situation') else ""))
                    c2.markdown(f"**{fmt_date(row['Follow_Up_Date'])}**")
                    if row.get("Next_Step"): st.caption(f"→ {row['Next_Step']}")

        # Stale dates — collapsed, sheet not cleaned yet
        if not fu_stale.empty:
            with st.expander(f"🗄️ Stale follow-up dates — older than 14 days ({len(fu_stale)}) · clean these in your sheet"):
                tbl = fu_stale[["Name","Company","Follow_Up_Date","Stage"]].copy()
                tbl["Follow_Up_Date"] = tbl["Follow_Up_Date"].dt.strftime("%d %b %Y")
                tbl.columns = ["Name","Company","Follow-up Date","Stage"]
                st.dataframe(tbl.sort_values("Follow-up Date"), use_container_width=True, hide_index=True)

        action_config = [
            ("1st follow-up",   "📤", "1st Follow-up"),
            ("2nd follow-up",   "📤", "2nd Follow-up"),
            ("Final follow-up", "⚡", "Final Follow-up"),
            ("Mark cold",       "🧊", "Ready to Mark Cold"),
        ]
        for action_key, icon, label in action_config:
            rows = fu_queue[action_key]
            if rows.empty: continue

            st.subheader(f"{icon} {label} ({len(rows)})")
            rows_s = rows.copy()
            rows_s["_score"] = rows_s.apply(priority_score, axis=1)
            rows_s = rows_s.sort_values("_score", ascending=False)

            for _, row in rows_s.head(20).iterrows():
                d = days_since(row.get("Last_Contact"))
                with st.container(border=True):
                    c1, c2 = st.columns([3,1])
                    with c1:
                        badge = seniority_badge(row)
                        st.markdown(f"{badge} **{row['Name']}** — {row['Company']}")
                        if row.get("Title"): st.caption(row["Title"])
                    with c2:
                        if d: st.caption(f"{d}d ago")
                        if pd.notna(row.get("Follow_Up_Date")):
                            st.caption(f"📅 {fmt_date(row['Follow_Up_Date'])}")

            rest = rows_s.iloc[20:]
            if not rest.empty:
                with st.expander(f"Show remaining {len(rest)}"):
                    tbl = rest[["Name","Company","Title"]].rename(
                        columns={"Title":"Role"})
                    st.dataframe(tbl, use_container_width=True, hide_index=True)

        if not going_cold.empty:
            st.subheader(f"🧊 Responded — Going Cold ({len(going_cold)})")
            for _, row in going_cold.iterrows():
                d = days_since(row["Last_Contact"])
                with st.container(border=True):
                    c1, c2 = st.columns([3,1])
                    c1.markdown(f"**{row['Name']}** — {row['Company']}")
                    if row.get("Situation"): c1.caption(row["Situation"])
                    c2.markdown(f"**{d}d ago**")

    with right:
        st.subheader(f"🤝 Meetings ({len(meeting_df)})")
        for _, row in meeting_df.iterrows():
            with st.container(border=True):
                st.markdown(f"**{row['Name']}**")
                st.caption(row["Company"])
                md = fmt_date(row.get("Meeting_Date"))
                if md != "—": st.caption(f"📅 {md}")
                if row.get("Situation"): st.caption(row["Situation"][:100])


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: ACTIVE PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🤝 Active Pipeline":
    st.title("Active Pipeline")
    st.caption(f"{len(meeting_df) + len(responded_df)} active conversations")

    meetings_r  = meeting_df.reset_index()
    responded_r = responded_df.reset_index()

    col_m, col_r = st.columns(2)

    with col_m:
        st.subheader(f"🤝 Meeting ({len(meetings_r)})")
        st.caption("In active conversation — progressing")
        st.markdown("---")
        for _, row in meetings_r.iterrows():
            with st.container(border=True):
                contact_card(row, f"m_{row['index']}", row["index"])

    with col_r:
        st.subheader(f"💬 Responded ({len(responded_r)})")
        st.caption("Replied — needs follow-up or next step")
        st.markdown("---")
        for _, row in responded_r.iterrows():
            with st.container(border=True):
                contact_card(row, f"r_{row['index']}", row["index"])


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: TO CONTACT
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🎯 To Contact":
    st.title("To Contact")
    st.caption("Leads from your research list not yet in LinkedIn outreach")

    tab_h, tab_w, tab_c = st.tabs([
        f"🔥 HOT ({len(master_hot)})",
        f"🌡️ WARM ({len(master_warm)})",
        f"❄️ COLD ({len(master_cold)})",
    ])

    def lead_table(df, key_prefix):
        search = st.text_input("Search", key=f"search_{key_prefix}")
        if search:
            df = df[
                df["Name"].str.contains(search, case=False, na=False) |
                df["Company"].str.contains(search, case=False, na=False)
            ]
        st.caption(f"{len(df)} leads")

        for _, row in df.iterrows():
            with st.expander(f"**{row['Name']}** — {row['Company']}  ·  {row.get('Location','')}"):
                c1, c2 = st.columns([2,1])
                with c1:
                    if row.get("Title"):      st.caption(f"**Role:** {row['Title']}")
                    if row.get("Type"):       st.caption(f"**Type:** {row['Type']}")
                    if row.get("Why_Fit"):    st.info(row["Why_Fit"][:250])
                with c2:
                    if row.get("Est_Ticket"): st.metric("Est. Ticket", row["Est_Ticket"])
                    if row.get("LinkedIn") and row["LinkedIn"] != "nan":
                        st.markdown(f"[LinkedIn Profile]({row['LinkedIn']})")
                    if row.get("Email") and row["Email"] != "nan":
                        st.caption(f"✉️ {row['Email']}")

    with tab_h:
        lead_table(master_hot.copy(), "hot")
    with tab_w:
        lead_table(master_warm.copy(), "warm")
    with tab_c:
        lead_table(master_cold.copy(), "cold")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: ALL OUTREACH
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📋 All Outreach":
    st.title("All Outreach")

    contacted_df = sheet[sheet["Stage"] == "Contacted"].copy()

    tab_m, tab_r, tab_c, tab_p = st.tabs([
        f"🤝 Meeting ({len(meeting_df)})",
        f"💬 Responded ({len(responded_df)})",
        f"📤 Contacted ({len(contacted_df)})",
        f"❌ Pass ({len(pass_df)})",
    ])

    def search_filter(df, key):
        s = st.text_input("Search", key=f"search_{key}")
        if s:
            df = df[df["Name"].str.contains(s,case=False,na=False)|
                    df["Company"].str.contains(s,case=False,na=False)]
        return df

    with tab_m:
        data = search_filter(meeting_df.copy(), "tab_m")
        for _, row in data.reset_index().iterrows():
            with st.container(border=True):
                contact_card(row, f"tm_{row['index']}", row["index"])

    with tab_r:
        data = search_filter(responded_df.copy(), "tab_r")
        for _, row in data.reset_index().iterrows():
            with st.container(border=True):
                contact_card(row, f"tr_{row['index']}", row["index"])

    with tab_c:
        cc1, cc2 = st.columns(2)
        search  = cc1.text_input("Search", key="search_tab_c")
        fu_only = cc2.checkbox("Follow-up date set only")

        data = contacted_df.copy()
        data["_action"] = data.apply(followup_action, axis=1)
        data["FU Count"] = data["Situation"].apply(count_followups).astype(str)
        data["Action"]   = data["_action"].fillna("—")
        action_order = {"1st follow-up":0,"2nd follow-up":1,"Final follow-up":2,"Mark cold":3,"—":4}
        data["_sort"] = data["Action"].map(action_order).fillna(4)
        data = data.sort_values(["_sort","Follow_Up_Date","Last_Contact"],
                                ascending=[True,True,False], na_position="last")
        if search:
            data = data[data["Name"].str.contains(search,case=False,na=False)|
                        data["Company"].str.contains(search,case=False,na=False)]
        if fu_only:
            data = data[data["Follow_Up_Date"].notna()]

        display = data[["Name","Company","Title","FU Count","Action","Last_Contact","Follow_Up_Date"]].copy()
        display["Last_Contact"]   = data["Last_Contact"].dt.strftime("%d %b %Y").fillna("—")
        display["Follow_Up_Date"] = data["Follow_Up_Date"].dt.strftime("%d %b %Y").fillna("—")
        display.columns = ["Name","Company","Role","FU Done","Action Needed","Last Contact","Follow-up Date"]
        st.caption(f"{len(display)} contacts")
        st.dataframe(display, use_container_width=True, hide_index=True)

    with tab_p:
        data = search_filter(pass_df.copy(), "tab_p")
        for _, row in data.reset_index().iterrows():
            c1, c2 = st.columns([3,1])
            c1.write(f"**{row['Name']}** — {row['Company']}")
            c2.caption(row.get("Situation","")[:60])
