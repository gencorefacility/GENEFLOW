# Changelog

All notable changes to this project will be documented in this file, effective May 2025.

## [2025-10-21]
### Updated
- Updated Picard Tools to version 3.4.0
- Updated JDK to openjdk/17.0.2

## [2025-09-04]
### Updated
- Updated Bases2Fastq to version 2.2.0

## [2025-05-25]  
### Changed  
- Source **Num PF reads** exclusively from SAV (Illumina) or `AvitiRunStats.json`.
- Code cleanup and refactoring for readability and maintenance.

### Improved  
- Now include `PhiX %` and `Total # of Reads` in the QC report for Aviti runs.

## [2025-05-02]  
### Improved  
- `get_num_lanes()` now reads from local files instead of the TuboWeb (LIMS) API to avoid silent mis-counts if LIMS is stale or a lane failed.
