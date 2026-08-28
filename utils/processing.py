import pandas as pd
import numpy as np
from dateutil import parser
from datetime import datetime
import os

def is_allowed_file(filename):
    ALLOWED_EXTENSIONS = {'.xlsx', '.xls', '.csv'}
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

def load_file(file, columns_to_read=None):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext == '.csv':
        return pd.read_csv(file, dtype=str, encoding='utf-8', usecols=columns_to_read)
    elif ext in ['.xls', '.xlsx']:
        return pd.read_excel(file, sheet_name=0, dtype=object, usecols=columns_to_read, engine='openpyxl')
    raise ValueError("Unsupported file type")

def parse_date(date):
    if pd.isna(date): return pd.NaT
    try:
        return parser.parse(str(date), fuzzy=True, ignoretz=True)
    except:
        return pd.NaT

def convert_dates(df, date_columns):
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
    return df

def compute_viral_load_flags(df, end_date):
    today = pd.to_datetime(end_date)
    last_30_days = today - pd.Timedelta(days=29)
    next_30_days = today + pd.Timedelta(days=29)
    last_year = today - pd.DateOffset(years=1)
    first_quarter_last_year = pd.to_datetime(last_year) + pd.tseries.offsets.QuarterEnd(0)

    df['validVlResult'] = df['DateResultReceivedFacility'].apply(lambda x: 'Valid Result' if pd.notnull(x) and x > first_quarter_last_year else 'Invalid Result')
    df['validVlSampleCollection'] = df['LastDateOfSampleCollection'].apply(lambda x: 'Valid SC' if pd.notnull(x) and x > first_quarter_last_year else 'Invalid SC')

    df['vlSCGap'] = df['validVlSampleCollection'].apply(lambda x: 'SC Gap' if x == 'Invalid SC' else 'Not SC Gap')

    df['PendingResult'] = df.apply(lambda row: 'Pending' if ((row['validVlSampleCollection'] == 'Valid SC') and (row['validVlResult'] == 'Invalid Result')) else 'Not pending', axis=1)
    df['last30daysmissedSC'] = df.apply(lambda row: 'Missed SC' if ((row['vlSCGap'] == 'SC Gap') and (row['Pharmacy_LastPickupdate'] >= last_30_days) and (row['Pharmacy_LastPickupdate'] < today)) else 'Not Missed SC', axis=1)
    df['expNext30daysdueforSC'] = df.apply(lambda row: 'due for SC' if ((row['vlSCGap'] == 'SC Gap') and (row['NextAppt'] >= today) and (row['NextAppt'] < next_30_days)) else 'Not due for SC', axis=1)

    df['Suppression'] = df.apply(lambda row: 'Suppressed' if ((row['validVlResult'] == 'Valid Result') and (row['CurrentViralLoad'] < 1000)) else ('Unsuppressed' if ((row['validVlResult'] == 'Valid Result') and (row['CurrentViralLoad'] > 1000)) else 'Invalid Result'), axis=1)
    return df

def generate_trimmed_dataframes(df):
    def extract_by_flag(flag_col, value='SC Gap'):
        df_flag = df[df[flag_col] == value].reset_index()
        df_flag.insert(0, 'S/N', df_flag.index + 1)
        return df_flag

    return {
        "SC GAP": extract_by_flag('vlSCGap', 'SC Gap'),
        "PENDING RESULT": extract_by_flag('PendingResult', 'Pending'),
        "LAST 30 DAYS MISSED SC": extract_by_flag('last30daysmissedSC', 'Missed SC'),
        "EXP NEXT 30 DAYS DUE FOR SC": extract_by_flag('expNext30daysdueforSC', 'due for SC'),
        "UNSUPPRESSED RESULTS": extract_by_flag('Suppression', 'Unsuppressed')
    }

def write_dataframes_to_excel(dataframes, summary_df):
    from io import BytesIO
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    workbook = writer.book

    for sheet_name, dataframe in dataframes.items():
        dataframe.to_excel(writer, sheet_name=sheet_name, startrow=1, header=False, index=False)
        worksheet = writer.sheets[sheet_name]

        header_format = workbook.add_format({"bold": True, "text_wrap": True, "valign": "bottom", "fg_color": "#D7E4BC", "border": 1})
        for col_num, value in enumerate(dataframe.columns.values):
            worksheet.write(0, col_num, value, header_format)

    # Write summary with formatting
    summary_df.to_excel(writer, sheet_name='3RD 95 SUMMARY', startrow=1, header=False, index=False)
    ws = writer.sheets['3RD 95 SUMMARY']
    title_format = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center'})
    ws.merge_range(0, 0, 0, len(summary_df.columns)-1, '3RD 95 SUMMARY', title_format)

    percent_format = workbook.add_format({'num_format': '0.00%'})
    ws.set_column('F:F', None, percent_format)
    ws.set_column('G:G', None, percent_format)
    ws.set_column('I:I', None, percent_format)

    row_band_format = workbook.add_format({'bg_color': '#F9F9F9'})
    ws.conditional_format(2, 0, len(summary_df)+1, len(summary_df.columns)-1, {'type': 'formula', 'criteria': 'MOD(ROW(),2)=0', 'format': row_band_format})

    writer.close()
    output.seek(0)
    return output

def process_emr_data(df, dfbaseline, emr_df):
    def clean_id(val):
        return str(val).strip().lower().replace(' ', '').lstrip('0') if pd.notna(val) else ''

    emr_df = emr_df[(emr_df != '').all(axis=1)]
    emr_subset = emr_df[['Name on NMRS', 'LGA', 'STATE', 'Name on Lamis']].drop_duplicates(subset='Name on NMRS')

    df = df.merge(emr_subset, how='left', left_on='FacilityName', right_on='Name on NMRS', suffixes=('', '_emr'))
    df['LGA'] = df['LGA'].fillna(df['LGA_emr'])
    df['State'] = df['State'].fillna(df['STATE'])
    df.loc[df['Name on Lamis'] != df['FacilityName'], 'FacilityName'] = df['Name on Lamis']
    df.drop(['Name on NMRS', 'LGA_emr', 'STATE', 'Name on Lamis'], axis=1, inplace=True)

    df['PatientHospitalNo1'] = df['PatientHospitalNo'].apply(clean_id)
    df['PatientUniqueID1'] = df['PEPID'].apply(clean_id)
    dfbaseline['Hospital Number1'] = dfbaseline['Hospital Number'].apply(clean_id)
    dfbaseline['Unique ID1'] = dfbaseline['Unique ID'].apply(clean_id)

    dfbaseline['unique identifiers'] = dfbaseline['LGA'].astype(str).str.lower().str.strip().str.replace(' ', '') + dfbaseline['Facility'].astype(str).str.lower().str.strip().str.replace(' ', '') + dfbaseline['Hospital Number1'] + dfbaseline['Unique ID1']
    df['unique identifiers'] = df['LGA'].astype(str).str.lower().str.strip().str.replace(' ', '') + df['FacilityName'].astype(str).str.lower().str.strip().str.replace(' ', '') + df['PatientHospitalNo1'] + df['PatientUniqueID1']

    dfbaseline = dfbaseline.drop_duplicates(subset=['unique identifiers'], keep=False)
    dup_mask = df.duplicated('unique identifiers', keep=False)
    df.loc[dup_mask, 'unique identifiers'] = df.loc[dup_mask].groupby('unique identifiers').cumcount().astype(str).radd(df.loc[dup_mask, 'unique identifiers'] + '_')

    df = df.merge(dfbaseline[['unique identifiers', 'Date of TPT Start (yyyy-mm-dd)', 'TPT Type']], on='unique identifiers', how='left', suffixes=('', '_baseline'))
    df['Date of TPT Start (yyyy-mm-dd)'] = pd.to_datetime(df['Date of TPT Start (yyyy-mm-dd)'], errors='coerce', dayfirst=True)
    df['First_TPT_Pickupdate'] = pd.to_datetime(df['First_TPT_Pickupdate'], errors='coerce', dayfirst=True)
    df['First_TPT_Pickupdate'] = df['First_TPT_Pickupdate'].fillna(df['Date of TPT Start (yyyy-mm-dd)'])
    df['Current_TPT_Received'] = df['Current_TPT_Received'].fillna(df['TPT Type'])
    return df