"""
수집기 베이스 클래스
"""
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from database import get_db, CollectionLog


class BaseCollector(ABC):
    """모든 수집기의 기본 클래스"""

    def __init__(self, name: str):
        self.name = name
        self.collected_count = 0
        self.inserted_count = 0
        self.updated_count = 0
        self.errors = []

    @abstractmethod
    def collect(self) -> List[Dict[str, Any]]:
        """데이터 수집 (동기)"""
        pass

    @abstractmethod
    async def collect_async(self) -> List[Dict[str, Any]]:
        """데이터 수집 (비동기)"""
        pass

    @abstractmethod
    def save(self, items: List[Dict[str, Any]]) -> None:
        """수집된 데이터 저장"""
        pass

    def run(self) -> Dict[str, Any]:
        """수집 실행 및 로깅"""
        started_at = datetime.utcnow()
        status = "success"
        error_msg = None

        try:
            logger.info(f"[{self.name}] 수집 시작")
            items = self.collect()
            self.collected_count = len(items)

            if items:
                self.save(items)

            logger.info(f"[{self.name}] 수집 완료: {self.collected_count}건")

        except Exception as e:
            status = "failed"
            error_msg = str(e)
            self.errors.append(error_msg)
            logger.error(f"[{self.name}] 수집 실패: {error_msg}")

        finished_at = datetime.utcnow()

        # 로그 저장
        try:
            with get_db() as db:
                log = CollectionLog(
                    collector_name=self.name,
                    status=status,
                    items_collected=self.collected_count,
                    items_inserted=self.inserted_count,
                    items_updated=self.updated_count,
                    error_message=error_msg,
                    started_at=started_at,
                    finished_at=finished_at,
                )
                db.add(log)
        except Exception as e:
            logger.error(f"[{self.name}] 로그 저장 실패: {e}")

        return {
            "collector": self.name,
            "status": status,
            "collected": self.collected_count,
            "inserted": self.inserted_count,
            "updated": self.updated_count,
            "errors": self.errors,
        }

    async def run_async(self) -> Dict[str, Any]:
        """비동기 수집 실행"""
        started_at = datetime.utcnow()
        status = "success"
        error_msg = None

        try:
            logger.info(f"[{self.name}] 비동기 수집 시작")
            items = await self.collect_async()
            self.collected_count = len(items)

            if items:
                # 비동기 컨텍스트에서 DB 작업은 동기로 처리
                await asyncio.to_thread(self.save, items)

            logger.info(f"[{self.name}] 비동기 수집 완료: {self.collected_count}건")

        except Exception as e:
            status = "failed"
            error_msg = str(e)
            self.errors.append(error_msg)
            logger.error(f"[{self.name}] 비동기 수집 실패: {error_msg}")

        finished_at = datetime.utcnow()

        try:
            with get_db() as db:
                log = CollectionLog(
                    collector_name=self.name,
                    status=status,
                    items_collected=self.collected_count,
                    items_inserted=self.inserted_count,
                    items_updated=self.updated_count,
                    error_message=error_msg,
                    started_at=started_at,
                    finished_at=finished_at,
                )
                db.add(log)
        except Exception as e:
            logger.error(f"[{self.name}] 로그 저장 실패: {e}")

        return {
            "collector": self.name,
            "status": status,
            "collected": self.collected_count,
            "inserted": self.inserted_count,
            "updated": self.updated_count,
            "errors": self.errors,
        }
