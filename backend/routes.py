from flask import Blueprint, request, jsonify
from datetime import datetime
from services.bluefolder_service import BlueFolderService
from services.routing_service import RoutingService

api = Blueprint("api", __name__, url_prefix="/api")
bf = BlueFolderService()
router = RoutingService()

@api.get("/techs")
def techs():
    return jsonify(bf.list_techs())

@api.get("/route/preview")
def preview():
    tech_id=int(request.args.get("tech_id"))
    date=datetime.fromisoformat(request.args.get("date")).date()
    stops=bf.get_tech_assignments_for_day(tech_id,date)
    origin=request.args.get("origin")
    destination=request.args.get("destination")
    return jsonify(router.preview_route(stops, origin=origin, destination=destination))

@api.post("/route/simulate")
def simulate():
    data=request.get_json()
    result = router.simulate_route(
        data.get("existing_assignments",[]),
        data.get("added_stops",[]),
        data.get("removed_ids",[]),
        data.get("manual_order",[]),
        data.get("origin"),
        data.get("destination"),
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
