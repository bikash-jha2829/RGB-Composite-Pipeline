# RGB-Composite-Pipeline
on-demand ingestion and processing of satellite imagery from public STAC and staking it
# Assignment Geospatial : RGB Composite Pipeline

### PS
- 🚀 **Dask, Ray** are our distributed superheroes for data processing!
- 🖥️ **Running Locally?** Remember, we’re not in full driver-worker mode here, so stick with a medium dataset for smooth sailing. (Refer main.py-> calls ->pipeline_manager.py)
- 📈 **Geek Out with Dask Dashboard!** Dive in to monitor memory usage and track stage progress like a pro.
- 🧭 Prefect is our orchaestrator 
- ⚙️ We can leverage Curl/Postman to run workload via fast api -> prefect -> dask/RAY
- In progress work on a 2 use 1 for ML and one for UI 


Outputs are available : data directory

## 📝 Notes & Assumptions

- ? : Why we cataloging raw data : To maintain an internal archive, avoid future data loss, and reduce egress costs from commercial providers.

- ❌ **Tests Not Yet Included**  
  Due to time constraints, unit and integration tests have not been added yet. However, I plan to implement them as a follow-up task.

- 🛰️ **Only Landsat Considered for Simplicity**  
  For simplicity, only **Landsat imagery** is used in this version.  
  The API is generic and supports any satellite collection defined in `config.py`.

- ⚙️ **Dask-Only for Now (Ray-Compatible)**  
  The current implementation uses **Dask** for all processing.  
  However, the architecture is designed to support **Ray** as a drop-in replacement via pluggable task runners.

- 🐳 **Docker Work in Progress**  
  While the `Dockerfile` setup is incomplete, a **Docker Compose** configuration is available to:
  - Launch **Prefect**
  - Set up all required services locally for easier testing and visualization

- 📊 **Jupyter Notebook Included**  
  A sample **Jupyter Notebook** is provided to help visualize output data and inspect the processed imagery interactively.


## Overview

This pipeline enables on-demand ingestion and processing of satellite imagery from public STAC (SpatioTemporal Asset Catalog) APIs such as Sentinel and Landsat. It uses Dask and Ray for efficient, scalable, and lazy computation, and is orchestrated through Prefect.

A FastAPI interface allows users to trigger workflows by submitting inputs like AOI (Area of Interest), TOI (Time of Interest), and desired bands. Once validated, the flow is passed to Prefect, which manages the pipeline execution.

The system processes and stores:

Raw data, updating the Raw STAC Catalog.

Derived composites (e.g., RGB COGs/Zarr), updating the Derived STAC Catalog.



## Architecture


![ScreenRecording2025-05-22at09 48 27-ezgif com-video-to-gif-converter](https://github.com/user-attachments/assets/a589a802-e08b-4c01-b37e-a035ab417dce)


## 🧭 Pipeline Overview

This pipeline dynamically ingests satellite imagery from public STAC APIs such as **Sentinel** and **Landsat**, based on user input.

---

### 🔄 Full Flow

#### 📥 User Input (via FastAPI)
- A POST request is made with a JSON payload:
  ```json
  {
    "aoi": [...],      // Area of Interest
    "toi": "...",      // Time of Interest (ISO interval)
    "bands": [...]     // List of desired spectral bands
  }


#### ⚙️ Prefect Orchestration
The FastAPI service receives the request.
Input is validated.
Prefect triggers a pipeline flow to begin processing.

#### 🧩 Phase 1 – Raw Asset Ingestion
Query the STAC API for satellite scenes that match the given AOI and TOI.
Download raw assets to local disk or an S3-compatible storage bucket.
Create and register a Raw STAC Catalog for traceability and future access.

#### 🧪 Phase 2 – Processing & Derivation
Use Dask (can run on Ray) to lazily load bands as xarrays.
Perform band stacking and compute monthly median RGB composites.
Save derived outputs in cloud-friendly formats: COGs (Cloud-Optimized GeoTIFFs) or Zarr arrays.
Create and publish a Derived STAC Catalog with the newly generated assets.

#### 🔁 Data Reuse & Integration
Both raw and derived STAC catalogs support:
AI/ML pipelines for direct model input using Zarr or COGs.
Front-end UIs to render mosaics or time series views via catalog metadata.
