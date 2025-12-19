# Assets Directory

This directory stores binary assets and files referenced by items.

## Directory Structure

Organize assets by system and type:

```
assets/
  docs/
    FPS/
      FID/
        design_report_v1.pdf
    SPS/
      DET/
        detector_spec.pdf
  data/
    FPS/
      FID/
        positioning_test_results.fits
  images/
    diagrams/
      system_architecture.png
```

## Guidelines

1. **Do not embed binaries in YAML/JSON** - Store files here and reference them by path
2. **Use relative paths** - Reference as `assets/docs/FPS/FID/design_report.pdf`
3. **Version large files** - Consider Git LFS for files > 10MB
4. **Naming convention** - Use lowercase with underscores, include version if applicable

## File Types

Supported and commonly used file types:
- Documents: PDF, DOCX, MD
- Data: FITS, HDF5, CSV, JSON
- Images: PNG, JPG, SVG
- Presentations: PPTX, PDF

## References

To reference an asset in an item, use the `file_path` field (for DOC/DAT types)
or include the path in the item text.

