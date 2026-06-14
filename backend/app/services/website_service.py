from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_, desc, asc
from uuid import UUID
from typing import Tuple, List, Optional, Dict
import logging

from app.models.enums import VerificationStatus, QualificationStatus, ManualReviewStatus, ContactType
from app.models.website import Website
from app.models.traffic_metric import TrafficMetric
from app.models.contact import Contact
from app.schemas.website import WebsiteSummary, WebsiteReviewUpdate, WebsiteDetail
from app.schemas.traffic_metric import TrafficMetricResponse
from app.schemas.contact import ContactResponse
from app.schemas.website_verification import WebsiteVerificationResponse
from app.schemas.discovery_source import DiscoverySourceResponse
from app.schemas.processing_error import ProcessingErrorResponse
from app.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)

CONTACT_TYPE_PRIORITY = {
    ContactType.advertising: 1,
    ContactType.partnerships: 2,
    ContactType.business: 3,
    ContactType.sales: 4,
    ContactType.editorial: 5,
    ContactType.editor: 6,
    ContactType.press: 7,
    ContactType.general: 8,
    ContactType.support: 9,
    ContactType.privacy: 10,
    ContactType.unknown: 11
}

def get_effective_review_decision(manual_status: ManualReviewStatus, auto_status: VerificationStatus) -> str:
    if manual_status == ManualReviewStatus.approved:
        return "approved"
    if manual_status == ManualReviewStatus.rejected:
        return "rejected"
    if manual_status == ManualReviewStatus.needs_review:
        return "needs_review"
        
    if auto_status == VerificationStatus.verified:
        return "verified"
    if auto_status == VerificationStatus.rejected:
        return "rejected"
    if auto_status in (VerificationStatus.uncertain, VerificationStatus.fetch_failed):
        return "needs_review"
        
    return "needs_review"

def get_best_contact(contacts: List[Contact]) -> Optional[Contact]:
    valid_contacts = [c for c in contacts if c.is_active and c.email]
    if not valid_contacts:
        return None
        
    def sort_key(c: Contact):
        priority = CONTACT_TYPE_PRIORITY.get(c.contact_type, 99)
        return (
            priority,
            not c.is_primary,
            -(float(c.confidence) if c.confidence is not None else 0.0),
            -c.discovered_at.timestamp()
        )
        
    return sorted(valid_contacts, key=sort_key)[0]

def build_website_summary(website: Website, latest_traffic: Optional[TrafficMetric] = None, best_contact: Optional[Contact] = None) -> WebsiteSummary:
    summary_data = {
        "id": website.id,
        "domain": website.domain,
        "homepage_url": website.homepage_url,
        "name": website.name,
        "country": website.country,
        "language": website.language,
        "categories": website.categories,
        "current_verification_status": website.current_verification_status,
        "current_qualification_status": website.current_qualification_status,
        "manual_review_status": website.manual_review_status,
        "is_active": website.is_active,
        "last_checked_at": website.last_checked_at,
        "created_at": website.created_at,
        "updated_at": website.updated_at,
        "effective_review_decision": get_effective_review_decision(website.manual_review_status, website.current_verification_status)
    }
    
    if latest_traffic:
        summary_data.update({
            "latest_metric_type": latest_traffic.metric_type,
            "latest_monthly_visits": latest_traffic.monthly_visits,
            "latest_pages_per_visit": latest_traffic.pages_per_visit,
            "latest_monthly_pageviews": latest_traffic.monthly_pageviews,
            "latest_estimated_pageviews": latest_traffic.estimated_pageviews,
            "latest_growth_rate": latest_traffic.growth_rate,
            "latest_traffic_provider": latest_traffic.provider,
            "latest_evidence_url": latest_traffic.evidence_url,
            "latest_traffic_recorded_at": latest_traffic.retrieved_at,
        })
        
    if best_contact:
        summary_data.update({
            "best_contact_email": best_contact.email,
            "best_contact_type": best_contact.contact_type
        })
        
    return WebsiteSummary.model_validate(summary_data)

def list_websites(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    verification_status: Optional[VerificationStatus] = None,
    qualification_status: Optional[QualificationStatus] = None,
    manual_review_status: Optional[ManualReviewStatus] = None,
    country: Optional[str] = None,
    language: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc"
) -> Tuple[List[WebsiteSummary], int]:
    query = db.query(Website)
    
    if verification_status:
        query = query.filter(Website.current_verification_status == verification_status)
    if qualification_status:
        query = query.filter(Website.current_qualification_status == qualification_status)
    if manual_review_status:
        query = query.filter(Website.manual_review_status == manual_review_status)
    if country:
        query = query.filter(Website.country == country)
    if language:
        query = query.filter(Website.language == language)
    if is_active is not None:
        query = query.filter(Website.is_active == is_active)
    if search:
        query = query.filter(or_(
            Website.name.ilike(f"%{search}%"),
            Website.domain.ilike(f"%{search}%")
        ))
        
    sort_column = getattr(Website, sort_by, Website.created_at)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))
        
    total = query.count()
    offset = (page - 1) * page_size
    websites = query.offset(offset).limit(page_size).all()
    
    if not websites:
        return [], total
        
    website_ids = [w.id for w in websites]
    
    traffic_records = db.query(TrafficMetric).filter(TrafficMetric.website_id.in_(website_ids)).all()
    traffic_by_website: Dict[UUID, List[TrafficMetric]] = {wid: [] for wid in website_ids}
    for t in traffic_records:
        traffic_by_website[t.website_id].append(t)
        
    latest_traffic_map = {}
    for wid, records in traffic_by_website.items():
        if records:
            records.sort(key=lambda r: (r.retrieved_at, r.id), reverse=True)
            latest_traffic_map[wid] = records[0]
            
    contacts = db.query(Contact).filter(
        Contact.website_id.in_(website_ids),
        Contact.is_active == True,
        Contact.email.isnot(None)
    ).all()
    
    contacts_by_website: Dict[UUID, List[Contact]] = {wid: [] for wid in website_ids}
    for c in contacts:
        contacts_by_website[c.website_id].append(c)
        
    best_contact_map = {}
    for wid, c_list in contacts_by_website.items():
        best_contact_map[wid] = get_best_contact(c_list)
        
    summaries = []
    for w in websites:
        summaries.append(build_website_summary(w, latest_traffic_map.get(w.id), best_contact_map.get(w.id)))
        
    return summaries, total

def get_website(db: Session, website_id: UUID) -> WebsiteDetail:
    website = db.query(Website).options(
        selectinload(Website.traffic_metrics),
        selectinload(Website.verifications),
        selectinload(Website.contacts),
        selectinload(Website.discovery_sources),
        selectinload(Website.processing_errors)
    ).filter(Website.id == website_id).first()
    
    if not website:
        raise ResourceNotFoundError("Website not found")
        
    traffic = sorted(website.traffic_metrics, key=lambda x: x.retrieved_at, reverse=True)
    verifications = sorted(website.verifications, key=lambda x: x.verified_at, reverse=True)
    sources = sorted(website.discovery_sources, key=lambda x: x.discovered_at, reverse=True)
    errors = sorted(website.processing_errors, key=lambda x: x.created_at, reverse=True)[:20]
    
    contacts = []
    for c in website.contacts:
        contacts.append(c)
    
    def contact_sort_key(c: Contact):
        priority = CONTACT_TYPE_PRIORITY.get(c.contact_type, 99)
        return (
            priority,
            not c.is_primary,
            -(float(c.confidence) if c.confidence is not None else 0.0),
            -c.discovered_at.timestamp()
        )
    contacts.sort(key=contact_sort_key)
    
    summary = build_website_summary(website, traffic[0] if traffic else None, get_best_contact(contacts))
    
    return WebsiteDetail(
        **summary.model_dump(),
        verification_history=[WebsiteVerificationResponse.model_validate(v) for v in verifications],
        traffic_history=[TrafficMetricResponse.model_validate(t) for t in traffic],
        contacts=[ContactResponse.model_validate(c) for c in contacts],
        discovery_sources=[DiscoverySourceResponse.model_validate(s) for s in sources],
        recent_processing_errors=[ProcessingErrorResponse.model_validate(e) for e in errors]
    )

def update_manual_review(db: Session, website_id: UUID, payload: WebsiteReviewUpdate) -> WebsiteSummary:
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise ResourceNotFoundError("Website not found")
        
    website.manual_review_status = payload.manual_review_status
    
    try:
        db.commit()
        db.refresh(website)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update manual review for website {website_id}: {e}")
        raise
        
    latest_traffic = db.query(TrafficMetric).filter(TrafficMetric.website_id == website_id).order_by(TrafficMetric.retrieved_at.desc()).first()
    contacts = db.query(Contact).filter(Contact.website_id == website_id, Contact.is_active == True, Contact.email.isnot(None)).all()
    best_contact = get_best_contact(contacts)
    
    return build_website_summary(website, latest_traffic, best_contact)
