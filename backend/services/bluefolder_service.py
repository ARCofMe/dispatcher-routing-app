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
        default_duration = os.getenv("DEFAULT_DURATION_MINUTES")
        try:
            self.default_duration = int(default_duration) if default_duration else 60
        except Exception:
            self.default_duration = 60

    def _integration_with_credentials(self, api_key: Optional[str], account: Optional[str]):
        if not api_key or not account:
            return None
        try:
            from optimized_routing.bluefolder_integration import BlueFolderIntegration  # type: ignore
            from bluefolder_api.client import BlueFolderClient  # type: ignore

            def _build():
                client = BlueFolderClient()
                return BlueFolderIntegration(client=client)

            return self._with_env_creds(api_key, account, _build)
        except Exception:
            return None

    def _with_env_creds(self, api_key: Optional[str], account: Optional[str], fn):
        prev_key = os.environ.get("BLUEFOLDER_API_KEY")
        prev_account = os.environ.get("BLUEFOLDER_ACCOUNT_NAME")
        try:
            if api_key:
                os.environ["BLUEFOLDER_API_KEY"] = api_key
            if account:
                os.environ["BLUEFOLDER_ACCOUNT_NAME"] = account
            return fn()
        finally:
            if prev_key is not None:
                os.environ["BLUEFOLDER_API_KEY"] = prev_key
            else:
                os.environ.pop("BLUEFOLDER_API_KEY", None)
            if prev_account is not None:
                os.environ["BLUEFOLDER_ACCOUNT_NAME"] = prev_account
            else:
                os.environ.pop("BLUEFOLDER_ACCOUNT_NAME", None)

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

    def _client_with_credentials(self, api_key: Optional[str], account: Optional[str]):
        if not api_key or not account:
            return None
        try:
            from bluefolder_api.client import BlueFolderClient  # type: ignore

            return self._with_env_creds(api_key, account, lambda: BlueFolderClient())
        except Exception:
            return None

    def list_techs(self, api_key: Optional[str] = None, account: Optional[str] = None):
        """
        Return active technicians from BlueFolder.
        Uses BlueFolderIntegration.get_active_users() when available.
        """
        def _list_from_client():
            client = self._client_with_credentials(api_key, account)
            if client and hasattr(client, "users"):
                techs = client.users.list_active()
                return [
                    {
                        "id": int(t.get("userId") or t.get("id")),
                        "name": f"{t.get('firstName','').strip()} {t.get('lastName','').strip()}".strip(),
                    }
                    for t in techs
                    if t.get("userId") or t.get("id")
                ]
            return None

        try:
            techs = self._with_env_creds(api_key, account, _list_from_client)
            if techs:
                return techs
        except Exception:
            pass

        integration = self._integration_with_credentials(api_key, account) or self._integration
        if integration and hasattr(integration, "get_active_users"):
            try:
                techs = integration.get_active_users()
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

    def get_tech_assignments_for_day(self, tech_id: int, day: date, api_key: Optional[str] = None, account: Optional[str] = None) -> List[dict]:
        """
        Pull assignments for a technician on a given day.
        Real implementation uses BlueFolderIntegration.get_user_assignments_range.
        """
        def _assignments_from_client():
            client = self._client_with_credentials(api_key, account)
            if client and hasattr(client, "assignments"):
                start_date = f"{day.strftime('%Y.%m.%d')} 12:00 AM"
                end_date = f"{day.strftime('%Y.%m.%d')} 11:59 PM"
                return client.assignments.list_for_user_range(
                    user_id=tech_id,
                    start_date=start_date,
                    end_date=end_date,
                    date_range_type="scheduled",
                )
            return None

        try:
            integration = self._integration_with_credentials(api_key, account) or self._integration
            if integration and hasattr(integration, "get_user_assignments_range"):
                start_date = f"{day.strftime('%Y.%m.%d')} 12:00 AM"
                end_date = f"{day.strftime('%Y.%m.%d')} 11:59 PM"
                assignments = integration.get_user_assignments_range(
                    user_id=tech_id,
                    start_date=start_date,
                    end_date=end_date,
                    date_range_type="scheduled",
                )
                if assignments:
                    return [self._map_assignment_to_stop(a) for a in assignments]
        except Exception:
            pass

        try:
            assignments = self._with_env_creds(api_key, account, _assignments_from_client)
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

        status = (
            assignment.get("status")
            or assignment.get("serviceRequestStatus")
            or assignment.get("service_request_status")
            or ("complete" if str(assignment.get("isComplete")).lower() in ("1", "true", "yes") else "scheduled")
        )

        equipment = assignment.get("equipmentToService") or assignment.get("equipment") or assignment.get("equipment_type")
        equipment_id = assignment.get("equipmentId") or assignment.get("equipment_id") or assignment.get("equipment_id_str") or None

        return asdict(
            Stop(
                id=str(assignment.get("assignmentId") or assignment.get("serviceRequestId")),
                address=address,
                customer_name=assignment.get("subject") or "Service Request",
                duration_minutes=self.default_duration,
                window_start=window_start,
                window_end=window_end,
                lat=assignment.get("lat"),
                lon=assignment.get("lon"),
                # Extra context passed through to frontend
                service_request_id=assignment.get("serviceRequestId"),
                subject=assignment.get("subject"),
                status=status,
                equipment=equipment,
                equipment_type=assignment.get("equipment_type") or equipment,
                equipment_id=str(equipment_id) if equipment_id is not None else None,
            )
        )
