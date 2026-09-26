"""Fake school device fleet + mock admin tools. Nothing real is ever called."""
import random

random.seed(7)
GROUPS = {
    "Group 7": "Science Teachers",
    "Grade 6 Students": "Grade 6 Students",
    "Front Office": "Front Office Staff",
}
_SIZES = {"Group 7": 48, "Grade 6 Students": 120, "Front Office": 6}

DEVICES = {}
n = 100
for g, size in _SIZES.items():
    for _ in range(size):
        DEVICES[f"MAC-{n:04d}"] = {"group": g, "user": None, "status": "active"}
        n += 1


def devices_affected(tool, args):
    if "group" in args:
        return _SIZES.get(args["group"], 1)
    return 1


def run(tool, args):
    """Pretend to execute. Returns a log line."""
    if tool == "lookup_asset":
        d = DEVICES.get(args.get("device_id"), {})
        return f"Looked up {args.get('device_id')}: {d}"
    if tool == "reassign_device":
        DEVICES.setdefault(args["device_id"], {})["user"] = args["to_user"]
        return f"Reassigned {args['device_id']} to {args['to_user']}"
    if tool == "reset_password":
        target = args.get("group") or args.get("user")
        return f"Reset passwords for {target} ({devices_affected(tool, args)} accounts)"
    if tool == "wipe_device":
        target = args.get("group") or args.get("device_id")
        return f"WIPED {target} ({devices_affected(tool, args)} devices)"
    if tool == "bulk_update_group":
        return f"Updated {devices_affected(tool, args)} devices in {args.get('group')}"
    return f"Unknown tool {tool}"
