"""phase4a_traffic_evidence

Revision ID: 2a60a4affa2b
Revises: 7d68011f0197
Create Date: 2026-06-13 18:44:45.267647

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a60a4affa2b'
down_revision: Union[str, Sequence[str], None] = '7d68011f0197'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('traffic_metrics', sa.Column('monthly_pageviews', sa.Numeric(precision=24, scale=2), nullable=True))
    op.add_column('traffic_metrics', sa.Column('metric_type', sa.String(), server_default='estimated_monthly_pageviews', nullable=False))
    op.add_column('traffic_metrics', sa.Column('evidence_url', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('traffic_metrics', 'evidence_url')
    op.drop_column('traffic_metrics', 'metric_type')
    op.drop_column('traffic_metrics', 'monthly_pageviews')
