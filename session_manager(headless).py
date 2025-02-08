from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options


class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.busy_users = set()  # Track users who are currently in an operation

    def is_user_busy(self, user_id):
        """Check if user is currently performing an operation"""
        return user_id in self.busy_users

    def set_user_busy(self, user_id, busy=True):
        """Set user's busy status"""
        if busy:
            self.busy_users.add(user_id)
        else:
            self.busy_users.discard(user_id)

    def get_session(self, user_id):
        """Get existing session or create new one"""
        if user_id in self.sessions and self.sessions[user_id]['driver']:
            return self.sessions[user_id]

        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Enable headless mode
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920x1080')

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

        self.sessions[user_id] = {'driver': driver}
        return self.sessions[user_id]

    def close_session(self, user_id):
        """Close and remove session"""
        if user_id in self.sessions:
            try:
                self.sessions[user_id]['driver'].quit()
            except:
                pass
            del self.sessions[user_id]
        self.set_user_busy(user_id, False)  # Make sure to clear busy status

    def close_all_sessions(self):
        """Close all active sessions"""
        for user_id in list(self.sessions.keys()):
            self.close_session(user_id)
        self.busy_users.clear()


session_manager = SessionManager()
