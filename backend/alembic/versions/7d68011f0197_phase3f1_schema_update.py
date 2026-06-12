"""phase3f1_schema_update

Revision ID: 7d68011f0197
Revises: 2c8945ca246b
Create Date: 2026-06-13 03:45:26.021391

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d68011f0197'
down_revision: Union[str, Sequence[str], None] = '2c8945ca246b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    context = op.get_context()
    is_offline = context.as_sql
    
    # 1. Add new columns as nullable, or with safe server defaults.
    op.add_column('discovery_jobs', sa.Column('attempt_number', sa.Integer(), server_default='0', nullable=True))
    op.add_column('discovery_jobs', sa.Column('websites_uncertain', sa.Integer(), server_default='0', nullable=True))
    op.add_column('discovery_jobs', sa.Column('contacts_found', sa.Integer(), server_default='0', nullable=True))
    
    op.add_column('websites', sa.Column('canonical_key', sa.String(), nullable=True))
    op.add_column('websites', sa.Column('is_multitenant', sa.Boolean(), server_default=sa.text('false'), nullable=True))
    
    op.add_column('website_verifications', sa.Column('attempt_number', sa.Integer(), server_default='1', nullable=True))
    
    # 2. Backfill DiscoveryJob counters and attempt number.
    conn.execute(sa.text("""
        UPDATE discovery_jobs SET 
            attempt_number = 0,
            websites_uncertain = (SELECT count(DISTINCT website_id) FROM website_verifications WHERE discovery_jobs.id = website_verifications.discovery_job_id AND status = 'uncertain'),
            contacts_found = (SELECT count(DISTINCT email) FROM contacts WHERE discovery_jobs.id = contacts.discovery_job_id)
    """))
    
    # 3. Backfill Website canonical key and multi-tenant flag.
    conn.execute(sa.text("""
        UPDATE websites SET
            is_multitenant = CASE WHEN domain LIKE '%substack.com' OR domain LIKE '%wordpress.com' OR domain LIKE '%blogspot.com' THEN true ELSE false END,
            canonical_key = domain
    """))
    
    # 4. Detect canonical-key collisions.
    res = conn.execute(sa.text("""
        SELECT canonical_key, count(*) FROM websites GROUP BY canonical_key HAVING count(*) > 1
    """))
    if not is_offline:
        collisions = res.fetchall()
        if collisions:
            raise Exception(f"Canonical key collisions detected: {collisions}")

    # 5. Make Website columns non-null.
    op.alter_column('discovery_jobs', 'attempt_number', nullable=False)
    op.alter_column('discovery_jobs', 'websites_uncertain', nullable=False)
    op.alter_column('discovery_jobs', 'contacts_found', nullable=False)
    op.alter_column('websites', 'canonical_key', nullable=False)
    op.alter_column('websites', 'is_multitenant', nullable=False)
    op.alter_column('website_verifications', 'attempt_number', nullable=False)
    
    # 6. Drop the exact old domain uniqueness object.
    op.drop_index('ix_websites_domain', table_name='websites')
    
    # 7. Create normal domain index if one is not already present.
    op.create_index('ix_websites_domain', 'websites', ['domain'], unique=False)
    
    # 8. Create unique canonical-key index/constraint.
    op.create_index('ix_websites_canonical_key', 'websites', ['canonical_key'], unique=True)
    
    # 9. Backfill WebsiteVerification attempt numbers safely.
    conn.execute(sa.text("""
        UPDATE website_verifications SET attempt_number = 1
    """))
    
    # 10. Detect verification-key collisions.
    res = conn.execute(sa.text("""
        SELECT website_id, discovery_job_id, attempt_number, classifier_version, count(*) 
        FROM website_verifications 
        GROUP BY website_id, discovery_job_id, attempt_number, classifier_version 
        HAVING count(*) > 1
    """))
    
    if is_offline:
        # Provide fallback SQL in offline mode without checking condition
        conn.execute(sa.text("""
            WITH ordered AS (
                SELECT id, row_number() OVER (
                    PARTITION BY website_id, discovery_job_id, classifier_version 
                    ORDER BY verified_at ASC, id ASC
                ) as rn
                FROM website_verifications
            )
            UPDATE website_verifications
            SET attempt_number = ordered.rn
            FROM ordered
            WHERE website_verifications.id = ordered.id
        """))
    else:
        v_collisions = res.fetchall()
        if v_collisions:
            conn.execute(sa.text("""
                WITH ordered AS (
                    SELECT id, row_number() OVER (
                        PARTITION BY website_id, discovery_job_id, classifier_version 
                        ORDER BY verified_at ASC, id ASC
                    ) as rn
                    FROM website_verifications
                )
                UPDATE website_verifications
                SET attempt_number = ordered.rn
                FROM ordered
                WHERE website_verifications.id = ordered.id
            """))
    
    # 12. Create verification uniqueness constraint.
    op.create_unique_constraint('uq_wv_job_site_attempt_version', 'website_verifications', ['website_id', 'discovery_job_id', 'attempt_number', 'classifier_version'])
    
    # 13. Detect and safely handle Contact duplicates.
    res = conn.execute(sa.text("""
        SELECT website_id, lower(email), count(*) FROM contacts WHERE email IS NOT NULL GROUP BY website_id, lower(email) HAVING count(*) > 1
    """))
    
    if is_offline:
        conn.execute(sa.text("""
            WITH duplicates AS (
                SELECT id, row_number() OVER (
                    PARTITION BY website_id, lower(email)
                    ORDER BY confidence DESC NULLS LAST, discovered_at ASC, id ASC
                ) as rn
                FROM contacts
                WHERE email IS NOT NULL
            )
            DELETE FROM contacts WHERE id IN (SELECT id FROM duplicates WHERE rn > 1)
        """))
    else:
        email_dups = res.fetchall()
        if email_dups:
            conn.execute(sa.text("""
                WITH duplicates AS (
                    SELECT id, row_number() OVER (
                        PARTITION BY website_id, lower(email)
                        ORDER BY confidence DESC NULLS LAST, discovered_at ASC, id ASC
                    ) as rn
                    FROM contacts
                    WHERE email IS NOT NULL
                )
                DELETE FROM contacts WHERE id IN (SELECT id FROM duplicates WHERE rn > 1)
            """))
        
    res = conn.execute(sa.text("""
        SELECT website_id, contact_form_url, count(*) FROM contacts WHERE contact_form_url IS NOT NULL GROUP BY website_id, contact_form_url HAVING count(*) > 1
    """))
    
    if is_offline:
        conn.execute(sa.text("""
            WITH duplicates AS (
                SELECT id, row_number() OVER (
                    PARTITION BY website_id, contact_form_url
                    ORDER BY confidence DESC NULLS LAST, discovered_at ASC, id ASC
                ) as rn
                FROM contacts
                WHERE contact_form_url IS NOT NULL
            )
            DELETE FROM contacts WHERE id IN (SELECT id FROM duplicates WHERE rn > 1)
        """))
    else:
        form_dups = res.fetchall()
        if form_dups:
            conn.execute(sa.text("""
                WITH duplicates AS (
                    SELECT id, row_number() OVER (
                        PARTITION BY website_id, contact_form_url
                        ORDER BY confidence DESC NULLS LAST, discovered_at ASC, id ASC
                    ) as rn
                    FROM contacts
                    WHERE contact_form_url IS NOT NULL
                )
                DELETE FROM contacts WHERE id IN (SELECT id FROM duplicates WHERE rn > 1)
            """))
    
    # 14. Drop the exact old contact email/source index.
    op.drop_index('uix_contact_email_source', table_name='contacts')
    
    # 15. Create partial functional email index.
    op.create_index('ix_contacts_unique_email', 'contacts', ['website_id', sa.text("lower(email)")], unique=True, postgresql_where=sa.text("email IS NOT NULL"))
    
    # 16. Create partial form-URL index.
    op.create_index('ix_contacts_unique_form', 'contacts', ['website_id', 'contact_form_url'], unique=True, postgresql_where=sa.text("contact_form_url IS NOT NULL"))
    
    # 17. Remove temporary server defaults
    op.alter_column('discovery_jobs', 'attempt_number', server_default=None)
    op.alter_column('discovery_jobs', 'websites_uncertain', server_default=None)
    op.alter_column('discovery_jobs', 'contacts_found', server_default=None)
    op.alter_column('websites', 'is_multitenant', server_default=None)
    op.alter_column('website_verifications', 'attempt_number', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    context = op.get_context()
    is_offline = context.as_sql
    
    # Downgrade preconditions
    res = conn.execute(sa.text("""
        SELECT domain, count(*) FROM websites GROUP BY domain HAVING count(*) > 1
    """))
    if not is_offline:
        domain_dups = res.fetchall()
        if domain_dups:
            raise Exception(f"Cannot downgrade: {len(domain_dups)} duplicate domains exist due to multi-tenant feature.")
        
    res = conn.execute(sa.text("""
        SELECT website_id, email, source_url, count(*) FROM contacts WHERE email IS NOT NULL GROUP BY website_id, email, source_url HAVING count(*) > 1
    """))
    if not is_offline:
        old_contact_dups = res.fetchall()
        if old_contact_dups:
            raise Exception("Cannot downgrade: duplicate email/source_url combinations exist.")

    op.drop_index('ix_contacts_unique_form', table_name='contacts')
    op.drop_index('ix_contacts_unique_email', table_name='contacts')
    op.create_index('uix_contact_email_source', 'contacts', ['website_id', 'email', 'source_url'], unique=True, postgresql_where=sa.text("email IS NOT NULL"))
    
    op.drop_constraint('uq_wv_job_site_attempt_version', 'website_verifications', type_='unique')
    
    op.drop_index('ix_websites_canonical_key', table_name='websites')
    op.drop_index('ix_websites_domain', table_name='websites')
    op.create_index('ix_websites_domain', 'websites', ['domain'], unique=True)
    
    op.drop_column('website_verifications', 'attempt_number')
    
    op.drop_column('websites', 'is_multitenant')
    op.drop_column('websites', 'canonical_key')
    
    op.drop_column('discovery_jobs', 'contacts_found')
    op.drop_column('discovery_jobs', 'websites_uncertain')
    op.drop_column('discovery_jobs', 'attempt_number')
