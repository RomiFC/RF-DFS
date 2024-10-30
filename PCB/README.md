# Board Files

Any footprints, symbols, and models, not included with KiCad 7.0/8.0 should be added the libraries in [_dependencies](./_dependencies). Ensure that all projects are in their own directory and that each project is linked to the following library paths:

### Footprints

```pcbnew
${KIPRJMOD}/../_dependencies/footprints
```

### Symbols

```pcbnew
${KIPRJMOD}/../_dependencies/symbols/rf-dfs.kicad_sym
```

### 3D Models

Footprints should be linked to imported 3D models using the following path:

```pcbnew
${KIPRJMOD}/../_dependencies/3dmodels/<FILE_NAME>.STEP
```
