import uuid
import logging
from typing import List, Optional, Tuple, Dict, Any, Set
from datetime import datetime, timezone
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, update, select, text

from app.models.discovery_job import DiscoveryJob
from app.models.search_query import SearchQuery
from app.models.website import Website
from app.models.discovery_source import DiscoverySource
from app.models.website_verification import WebsiteVerification
from app.models.contact import Contact
from app.models.processing_error import ProcessingError
from app.models.enums import DiscoveryJobStatus, ProcessingStage, VerificationStatus
from app.schemas.search import GeneratedSearchQuery, NormalizedCandidate
from app.schemas.verification import VerificationResult
from app.schemas.contact_discovery import ContactDiscoveryResult
from app.config import get_settings

logger = logging.getLogger(__name__)

class InvalidJobTransition(Exception):
    pass

class JobNotFound(Exception):
    pass

class IncompleteJobFinalization(Exception):
    pass

class PersistenceFailure(Exception):
    pass

class PersistenceConflict(Exception):
    pass

@dataclass
class WebsiteUpsertResult:
    website: Website
    created: bool

@dataclass
class ContactPersistenceSummary:
    created: int = 0
    reused: int = 0
    emails: int = 0
    forms: int = 0

def is_unique_violation(exc: IntegrityError) -> bool:
    original = getattr(exc, "orig", None)
    sqlstate = getattr(original, "sqlstate", getattr(original, "pgcode", None))
    if sqlstate == "23505":
        return True
    msg = str(exc).lower()
    if "unique constraint failed" in msg:
        return True
    return False

class DiscoveryPersistenceService:
    def __init__(self, session: Session):
        self.session = session
        self.settings = get_settings()

    def start_job(self, job_id: uuid.UUID) -> DiscoveryJob:
        stmt = (
            update(DiscoveryJob)
            .where(
                DiscoveryJob.id == job_id,
                DiscoveryJob.status.in_([
                    DiscoveryJobStatus.pending,
                    DiscoveryJobStatus.failed,
                    DiscoveryJobStatus.completed_with_errors
                ])
            )
            .values(
                status=DiscoveryJobStatus.running,
                attempt_number=DiscoveryJob.attempt_number + 1,
                started_at=func.now(),
                completed_at=None
            )
            .returning(DiscoveryJob)
        )
        job = self.session.execute(stmt).scalar_one_or_none()

        if job is None:
            existing = self.session.execute(
                select(DiscoveryJob.status).where(DiscoveryJob.id == job_id)
            ).scalar_one_or_none()
            if existing is None:
                raise JobNotFound(f"Job {job_id} not found")
            raise InvalidJobTransition(f"Cannot start job {job_id} from state {existing}")

        self.session.commit()
        return job

    def persist_generated_queries(self, job_id: uuid.UUID, generated_queries: List[GeneratedSearchQuery]) -> List[SearchQuery]:
        result_queries = []
        for gq in generated_queries:
            try:
                with self.session.begin_nested():
                    query = self.session.execute(
                        select(SearchQuery)
                        .where(
                            SearchQuery.discovery_job_id == job_id,
                            SearchQuery.query_text == gq.query_text
                        )
                    ).scalar_one_or_none()

                    if not query:
                        query = SearchQuery(
                            discovery_job_id=job_id,
                            query_text=gq.query_text,
                            category=gq.category,
                            market=gq.market,
                            language=gq.language,
                            provider=self.settings.SEARCH_PROVIDER,
                            requested_limit=self.settings.SEARCH_RESULTS_PER_QUERY,
                            status="pending"
                        )
                        self.session.add(query)
                        self.session.flush()
                result_queries.append(query)
            except IntegrityError as exc:
                if not is_unique_violation(exc):
                    raise PersistenceFailure("Query persistence failed") from exc

                query = self.session.execute(
                    select(SearchQuery)
                    .where(
                        SearchQuery.discovery_job_id == job_id,
                        SearchQuery.query_text == gq.query_text
                    )
                ).scalar_one_or_none()
                if not query:
                    raise PersistenceConflict("Unique conflict but no existing query found") from exc
                result_queries.append(query)

        self.session.commit()
        return result_queries

    def mark_query_completed(self, query_id: uuid.UUID, result_count: int) -> None:
        stmt = (
            update(SearchQuery)
            .where(SearchQuery.id == query_id)
            .values(
                status="completed",
                result_count=result_count,
                completed_at=func.now(),
                attempt_count=SearchQuery.attempt_count + 1
            )
        )
        self.session.execute(stmt)
        self.session.commit()

    def mark_query_failed(self, query_id: uuid.UUID, safe_error: str) -> None:
        stmt = (
            update(SearchQuery)
            .where(
                SearchQuery.id == query_id,
                SearchQuery.status != "completed"
            )
            .values(
                status="failed",
                error_message=safe_error[:1000] if safe_error else None,
                attempt_count=SearchQuery.attempt_count + 1
            )
        )
        self.session.execute(stmt)
        self.session.commit()

    def _determine_canonical_key(self, candidate: NormalizedCandidate) -> str:
        is_multitenant = candidate.registered_domain in self.settings.MULTITENANT_HOSTING_DOMAINS
        if is_multitenant:
            return f"{candidate.subdomain}.{candidate.registered_domain}" if candidate.subdomain else candidate.registered_domain
        return candidate.registered_domain

    def upsert_website(self, candidate: NormalizedCandidate) -> WebsiteUpsertResult:
        canonical_key = self._determine_canonical_key(candidate)
        is_multitenant = candidate.registered_domain in self.settings.MULTITENANT_HOSTING_DOMAINS

        try:
            with self.session.begin_nested():
                website = self.session.execute(
                    select(Website).where(Website.canonical_key == canonical_key)
                ).scalar_one_or_none()

                if website:
                    if not website.name and candidate.title:
                        website.name = candidate.title
                    if not website.description and candidate.snippet:
                        website.description = candidate.snippet
                    if not website.homepage_url:
                        website.homepage_url = candidate.homepage_url
                    return WebsiteUpsertResult(website=website, created=False)

                website = Website(
                    domain=candidate.registered_domain if not is_multitenant else f"{candidate.subdomain}.{candidate.registered_domain}",
                    canonical_key=canonical_key,
                    is_multitenant=is_multitenant,
                    homepage_url=candidate.homepage_url,
                    name=candidate.title,
                    description=candidate.snippet,
                    country=candidate.market,
                    language=candidate.language
                )
                self.session.add(website)
                self.session.flush()
            return WebsiteUpsertResult(website=website, created=True)
        except IntegrityError as exc:
            if not is_unique_violation(exc):
                raise PersistenceFailure("Website upsert failed") from exc

            website = self.session.execute(
                select(Website).where(Website.canonical_key == canonical_key)
            ).scalar_one_or_none()
            if not website:
                raise PersistenceConflict("Unique conflict but no existing website found") from exc

            if not website.name and candidate.title:
                website.name = candidate.title
            if not website.description and candidate.snippet:
                website.description = candidate.snippet
            if not website.homepage_url:
                website.homepage_url = candidate.homepage_url
            return WebsiteUpsertResult(website=website, created=False)

    def get_existing_canonical_keys(self, keys: List[str]) -> Set[str]:
        if not keys:
            return set()
        stmt = select(Website.canonical_key).where(Website.canonical_key.in_(keys))
        return set(self.session.execute(stmt).scalars().all())

    def persist_discovery_source(self, job: DiscoveryJob, query: SearchQuery, website: Website, candidate: NormalizedCandidate) -> DiscoverySource:
        try:
            with self.session.begin_nested():
                source = self.session.execute(
                    select(DiscoverySource)
                    .where(
                        DiscoverySource.website_id == website.id,
                        DiscoverySource.discovery_job_id == job.id,
                        DiscoverySource.query_text == query.query_text,
                        DiscoverySource.result_url == candidate.original_url
                    )
                ).scalar_one_or_none()

                if source:
                    return source

                source = DiscoverySource(
                    website_id=website.id,
                    discovery_job_id=job.id,
                    search_query_id=query.id,
                    provider=candidate.provider,
                    query_text=query.query_text,
                    result_url=candidate.original_url,
                    result_title=candidate.title,
                    result_snippet=candidate.snippet,
                    result_position=candidate.result_position
                )
                self.session.add(source)
                self.session.flush()
            return source
        except IntegrityError as exc:
            if not is_unique_violation(exc):
                raise PersistenceFailure("DiscoverySource persistence failed") from exc

            source = self.session.execute(
                select(DiscoverySource)
                .where(
                    DiscoverySource.website_id == website.id,
                    DiscoverySource.discovery_job_id == job.id,
                    DiscoverySource.query_text == query.query_text,
                    DiscoverySource.result_url == candidate.original_url
                )
            ).scalar_one_or_none()
            if not source:
                raise PersistenceConflict("Unique conflict but no existing source found") from exc
            return source

    def persist_verification(self, job: DiscoveryJob, website: Website, result: VerificationResult) -> WebsiteVerification:
        try:
            with self.session.begin_nested():
                verif = self.session.execute(
                    select(WebsiteVerification)
                    .where(
                        WebsiteVerification.website_id == website.id,
                        WebsiteVerification.discovery_job_id == job.id,
                        WebsiteVerification.attempt_number == job.attempt_number,
                        WebsiteVerification.classifier_version == result.classifier_version
                    )
                ).scalar_one_or_none()

                if verif:
                    return verif

                positive_reasons = [{"code": r.code, "evidence": r.evidence[:300]} for r in result.positive_reasons][:20]
                negative_reasons = [{"code": r.code, "evidence": r.evidence[:300]} for r in result.negative_reasons][:20]

                status = VerificationStatus(result.status)

                verif = WebsiteVerification(
                    website_id=website.id,
                    discovery_job_id=job.id,
                    score=result.score,
                    status=status,
                    confidence=result.confidence,
                    positive_reasons=positive_reasons,
                    negative_reasons=negative_reasons,
                    detected_categories=result.detected_categories[:5],
                    activity_status="active" if result.is_active else "inactive",
                    classifier_version=result.classifier_version,
                    attempt_number=job.attempt_number,
                    homepage_title=result.metadata.title[:500] if result.metadata and result.metadata.title else None,
                    homepage_description=result.metadata.description[:1000] if result.metadata and result.metadata.description else None
                )
                self.session.add(verif)

                # Update denormalized fields on the website
                website.current_verification_status = status
                website.current_verification_score = result.score
                website.current_activity_status = "active" if result.is_active else "inactive"

                self.session.flush()
            return verif
        except IntegrityError as exc:
            if not is_unique_violation(exc):
                raise PersistenceFailure("Verification persistence failed") from exc

            verif = self.session.execute(
                select(WebsiteVerification)
                .where(
                    WebsiteVerification.website_id == website.id,
                    WebsiteVerification.discovery_job_id == job.id,
                    WebsiteVerification.attempt_number == job.attempt_number,
                    WebsiteVerification.classifier_version == result.classifier_version
                )
            ).scalar_one_or_none()
            if not verif:
                raise PersistenceConflict("Unique conflict but no existing verification found") from exc
            return verif

    def persist_contacts(self, job: DiscoveryJob, website: Website, result: ContactDiscoveryResult) -> ContactPersistenceSummary:
        summary = ContactPersistenceSummary()
        summary.emails = len(result.emails)
        summary.forms = len(result.forms)

        for email_contact in result.emails:
            email_lower = email_contact.email.lower()

            c_type = getattr(email_contact, "primary_type", getattr(email_contact, "contact_type", "unknown"))
            s_url = ""
            if getattr(email_contact, "evidence", None) and len(email_contact.evidence) > 0:
                s_url = email_contact.evidence[0].source_url
            elif getattr(email_contact, "source_url", None):
                s_url = getattr(email_contact, "source_url")
            else:
                s_url = website.homepage_url

            is_prim = getattr(email_contact, "is_primary", False)
            if getattr(result, "best_contact", None) and result.best_contact.email == email_contact.email:
                is_prim = True

            try:
                with self.session.begin_nested():
                    existing = self.session.execute(
                        select(Contact)
                        .where(Contact.website_id == website.id, func.lower(Contact.email) == email_lower)
                    ).scalar_one_or_none()

                    if existing:
                        if existing.confidence < email_contact.confidence:
                            existing.confidence = email_contact.confidence
                            existing.contact_type = c_type
                            existing.source_url = s_url
                        existing.discovery_job_id = job.id
                        summary.reused += 1
                    else:
                        c = Contact(
                            website_id=website.id,
                            discovery_job_id=job.id,
                            email=email_contact.email,
                            contact_type=c_type,
                            source_url=s_url,
                            confidence=email_contact.confidence,
                            is_primary=is_prim,
                            is_active=True
                        )
                        self.session.add(c)
                        self.session.flush()
                        summary.created += 1
            except IntegrityError as exc:
                if not is_unique_violation(exc):
                    raise PersistenceFailure("Contact email persistence failed") from exc

                existing = self.session.execute(
                    select(Contact)
                    .where(Contact.website_id == website.id, func.lower(Contact.email) == email_lower)
                ).scalar_one_or_none()
                if not existing:
                    raise PersistenceConflict("Unique conflict but no existing email contact found") from exc
                if existing.confidence < email_contact.confidence:
                    existing.confidence = email_contact.confidence
                    existing.contact_type = c_type
                    existing.source_url = s_url
                existing.discovery_job_id = job.id
                summary.reused += 1

        for form_contact in result.forms:
            c_type = getattr(form_contact, "purpose", getattr(form_contact, "contact_type", "unknown"))
            s_url = getattr(form_contact, "page_url", getattr(form_contact, "source_url", website.homepage_url))
            is_prim = getattr(form_contact, "is_primary", False)
            form_u = getattr(form_contact, "page_url", getattr(form_contact, "form_url", None))

            try:
                with self.session.begin_nested():
                    existing = self.session.execute(
                        select(Contact)
                        .where(Contact.website_id == website.id, Contact.contact_form_url == form_u)
                    ).scalar_one_or_none()

                    if existing:
                        if existing.confidence < form_contact.confidence:
                            existing.confidence = form_contact.confidence
                            existing.contact_type = c_type
                            existing.source_url = s_url
                        existing.discovery_job_id = job.id
                        summary.reused += 1
                    else:
                        c = Contact(
                            website_id=website.id,
                            discovery_job_id=job.id,
                            contact_type=c_type,
                            source_url=s_url,
                            confidence=form_contact.confidence,
                            is_primary=is_prim,
                            is_active=True,
                            contact_form_url=form_u
                        )
                        self.session.add(c)
                        self.session.flush()
                        summary.created += 1
            except IntegrityError as exc:
                if not is_unique_violation(exc):
                    raise PersistenceFailure("Contact form persistence failed") from exc

                existing = self.session.execute(
                    select(Contact)
                    .where(Contact.website_id == website.id, Contact.contact_form_url == form_u)
                ).scalar_one_or_none()
                if not existing:
                    raise PersistenceConflict("Unique conflict but no existing form contact found") from exc
                if existing.confidence < form_contact.confidence:
                    existing.confidence = form_contact.confidence
                    existing.contact_type = c_type
                    existing.source_url = s_url
                existing.discovery_job_id = job.id
                summary.reused += 1

        return summary

    def record_processing_error(self, job_id: uuid.UUID, attempt_number: int, stage: ProcessingStage, error_code: str, safe_message: str, retryable: bool, search_query_id: uuid.UUID = None, website_id: uuid.UUID = None) -> ProcessingError:
        with self.session.begin_nested():
            err = ProcessingError(
                discovery_job_id=job_id,
                website_id=website_id,
                search_query_id=search_query_id,
                stage=stage,
                error_type=error_code[:255],
                message=safe_message[:2000] if safe_message else "Unknown error",
                is_retryable=retryable,
                attempt_number=attempt_number
            )
            self.session.add(err)
        return err

    @classmethod
    def record_processing_error_isolated(cls, session_factory, job_id: uuid.UUID, attempt_number: int, stage: ProcessingStage, error_code: str, safe_message: str, retryable: bool, search_query_id: uuid.UUID = None, website_id: uuid.UUID = None) -> ProcessingError:
        with session_factory() as session:
            service = cls(session)
            err = service.record_processing_error(job_id, attempt_number, stage, error_code, safe_message, retryable, search_query_id, website_id)
            session.commit()
            session.refresh(err)
            return err

    def recalculate_job_counters(self, job_id: uuid.UUID) -> DiscoveryJob:
        job = self.session.execute(select(DiscoveryJob).where(DiscoveryJob.id == job_id)).scalar_one()

        job.queries_generated = self.session.execute(select(func.count(SearchQuery.id)).where(SearchQuery.discovery_job_id == job_id)).scalar()
        job.queries_completed = self.session.execute(select(func.count(SearchQuery.id)).where(SearchQuery.discovery_job_id == job_id, SearchQuery.status == "completed")).scalar()
        job.candidates_found = self.session.execute(select(func.count(func.distinct(DiscoverySource.website_id))).where(DiscoverySource.discovery_job_id == job_id)).scalar()

        subq = (
            select(
                WebsiteVerification.website_id,
                WebsiteVerification.status,
                WebsiteVerification.attempt_number,
                func.row_number().over(
                    partition_by=WebsiteVerification.website_id,
                    order_by=(WebsiteVerification.attempt_number.desc(), WebsiteVerification.verified_at.desc(), WebsiteVerification.id.desc())
                ).label("rn")
            )
            .where(WebsiteVerification.discovery_job_id == job_id)
            .subquery()
        )

        latest_verifs = (
            select(subq.c.status, func.count(subq.c.website_id))
            .where(subq.c.rn == 1)
            .group_by(subq.c.status)
        )

        status_counts = dict(self.session.execute(latest_verifs).all())

        job.sites_fetched = sum(status_counts.values()) - status_counts.get(VerificationStatus.fetch_failed.value, 0)
        job.sites_verified = status_counts.get(VerificationStatus.verified.value, 0)
        job.websites_uncertain = status_counts.get(VerificationStatus.uncertain.value, 0)
        job.sites_rejected = status_counts.get(VerificationStatus.rejected.value, 0)

        job.contacts_found = self.session.execute(select(func.count(func.distinct(Contact.id))).where(Contact.discovery_job_id == job_id)).scalar()
        job.errors_count = self.session.execute(select(func.count(ProcessingError.id)).where(ProcessingError.discovery_job_id == job_id)).scalar()

        from app.models.enums import QualificationStatus
        qual_subq = (
            select(
                Website.id,
                Website.current_qualification_status
            )
            .join(DiscoverySource, DiscoverySource.website_id == Website.id)
            .where(DiscoverySource.discovery_job_id == job_id)
            .distinct()
            .subquery()
        )

        qual_counts_query = (
            select(qual_subq.c.current_qualification_status, func.count(qual_subq.c.id))
            .group_by(qual_subq.c.current_qualification_status)
        )

        qual_counts = dict(self.session.execute(qual_counts_query).all())

        job.sites_qualified = qual_counts.get(QualificationStatus.qualified, qual_counts.get(QualificationStatus.qualified.value, 0))
        job.sites_upcoming = qual_counts.get(QualificationStatus.upcoming, qual_counts.get(QualificationStatus.upcoming.value, 0))
        job.sites_traffic_missing = qual_counts.get(QualificationStatus.traffic_missing, qual_counts.get(QualificationStatus.traffic_missing.value, 0))

        self.session.commit()
        return job

    def finalize_job(self, job_id: uuid.UUID) -> DiscoveryJob:
        job = self.recalculate_job_counters(job_id)

        incomplete_queries = self.session.execute(
            select(func.count(SearchQuery.id))
            .where(SearchQuery.discovery_job_id == job_id, SearchQuery.status == "pending")
        ).scalar()

        if incomplete_queries > 0:
            raise IncompleteJobFinalization("Job has pending queries")

        websites = self.session.execute(
            select(func.distinct(DiscoverySource.website_id))
            .where(DiscoverySource.discovery_job_id == job_id)
        ).scalars().all()

        for w_id in websites:
            if isinstance(w_id, str):
                w_id = uuid.UUID(w_id)
            if isinstance(job_id, str):
                job_id = uuid.UUID(job_id)
            has_verif = self.session.execute(
                select(WebsiteVerification.id)
                .where(WebsiteVerification.website_id == w_id, WebsiteVerification.discovery_job_id == job_id, WebsiteVerification.attempt_number == job.attempt_number)
            ).scalar_one_or_none()

            if not has_verif:
                has_error = self.session.execute(
                    select(ProcessingError.id)
                    .where(ProcessingError.website_id == w_id, ProcessingError.discovery_job_id == job_id, ProcessingError.attempt_number == job.attempt_number, ProcessingError.is_retryable == False)
                ).scalar_one_or_none()

                if not has_error:
                    raise IncompleteJobFinalization(f"Website {w_id} has no verification or terminal error for attempt {job.attempt_number}")

        if job.errors_count == 0:
            job.status = DiscoveryJobStatus.completed
        else:
            job.status = DiscoveryJobStatus.completed_with_errors

        job.completed_at = func.now()
        self.session.commit()
        return job
