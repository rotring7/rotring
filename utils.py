import json
import time
from datetime import datetime, timedelta
import base64
import feedparser
import google.generativeai as genai
from github import Github, GithubException
import streamlit as st

class GithubStorage:
    def __init__(self, token, repo_name, file_path="news_data.json"):
        self.github = Github(token)
        self.repo = self.github.get_repo(repo_name)
        self.file_path = file_path

    def load_data(self):
        try:
            contents = self.repo.get_contents(self.file_path)
            json_str = base64.b64decode(contents.content).decode("utf-8")
            return json.loads(json_str), contents.sha
        except GithubException as e:
            if e.status == 404:
                # If file doesn't exist, return default structure and None for SHA
                return {
                    "feeds": [],
                    "reports": {},
                    "stats": {"visits": 0, "last_updated": ""}
                }, None
            raise e

    def verify_access(self):
        """Verifies if the token has access to the repository."""
        try:
            # Try to get the repo object properties to ensure it exists and is accessible
            _ = self.repo.full_name
            return True, f"Successfully connected to {self.repo.full_name}"
        except GithubException as e:
            if e.status == 404:
                return False, f"Repository '{self.repo.name}' not found or token has insufficient permissions."
            return False, f"GitHub Error: {str(e)}"

    def save_data(self, data, sha=None, commit_message="Update news data"):
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        # Get default branch
        try:
            branch = self.repo.default_branch
        except:
            branch = "main" # Fallback

        if sha:
            self.repo.update_file(self.file_path, commit_message, json_str, sha, branch=branch)
        else:
            self.repo.create_file(self.file_path, commit_message, json_str, branch=branch)

class NewsAggregator:
    def __init__(self, feeds):
        self.feeds = feeds

    def fetch_and_filter(self, days=3):
        articles = []
        limit_date = datetime.now() - timedelta(days=days)
        
        for feed_url in self.feeds:
            parsed_feed = feedparser.parse(feed_url)
            source_title = parsed_feed.feed.get('title', 'Unknown Source')
            
            for entry in parsed_feed.entries:
                # published_parsed is a struct_time
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published_dt = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                    if published_dt >= limit_date:
                        articles.append({
                            'title': entry.title,
                            'link': entry.link,
                            'source': source_title,
                            'published': published_dt.strftime('%Y-%m-%d %H:%M:%S')
                        })
        return articles

class AIEditor:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    def generate_report(self, articles):
        if not articles:
            return "## 분석할 뉴스가 없습니다."

        # Prepare input for Gemini
        news_text = ""
        for idx, article in enumerate(articles):
            news_text += f"{idx+1}. [{article['source']}] {article['title']} - {article['link']}\n"

        system_prompt = """
        당신은 수석 IT 에디터입니다.
        주어지는 뉴스 리스트를 바탕으로 'A4 1장 분량의 핵심 요약 보고서'를 작성하세요.
        
        **지시사항:**
        1. 언어: 한국어
        2. 형식: Markdown
        3. 구조: 유사한 주제끼리 **토픽(Topic)**으로 그룹화하여 헤더(###)로 구분하세요.
        4. 내용: 각 기사의 핵심 내용을 명확하고 간결하게 요약하세요.
        5. 출처: 각 요약문 끝에 반드시 `[기사제목](링크)` 형태로 원문 링크를 포함하세요.
        6. 서두에 전체적인 트렌드 요약을 3줄 내외로 작성하세요.
        """

        try:
            response = self.model.generate_content(f"{system_prompt}\n\n**뉴스 리스트:**\n{news_text}")
            return response.text
        except Exception as e:
            return f"## AI 분석 중 오류 발생\n{str(e)}"
