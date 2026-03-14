import os
import sys
from datetime import date
import traceback
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
        self._apply_base_url_env()
        self._integration = self._init_integration()
        default_duration = os.getenv("DEFAULT_DURATION_MINUTES")
        try:
            self.default_duration = int(default_duration) if default_duration else 60
        except Exception:
            self.default_duration = 60

    def _build_base_url(self, account: Optional[str] = None) -> Optional[str]:
        """
        Derive the BlueFolder base URL from explicit env or the account name.
        Avoids the placeholder default baked into the upstream integration config.
        """
        env_base = os.getenv("BLUEFOLDER_BASE_URL")
        if env_base:
            return env_base.rstrip("/")
        account_name = account or os.getenv("BLUEFOLDER_ACCOUNT_NAME")
        if account_name:
            return f"https://{account_name}.bluefolder.com/api/2.0"
        return None

    def _apply_base_url_env(self, account: Optional[str] = None):
        """
        Ensure the environment exposes BLUEFOLDER_BASE_URL before importing the integration.
        """
        base_url = self._build_base_url(account)
        if base_url:
            os.environ.setdefault("BLUEFOLDER_BASE_URL", base_url)

    def _integration_with_credentials(self, api_key: Optional[str], account: Optional[str]):
        if not api_key or not account:
            return None
        try:
            base_url = self._build_base_url(account)

            def _build():
                from optimized_routing.bluefolder_integration import BlueFolderIntegration  # type: ignore
                from bluefolder_api.client import BlueFolderClient  # type: ignore

                client_kwargs = {"base_url": base_url} if base_url else {}
                client = BlueFolderClient(**client_kwargs)
                return BlueFolderIntegration(client=client, base_url=base_url)

            return self._with_env_creds(api_key, account, _build, base_url=base_url)
        except Exception:
            return None

    def _with_env_creds(self, api_key: Optional[str], account: Optional[str], fn, base_url: Optional[str] = None):
        prev_key = os.environ.get("BLUEFOLDER_API_KEY")
        prev_account = os.environ.get("BLUEFOLDER_ACCOUNT_NAME")
        prev_base_url = os.environ.get("BLUEFOLDER_BASE_URL")
        base_url = base_url or self._build_base_url(account)
        try:
            if api_key:
                os.environ["BLUEFOLDER_API_KEY"] = api_key
            if account:
                os.environ["BLUEFOLDER_ACCOUNT_NAME"] = account
            if base_url:
                os.environ["BLUEFOLDER_BASE_URL"] = base_url
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
            if prev_base_url is not None:
                os.environ["BLUEFOLDER_BASE_URL"] = prev_base_url
            else:
                os.environ.pop("BLUEFOLDER_BASE_URL", None)

    def _init_integration(self):
        base_url = self._build_base_url()
        if base_url:
            os.environ.setdefault("BLUEFOLDER_BASE_URL", base_url)
        try:
            from optimized_routing.bluefolder_integration import BlueFolderIntegration  # type: ignore

            return BlueFolderIntegration(base_url=base_url)
        except Exception:
            try:
                from bluefolder_api.client import BlueFolderClient  # type: ignore

                class _Wrapper:
                    def __init__(self):
                        client_kwargs = {"base_url": base_url} if base_url else {}
                        self.client = BlueFolderClient(**client_kwargs)

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

            base_url = self._build_base_url(account)
            return self._with_env_creds(
                api_key,
                account,
                lambda: BlueFolderClient(**({"base_url": base_url} if base_url else {})),
                base_url=base_url,
            )
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
        # Optional offline fallback: if set, serve from a cached JSON file when BF is unreachable.
        offline_path = os.getenv("BLUEFOLDER_OFFLINE_FILE")

        # Prefer the integration path because it enriches assignments with SR/location data.
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
                    print("bf_source=integration", "count=", len(assignments))
                    try:
                        first = assignments[0]
                        print("bf_assignment_keys", list(first.keys()))
                    except Exception:
                        pass
                    return [self._map_assignment_to_stop(a) for a in assignments]
        except Exception as e:
            print("bf_integration_assignments_error", e)
            print(traceback.format_exc())

        # Fall back to direct client (minimal payloads) if integration fails.
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
            assignments = self._with_env_creds(api_key, account, _assignments_from_client)
            if assignments:
                print("bf_source=client", "count=", len(assignments))
                try:
                    print("bf_first_assignment", assignments[0])
                except Exception:
                    pass
                return [self._map_assignment_to_stop(a) for a in assignments]
        except Exception as e:
            print("bf_client_assignments_error", e)
            print(traceback.format_exc())

        # Offline fallback if provided
        if offline_path:
            try:
                import json
                with open(offline_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Expecting a list of assignment dicts
                return [self._map_assignment_to_stop(a) for a in data]
            except Exception as e:
                print("bf_offline_fallback_error", e)
                print(traceback.format_exc())

        # If everything fails, return empty to avoid misleading demo data.
        return []

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

    def _map_assignment_to_stop(self, assignment) -> dict:
        """
        Translate a BlueFolder assignment object into the internal Stop schema.
        Expects BlueFolderIntegration-enriched assignments with address/city/state/zip.
        """
        # If assignment is not enriched (missing subject/address), try to enrich it here
        if not assignment.get("subject") and assignment.get("serviceRequestId"):
            try:
                from bluefolder_api.client import BlueFolderClient
                import xml.etree.ElementTree as ET
                client = BlueFolderClient()
                sr_id = assignment["serviceRequestId"]
                sr_xml = client.service_requests.get_by_id(sr_id)
                sr = sr_xml.find(".//serviceRequest")
                if sr:
                    assignment["subject"] = sr.findtext("description") or sr.findtext("subject") or "Service Request"
                    customer_id = sr.findtext("customerId")
                    location_id = sr.findtext("customerLocationId")
                    if customer_id and location_id:
                        loc_xml = client.customers.get_location_by_id(customer_id, location_id)
                        loc = loc_xml.find(".//customerLocation")
                        if loc:
                            assignment["address"] = loc.findtext("addressStreet")
                            assignment["city"] = loc.findtext("addressCity")
                            assignment["state"] = loc.findtext("addressState")
                            assignment["zip"] = loc.findtext("addressPostalCode")
            except Exception:
                pass  # Silently fail to avoid breaking the app

        # Normalize address fields from the assignment payload.
        address_parts = [
            assignment.get("address") or "",
            assignment.get("city") or "",
            assignment.get("state") or "",
            assignment.get("zip") or "",
        ]
        address = ", ".join([p for p in address_parts if p]).strip(", ")

        # Window start/end from BF start/end (expected format YYYY-MM-DDTHH:MM:SS or similar).
        def _time_str(val):
            if not val:
                return None
            try:
                return str(val)[11:16]
            except Exception:
                return None

        window_start = _time_str(assignment.get("start"))
        window_end = _time_str(assignment.get("end"))

        # Status
        status = (
            assignment.get("status")
            or assignment.get("serviceRequestStatus")
            or assignment.get("service_request_status")
            or ("complete" if str(assignment.get("isComplete")).lower() in ("1", "true", "yes") else "scheduled")
        )

        # Equipment placeholders (not provided in current payload keys).
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
