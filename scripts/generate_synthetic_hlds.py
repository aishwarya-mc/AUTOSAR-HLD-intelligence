"""Generate a corpus of synthetic AUTOSAR HLDs with ground truth and seeded-defect variants.

Usage: python scripts/generate_synthetic_hlds.py [OUTPUT_DIR]   (default: data/synthetic)

For each domain spec this writes
  <key>.pdf            consistent HLD (same section/table layout as the sample HLD)
  <key>_defect.pdf     same HLD with four seeded defects (one per kind)
  <key>.truth.json     ground truth: entities, tables and the seeded defects with expected rule ids
Domains differ in names, sizes and signal naming, so held-out documents test generalisation.
"""
import json
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "data/synthetic")

# components: (name, role, responsibility)
# interfaces: (name, provider, consumer, signal, datatype)
SPECS = {
    "powertrain": {
        "title": "Powertrain Control System", "code": "PTC",
        "components": [
            ("EngineControlManager", "Coordinator", "Coordinates torque requests and engine state."),
            ("ThrottleControl", "Provider", "Measures throttle position and reports it."),
            ("FuelInjectionControl", "Consumer", "Meters fuel based on load and speed."),
            ("TransmissionControl", "Consumer", "Selects gears using engine speed and torque."),
            ("CrankSensorManager", "Provider", "Derives engine speed from the crank sensor."),
        ],
        "interfaces": [
            ("IThrottlePosition", "ThrottleControl", "EngineControlManager", "ThrottlePosition", "uint8"),
            ("IEngineSpeed", "CrankSensorManager", "EngineControlManager", "EngineSpeed", "uint16"),
            ("IFuelDemand", "EngineControlManager", "FuelInjectionControl", "FuelDemand", "uint16"),
            ("IGearRequest", "EngineControlManager", "TransmissionControl", "GearRequest", "uint8"),
            ("ITorqueLimit", "TransmissionControl", "EngineControlManager", "TorqueLimit", "uint16"),
        ],
    },
    "adas": {
        "title": "Driver Assistance Perception System", "code": "ADA",
        "components": [
            ("PerceptionManager", "Coordinator", "Fuses object lists and publishes the environment model."),
            ("RadarControl", "Provider", "Delivers radar object distance and velocity."),
            ("CameraControl", "Provider", "Delivers lane and object detections."),
            ("BrakeAssistControl", "Consumer", "Requests braking when a collision is predicted."),
            ("LaneKeepControl", "Consumer", "Computes steering corrections."),
            ("WarningManager", "Consumer", "Raises driver warnings."),
        ],
        "interfaces": [
            ("IRadarObjects", "RadarControl", "PerceptionManager", "ObjectDistance", "uint16"),
            ("ILaneDetection", "CameraControl", "PerceptionManager", "LaneOffset", "int16"),
            ("ICollisionRisk", "PerceptionManager", "BrakeAssistControl", "CollisionRisk", "uint8"),
            ("ISteeringCorrection", "LaneKeepControl", "PerceptionManager", "SteeringAngleCommand", "int16"),
            ("IDriverWarning", "PerceptionManager", "WarningManager", "WarningLevel", "uint8"),
            ("ICameraStatus", "CameraControl", "WarningManager", "CameraStatus", "boolean"),
        ],
    },
    "infotainment": {
        "title": "Infotainment Head Unit", "code": "IVI",
        "components": [
            ("MediaManager", "Coordinator", "Controls playback and source selection."),
            ("AudioControl", "Consumer", "Drives the amplifier and equaliser."),
            ("DisplayControl", "Consumer", "Renders the user interface."),
            ("BluetoothManager", "Provider", "Handles phone pairing and streaming."),
            ("VolumeControl", "Provider", "Reads steering-wheel volume buttons."),
        ],
        "interfaces": [
            ("IVolumeLevel", "VolumeControl", "AudioControl", "VolumeLevel", "uint8"),
            ("IAudioStream", "MediaManager", "AudioControl", "StreamState", "uint8"),
            ("IPhoneConnection", "BluetoothManager", "MediaManager", "PhoneStatus", "boolean"),
            ("IDisplayContent", "MediaManager", "DisplayControl", "TrackTitle", "uint32"),
        ],
    },
    "battery": {
        "title": "Battery Management System", "code": "BMS",
        "components": [
            ("BatteryManager", "Coordinator", "Supervises pack state and limits."),
            ("CellMonitorControl", "Provider", "Measures cell voltages and temperatures."),
            ("ChargeControl", "Consumer", "Regulates charge current."),
            ("ContactorControl", "Consumer", "Opens and closes the high-voltage contactors."),
            ("ThermalManager", "Consumer", "Controls pack cooling."),
        ],
        "interfaces": [
            ("ICellVoltage", "CellMonitorControl", "BatteryManager", "CellVoltage", "uint16"),
            ("ICellTemperature", "CellMonitorControl", "ThermalManager", "CellTemperature", "int16"),
            ("IChargeLimit", "BatteryManager", "ChargeControl", "ChargeCurrentLimit", "uint16"),
            ("IContactorCommand", "BatteryManager", "ContactorControl", "ContactorCommand", "uint8"),
            ("IPackStatus", "BatteryManager", "ThermalManager", "PackStatus", "uint8"),
        ],
    },
    "lighting": {
        "title": "Exterior Lighting System", "code": "LCS",
        "components": [
            ("LightingManager", "Coordinator", "Combines switch and sensor inputs into lamp commands."),
            ("HeadlampControl", "Consumer", "Drives low and high beam outputs."),
            ("IndicatorControl", "Consumer", "Drives turn indicators and hazard lights."),
            ("LightSensorManager", "Provider", "Provides ambient light level."),
            ("SwitchControl", "Provider", "Reads the column switches."),
        ],
        "interfaces": [
            ("IAmbientLight", "LightSensorManager", "LightingManager", "AmbientLightLevel", "uint16"),
            ("ISwitchPosition", "SwitchControl", "LightingManager", "SwitchPosition", "uint8"),
            ("IHeadlampCommand", "LightingManager", "HeadlampControl", "HeadlampCommand", "uint8"),
            ("IIndicatorCommand", "LightingManager", "IndicatorControl", "IndicatorCommand", "uint8"),
        ],
    },
    "thermal": {
        "title": "Climate and Thermal Management", "code": "TMS",
        "components": [
            ("ClimateManager", "Coordinator", "Computes cabin temperature targets."),
            ("CompressorControl", "Consumer", "Controls the A/C compressor."),
            ("BlowerControl", "Consumer", "Controls blower fan speed."),
            ("CabinSensorManager", "Provider", "Measures cabin and outside temperature."),
            ("CoolantControl", "Provider", "Reports coolant circuit state."),
            ("DefrostManager", "Consumer", "Activates window defrost."),
        ],
        "interfaces": [
            ("ICabinTemperature", "CabinSensorManager", "ClimateManager", "CabinTemperature", "int16"),
            ("IOutsideTemperature", "CabinSensorManager", "ClimateManager", "OutsideTemperature", "int16"),
            ("ICompressorRequest", "ClimateManager", "CompressorControl", "CompressorSpeed", "uint16"),
            ("IBlowerRequest", "ClimateManager", "BlowerControl", "BlowerSpeed", "uint8"),
            ("ICoolantState", "CoolantControl", "ClimateManager", "CoolantStatus", "uint8"),
            ("IDefrostRequest", "ClimateManager", "DefrostManager", "DefrostCommand", "uint8"),
        ],
    },
    # ---- held-out TEST domains: never used while developing or tuning ----
    "steering": {
        "title": "Electric Power Steering System", "code": "EPS", "split": "test",
        "components": [
            ("SteeringManager", "Coordinator", "Computes assist torque from driver input."),
            ("TorqueSensorControl", "Provider", "Measures driver steering torque."),
            ("MotorDriveControl", "Consumer", "Drives the assist motor."),
            ("AngleSensorManager", "Provider", "Reports steering wheel angle."),
            ("DiagnosticManager", "Consumer", "Collects steering fault information."),
        ],
        "interfaces": [
            ("IDriverTorque", "TorqueSensorControl", "SteeringManager", "DriverTorque", "int16"),
            ("ISteeringAngle", "AngleSensorManager", "SteeringManager", "WheelAngle", "int16"),
            ("IAssistRequest", "SteeringManager", "MotorDriveControl", "AssistCurrent", "int16"),
            ("IFaultReport", "SteeringManager", "DiagnosticManager", "FaultCode", "uint16"),
            ("IMotorFeedback", "MotorDriveControl", "SteeringManager", "MotorSpeed", "uint16"),
        ],
    },
    "keyless": {
        "title": "Passive Keyless Entry", "code": "PKE", "split": "test",
        "components": [
            ("AccessManager", "Coordinator", "Authorises entry and engine start."),
            ("KeyFobControl", "Provider", "Receives and decodes key fob messages."),
            ("DoorLockControl", "Consumer", "Locks and unlocks the doors."),
            ("ImmobilizerControl", "Consumer", "Releases engine start authorisation."),
            ("ProximitySensorManager", "Provider", "Estimates the key distance."),
        ],
        "interfaces": [
            ("IKeyMessage", "KeyFobControl", "AccessManager", "KeyChallenge", "uint32"),
            ("IKeyDistance", "ProximitySensorManager", "AccessManager", "KeyDistance", "uint8"),
            ("ILockRequest", "AccessManager", "DoorLockControl", "LockState", "boolean"),
            ("IStartRelease", "AccessManager", "ImmobilizerControl", "StartAuthorisation", "boolean"),
        ],
    },
    "wiper": {
        "title": "Wiper and Rain Sensing", "code": "WRS", "split": "test",
        "components": [
            ("WiperManager", "Coordinator", "Selects wiper mode from sensor and switch inputs."),
            ("RainSensorControl", "Provider", "Measures rain intensity."),
            ("WiperMotorControl", "Consumer", "Drives the front wiper motor."),
            ("WasherControl", "Consumer", "Controls the washer pump."),
            ("StalkSwitchManager", "Provider", "Reads wiper stalk switch."),
            ("RearWiperControl", "Consumer", "Drives the rear wiper."),
        ],
        "interfaces": [
            ("IRainIntensity", "RainSensorControl", "WiperManager", "RainIntensity", "uint8"),
            ("IStalkInput", "StalkSwitchManager", "WiperManager", "StalkSetting", "uint8"),
            ("IWiperDrive", "WiperManager", "WiperMotorControl", "WipeInterval", "uint16"),
            ("IWasherDrive", "WiperManager", "WasherControl", "WasherPulse", "uint8"),
            ("IRearWiperDrive", "WiperManager", "RearWiperControl", "RearWipeMode", "uint8"),
        ],
    },
}

DEFECT_KINDS = {
    "wrong_direction": ["V003"],
    "missing_dependency": ["V005"],
    "undefined_interface_on_port": ["V002"],
    "signal_endpoint_mismatch": ["V007"],
}


def spaced(camel: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", camel)


def derive(spec: dict) -> dict:
    """Derive the dependent tables (ports, signals, dependencies, flows) from components/interfaces."""
    ports, signals, deps, flows = [], [], [], []
    for n, (iface, prov, cons, sig, dtype) in enumerate(spec["interfaces"], 1):
        base = iface[1:]
        ports.append([prov, f"{base}_Out", "P-PORT", iface])
        ports.append([cons, f"{base}_In", "R-PORT", iface])
        signals.append([sig, dtype, prov, cons])
        deps.append([prov, "PROVIDES_INTERFACE", iface, f"Publishes {spaced(sig).lower()}."])
        deps.append([cons, "REQUIRES_INTERFACE", iface, f"Consumes {spaced(sig).lower()}."])
        flows.append((f"F-{n:03d}", f"{spaced(sig)} Distribution",
                      f"{prov} publishes {sig} through {iface}. {cons} receives the signal through "
                      f"{base}_In and updates its internal state model."))
    return {"ports": ports, "signals": signals, "dependencies": deps, "flows": flows}


def inject_defects(spec: dict, tables: dict) -> tuple[dict, list[dict]]:
    """Return modified tables and the list of seeded defects (one per kind, on distinct interfaces)."""
    t = {k: [list(r) if isinstance(r, list) else r for r in v] for k, v in tables.items()}
    ifaces = spec["interfaces"]
    defects = []

    # 1. consumer port direction flipped to P-PORT
    iface = ifaces[0]
    for row in t["ports"]:
        if row[0] == iface[2] and row[3] == iface[0]:
            row[2] = "P-PORT"
    defects.append({"kind": "wrong_direction", "subject": iface[0], "expected_rules": ["V003"]})

    # 2. a REQUIRES dependency is dropped
    iface = ifaces[1]
    t["dependencies"] = [r for r in t["dependencies"]
                         if not (r[0] == iface[2] and r[1] == "REQUIRES_INTERFACE" and r[2] == iface[0])]
    defects.append({"kind": "missing_dependency", "subject": iface[0], "expected_rules": ["V005"]})

    # 3. a port references an interface that does not exist
    iface = ifaces[2]
    for row in t["ports"]:
        if row[0] == iface[1] and row[3] == iface[0]:
            row[3] = "I" + iface[0][1:] + "Legacy"
    defects.append({"kind": "undefined_interface_on_port", "subject": iface[0], "expected_rules": ["V002"]})

    # 4. the signal table lists a wrong destination
    iface = ifaces[3 % len(ifaces)]
    wrong = next(c[0] for c in spec["components"] if c[0] not in (iface[1], iface[2]))
    for row in t["signals"]:
        if row[0] == iface[3]:
            row[3] = wrong
    defects.append({"kind": "signal_endpoint_mismatch", "subject": iface[3], "expected_rules": ["V007"]})
    return t, defects


# ---------------------------------------------------------------- PDF rendering

_styles = getSampleStyleSheet()
H = ParagraphStyle("H", parent=_styles["Heading1"], fontSize=15, leading=19, spaceBefore=8, spaceAfter=10)
BODY = ParagraphStyle("B", parent=_styles["BodyText"], fontSize=9.5, leading=14, spaceAfter=8)
TITLE = ParagraphStyle("T", parent=_styles["Title"], fontSize=20, leading=25, spaceAfter=18)


def make_table(data, widths):
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9EAF7")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


def render(path: Path, spec: dict, tables: dict, revision: str) -> None:
    names = ", ".join(c[0] for c in spec["components"][:-1]) + f", and {spec['components'][-1][0]}"
    story = [
        Paragraph(spec["title"].upper(), TITLE),
        Paragraph(f"<b>High-Level Design Document</b><br/>Document ID: HLD-{spec['code']}-001<br/>"
                  f"Revision: {revision}<br/>Status: Approved for Engineering Analysis<br/>"
                  "Classification: Synthetic Demonstration Data"),
        Spacer(1, 10),
        Paragraph("1. System Overview", H),
        Paragraph(f"The {spec['title']} coordinates its functions through typed AUTOSAR interfaces and ports. "
                  "Software components exchange signals through provider and consumer ports.", BODY),
        Paragraph("2. Software Architecture", H),
        Paragraph(f"The primary software components are {names}.", BODY),
        Paragraph("3. Software Components", H),
        make_table([["Component", "Role", "Primary Responsibility"]] + [list(c) for c in spec["components"]],
                   [45, 30, 100]),
        PageBreak(),
        Paragraph("4. Interfaces", H),
        make_table([["Interface", "Provider", "Consumer", "Signals"]]
                   + [[i[0], i[1], i[2], i[3]] for i in spec["interfaces"]], [42, 42, 42, 49]),
        Paragraph("5. Ports", H),
        make_table([["Component", "Port", "Direction", "Interface"]] + tables["ports"], [45, 50, 30, 50]),
        Paragraph("6. Signals", H),
        make_table([["Signal", "Data Type", "Source", "Destination"]] + tables["signals"], [45, 30, 50, 50]),
        PageBreak(),
        Paragraph("7. Dependencies", H),
        make_table([["Source", "Relationship", "Target", "Reason"]] + tables["dependencies"],
                   [42, 43, 40, 50]),
        Paragraph("8. Functional Flows", H),
    ]
    for fid, title, text in tables["flows"]:
        story.append(Paragraph(f"<b>Flow {fid}: {title}</b><br/>{text}", BODY))
    story += [
        Paragraph("9. Integration Constraints", H),
        Paragraph("All provider and consumer ports shall reference compatible interfaces. Signal names shall remain "
                  "consistent between interface definitions and functional flows. Architecture dependencies must "
                  "be traceable to an approved source section.", BODY),
        Paragraph("<b>10. Engineering Traceability</b><br/>This synthetic HLD supports extraction, retrieval, "
                  "validation and revision comparison experiments.", BODY),
    ]
    SimpleDocTemplate(str(path), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm,
                      bottomMargin=18 * mm, title=spec["title"], author="Synthetic Engineering Fixture").build(story)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for key, spec in SPECS.items():
        tables = derive(spec)
        truth = {
            "key": key, "title": spec["title"], "split": spec.get("split", "dev"),
            "component": [c[0] for c in spec["components"]],
            "interface": [i[0] for i in spec["interfaces"]],
            "port": [r[1] for r in tables["ports"]],
            "signal": [r[0] for r in tables["signals"]],
            "dependency": [f"{r[0]} {r[1]} {r[2]}" for r in tables["dependencies"]],
            "functional_flow": [f"{fid}: {title}" for fid, title, _ in tables["flows"]],
            "tables": {"components": spec["components"], "interfaces": spec["interfaces"], **tables},
        }
        defect_tables, defects = inject_defects(spec, tables)
        truth["seeded_defects"] = defects
        render(OUT / f"{key}.pdf", spec, tables, "1.0")
        render(OUT / f"{key}_defect.pdf", spec, defect_tables, "1.1")
        (OUT / f"{key}.truth.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")
        print(f"{key}: {len(spec['components'])} components, {len(spec['interfaces'])} interfaces")


if __name__ == "__main__":
    main()
