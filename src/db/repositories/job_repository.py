from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from src.db.models.job import CrawlJob
from src.core.constants import JobStatus


class JobRepository:
    """Repository for CrawlJob operations"""

    @staticmethod
    def create(
        db: Session,
        url: str,
        max_depth: int = 3,
        max_pages: int = 100,
        respect_robots_txt: bool = True,
        user_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> CrawlJob:
        """Create a new crawl job"""
        job = CrawlJob(
            url=url,
            max_depth=max_depth,
            max_pages=max_pages,
            respect_robots_txt=respect_robots_txt,
            user_id=user_id,
            metadata=metadata,
            status=JobStatus.PENDING.value
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def get(db: Session, job_id: UUID) -> Optional[CrawlJob]:
        """Get job by ID"""
        return db.query(CrawlJob).filter(CrawlJob.id == job_id).first()

    @staticmethod
    def get_by_celery_task_id(db: Session, celery_task_id: str) -> Optional[CrawlJob]:
        """Get job by Celery task ID"""
        return db.query(CrawlJob).filter(CrawlJob.celery_task_id == celery_task_id).first()

    @staticmethod
    def list_jobs(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> List[CrawlJob]:
        """List jobs with optional filtering"""
        query = db.query(CrawlJob)

        if status:
            query = query.filter(CrawlJob.status == status)
        if user_id:
            query = query.filter(CrawlJob.user_id == user_id)

        return query.order_by(CrawlJob.created_at.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def update_status(
        db: Session,
        job_id: UUID,
        status: str,
        error_message: Optional[str] = None
    ) -> Optional[CrawlJob]:
        """Update job status"""
        job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
        if job:
            job.status = status

            if status == JobStatus.IN_PROGRESS.value and not job.started_at:
                job.started_at = datetime.utcnow()
            elif status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value]:
                job.completed_at = datetime.utcnow()

            if error_message:
                job.error_message = error_message

            db.commit()
            db.refresh(job)
        return job

    @staticmethod
    def update_celery_task_id(db: Session, job_id: UUID, celery_task_id: str) -> Optional[CrawlJob]:
        """Update Celery task ID"""
        job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
        if job:
            job.celery_task_id = celery_task_id
            db.commit()
            db.refresh(job)
        return job

    @staticmethod
    def increment_pages_crawled(db: Session, job_id: UUID) -> Optional[CrawlJob]:
        """Increment pages crawled counter"""
        job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
        if job:
            job.total_pages_crawled += 1
            db.commit()
            db.refresh(job)
        return job

    @staticmethod
    def increment_links_found(db: Session, job_id: UUID, count: int = 1) -> Optional[CrawlJob]:
        """Increment links found counter"""
        job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
        if job:
            job.total_links_found += count
            db.commit()
            db.refresh(job)
        return job

    @staticmethod
    def increment_broken_links(db: Session, job_id: UUID) -> Optional[CrawlJob]:
        """Increment broken links counter"""
        job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
        if job:
            job.total_broken_links += 1
            db.commit()
            db.refresh(job)
        return job

    @staticmethod
    def delete(db: Session, job_id: UUID) -> bool:
        """Delete a job (cascades to related records)"""
        job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
        if job:
            db.delete(job)
            db.commit()
            return True
        return False
