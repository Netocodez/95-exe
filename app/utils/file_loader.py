import os
import pandas as pd

ALLOWED_EXTENSIONS = {'.xlsx', '.xls', '.csv'}

DATE_COLUMNS = ['ARTStartDate', 'Pharmacy_LastPickupdate', 'DateResultReceivedFacility', 'LastDateOfSampleCollection',
                'Date_Transfered_In', 'Outcomes_Date', 'DateofCurrent_TBStatus', 'First_TPT_Pickupdate', 'DateConfirmedHIV+', 'IIT_Date', 'PBS_Capture_Date']
NUMERIC_COLUMNS = ['DaysOfARVRefill', 'CurrentViralLoad']

#columns to process
columns_to_read = [
    'State', 'LGA', 'FacilityName', 'PatientHospitalNo', 'PEPID', 'uuid', 'ARTStatus_PreviousQuarter','CurrentARTStatus', 'DOB', 'ARTStartDate', 'Pharmacy_LastPickupdate',
    'DateResultReceivedFacility', 'LastDateOfSampleCollection', 'Date_Transfered_In',
    'CurrentPregnancyStatus', 'First_TPT_Pickupdate', 'Current_TPT_Received', 'Current_TB_Status', 'CurrentRegimenLine',
    'DaysOfARVRefill', 'DSD_Model', 'Sex', 'Outcomes_Date', 'CurrentViralLoad', 'ViralLoadIndication', 'DateofCurrent_TBStatus'
]

b_columns_to_read = [
    'uuid', 'CurrentARTStatus'
]

r_columns_to_read = [
    'State', 'LGA', 'Facility', 'Hospital Number', 'Unique ID', 'Patient ID', 'Date of TPT Start (yyyy-mm-dd)', 'TPT Type', 'TPT Completion date (yyyy-mm-dd)'
]

def is_allowed_file(filename):
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

def load_file(file, columns_to_read=None):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext == '.csv':
        return pd.read_csv(file, dtype=str, encoding='utf-8', usecols=columns_to_read)
    elif ext in ['.xls', '.xlsx']:
        return pd.read_excel(file, dtype=object, usecols=columns_to_read, engine='openpyxl')
    raise ValueError("Unsupported file type")
