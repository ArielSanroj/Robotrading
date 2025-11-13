import threading
import queue
import smtplib
from email.message import EmailMessage
from typing import Optional, List, Dict


class EmailQueue:
    def __init__(self, smtp_server: str, smtp_port: int, username: str, password: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self._queue: "queue.Queue[Dict]" = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._started = False

    def start(self):
        if not self._started:
            self._thread.start()
            self._started = True

    def enqueue(self, subject: str, content: str, recipients: List[str]):
        self._queue.put({"subject": subject, "content": content, "recipients": recipients})

    def _worker(self):
        while True:
            item = self._queue.get()
            try:
                self._send_email(item["subject"], item["content"], item["recipients"])
            except Exception:
                # Best-effort; errors are swallowed here to avoid blocking trading loop
                pass
            finally:
                self._queue.task_done()

    def _send_email(self, subject: str, content: str, recipients: List[str]):
        msg = EmailMessage()
        msg.set_content(content)
        msg["Subject"] = subject
        msg["From"] = self.username
        for recipient in recipients:
            msg["To"] = recipient
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as smtp:
                smtp.login(self.username, self.password)
                smtp.send_message(msg)
