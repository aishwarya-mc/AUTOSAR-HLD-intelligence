from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)


OUTPUT = Path("data/sample/sample_hld.pdf")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)


styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    "HLDTitle",
    parent=styles["Title"],
    alignment=TA_CENTER,
    fontSize=20,
    leading=25,
    spaceAfter=18,
)

heading_style = ParagraphStyle(
    "HLDHeading",
    parent=styles["Heading1"],
    fontSize=15,
    leading=19,
    spaceBefore=8,
    spaceAfter=10,
)

subheading_style = ParagraphStyle(
    "HLDSubHeading",
    parent=styles["Heading2"],
    fontSize=12,
    leading=15,
    spaceBefore=6,
    spaceAfter=6,
)

body_style = ParagraphStyle(
    "HLDBody",
    parent=styles["BodyText"],
    fontSize=9.5,
    leading=14,
    spaceAfter=8,
)


def p(text, style=body_style):
    return Paragraph(text, style)


def make_table(data, widths):
    table = Table(data, colWidths=widths, repeatRows=1)

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9EAF7")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    return table


doc = SimpleDocTemplate(
    str(OUTPUT),
    pagesize=A4,
    rightMargin=18 * mm,
    leftMargin=18 * mm,
    topMargin=18 * mm,
    bottomMargin=18 * mm,
    title="AUTOSAR Body Control System High-Level Design",
    author="Synthetic Engineering Fixture",
)

story = []

# Title
story.append(p("AUTOSAR BODY CONTROL SYSTEM", title_style))
story.append(
    p(
        "<b>High-Level Design Document</b><br/>"
        "Document ID: HLD-BCS-001<br/>"
        "Revision: 1.0<br/>"
        "Status: Approved for Engineering Analysis<br/>"
        "Classification: Synthetic Demonstration Data"
    )
)
story.append(Spacer(1, 10))

story.append(p("1. System Overview", heading_style))
story.append(
    p(
        "The Body Control System (BCS) coordinates body-related vehicle "
        "functions including door state monitoring, window commands, and "
        "vehicle state information. The architecture follows an AUTOSAR "
        "software-component model in which software components communicate "
        "through typed interfaces and ports."
    )
)

story.append(p("2. Software Architecture", heading_style))
story.append(
    p(
        "The primary software components are BodyControlManager, "
        "DoorControl, WindowControl, and VehicleStateManager. "
        "BodyControlManager acts as the central coordination component. "
        "DoorControl publishes door state information. WindowControl "
        "consumes window commands. VehicleStateManager provides vehicle "
        "state information such as vehicle speed."
    )
)

story.append(p("3. Software Components", heading_style))

component_data = [
    ["Component", "Role", "Primary Responsibility"],
    [
        "BodyControlManager",
        "Coordinator",
        "Coordinates body-control functions and consumes door and vehicle state information.",
    ],
    [
        "DoorControl",
        "Provider",
        "Monitors door status and publishes door-state information.",
    ],
    [
        "WindowControl",
        "Consumer",
        "Controls window operation based on commands and vehicle state.",
    ],
    [
        "VehicleStateManager",
        "Provider",
        "Provides vehicle-level state information including vehicle speed.",
    ],
]

story.append(make_table(component_data, [40 * mm, 30 * mm, 105 * mm]))
story.append(PageBreak())

# Interfaces
story.append(p("4. Interfaces", heading_style))

interface_data = [
    ["Interface", "Provider", "Consumer", "Signals"],
    [
        "IDoorStatus",
        "DoorControl",
        "BodyControlManager",
        "DoorOpenStatus",
    ],
    [
        "IWindowCommand",
        "BodyControlManager",
        "WindowControl",
        "WindowPosition",
    ],
    [
        "IVehicleState",
        "VehicleStateManager",
        "WindowControl",
        "VehicleSpeed",
    ],
]

story.append(make_table(interface_data, [38 * mm, 38 * mm, 42 * mm, 57 * mm]))

story.append(p("5. Ports", heading_style))

port_data = [
    ["Component", "Port", "Direction", "Interface"],
    [
        "DoorControl",
        "DoorStatus_Out",
        "P-PORT",
        "IDoorStatus",
    ],
    [
        "BodyControlManager",
        "DoorStatus_In",
        "R-PORT",
        "IDoorStatus",
    ],
    [
        "BodyControlManager",
        "WindowCommand_Out",
        "P-PORT",
        "IWindowCommand",
    ],
    [
        "WindowControl",
        "WindowCommand_In",
        "R-PORT",
        "IWindowCommand",
    ],
    [
        "VehicleStateManager",
        "VehicleState_Out",
        "P-PORT",
        "IVehicleState",
    ],
    [
        "WindowControl",
        "VehicleState_In",
        "R-PORT",
        "IVehicleState",
    ],
]

story.append(make_table(port_data, [45 * mm, 45 * mm, 30 * mm, 55 * mm]))

story.append(p("6. Signals", heading_style))

signal_data = [
    ["Signal", "Data Type", "Source", "Destination"],
    [
        "DoorOpenStatus",
        "boolean",
        "DoorControl",
        "BodyControlManager",
    ],
    [
        "WindowPosition",
        "uint8",
        "BodyControlManager",
        "WindowControl",
    ],
    [
        "VehicleSpeed",
        "uint16",
        "VehicleStateManager",
        "WindowControl",
    ],
]

story.append(make_table(signal_data, [40 * mm, 35 * mm, 50 * mm, 50 * mm]))

story.append(PageBreak())

# Dependencies
story.append(p("7. Dependencies", heading_style))

dependency_data = [
    ["Source", "Relationship", "Target", "Reason"],
    [
        "DoorControl",
        "PROVIDES_INTERFACE",
        "IDoorStatus",
        "Publishes door state.",
    ],
    [
        "BodyControlManager",
        "REQUIRES_INTERFACE",
        "IDoorStatus",
        "Consumes door state.",
    ],
    [
        "BodyControlManager",
        "PROVIDES_INTERFACE",
        "IWindowCommand",
        "Generates window commands.",
    ],
    [
        "WindowControl",
        "REQUIRES_INTERFACE",
        "IWindowCommand",
        "Consumes window commands.",
    ],
    [
        "VehicleStateManager",
        "PROVIDES_INTERFACE",
        "IVehicleState",
        "Provides vehicle state.",
    ],
    [
        "WindowControl",
        "REQUIRES_INTERFACE",
        "IVehicleState",
        "Uses vehicle speed.",
    ],
]

story.append(make_table(dependency_data, [40 * mm, 43 * mm, 43 * mm, 54 * mm]))

story.append(p("8. Functional Flows", heading_style))

story.append(
    p(
        "<b>Flow F-001: Door State Monitoring</b><br/>"
        "DoorControl reads the physical door state and publishes "
        "DoorOpenStatus through IDoorStatus. BodyControlManager receives "
        "the signal through DoorStatus_In and updates the body-state model."
    )
)

story.append(
    p(
        "<b>Flow F-002: Window Command</b><br/>"
        "BodyControlManager evaluates the requested window operation and "
        "publishes WindowPosition through IWindowCommand. WindowControl "
        "receives the command through WindowCommand_In."
    )
)

story.append(
    p(
        "<b>Flow F-003: Vehicle State Dependency</b><br/>"
        "VehicleStateManager publishes VehicleSpeed through IVehicleState. "
        "WindowControl consumes VehicleSpeed to apply safety-related "
        "window-operation constraints."
    )
)

story.append(p("9. Integration Constraints", heading_style))
story.append(
    p(
        "All provider and consumer ports shall reference compatible "
        "interfaces. Signal names shall remain consistent between interface "
        "definitions and functional flows. Architecture dependencies must "
        "be traceable to an approved source section."
    )
)

story.append(
    p(
        "<b>10. Engineering Traceability</b><br/>"
        "This synthetic HLD is intentionally structured to support "
        "document extraction, semantic retrieval, relationship mapping, "
        "validation, revision comparison, and evidence-based question "
        "answering."
    )
)

doc.build(story)

print(f"Created: {OUTPUT}")
print(f"Size: {OUTPUT.stat().st_size} bytes")
