import os
import sqlite3
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("MockMentorDB")

class DatabaseManager:
    def __init__(self, db_path: str = None):
        if not db_path:
            # Check for DATABASE_URL env var
            db_url = os.getenv("DATABASE_URL", "")
            if db_url.startswith("sqlite:///"):
                db_path = db_url.replace("sqlite:///", "")
            else:
                # Fallback to local path relative to current file
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                db_path = os.path.join(base_dir, "data", "mockmentor.db")
        
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.initialize_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize_db(self):
        """Initializes the database using schema.sql if tables do not exist."""
        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
        if not os.path.exists(schema_path):
            logger.warning(f"schema.sql not found at {schema_path}, skipping initialization.")
            return

        with open(schema_path, "r") as f:
            schema_sql = f.read()

        conn = self._get_connection()
        try:
            conn.executescript(schema_sql)
            conn.commit()
            logger.info("Database initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_or_create_user(self, name: str, domain: str) -> int:
        """Retrieves user ID or creates a new user if not found."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Check if user already exists
            cursor.execute(
                "SELECT id FROM users WHERE name = ? AND domain = ?",
                (name.strip(), domain.strip())
            )
            row = cursor.fetchone()
            if row:
                return row["id"]
            
            # Create new user
            cursor.execute(
                "INSERT INTO users (name, domain) VALUES (?, ?)",
                (name.strip(), domain.strip())
            )
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error in get_or_create_user: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_session(self, session_id: str, user_id: int, mode: str, jd_text: str, resume_text: str):
        """Creates a new interview session record."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO sessions (id, user_id, mode, jd_text, resume_text) VALUES (?, ?, ?, ?, ?)",
                (session_id, user_id, mode, jd_text.strip(), resume_text.strip())
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Error in create_session: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Gets session details along with candidate name and domain."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT s.id, s.user_id, s.mode, s.jd_text, s.resume_text, s.date,
                       u.name as user_name, u.domain
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.id = ?
                """,
                (session_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error in get_session: {e}")
            raise
        finally:
            conn.close()

    def save_question_history(
        self,
        session_id: str,
        question: str,
        answer: str,
        score: int,
        feedback: str,
        weaknesses: str
    ):
        """Saves a question-answer evaluation instance to the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO questions_history (session_id, question, answer, score, feedback, weaknesses)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, question, answer, score, feedback, weaknesses)
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Error in save_question_history: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Gets all question-evaluation pairs for a session."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT question, answer, score, feedback, weaknesses FROM questions_history WHERE session_id = ? ORDER BY id ASC",
                (session_id,)
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Error in get_session_history: {e}")
            raise
        finally:
            conn.close()

    def get_user_weakspots(self, user_id: int) -> List[Dict[str, Any]]:
        """Gets the weakness profile (topics, ratings) for a candidate."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT topic, rating, times_tested FROM weakspots WHERE user_id = ? ORDER BY rating ASC",
                (user_id,)
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Error in get_user_weakspots: {e}")
            raise
        finally:
            conn.close()

    def update_user_weakspots(self, user_id: int, topic: str, score: int):
        """Updates the weakness score and times tested for a specific topic."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Check if topic already exists
            cursor.execute(
                "SELECT rating, times_tested FROM weakspots WHERE user_id = ? AND topic = ?",
                (user_id, topic)
            )
            row = cursor.fetchone()
            if row:
                current_rating = row["rating"]
                times = row["times_tested"]
                # Weighted average update for rating: (old_rating * old_times + new_score) / (old_times + 1)
                new_rating = int((current_rating * times + score) / (times + 1))
                new_times = times + 1
                cursor.execute(
                    """
                    UPDATE weakspots
                    SET rating = ?, times_tested = ?, last_tested_date = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND topic = ?
                    """,
                    (new_rating, new_times, user_id, topic)
                )
            else:
                # Insert new weak spot
                cursor.execute(
                    """
                    INSERT INTO weakspots (user_id, topic, rating, times_tested)
                    VALUES (?, ?, ?, 1)
                    """,
                    (user_id, topic, score)
                )
            conn.commit()
        except Exception as e:
            logger.error(f"Error in update_user_weakspots: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
