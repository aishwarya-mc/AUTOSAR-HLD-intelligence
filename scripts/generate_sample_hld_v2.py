"""Build revision 2 of the synthetic HLD (changes + seeded defects) from the v1 generator.

Changes vs v1 (useful for demonstrating comparison, impact analysis and validation):
  * New component ClimateControl with interface IClimateState, ports and signal CabinTemperature
  * VehicleSpeed widened uint16 -> uint32
  * Seeded defect: WindowCommand_In is declared as a P-PORT
  * Seeded defect: dependency 'WindowControl REQUIRES_INTERFACE IVehicleState' removed from section 7
"""
from pathlib import Path

HERE = Path(__file__).parent
source = (HERE / "generate_sample_hld.py").read_text(encoding="utf-8")


def sub(old: str, new: str) -> None:
    global source
    assert old in source, f"pattern not found: {old[:40]!r}"
    source = source.replace(old, new, 1)


sub('data/sample/sample_hld.pdf', 'data/sample/sample_hld_v2.pdf')
sub('Revision: 1.0', 'Revision: 2.0')
sub('''        "Provides vehicle-level state information including vehicle speed.",
    ],
]''', '''        "Provides vehicle-level state information including vehicle speed.",
    ],
    [
        "ClimateControl",
        "Provider",
        "Publishes cabin temperature information.",
    ],
]''')
sub('''        "VehicleSpeed",
    ],
]

story.append(make_table(interface_data''', '''        "VehicleSpeed",
    ],
    [
        "IClimateState",
        "ClimateControl",
        "BodyControlManager",
        "CabinTemperature",
    ],
]

story.append(make_table(interface_data''')
sub('''        "VehicleState_In",
        "R-PORT",
        "IVehicleState",
    ],
]''', '''        "VehicleState_In",
        "R-PORT",
        "IVehicleState",
    ],
    [
        "ClimateControl",
        "ClimateState_Out",
        "P-PORT",
        "IClimateState",
    ],
    [
        "BodyControlManager",
        "ClimateState_In",
        "R-PORT",
        "IClimateState",
    ],
]''')
sub('''        "WindowCommand_In",
        "R-PORT",''', '''        "WindowCommand_In",
        "P-PORT",''')
sub('''        "uint16",
        "VehicleStateManager",
        "WindowControl",
    ],
]''', '''        "uint32",
        "VehicleStateManager",
        "WindowControl",
    ],
    [
        "CabinTemperature",
        "int16",
        "ClimateControl",
        "BodyControlManager",
    ],
]''')
sub('''    [
        "WindowControl",
        "REQUIRES_INTERFACE",
        "IVehicleState",
        "Uses vehicle speed.",
    ],
]''', '''    [
        "ClimateControl",
        "PROVIDES_INTERFACE",
        "IClimateState",
        "Publishes cabin temperature.",
    ],
    [
        "BodyControlManager",
        "REQUIRES_INTERFACE",
        "IClimateState",
        "Consumes cabin temperature.",
    ],
]''')
exec(compile(source, "generate_sample_hld_v2", "exec"))
