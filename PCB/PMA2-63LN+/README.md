# Changelog

## Revision C - 2/23/2023

### Added

- SMA connectors dimensioned.

### Changed

- Drawing sheets changed from A4 to Letter size.
- New stackup table format.

### Fixed

- SMA launch pad widened with ground plane cutout to improve Z-matching.
- Mounting holes now correctly part of GND net.

## Revision B - 1/23/2023

### Added

- GCPW cross-section to assembly drawing.
- Board characteristics to assembly drawing.
- Board dimensioning to assembly drawing.
- Test points for DC power as an alternative to SMA.
- Test points for Iadj control.
- More PTH vias around and directly under RF components.
- Layer indicator to top left of assembly drawing.

### Changed

- Stackup changed from 2-layer, 30 mil RO4350b to 4-layer OSHPark specifications.
- Board compacted in attempt to reduce oscillations from quarter-wave resonance.
- Connector references changed from J- to more descriptive names.

### Fixed

- Removed back mask from linear regulator pads to improve thermal conductance.
- Iadj resistor to ground replaced with voltage divider for control from +5VDC to GND.

## Revision A - 7/6/2023

### First revision 🎉🎉🎉

- Board is built on 30-mil Rogers RO4350b with 2 layers. Contains two LNAs with their own linear regulators and a 1 dB attenuator between them to improve return loss.
- Testing shows amplifier instability/oscillations at ~10.8 GHz with both PMA2-63LN+ and PMA2-123LN+. This was caused by shunt capacitance introduced from the relatively large SMA landing pads and Molex center conductor.
- 30-mil substrate proved to be thin and more prone to breakage/flexing, especially when torquing SMA connectors.
