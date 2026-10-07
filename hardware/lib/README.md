# hardware/lib: everything the boards are drawn with

Made by `gen/library.py`; do not edit by hand.

- `OWL.kicad_sym`: KiCad's own symbols (flattened), plus the ones drawn for this board
  in `gen/symbols.py` (RP2354A, DRV8874, NS4150B, TMAG5273, the SO-8 P-MOSFET, the
  three-die LED, the PCB coil, the debug connectors, the power symbols).
- `OWL.pretty/`: KiCad's own footprints; Raspberry Pi's QFN-60, inductor and 0402
  footprints (`gen/rpi_minimal/`, MIT licence), so their regulator layout is copied
  exactly; and four drawn in `gen/footprints.py` from their makers' drawings.
- `OWL.3dshapes/`: KiCad's 3D models, plus three drawn for GPiBridge (`gen/models/`).

Licences: KiCad's libraries are CC-BY-SA 4.0 with the KiCad libraries' exception (using
them in a design does not put the design under CC-BY-SA).  Raspberry Pi's footprints
are MIT licensed (`gen/rpi_minimal/LICENSE.txt`).  The rest is this project's (`LICENSE`).
