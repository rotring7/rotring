import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils import GithubStorage, NewsAggregator, AIEditor

# Page Config
st.set_page_config(
    page_title="AI Insight Newsroom",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load Secrets
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except KeyError as e:
    st.error(f"❌ Secrets incorrectly configured. Missing key: {e}. Please check `.streamlit/secrets.toml`.")
    st.write("Current secrets keys:", st.secrets.keys()) # Debug info
    st.stop()

# Initialize Backend
@st.cache_resource
def get_storage():
    return GithubStorage(GITHUB_TOKEN, REPO_NAME)

storage = get_storage()

# Verify Connection
is_connected, error_msg = storage.verify_access()
if not is_connected:
    st.error(f"❌ GitHub Connection Failed: {error_msg}")
    st.info("Check your `.streamlit/secrets.toml`:\n1. Is `REPO_NAME` correct? (User/Repo)\n2. Does `GITHUB_TOKEN` have `repo` permissions?")
    st.stop()

# Load Data State
if 'data_sha' not in st.session_state:
    st.session_state.data = None
    st.session_state.sha = None

def load_data():
    data, sha = storage.load_data()
    st.session_state.data = data
    st.session_state.sha = sha
    return data

if st.session_state.data is None:
    load_data()

data = st.session_state.data

# -- Sidebar --
st.sidebar.title("📡 AI Insight Newsroom")

# Date Navigation
if data and "reports" in data:
    report_dates = sorted(data["reports"].keys(), reverse=True)
else:
    report_dates = []

selected_date = st.sidebar.selectbox(
    "🗓️ 날짜 선택",
    options=report_dates,
    index=0 if report_dates else None
)

# Stats
st.sidebar.markdown("---")
if data and "stats" in data:
    st.sidebar.metric("총 방문자 수", data["stats"].get("visits", 0))
    st.sidebar.caption(f"Last Updated: {data['stats'].get('last_updated', 'N/A')}")

# Admin Mode Toggle
st.sidebar.markdown("---")
admin_mode = st.sidebar.checkbox("관리자 모드")

# -- Main Content --
if admin_mode:
    password = st.sidebar.text_input("비밀번호", type="password")
    if password == ADMIN_PASSWORD:
        st.title("🛠️ 관리자 대시보드")
        
        # 1. RSS Feed Management
        st.subheader("📰 RSS 피드 관리")
        
        current_feeds = data.get("feeds", [])
        new_feed = st.text_input("새 RSS URL 추가")
        if st.button("추가"):
            if new_feed and new_feed not in current_feeds:
                current_feeds.append(new_feed)
                data["feeds"] = current_feeds
                storage.save_data(data, st.session_state.sha, commit_message="Add RSS feed")
                load_data() # Reload to get new SHA
                st.success(f"Added: {new_feed}")
                st.rerun()

        st.write("등록된 피드 목록:")
        for feed in current_feeds:
            col1, col2 = st.columns([0.8, 0.2])
            col1.write(feed)
            if col2.button("삭제", key=feed):
                current_feeds.remove(feed)
                data["feeds"] = current_feeds
                storage.save_data(data, st.session_state.sha, commit_message="Remove RSS feed")
                load_data()
                st.rerun()

        st.markdown("---")

        # 2. Manual Update Trigger
        st.subheader("⚡ 뉴스 수집 및 AI 분석 실행")
        if st.button("지금 업데이트 (Update Now)"):
            with st.status("업데이트 진행 중...", expanded=True) as status:
                # Step 1: Fetch
                st.write("RSS 피드 수집 중...")
                aggregator = NewsAggregator(current_feeds)
                articles = aggregator.fetch_and_filter(days=3)
                st.write(f"✅ 수집 완료: {len(articles)}개 기사")

                # Step 2: AI Analysis
                st.write("Gemini AI 분석 중...")
                editor = AIEditor(GEMINI_API_KEY)
                report_content = editor.generate_report(articles)
                st.write("✅ 리포트 생성 완료")

                # Step 3: Save to GitHub
                st.write("GitHub에 저장 중...")
                today_str = datetime.now().strftime("%Y-%m-%d")
                
                # Update data structure
                if "reports" not in data:
                    data["reports"] = {}
                data["reports"][today_str] = report_content
                
                if "stats" not in data:
                    data["stats"] = {}
                data["stats"]["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                storage.save_data(data, st.session_state.sha, commit_message=f"Update report for {today_str}")
                load_data() # Reload
                
                status.update(label="업데이트 완료!", state="complete", expanded=False)
                st.success("데이터가 성공적으로 업데이트되었습니다.")
                st.rerun()

    elif password:
        st.error("비밀번호가 틀렸습니다.")

else:
    # User Mode - View Report
    if selected_date:
        st.title(f"🗓️ {selected_date} 브리핑")
        report_content = data["reports"].get(selected_date, "내용이 없습니다.")
        st.markdown(report_content)
    else:
        st.title("👋 AI Insight Newsroom")
        st.info("아직 생성된 리포트가 없습니다. 관리자 모드에서 업데이트를 진행해주세요.")

    # Visit Counter (Simple increment on load)
    # Note: In a real app, we'd need a more robust way to count visits to avoid updating GitHub on every refresh.
    # For now, we'll just display what's in the JSON.
