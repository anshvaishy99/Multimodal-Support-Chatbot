from typing import Dict, List, Optional, Sequence, Tuple

import mysql.connector
from mysql.connector import Error

from app.config import settings


class DatabaseUnavailable(RuntimeError):
    pass


class Database:
    def _connect(self):
        try:
            return mysql.connector.connect(
                host=settings.mysql_host,
                port=settings.mysql_port,
                user=settings.mysql_user,
                password=settings.mysql_password,
                database=settings.mysql_database,
                connection_timeout=5,
            )
        except Error as exc:
            raise DatabaseUnavailable("MySQL is unavailable.") from exc

    def check_connection(self) -> bool:
        connection = self._connect()
        connection.close()
        return True

    def ensure_schema(self, cursor):
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                filename VARCHAR(255) NOT NULL,
                mime_type VARCHAR(100) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS document_chunks (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                document_id BIGINT NOT NULL,
                page_number INT NULL,
                chunk_text TEXT NOT NULL,
                INDEX idx_document_chunks_document_id (document_id),
                CONSTRAINT fk_document_chunks_document
                    FOREIGN KEY (document_id) REFERENCES documents(id)
                    ON DELETE CASCADE
            ) CHARACTER SET utf8mb4
            """
        )

    def add_document(self, filename: str, mime_type: str, chunks: Sequence[Tuple[Optional[int], str]]) -> int:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            self.ensure_schema(cursor)
            cursor.execute(
                "INSERT INTO documents (filename, mime_type) VALUES (%s, %s)",
                (filename, mime_type),
            )
            document_id = cursor.lastrowid
            cursor.executemany(
                "INSERT INTO document_chunks (document_id, page_number, chunk_text) "
                "VALUES (%s, %s, %s)",
                [(document_id, page, text) for page, text in chunks],
            )
            connection.commit()
            cursor.close()
            return document_id
        except Error as exc:
            connection.rollback()
            raise DatabaseUnavailable("Could not save the uploaded document.") from exc
        finally:
            connection.close()

    def search_candidates(self) -> List[Dict]:
        connection = self._connect()
        try:
            cursor = connection.cursor(dictionary=True)
            self.ensure_schema(cursor)
            cursor.execute(
                """
                SELECT d.filename, c.page_number, c.chunk_text
                FROM document_chunks AS c
                JOIN documents AS d ON d.id = c.document_id
                ORDER BY c.id DESC
                LIMIT 2000
                """
            )
            return cursor.fetchall()
        except Error as exc:
            raise DatabaseUnavailable("Could not retrieve document passages.") from exc
        finally:
            connection.close()

    def list_documents(self) -> List[Dict]:
        connection = self._connect()
        try:
            cursor = connection.cursor(dictionary=True)
            self.ensure_schema(cursor)
            cursor.execute(
                "SELECT id, filename, created_at FROM documents ORDER BY id DESC"
            )
            return cursor.fetchall()
        except Error as exc:
            raise DatabaseUnavailable("Could not list uploaded documents.") from exc
        finally:
            connection.close()


database = Database()
