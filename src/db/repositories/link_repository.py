from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID
from src.db.models.broken_link import BrokenLink
from src.db.models.visited_url import VisitedUrl
import hashlib


class LinkRepository:
    """Repository for link-related operations"""

    @staticmethod
    def create_broken_link(
        db: Session,
        job_id: UUID,
        source_url: str,
        broken_url: str,
        anchor_text: Optional[str] = None,
        status_code: Optional[int] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        depth: Optional[int] = None
    ) -> BrokenLink:
        """Create a new broken link record"""
        broken_link = BrokenLink(
            job_id=job_id,
            source_url=source_url,
            broken_url=broken_url,
            anchor_text=anchor_text,
            status_code=status_code,
            error_type=error_type,
            error_message=error_message,
            depth=depth
        )
        db.add(broken_link)
        db.commit()
        db.refresh(broken_link)
        return broken_link

    @staticmethod
    def get_broken_links_by_job(
        db: Session,
        job_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[BrokenLink]:
        """Get broken links for a job"""
        return db.query(BrokenLink).filter(
            BrokenLink.job_id == job_id
        ).order_by(
            BrokenLink.discovered_at.desc()
        ).offset(skip).limit(limit).all()

    @staticmethod
    def count_broken_links_by_job(db: Session, job_id: UUID) -> int:
        """Count broken links for a job"""
        return db.query(BrokenLink).filter(BrokenLink.job_id == job_id).count()

    @staticmethod
    def create_visited_url(
        db: Session,
        job_id: UUID,
        url: str,
        normalized_url: str,
        depth: Optional[int] = None,
        status_code: Optional[int] = None,
        content_type: Optional[str] = None
    ) -> VisitedUrl:
        """Create a visited URL record"""
        url_hash = hashlib.sha256(normalized_url.encode()).hexdigest()

        visited = VisitedUrl(
            job_id=job_id,
            url_hash=url_hash,
            original_url=url,
            normalized_url=normalized_url,
            depth=depth,
            status_code=status_code,
            content_type=content_type
        )
        db.add(visited)
        db.commit()
        db.refresh(visited)
        return visited

    @staticmethod
    def is_url_visited(db: Session, job_id: UUID, normalized_url: str) -> bool:
        """Check if a URL has been visited in this job"""
        url_hash = hashlib.sha256(normalized_url.encode()).hexdigest()
        return db.query(VisitedUrl).filter(
            VisitedUrl.job_id == job_id,
            VisitedUrl.url_hash == url_hash
        ).first() is not None

    @staticmethod
    def get_visited_urls_by_job(
        db: Session,
        job_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[VisitedUrl]:
        """Get visited URLs for a job"""
        return db.query(VisitedUrl).filter(
            VisitedUrl.job_id == job_id
        ).order_by(
            VisitedUrl.visited_at.desc()
        ).offset(skip).limit(limit).all()
