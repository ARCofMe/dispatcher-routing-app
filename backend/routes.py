from flask import Blueprint, request, jsonify
from datetime import datetime
from services.bluefolder_service import BlueFolderService
from services.routing_service import RoutingService

api = Blueprint("api", __name__, url_prefix="/api")
bf = BlueFolderService()
router = RoutingService()

def _creds_from_headers(req):
    api_key = req.headers.get("X-BF-API-KEY") or req.args.get("api_key")
    account = req.headers.get("X-BF-ACCOUNT") or req.args.get("account")
    return api_key, account

@api.get("/techs")
def techs():
    api_key, account = _creds_from_headers(request)
    return jsonify(bf.list_techs(api_key=api_key, account=account))

@api.get("/route/preview")
def preview():
    tech_id=int(request.args.get("tech_id"))
    date=datetime.fromisoformat(request.args.get("date")).date()
    api_key, account = _creds_from_headers(request)
    stops=bf.get_tech_assignments_for_day(tech_id,date, api_key=api_key, account=account)
    origin=request.args.get("origin")
    destination=request.args.get("destination")
    optimize=request.args.get("optimize")
    return jsonify(router.preview_route(stops, origin=origin, destination=destination, optimize=optimize in ("true","1",True)))

@api.post("/route/simulate")
def simulate():
    data=request.get_json()
    optimize = data.get("optimize")
    result = router.simulate_route(
        data.get("existing_assignments",[]),
        data.get("added_stops",[]),
        data.get("removed_ids",[]),
        data.get("manual_order",[]),
        data.get("origin"),
        data.get("destination"),
        optimize=optimize in (True, "true", "1"),
    )
    return jsonify(result)

@api.post("/route/commit")
def commit():
    data=request.get_json()
    tech_id=int(data.get("tech_id"))
    day=datetime.fromisoformat(data.get("date")).date()
    manual_order=data.get("manual_order",[])
    ordered_stops=data.get("ordered_stops",[])
    bf.commit_route(tech_id, day, ordered_stops, manual_order)
    return jsonify({"status":"ok","tech_id":tech_id,"date":day.isoformat()})
