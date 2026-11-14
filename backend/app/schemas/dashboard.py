from pydantic import BaseModel


class CommunityDashboard(BaseModel):
    total_connections: int
    active_connections: int
    total_meters: int
    collection_rate: float
    total_revenue: float
    total_arrears: float
    pending_maintenance: int
    avg_consumption_m3: float


class PartnerDashboard(BaseModel):
    total_communities: int
    total_connections: int
    overall_collection_rate: float
    total_revenue: float
    total_arrears: float
    pending_maintenance: int
    communities_at_risk: int


class SystemDashboard(BaseModel):
    total_partners: int
    total_communities: int
    total_connections: int
    total_users: int
    overall_collection_rate: float
    total_revenue: float
    total_arrears: float
