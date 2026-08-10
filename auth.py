import http.server
import socketserver
import urllib.parse
import webbrowser
import threading
import time
from typing import Optional, Callable

# OAuth 2.0 Config Constants for standard providers
AUTH_ENDPOINTS = {
    "codex": {
        "name": "OpenAI / GPT",
        "auth_url": "https://platform.openai.com/account/api-keys", # 사용자 직관적 API Key / Auth 브라우저 자동 페이지
    },
    "antigravity": {
        "name": "Google Gemini",
        "auth_url": "https://aistudio.google.com/app/apikey", # Google AI Studio 원클릭 키/토큰 자동 페이지
    },
    "claude": {
        "name": "Anthropic Claude",
        "auth_url": "https://console.anthropic.com/settings/keys", # Anthropic Console 자동 브라우저 연결
    },
    "deepseek": {
        "name": "DeepSeek AI",
        "auth_url": "https://platform.deepseek.com/api_keys",
    },
    "grok": {
        "name": "xAI Grok",
        "auth_url": "https://console.x.ai/",
    }
}

class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    token_received_callback: Optional[Callable[[str], None]] = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        token = None
        if "code" in params:
            token = params["code"][0]
        elif "token" in params:
            token = params["token"][0]
        elif "key" in params:
            token = params["key"][0]

        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>SynapCap 계정 연동 완료</title>
            <style>
                body { background-color: #1E1E2E; color: #CDD6F4; font-family: sans-serif; text-align: center; padding-top: 50px; }
                .card { background: #313244; display: inline-block; padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
                h1 { color: #A6E3A1; margin-bottom: 10px; }
                p { color: #BAC2DE; font-size: 16px; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>✓ 계정 연동이 성공적으로 완료되었습니다!</h1>
                <p>SynapCap 앱으로 돌아가시면 자동으로 설정이 반영됩니다.</p>
                <p>이 웹 브라우저 창을 닫으셔도 좋습니다.</p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html_content.encode("utf-8"))

        if token and OAuthCallbackHandler.token_received_callback:
            OAuthCallbackHandler.token_received_callback(token)

    def log_message(self, format, *args):
        pass  # 로깅 억제

def open_browser_login(provider_type: str, callback_on_token: Callable[[str], None]):
    """
    브라우저를 열어 계정 로그인 및 인증을 안내하고, 인증 완료를 감지하는 함수
    """
    p_info = AUTH_ENDPOINTS.get(provider_type.lower(), {
        "name": provider_type,
        "auth_url": "https://google.com"
    })
    
    url = p_info["auth_url"]
    
    # 1. 시스템 기본 브라우저로 계정 로그인 페이지 열기
    webbrowser.open(url)
