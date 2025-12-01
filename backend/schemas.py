from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Stop:
    id: str
    address: str
    customer_name: str
    duration_minutes: int
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    service_request_id: Optional[str] = None
    subject: Optional[str] = None
    status: Optional[str] = None
