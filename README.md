
# NMRS ART Line List Data Processing APP (2nd & 3rd 95 Analysis)

This project provides a Flask-based API for processing **ART Line List** data files to generate analyses for the **2nd 95** and **3rd 95** HIV epidemic control targets.  

The API accepts ART line list files (and optionally baseline and case manager files), applies data cleaning and merging logic, and produces downloadable reports.


## 🚀 Features

- Upload ART Line List files (`Excel` or `CSV`) for processing
- Supports multiple inputs:
  - `file1`: ART Line List (required)
  - `file2`: Baseline file (optional)
  - `file3`: Case Manager assignment file (optional)
- Generates **3rd 95 Analysis** (`/fetch` endpoint)
- Generates **2nd 95 Analysis** (`/fetch2nd95` endpoint)
- Case Manager mapping support for assigning clients
- Baseline comparison support for longitudinal analysis
- Download generated reports via `/download/<filename>` endpoint## ⚙️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/netocodez/emr-analysis-api.git
   cd emr-analysis-api

2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

3. Install dependencies
pip install -r requirements.txt

4. Run the Flask app
flask run



    🛠️ APP Endpoints
1. 3rd 95 Analysis

POST /fetch

Inputs:

file1 → ART Line List (required)

file2 → Baseline file (optional)

file3 → Case Manager file (optional)

endDate → Reporting end date

Response:
{
  "message": "3RD 95 Analysis completed successfully.",
  "download_url": "/download/output_filename.xlsx"
}


2. 2nd 95 Analysis

POST /fetch2nd95

Inputs:

file1 → ART Line List (required)

file2 → Baseline file (optional)

file3 → Case Manager file (optional)

endDate → Reporting end date

Response:
{
  "message": "2ND 95 Analysis completed successfully.",
  "download_url": "/download/output_filename.xlsx"
}


---

#### **Project Structure**


## Documentation

Input File Requirements

ART Line List (file1) → Must contain patient-level data with required fields such as uuid, dates, ART status, etc.

Baseline File (file2) → Must include uuid and CurrentARTStatus.

Case Manager File (file3) → Must include uuid and CASE MANAGER.

curl -X POST http://127.0.0.1:5000/fetch \
  -F "file1=@ART_LineList.xlsx" \
  -F "endDate=2025-06-30"


curl -X POST http://127.0.0.1:5000/fetch2nd95 \
  -F "file1=@ART_LineList.xlsx" \
  -F "file2=@Baseline.xlsx" \
  -F "file3=@CaseManagers.xlsx" \
  -F "endDate=2025-06-30"


# Error Handling

Returns 400 for invalid/missing files.

Returns 500 with traceback if processing fails.

Returns 404 if a requested download file is missing.


# License

This project is licensed under the MIT License.
See the LICENSE
 file for details.


# Contributing

Fork the repository.

Create a new branch (feature/my-feature).

Commit your changes.

Push to your branch.

Open a Pull Request.


👨 Author

Developed and maintained by [netocodez]


---

Would you like me to also add **badges** (build status, Python version, license, etc.) at the top so it looks more like a professional GitHub README?
## 🚀 Deployment

You can deploy this app on platforms like **Render**, **Heroku**, or **Docker**.

Example (Heroku):
```bash
git push heroku main
heroku open
