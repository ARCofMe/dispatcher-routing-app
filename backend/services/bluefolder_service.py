import os
import sys
from datetime import date
from typing import List, Optional

from dataclasses import asdict

from config import config
from schemas import Stop


def _maybe_extend_sys_path():
    """
    Allow importing the locally checked-out BlueFolder SDK / optimized-routing-extension
    without publishing them. Set BLUEFOLDER_API_PATH if the default path is different.
    """
    bf_path = os.getenv("BLUEFOLDER_API_PATH", "/home/ner0tic/Documents/Projects/ARCoM/bluefolder-api")
    routing_path = os.getenv("ROUTING_EXTENSION_PATH", "/home/ner0tic/Documents/Projects/ARCoM/optimized-routing-extension")
    for candidate in (bf_path, routing_path):
        if candidate and candidate not in sys.path:
            sys.path.append(candidate)


class BlueFolderService:
    """
    Adapter for the local BlueFolder API wrapper.
    Integration points:
      - Use BlueFolderIntegration (from optimized-routing-extension) for techs/assignments.
      - Use client.service_requests / assignments to persist updated sequence when available.
    """

    def __init__(self):
        _maybe_extend_sys_path()
        self._integration = self._init_integration()

    def _init_integration(self):
        try:
            from optimized_routing.bluefolder_integration import BlueFolderIntegration  # type: ignore

            return BlueFolderIntegration()
        except Exception:
            try:
                from bluefolder_api.client import BlueFolderClient  # type: ignore

                class _Wrapper:
                    def __init__(self):
                        self.client = BlueFolderClient()

                    def get_active_users(self):
                        return self.client.users.list_active()

                    def get_user_assignments_range(self, user_id, start_date, end_date, date_range_type="scheduled"):
                        return self.client.assignments.list_for_user_range(
                            user_id=user_id,
                            start_date=start_date,
                            end_date=end_date,
                            date_range_type=date_range_type,
                        )

                return _Wrapper()
            except Exception:
                return None

    def list_techs(self):
        """
        Return active technicians from BlueFolder.
        Uses BlueFolderIntegration.get_active_users() when available.
        """
        if self._integration and hasattr(self._integration, "get_active_users"):
            try:
                techs = self._integration.get_active_users()
                return [
                    {
                        "id": int(t.get("userId") or t.get("id")),
                        "name": f"{t.get('firstName','').strip()} {t.get('lastName','').strip()}".strip(),
                    }
                    for t in techs
                    if t.get("userId") or t.get("id")
                ]
            except Exception:
                pass
        # Demo fallback
        return [{"id": 1, "name": "Demo Tech"}]

    def get_tech_assignments_for_day(self, tech_id: int, day: date) -> List[dict]:
        """
        Pull assignments for a technician on a given day.
        Real implementation uses BlueFolderIntegration.get_user_assignments_range.
        """
        if self._integration and hasattr(self._integration, "get_user_assignments_range"):
            try:
                start_date = f"{day.strftime('%Y.%m.%d')} 12:00 AM"
                end_date = f"{day.strftime('%Y.%m.%d')} 11:59 PM"
                assignments = self._integration.get_user_assignments_range(
                    user_id=tech_id,
                    start_date=start_date,
                    end_date=end_date,
                    date_range_type="scheduled",
                )
                if assignments:
                    return [self._map_assignment_to_stop(a) for a in assignments]
            except Exception:
                pass

        # Demo payload keeps the frontend and routing layers functional.
        return [
            Stop(
                id="A1",
                address="123 Demo St, City",
                customer_name="Contoso Bakery",
                duration_minutes=30,
                window_start="08:00",
                window_end="10:00",
                lat=40.7128,
                lon=-74.006,
            ).__dict__,
            Stop(
                id="A2",
                address="456 Sample Ave, City",
                customer_name="Fabrikam HQ",
                duration_minutes=45,
                window_start="10:30",
                window_end="12:30",
                lat=40.706,
                lon=-74.009,
            ).__dict__,
            Stop(
                id="A3",
                address="789 Placeholder Rd, City",
                customer_name="Northwind Depot",
                duration_minutes=20,
                window_start="13:00",
                window_end="16:00",
                lat=40.715,
                lon=-74.001,
            ).__dict__,
        ]

    def commit_route(self, tech_id: int, day: date, ordered_stops: List[dict], manual_order: Optional[list] = None):
        """
        Persist a route sequence back to BlueFolder.
        TODO: map manual_order to assignment updates once the SDK exposes an ordering endpoint.
        """
        if self._integration:
            try:
                client = getattr(self._integration, "client", None)
                if client and hasattr(client, "assignments"):
                    # Example (placeholder): client.assignments.update_order(tech_id, manual_order or [s["id"] for s in ordered_stops])
                    pass
            except Exception:
                pass
        return {"status": "queued", "tech_id": tech_id, "date": day.isoformat(), "count": len(ordered_stops)}

    @staticmethod
    def _map_assignment_to_stop(assignment) -> dict:
        """
        Translate a BlueFolder assignment object into the internal Stop schema.
        Expects BlueFolderIntegration-enriched assignments with address/city/state/zip.
        """
        address_parts = [
            assignment.get("address") or "",
            assignment.get("city") or "",
            assignment.get("state") or "",
            assignment.get("zip") or "",
        ]
        address = ", ".join([p for p in address_parts if p]).strip(", ")
        window_start = None
        window_end = None
        start_time = assignment.get("start")
        if start_time:
            try:
                window_start = start_time[11:16]
            except Exception:
                pass

        return asdict(
            Stop(
                id=str(assignment.get("assignmentId") or assignment.get("serviceRequestId")),
                address=address,
                customer_name=assignment.get("subject") or "Service Request",
                duration_minutes=30,
                window_start=window_start,
                window_end=window_end,
                lat=assignment.get("lat"),
                lon=assignment.get("lon"),
                # Extra context passed through to frontend
                service_request_id=assignment.get("serviceRequestId"),
                subject=assignment.get("subject"),
                status=assignment.get("status") or assignment.get("isComplete") or "scheduled",
            )
        )
