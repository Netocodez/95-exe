import pandas as pd
import numpy as np
import os
from io import BytesIO
from datetime import datetime

from pathlib import Path
from utils.paths import OUTPUTS

BASE_DIR = Path(__file__).resolve().parents[2]
CSV_FILE = BASE_DIR / "LAMISNMRS.csv"

emr_df = pd.read_csv(CSV_FILE, encoding="utf-8")

#Filter and process line list        
columns_to_select = ["S/N", "State", "LGA", "FacilityName", "PEPID", "PatientHospitalNo", "uuid", "Sex", "Current_Age", "Surname", "Firstname", "MaritalStatus", "PhoneNo", "Address", "State_of_Residence", "LGA_of_Residence", "DateConfirmedHIV+", "ARTStartDate", "Pharmacy_LastPickupdate", "DaysOfARVRefill", "CurrentARTRegimen", "NextAppt", "CurrentPregnancyStatus", "CurrentViralLoad", "DateResultReceivedFacility", "Alphanumeric_Viral_Load_Result", "LastDateOfSampleCollection", "Outcomes", "Outcomes_Date", "IIT_Date", "ARTStatus_PreviousQuarter", "CurrentARTStatus", "First_TPT_Pickupdate", "Current_TPT_Received", "Current_TB_Status", "PBS_Capturee", "PBS_Capture_Date", "Date_Generated", "CaseManager"]
columns_to_select2 = ["S/N", "State", "LGA", "FacilityName", "PEPID", "PatientHospitalNo", "uuid", "Sex", "Current_Age", "Surname", "Firstname", "MaritalStatus", "PhoneNo", "Address", "State_of_Residence", "LGA_of_Residence", "DateConfirmedHIV+", "ARTStartDate", "Pharmacy_LastPickupdate", "DaysOfARVRefill", "CurrentARTRegimen", "NextAppt", "CurrentPregnancyStatus", "CurrentViralLoad", "DateResultReceivedFacility", "Alphanumeric_Viral_Load_Result", "LastDateOfSampleCollection", "Outcomes", "Outcomes_Date", "IIT_Date", "ARTStatus_PreviousQuarter", "CurrentARTStatus", "First_TPT_Pickupdate", "Current_TPT_Received", "Current_TB_Status", "PBS_Capturee", "PBS_Capture_Date", "Date_Generated"]

#function to process line list
def process_Linelist(df, column_name, filter_value, columns_to_select, sort_by=None, ascending=True):
    # Filter the DataFrame
    df_filtered = df[df[column_name] == filter_value].reset_index(drop=True)

    # Sort if sort_by is specified and column(s) exist
    if sort_by:
        if isinstance(sort_by, list):
            valid_sort_cols = [col for col in sort_by if col in df_filtered.columns]
        else:
            valid_sort_cols = [sort_by] if sort_by in df_filtered.columns else []

        if valid_sort_cols:
            df_filtered = df_filtered.sort_values(by=valid_sort_cols, ascending=ascending).reset_index(drop=True)

    # Insert Serial Number
    df_filtered.insert(0, 'S/N', df_filtered.index + 1)

    # Select only existing columns
    existing_columns = [col for col in columns_to_select if col in df_filtered.columns]
    df_selected = df_filtered[existing_columns]

    return df_selected

def clean_id(val):
    return str(val).strip().lower().replace(' ', '').lstrip('0') if pd.notna(val) else ''

def appendLamisData(df, dfbaseline, emr_df):
    # Remove rows with any blank fields in mapping
    emr_df = emr_df[(emr_df != '').all(axis=1)]
    
    # Select and deduplicate necessary columns from emr_df
    emr_subset = emr_df[['Name on NMRS', 'LGA', 'STATE', 'Name on Lamis']].drop_duplicates(subset='Name on NMRS')

    # Merge once using FacilityName <-> Name on NMRS
    df = df.merge(
        emr_subset,
        how='left',
        left_on='FacilityName',
        right_on='Name on NMRS',
        suffixes=('', '_emr')
    )

    # Fill missing LGA and State from EMR
    df['LGA'] = df['LGA'].fillna(df['LGA_emr'])
    df['State'] = df['State'].fillna(df['STATE'])

    # Replace FacilityName if different
    df.loc[df['Name on Lamis'] != df['FacilityName'], 'FacilityName'] = df['Name on Lamis']

    # Drop extra columns
    df.drop(['Name on NMRS', 'LGA_emr', 'STATE', 'Name on Lamis'], axis=1, inplace=True)

    # Normalize hospital numbers and unique IDs
    df['PatientHospitalNo1'] = df['PatientHospitalNo'].apply(clean_id)
    df['PatientUniqueID1'] = df['PEPID'].apply(clean_id)
    dfbaseline['Hospital Number1'] = dfbaseline['Hospital Number'].apply(clean_id)
    dfbaseline['Unique ID1'] = dfbaseline['Unique ID'].apply(clean_id)

    # Create consistent unique identifiers for both datasets
    dfbaseline['unique identifiers'] = (
        dfbaseline["LGA"].astype(str).str.lower().str.strip().str.replace(' ', '') +
        dfbaseline["Facility"].astype(str).str.lower().str.strip().str.replace(' ', '') +
        dfbaseline["Hospital Number1"] +
        dfbaseline["Unique ID1"]
    )

    df['unique identifiers'] = (
        df["LGA"].astype(str).str.lower().str.strip().str.replace(' ', '') +
        df["FacilityName"].astype(str).str.lower().str.strip().str.replace(' ', '') +
        df["PatientHospitalNo1"] +
        df["PatientUniqueID1"]
    )

    # Drop duplicates from baseline data
    dfbaseline = dfbaseline.drop_duplicates(subset=['unique identifiers'], keep=False)

    # Identify duplicates in 'unique identifiers'
    dup_mask = df.duplicated('unique identifiers', keep=False)

    # Only modify duplicates
    df.loc[dup_mask, 'unique identifiers'] = (
        df.loc[dup_mask]
        .groupby('unique identifiers')
        .cumcount()
        .astype(str)
        .radd(df.loc[dup_mask, 'unique identifiers'] + '_')
    )

    # Merge into df
    df = df.merge(
        dfbaseline[['unique identifiers', 'Date of TPT Start (yyyy-mm-dd)', 'TPT Type']],
        on='unique identifiers',
        how='left',
        suffixes=('', '_baseline')
    )

    # Fill missing TPT values
    df['Date of TPT Start (yyyy-mm-dd)'] = pd.to_datetime(df['Date of TPT Start (yyyy-mm-dd)'], errors='coerce', dayfirst=True)
    df['First_TPT_Pickupdate'] = pd.to_datetime(df['First_TPT_Pickupdate'], errors='coerce', dayfirst=True)
    df['First_TPT_Pickupdate'] = df['First_TPT_Pickupdate'].fillna(df['Date of TPT Start (yyyy-mm-dd)'])
    df['Current_TPT_Received'] = df['Current_TPT_Received'].fillna(df['TPT Type'])

    return df


def ensureLGAState(df, emr_df):
    # Remove rows with any blank fields in mapping
    emr_df = emr_df[(emr_df != '').all(axis=1)]
    
    # Select and deduplicate necessary columns from emr_df
    emr_subset = emr_df[['Name on NMRS', 'LGA', 'STATE', 'Name on Lamis']].drop_duplicates(subset='Name on NMRS')

    # Merge once using FacilityName <-> Name on NMRS
    df = df.merge(
        emr_subset,
        how='left',
        left_on='FacilityName',
        right_on='Name on NMRS',
        suffixes=('', '_emr')
    )

    # Fill missing LGA and State from EMR
    df['LGA'] = df['LGA'].fillna(df['LGA_emr'])
    df['State'] = df['State'].fillna(df['STATE'])

    # Drop extra columns
    df.drop(['Name on NMRS', 'LGA_emr', 'STATE', 'Name on Lamis'], axis=1, inplace=True)
    
    return df

def calculate_age_vectorized(df, dob_col="DOB", ref_date=None):

    if ref_date is None:
        today = pd.Timestamp.today().normalize()
    else:
        today = pd.to_datetime(ref_date)

    # Clean and convert DOB
    dob = (
        df[dob_col]
        .astype(str)
        .str.strip()
        .replace({"": None, "nan": None})
    )

    dob = pd.to_datetime(dob, errors="coerce", dayfirst=True)

    # Calculate age safely
    age = (
        today.year - dob.dt.year
        - (
            (dob.dt.month > today.month) |
            ((dob.dt.month == today.month) & (dob.dt.day > today.day))
        ).astype(int)
    )

    # Keep NaN where DOB invalid
    age = age.where(dob.notna())

    return age

def calculate_age_vectorized2(dob_series, ref_date=None):
        """
        Vectorized age calculation equivalent to Excel:
        =DATEDIF(DOB, ref_date, "Y")
        """
        if ref_date is None:
            ref_date = pd.Timestamp.today().normalize()
        else:
            ref_date = pd.to_datetime(ref_date)

        dob = pd.to_datetime(dob_series, errors='coerce')

        age = (
            ref_date.year - dob.dt.year
            - (
                (dob.dt.month > ref_date.month) |
                ((dob.dt.month == ref_date.month) & (dob.dt.day > ref_date.day))
            ).astype(int)
        )

        return age

def sc_gap_mask(
        df: pd.DataFrame,
        end_date: str | pd.Timestamp,
        last_sample_col: str = "LastDateOfSampleCollection",
        art_start_col: str = "ARTStartDate",
        age_col: str = "Age"
    ) -> pd.Series:

    today = pd.to_datetime(end_date)
    end_of_quarter = today + pd.tseries.offsets.QuarterEnd(0)
    one_year_ago_quarter_end = (today - pd.DateOffset(years=1)) + pd.tseries.offsets.QuarterEnd(0)
    six_months_ago = today - pd.DateOffset(months=6) + pd.tseries.offsets.QuarterEnd(0)

    art_start = pd.to_datetime(df[art_start_col], errors="coerce", dayfirst=True)
    sample_date = pd.to_datetime(df[last_sample_col], errors="coerce", dayfirst=True)
    
    # months on ART as at end_of_quarter
    months_on_art = (
        (end_of_quarter.year - art_start.dt.year) * 12 +
        (end_of_quarter.month - art_start.dt.month) -
        (art_start.dt.day > end_of_quarter.day)
    )

    # Adults: no sample or last sample > 12 months ago
    adult_mask = (df[age_col] >= 15) & ((sample_date.isna()) | (sample_date <= one_year_ago_quarter_end))

    # Pediatrics: no sample or last sample > 6 months ago
    ped_mask = (df[age_col] < 15) & ((sample_date.isna()) | (sample_date <= six_months_ago))

    mask = (
        (df['CurrentARTStatus'] == 'Active') &
        (df['ARTStatus_PreviousQuarter'] == 'Active') &
        (months_on_art >= 6) &
        (adult_mask | ped_mask)
    )

    return mask

def tpt_gap_mask(df):
    """
    Returns True for clients who require TPT initiation.
    """

    mask = (
        (df['Current_TB_Status'] == "No signs or symptoms of disease") &
        (df['CurrentARTStatus'] == "Active") &
        df['First_TPT_Pickupdate'].isna() &
        df['Current_TPT_Received'].isna()
    )

    return mask

def export_to_excel_with_formatting(dataframes, formatted_period, summaryName="2ND 95 SUMMARY",
                                    column_widths=None, row_masks=None, column_config=None):

    if row_masks is None:
        row_masks = {}

    output = BytesIO()
    writer = pd.ExcelWriter(output, engine="xlsxwriter")

    # ----------------------------
    # Strip datetime columns
    # ----------------------------
    for df_name, df in dataframes.items():
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.date

    # ---------- CLEAN NUMERICS (avoid XlsxWriter NaN/Inf error) ----------
    for df_name, df in dataframes.items():
        num_cols = df.select_dtypes(include=[np.number]).columns
        if len(num_cols) > 0:
            df[num_cols] = df[num_cols].replace([np.inf, -np.inf], np.nan).fillna(0)

    # ----------------------------
    # Process each sheet
    # ----------------------------
    for sheet_name, df in dataframes.items():
        # initial write (we will rewrite content for the summary sheet later)
        df.to_excel(writer, sheet_name=sheet_name, startrow=1, header=False, index=False)
        workbook = writer.book
        worksheet = writer.sheets[sheet_name]

        # ----------------------------
        # Formats
        # ----------------------------
        header_format = workbook.add_format({
            "bold": True, "text_wrap": True, "valign": "bottom",
            "fg_color": "#D7E4BC", "border": 1
        })
        percentage_format = workbook.add_format({'num_format': '0.00%'})
        percentage_bold = workbook.add_format({
            "bold": True, "text_wrap": True, "valign": "bottom",
            "fg_color": "#D7E4BC", "border": 1, 'num_format': '0.00%'
        })
        row_band_format = workbook.add_format({'bg_color': '#F9F9F9'})
        alert_format = workbook.add_format({'bg_color': '#FFA500'})
        ok_format = workbook.add_format({'bg_color': '#C6EFCE'})  # light green
        mask_format = workbook.add_format({'bg_color': '#FFEB9C'})
        title_format = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center'})
        grand_total_format = workbook.add_format({
            "bold": True, "text_wrap": True, "valign": "vcenter",
            "fg_color": "#C6EFCE", "font_color": "#006100",
            "border": 2, "font_size": 12
        })
        grand_total_percentage_format = workbook.add_format({
            "bold": True, "valign": "vcenter",
            "fg_color": "#C6EFCE", "font_color": "#000300",
            "border": 2, "num_format": "0.00%", "font_size": 12
        })
        
        def col_idx_to_excel(col_idx):
            div, mod = divmod(col_idx, 26)
            return chr(65 + mod) if div == 0 else chr(64 + div) + chr(65 + mod)

        # ----------------------------
        # Write headers (top-left cell used for title in summary)
        # ----------------------------
        for col_num, value in enumerate(df.columns):
            worksheet.write(0, col_num, value, header_format)

        # ----------------------------
        # Summary Sheet
        # ----------------------------
        if sheet_name == summaryName:

            cfg = column_config.get(sheet_name, {}) if column_config else {}

            # 1️⃣ Title
            title_text = cfg.get("title", f"2ND 95 SUMMARY AS AT {formatted_period}")
            title_text = title_text.replace("{period}", formatted_period)

            # 2️⃣ Merge range for title
            merge_start, merge_end = cfg.get("merge_columns", (0, 2))

            # Merge title row
            worksheet.merge_range(0, 0, 0, len(df.columns) - 1, title_text, title_format)

            # Rewrite header below title
            for col_num, value in enumerate(df.columns):
                worksheet.write(1, col_num, value, header_format)

            # Write dataframe starting at row 2 (we will rewrite later)
            df.to_excel(writer, sheet_name=sheet_name, startrow=2, header=False, index=False)

            numeric_cols = cfg.get("numeric_cols", [3,4,5,6,8,9,10,11,12,13,14,15,17,18])
            print(f"Using numeric_cols for {sheet_name}: {numeric_cols}")

            percent_formulas = cfg.get("percent_formulas", {
                "%Weekly Refill Rate": "=G{subtotal_row}/F{subtotal_row}",
                "%Biometrics Coverage": "=P{subtotal_row}/D{subtotal_row}"
            })

            #worksheet.conditional_format(2, 0, 2 + max(len(df)-1, 0), len(df.columns)-1,
                                         #{'type': 'formula','criteria':'MOD(ROW(),2)=0','format':row_band_format})

            worksheet.hide_gridlines(2)

            # Column widths
            if column_widths:
                for col_range, width in column_widths.items():
                    worksheet.set_column(col_range, width)

            # ----------------------------
            # Subtotals per facility (PRECOMPUTED LAYOUT + MAPPING)
            # ----------------------------
            facility_col = 1
            start_row = 2  # Data starts at row 2 due to title + header
            df_len = len(df)

            # STEP 1 — Build layout with space for subtotals
            layout = []  # will contain ("data", df_idx) or ("subtotal", facility_name, start_idx, end_idx)

            i = 0
            while i < df_len:
                facility_name = df.iloc[i, facility_col]

                block_start = i
                block_end = i

                # Find contiguous facility block
                while block_end < df_len and df.iloc[block_end, facility_col] == facility_name:
                    block_end += 1

                # Add data rows (df index)
                for r in range(block_start, block_end):
                    layout.append(("data", r))

                # Add a subtotal placeholder row after the block
                layout.append(("subtotal", facility_name, block_start, block_end - 1))

                i = block_end

            # STEP 2 — Rewrite the sheet: write rows using layout and track mapping
            worksheet.set_default_row(15)
            worksheet.autofilter(1, 0, 1, len(df.columns)-1)

            excel_row = start_row
            subtotal_rows = []
            df_to_excel_row = {}  # map df index -> actual excel row (0-based)

            for item in layout:

                if item[0] == "data":
                    df_idx = item[1]
                    row_values = df.iloc[df_idx].tolist()
                    worksheet.write_row(excel_row, 0, row_values)
                    # record mapping
                    df_to_excel_row[df_idx] = excel_row
                    excel_row += 1

                else:  # subtotal row
                    facility_name, block_start, block_end = item[1], item[2], item[3]
                    subtotal_rows.append(excel_row + 1)  # Excel numbering (1-based)

                    # Label
                    worksheet.merge_range(
                        excel_row, merge_start,
                        excel_row, merge_end,
                        f"Subtotal – {facility_name}",
                        header_format
                    )

                    # Defensive: ensure mapping exists for block start/end
                    if block_start not in df_to_excel_row or block_end not in df_to_excel_row:
                        # If mapping missing (should not happen), skip formulas but still advance the row
                        excel_row += 1
                        continue

                    excel_start = df_to_excel_row[block_start]
                    excel_end = df_to_excel_row[block_end]

                    # Numeric subtotal formulas using mapped excel rows
                    for col in numeric_cols:
                        col_letter = col_idx_to_excel(col)
                        formula = f"=SUM({col_letter}{excel_start+1}:{col_letter}{excel_end+1})"
                        worksheet.write_formula(excel_row, col, formula, header_format)

                    # Percentage formulas (they reference the subtotal row itself)
                    for col_name, formula in percent_formulas.items():
                        if col_name in df.columns:
                            col_idx = df.columns.get_loc(col_name)
                            applied = formula.replace("{subtotal_row}", str(excel_row + 1))
                            worksheet.write_formula(excel_row, col_idx, applied, percentage_format)

                    excel_row += 1
                    
            # Apply 3-color scales to percentage columns AFTER df_to_excel_row and subtotal_rows are defined
            for col_name in percent_formulas.keys():
                if col_name in df.columns:
                    col_idx = df.columns.get_loc(col_name)
                    # Apply percentage format to the entire column
                    worksheet.set_column(col_idx, col_idx, None, percentage_format)

                    # Determine rows to format
                    min_row = min(df_to_excel_row.values())
                    max_row = max(df_to_excel_row.values())
                    if subtotal_rows:
                        max_row = max(max_row, max(subtotal_rows))  # include subtotal rows

                    # Apply 3-color scale
                    worksheet.conditional_format(min_row, col_idx, max_row, col_idx, {
                        'type': '3_color_scale',
                        'min_color': '#F8696B',
                        'mid_color': '#FFEB84',
                        'max_color': '#63BE7B'
                    })
            
            # If all data rows are contiguous, you can do:
            # Only data rows for banding
            data_rows = list(df_to_excel_row.values())
            for row in data_rows:
                worksheet.conditional_format(row, 0, row, len(df.columns)-1, 
                                            {'type': 'formula', 'criteria': 'MOD(ROW(),2)=0', 'format': row_band_format})


            # STEP 3 — GRAND TOTAL (after all subtotals)
            grand_total_excel_row = excel_row

            worksheet.merge_range(
                grand_total_excel_row, merge_start,
                grand_total_excel_row, merge_end,
                "GRAND TOTAL",
                grand_total_format
            )

            # Numeric GRAND TOTAL: sum all subtotal rows collected
            for col in numeric_cols:
                col_letter = col_idx_to_excel(col)
                if subtotal_rows:
                    cells = ",".join([f"{col_letter}{r}" for r in subtotal_rows])
                    worksheet.write_formula(
                        grand_total_excel_row, col,
                        f"=SUM({cells})",
                        grand_total_format
                    )
                else:
                    # no subtotal rows (edge case) -> sum entire data block
                    excel_start = start_row
                    excel_end = excel_row - 1
                    formula = f"=SUM({col_letter}{excel_start+1}:{col_letter}{excel_end+1})"
                    worksheet.write_formula(grand_total_excel_row, col, formula, grand_total_format)

            # Percentage GRAND TOTAL
            for col_name, formula in percent_formulas.items():
                if col_name in df.columns:
                    col_idx = df.columns.get_loc(col_name)
                    applied = formula.replace("{subtotal_row}", str(grand_total_excel_row + 1))
                    worksheet.write_formula(
                        grand_total_excel_row, col_idx,
                        applied,
                        grand_total_percentage_format
                    )

        # ----------------------------
        # Non-summary Sheets
        # ----------------------------
        else:
            first_col = 0
            last_col = len(df.columns) - 1

            notes_col_name = "PatientHospitalNo"
            comments_col_name = "Required Services"            

            # Ensure the Comments column exists
            if comments_col_name not in df.columns:
                df[comments_col_name] = ""

            if notes_col_name in df.columns:
                notes_idx = df.columns.get_loc(notes_col_name)
                comments_idx = len(df.columns) - 1  # place Comments at the end

                # Write the Comments column header
                worksheet.write(0, comments_idx, comments_col_name)
                
                highlight_columns = {
                    "biometrics": ["PBS_Capture_Date", "PBS_Capturee"],
                    "VL SC": ["LastDateOfSampleCollection"],
                    "Initiate TPT": ["First_TPT_Pickupdate", "Current_TPT_Received"],
                }
                
                # Loop through each row once
                for row_idx in range(len(df)):
                    alerts = set()  # collect unique alerts

                    # Biometrics alert
                    if "PBS_Capture_Date" in df.columns:
                        val = df.at[row_idx, "PBS_Capture_Date"]
                        if pd.isna(val) or val == "":
                            alerts.add("biometrics")

                    # Sample collection alert
                    # Row masks (VL SC, TPT, etc.)
                    if sheet_name in row_masks:
                        for alert_text, mask in row_masks[sheet_name].items():
                            if row_idx < len(mask) and mask.iloc[row_idx]:
                                alerts.add(alert_text)

                    # Default comment if no alerts
                    if not alerts:
                        alerts.add("OK")

                    # Combine alerts into a short string
                    comment_text = " | ".join(sorted(alerts))
                    
                    for alert in alerts:
                        if alert == "OK":
                            continue

                        for col_name in highlight_columns.get(alert, []):
                            if col_name in df.columns:
                                col_idx = df.columns.get_loc(col_name)

                                worksheet.conditional_format(
                                    row_idx + 1,
                                    col_idx,
                                    row_idx + 1,
                                    col_idx,
                                    {
                                        'type': 'no_errors',
                                        'format': alert_format
                                    }
                                )

                                worksheet.write_comment(
                                    row_idx + 1,
                                    col_idx,
                                    alert,
                                    {
                                        'visible': False,
                                        'x_scale': 1.5,
                                        'y_scale': 1.5
                                    }
                                )

                    # Optional Excel comment for Notes column (only if not OK)
                    if "OK" not in alerts and notes_idx is not None:
                        worksheet.write_comment(row_idx + 1, notes_idx, comment_text,
                                                {'visible': False, 'x_scale': 1.5, 'y_scale': 1.5})
                        # Highlight Notes column
                        worksheet.conditional_format(row_idx + 1, notes_idx, row_idx + 1, notes_idx,
                                                    {'type': 'no_errors', 'format': alert_format})

                    # Write the comment text without format
                    worksheet.write(row_idx + 1, comments_idx, comment_text)
                    df.at[row_idx, comments_col_name] = comment_text

                    # Apply conditional formatting based on cell value
                    worksheet.conditional_format(row_idx + 1, comments_idx, row_idx + 1, comments_idx, {
                        'type': 'formula',
                        'criteria': f'={col_idx_to_excel(comments_idx)}{row_idx + 2}="OK"',
                        'format': ok_format
                    })
                    worksheet.conditional_format(row_idx + 1, comments_idx, row_idx + 1, comments_idx, {
                        'type': 'formula',
                        'criteria': f'={col_idx_to_excel(comments_idx)}{row_idx + 2}<>"OK"',
                        'format': alert_format
                    })
                    

                # ===== AUTOFIT Required Services column =====
                max_length = max(
                    #df[comments_col_name].astype(str).map(len).max(),
                    df[comments_col_name].fillna("").astype(str).map(len).max(),
                    len(comments_col_name)
                )
                worksheet.set_column(comments_idx, comments_idx, max_length + 3)


            # Row banding
            worksheet.conditional_format(1, 0, len(df), len(df.columns)-1,
                                         {'type': 'formula', 'criteria': 'MOD(ROW(),2)=0', 'format': row_band_format})

            # fixed Column widths
            fixed_col_ranges = {'O:AF':10}
            for col_range, width in fixed_col_ranges.items():
                worksheet.set_column(col_range, width)

            # Helper: Convert Excel column letter to index (A→0, B→1, AA→26)
            def col_letter_to_index(col_letter):
                col_letter = col_letter.upper()
                result = 0
                for char in col_letter:
                    result = result * 26 + (ord(char) - ord('A') + 1)
                return result - 1

            # === AUTOFIT SPECIFIC COLUMN RANGES ===
            col_ranges = ['D:F','J:N', 'AL:AM']

            for col_range in col_ranges:
                start_col, end_col = col_range.split(":")
                start_idx = col_letter_to_index(start_col)
                end_idx = col_letter_to_index(end_col)

                for col_idx in range(start_idx, end_idx + 1):
                    if col_idx >= len(df.columns):
                        continue  # skip non-existing columns

                    col_name = df.columns[col_idx]
                    max_length = max(
                        #df[col_name].astype(str).map(len).max(),
                        df[col_name].fillna("").astype(str).map(len).max(),
                        len(col_name)
                    )
                    worksheet.set_column(col_idx, col_idx, max_length + 3)

            worksheet.set_column('G:G', None, None, {'hidden': True})

    # ----------------------------
    # Save workbook
    # ----------------------------
    writer.close()
    output.seek(0)

    #output_dir = os.path.join(os.path.dirname(__file__), "..", "outputs")
    #os.makedirs(output_dir, exist_ok=True)
    #timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    #filename = f"{summaryName}_{timestamp}.xlsx"
    #output_path = os.path.join(output_dir, filename)
    #with open(output_path, "wb") as f:
    #    f.write(output.getbuffer())

    #return filename

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{summaryName}_{timestamp}.xlsx"

    output_path = OUTPUTS / filename

    with open(output_path, "wb") as f:
        f.write(output.getbuffer())

    return filename

def parse_any_date(series):
    """
    Fully vectorized date parser.
    - Handles mixed date formats
    - Fixes 2-digit years (interpreted in past century if > current year)
    - Cleans junk characters
    """
    s = (
        series.astype(str)
        .str.strip()
        .str.replace(r'[^A-Za-z0-9:/\.\- ]', '', regex=True)   # remove junk
        .str.replace(r'\s+', ' ', regex=True)                  # normalize spaces
        .replace(['', 'nan', 'NaN', None], pd.NA)
    )

    # 1) Pandas auto-parse (fast, covers most formats)
    parsed = pd.to_datetime(
        s,
        errors="coerce",
        dayfirst=True,
        infer_datetime_format=True
    )

    # 2) 8-digit numeric formats (YYYYMMDD)
    mask = parsed.isna() & s.str.fullmatch(r'\d{8}', na=False)
    parsed[mask] = pd.to_datetime(
        s[mask].str.replace(r'(\d{4})(\d{2})(\d{2})', r'\1-\2-\3', regex=True),
        errors='coerce'
    )

    # 3) 6-digit numeric formats (DDMMYY)
    mask = parsed.isna() & s.str.fullmatch(r'\d{6}', na=False)
    tmp = pd.to_datetime(
        s[mask].str.replace(r'(\d{2})(\d{2})(\d{2})', r'\1-\2-\3', regex=True),
        format="%d-%m-%y",
        errors='coerce',
        dayfirst=True
    )
    parsed[mask] = tmp

    # 4) Fix 2-digit years that are in the future
    current_year = datetime.now().year
    mask = parsed.dt.year > current_year
    parsed.loc[mask] = parsed.loc[mask] - pd.DateOffset(years=100)

    return parsed
