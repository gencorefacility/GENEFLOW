# Changelog

All notable changes to this project will be documented in this file, effective May 2025.

## [2025-06-01]                                                                                                                       
### Changed                                                                                                                           
- Switched from HPC modules to containers (Apptainer/Conda)                         
- Replaced Nextflow `-entry` flag with `--workflow_type` parameter and a dispatcher workflow.                                                                   
                                                                                                                                     
### Added                                                                                                                             
- Regression test suite (`launch_tests.sh`, `compare_runs.py`) for validating pipeline output against ground truth.                   
- Version-tracking artifacts (`*_version.yml`) for basecalling and demultiplexing, aggregated into MultiQC reports.                                                                                                                   
                                                                                                                                      
### Fixed                                                                                                                             
- Process stream blocking in `get_num_lanes` that could cause the pipeline to hang.  

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
