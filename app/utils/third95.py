# app.py
from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import os
import logging
import traceback
from io import BytesIO
from datetime import datetime
from .emr_processor import process_Linelist, columns_to_select, columns_to_select2, export_to_excel_with_formatting, sc_gap_mask, tpt_gap_mask, calculate_age_vectorized, calculate_age_vectorized2
from .utils_3rd95 import export_3rd95_analysis

def third95(df, end_date):
    
    # All processing and Excel writing logic goes here.    
    endDate = pd.to_datetime(end_date)
    formatted_period = endDate.strftime('%d %B %Y')  # ✅ use the datetime object

    # --- The rest of the logic goes here ---
    
    # Ensure the 'Pharmacy_LastPickupdate' column is in datetime format and fill NaNs with a specific date
    df['Pharmacy_LastPickupdate2'] = pd.to_datetime(df['Pharmacy_LastPickupdate'], errors='coerce', dayfirst=True).fillna(pd.to_datetime('1900'))

    #Fill zero if the column contains number greater than 180
    df['DaysOfARVRefill2'] = df['DaysOfARVRefill'].apply(lambda x: 0 if x > 180 else x)

    # Calculate the 'NextAppt' column by adding the 'DaysOfARVRefill2' to 'Pharmacy_LastPickupdate2'
    df['NextAppt'] = df['Pharmacy_LastPickupdate2'] + pd.to_timedelta(df['DaysOfARVRefill2'], unit='D') 

    df.insert(0, 'S/N.', df.index + 1)
        
    #extract actives in both current and previous quarter
    df = df[(df['CurrentARTStatus'] == 'Active') & (df['ARTStatus_PreviousQuarter'] =='Active')]

    today = pd.to_datetime(endDate)
    endOfThisQuarter = pd.to_datetime(today) + pd.tseries.offsets.QuarterEnd(0)
    logging.info(f"End of Current Quarter: {endOfThisQuarter}")  
    # End of the previous quarter
    prev_q_end = (today - pd.offsets.QuarterEnd(1)).normalize()  
    
    df['end_date2'] = endOfThisQuarter
    df['end_date'] = prev_q_end
    df['ARTStartDate2'] = pd.to_datetime(df['ARTStartDate'].fillna('1900'))
    df['LastDateOfSampleCollection2'] = pd.to_datetime(df['LastDateOfSampleCollection'].fillna('1900'))
    df['DateResultReceivedFacility2'] = pd.to_datetime(df['DateResultReceivedFacility'].fillna('1900'))
    #df['Pharmacy_LastPickupdate2'] = pd.to_datetime(df['Pharmacy_LastPickupdate'], errors='coerce')

    # Function to calculate difference in months
    def date_diff_in_months2(date1, date2):
        return (date2.year - date1.year) * 12 + date2.month - date1.month - (1 if date2.day < date1.day else 0)
    
    #function to calculate current age and mirror excel datedif function
    #function to calculate current age and mirror excel datedif function
    def calculate_age_vectorized(dob_series, ref_date=None):
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
    
    #print(repr(df.loc[df['DOB'].str.contains('1976')]['DOB'].iloc[0]))
    # Clean DOB once
    #df['DOB'] = pd.to_datetime(df['DOB'].astype(str).str.strip(), errors='coerce')

    #df['Age'] = calculate_age_vectorized(df['DOB'], ref_date=end_date)
    #df['Current_Age'] = calculate_age_vectorized(df['DOB'], ref_date=end_date)
    
    df['DOB'] = pd.to_datetime(df['DOB'].astype(str).str.strip(), errors='coerce')
    df['Current_Age'] = calculate_age_vectorized2(df['DOB'], ref_date=endDate)
    df['Age'] = calculate_age_vectorized2(df['DOB'], ref_date=endDate)

    # Apply the function to the DataFrame
    df['durationOnART'] = df.apply(lambda row: date_diff_in_months2(row['ARTStartDate2'], row['end_date']), axis=1)
    df['durationOfSC'] = df.apply(lambda row: date_diff_in_months2(row['LastDateOfSampleCollection2'], row['end_date2']), axis=1)
    df['durationOfVlResult'] = df.apply(lambda row: date_diff_in_months2(row['DateResultReceivedFacility2'], row['end_date2']), axis=1)
    
    # Flag those who are already ≥ 6 months as at today
    df['eligible_today'] = df['ARTStartDate2'].apply(lambda d: date_diff_in_months2(d, today) >= 6)
             
    #drop irrelevant columns and extract actual VL eligible from dataframe
    df = df.drop(['end_date','ARTStartDate2'], axis=1)
    df = df[df['durationOnART'] >= 6]

    # Get the current date
    #today = pd.Timestamp('today')
    today = pd.to_datetime(endDate)
    currentWeek = today.isocalendar().week
    last_30_days = today - pd.Timedelta(days=29)
    next_30_days = today + pd.Timedelta(days=29)

    # Get the last day of the first quarter in the last one year
    last_year = today - pd.DateOffset(years=1)
    first_quarter_last_year = pd.to_datetime(last_year) + pd.tseries.offsets.QuarterEnd(0)
    
    # End of the quarter in the last 6 months
    six_months_ago = today - pd.DateOffset(months=6)
    end_of_quarter_last_6_months = pd.to_datetime(six_months_ago) + pd.tseries.offsets.QuarterEnd(0)

    logging.info(f"First quarter end from last year: {first_quarter_last_year}")
    
    #convert NextAppt to datetime
    df['NextAppt'] = pd.to_datetime(df['NextAppt'])

    #3rd 95 columns integration
    #df['validVlResult'] = df.apply(lambda row: 'Valid Result' if (row['DateResultReceivedFacility'] > first_quarter_last_year and row['LastDateOfSampleCollection'] > first_quarter_last_year) else 'Invalid Result', axis=1)
    df['validVlResult'] = df.apply(lambda row: 'Valid Result' if (((row['Age'] >= 15 and row['DateResultReceivedFacility'] > first_quarter_last_year) or (row['Age'] < 15 and row['durationOfVlResult'] <= 6)) and ((row['Age'] >= 15 and row['LastDateOfSampleCollection'] > first_quarter_last_year) or (row['Age'] < 15 and row['durationOfSC'] <= 6))) else 'Invalid Result', axis=1)
    #df['validVlSampleCollection'] = df.apply(lambda row: 'Valid SC' if row['LastDateOfSampleCollection'] > first_quarter_last_year else 'Invalid SC', axis=1)
    df['validVlSampleCollection'] = df.apply(lambda row: 'Valid SC' if ((row['Age'] >= 15 and row['LastDateOfSampleCollection'] > first_quarter_last_year) or (row['Age'] < 15 and row['durationOfSC'] <= 6)) else 'Invalid SC', axis=1)
    df['vlSCGap'] = df.apply(lambda row: 'SC Gap' if row['validVlSampleCollection'] == 'Invalid SC' else 'Not SC Gap', axis=1)
    df['vlWKMissedSC'] = df.apply(lambda row: 'vlWKMissedSC' if ((row['vlSCGap'] == 'SC Gap') and (row['Pharmacy_LastPickupdate2'].isocalendar().week == currentWeek) and row['eligible_today']) else 'NotvlWKMissedSC', axis=1)
    df['PendingResult'] = df.apply(lambda row: 'Pending' if ((row['validVlSampleCollection'] == 'Valid SC') & (row['validVlResult'] == 'Invalid Result')) else 'Not pending', axis=1)  
    df['last30daysmissedSC'] = df.apply(lambda row: 'Missed SC' if ((row['vlSCGap'] == 'SC Gap') & (row['Pharmacy_LastPickupdate'] >= last_30_days) & (row['Pharmacy_LastPickupdate'] < today)) else 'Not Missed SC', axis=1)  
    df['expNext30daysdueforSC'] = df.apply(lambda row: 'due for SC' if ((row['vlSCGap'] == 'SC Gap') & (row['NextAppt'] >= today) & (row['NextAppt'] < next_30_days)) else 'Not due for SC', axis=1)  
    df['Suppression'] = df.apply(lambda row: 'Suppressed' if ((row['validVlResult'] == 'Valid Result') & (row['CurrentViralLoad'] < 1000)) else ('Unsuppressed' if ((row['validVlResult'] == 'Valid Result') & (row['CurrentViralLoad'] > 1000)) else 'Invalid Result'), axis=1)
    
    #df.to_excel('3rd95.xlsx')           
    
    df_sc_Gap = process_Linelist(df, 'vlSCGap', 'SC Gap', columns_to_select2, sort_by=['LGA', 'FacilityName'])
    df_pending_results = process_Linelist(df, 'PendingResult', 'Pending', columns_to_select2, sort_by=['LGA', 'FacilityName'])
    df_last30daysmissedSC  = process_Linelist(df, 'last30daysmissedSC', 'Missed SC', columns_to_select2, sort_by=['LGA', 'FacilityName'])
    df_expNext30daysdueforSC = process_Linelist(df, 'expNext30daysdueforSC', 'due for SC', columns_to_select2, sort_by=['LGA', 'FacilityName'])
    df_Suppression = process_Linelist(df, 'Suppression', 'Unsuppressed', columns_to_select2, sort_by=['LGA', 'FacilityName'])       
    df_vlWKMissedSC = process_Linelist(df, 'vlWKMissedSC', 'vlWKMissedSC', columns_to_select2, sort_by=['LGA', 'FacilityName'])        
    
    df_active_Eligible = df[df['CurrentARTStatus']=="Active"]

    df_active_Eligible['vlEligible'] = df_active_Eligible['CurrentARTStatus'].apply(lambda x: 1 if x == "Active" else 0)
    df_active_Eligible['validVlResult_valid'] = df_active_Eligible['validVlResult'].apply(lambda x: 1 if x == "Valid Result" else 0)
    df_active_Eligible['validVlSampleCollection'] = df_active_Eligible['validVlSampleCollection'].apply(lambda x: 1 if x == "Valid SC" else 0)
    df_active_Eligible['vlSCGap'] = df_active_Eligible['vlSCGap'].apply(lambda x: 1 if x == "SC Gap" else 0)
    df_active_Eligible['PendingResult'] = df_active_Eligible['PendingResult'].apply(lambda x: 1 if x == "Pending" else 0)
    df_active_Eligible['last30daysmissedSC'] = df_active_Eligible['last30daysmissedSC'].apply(lambda x: 1 if x == "Missed SC" else 0)
    df_active_Eligible['expNext30daysdueforSC'] = df_active_Eligible['expNext30daysdueforSC'].apply(lambda x: 1 if x == "due for SC" else 0)
    df_active_Eligible['Suppressed'] = df_active_Eligible['Suppression'].apply(lambda x: 1 if x == "Suppressed" else 0)
    df_active_Eligible['vlWKMissedSC'] = df_active_Eligible['vlWKMissedSC'].apply(lambda x: 1 if x == "vlWKMissedSC" else 0)

    result = df_active_Eligible.groupby(['LGA','FacilityName'])[['vlEligible', 'validVlResult_valid', 'validVlSampleCollection','vlSCGap', 'PendingResult','last30daysmissedSC','expNext30daysdueforSC','Suppressed','vlWKMissedSC']].sum().reset_index()

    result['vl_result_rate'] = ((result['validVlResult_valid'] / result['vlEligible'])).round(4)
    result['sample_collection_rate'] = ((result['validVlSampleCollection'] / result['vlEligible'])).round(4)
    result['suppression_rate'] = ((result['Suppressed'] / result['validVlResult_valid'])).round(4)
    
    result = result[['LGA','FacilityName','vlEligible','validVlResult_valid','Suppressed','vl_result_rate','suppression_rate','validVlSampleCollection','sample_collection_rate','vlSCGap','PendingResult','last30daysmissedSC','expNext30daysdueforSC','vlWKMissedSC']]

    result = result.rename(columns={'validVlSampleCollection': 'Valid VL Samples',
                                    'validVlResult_valid': 'Valid VL Results',
                                    'vlEligible': 'Eligible for VL',
                                    'sample_collection_rate': '%VL Sample Collection Rate',
                                    'vl_result_rate': '%VL Coverage',
                                    'suppression_rate': '%VL Suppression Rate',
                                    'PendingResult': 'Pending VL Results',
                                    'vlSCGap': 'VL Sample Collection Gap',
                                    'last30daysmissedSC': 'Last 30 days Missed VL SC',
                                    'expNext30daysdueforSC': 'Expected Next 30 days due for VL SC',
                                    'vlWKMissedSC': 'Weekly VL SC Missed Oppurtunity',
                                    'Suppression': 'Suppressed',})

    #format and export
    sdate = endDate.strftime("%d-%m-%Y")
    
    # List of dataframes and their corresponding sheet names
    dataframes = {
        "SC GAP": df_sc_Gap,
        "PENDING RESULT": df_pending_results,
        "LAST 30 DAYS MISSED SC": df_last30daysmissedSC,
        "EXP NEXT 30 DAYS DUE FOR SC": df_expNext30daysdueforSC,
        "UNSUPPRESSED RESULTS": df_Suppression,
        "WK SC Missed Oppurtunity": df_vlWKMissedSC,
        "3RD 95 SUMMARY": result,
        #"Sheet3": df3,
        # Add more dataframes and sheet names as needed
    }
    
    # Build row_masks for all sheets except the summary
    row_masks_dict = {}

    for sheet_name, df in dataframes.items():
        if sheet_name != "3RD 95 SUMMARY":
            masks = {}

            masks["VL SC"] = sc_gap_mask(
                df,
                endDate,
                age_col="Current_Age"
            )

            masks["Initiate TPT"] = tpt_gap_mask(df)

            # Future additions
            # masks["Biometrics"] = biometrics_mask(df)
            # masks["EAC"] = eac_mask(df)

            row_masks_dict[sheet_name] = masks
    
    # Dynamic numeric and percentage column configuration
    column_config = {
        "3RD 95 SUMMARY": {
            "numeric_cols": [2,3,4,7,9,10,11,12,13],

            "percent_formulas": {
                "%VL Coverage": "=D{subtotal_row}/C{subtotal_row}",
                "%VL Suppression Rate": "=E{subtotal_row}/D{subtotal_row}",
                "%VL Sample Collection Rate": "=H{subtotal_row}/C{subtotal_row}"
            },

            # NEW (merge A:C)
            "merge_columns": (0, 1),

            # NEW title override
            "title": "3RD 95 PERFORMANCE REPORT – {period}"
        }
    }

    #filename = export_3rd95_analysis(dataframes, formatted_period=sdate, column_config=column_config)

    #return filename
            

    # Write each dataframe to a different sheet
    filename = export_to_excel_with_formatting(
        dataframes,
        sdate,
        summaryName="3RD 95 SUMMARY",
        column_widths={'A:A': 20, 'B:B': 35,},
        row_masks=row_masks_dict,  # << pass mask here
        column_config=column_config
    )
    return filename


def third95CMG(df, end_date):
        # All processing and Excel writing logic goes here.    
        endDate = pd.to_datetime(end_date)
        formatted_period = endDate.strftime('%d %B %Y')  # ✅ use the datetime object
        df['CaseManager'] = df['CaseManager'].fillna('UNASSIGNED')
              
        # Ensure the 'Pharmacy_LastPickupdate' column is in datetime format and fill NaNs with a specific date
        df['Pharmacy_LastPickupdate2'] = pd.to_datetime(df['Pharmacy_LastPickupdate'], errors='coerce', dayfirst=True).fillna(pd.to_datetime('1900'))

        #Fill zero if the column contains number greater than 180
        df['DaysOfARVRefill2'] = df['DaysOfARVRefill'].apply(lambda x: 0 if x > 180 else x)

        # Calculate the 'NextAppt' column by adding the 'DaysOfARVRefill2' to 'Pharmacy_LastPickupdate2'
        df['NextAppt'] = df['Pharmacy_LastPickupdate2'] + pd.to_timedelta(df['DaysOfARVRefill2'], unit='D')     
        
        df.insert(0, 'S/N.', df.index + 1)
            
        #extract actives in both current and previous quarter
        df = df[(df['CurrentARTStatus'] == 'Active') & (df['ARTStatus_PreviousQuarter'] =='Active')]

        today = pd.to_datetime(endDate)
        currentWeek = today.isocalendar().week
        
        endOfThisQuarter = pd.to_datetime(today) + pd.tseries.offsets.QuarterEnd(0)
        logging.info(f"End of Current Quarter: {endOfThisQuarter}")    
        # End of the previous quarter
        prev_q_end = (today - pd.offsets.QuarterEnd(1)).normalize()  
        print(f"previous quarter end: {prev_q_end}")
        logging.info(f"End of Previous Quarter: {prev_q_end}")
        
        df['end_date2'] = endOfThisQuarter
        df['end_date'] = prev_q_end
        df['ARTStartDate2'] = pd.to_datetime(df['ARTStartDate'].fillna('1900'))
        df['LastDateOfSampleCollection2'] = pd.to_datetime(df['LastDateOfSampleCollection'].fillna('1900'))
        df['DateResultReceivedFacility2'] = pd.to_datetime(df['DateResultReceivedFacility'].fillna('1900'))

        # Function to calculate difference in months
        def date_diff_in_months2(date1, date2):
            return (date2.year - date1.year) * 12 + date2.month - date1.month - (1 if date2.day < date1.day else 0)

        # Apply the function to the DataFrame
        df['durationOnART'] = df.apply(lambda row: date_diff_in_months2(row['ARTStartDate2'], row['end_date']), axis=1)
        df['durationOfSC'] = df.apply(lambda row: date_diff_in_months2(row['LastDateOfSampleCollection2'], row['end_date2']), axis=1)
        df['durationOfVlResult'] = df.apply(lambda row: date_diff_in_months2(row['DateResultReceivedFacility2'], row['end_date2']), axis=1)
        
        # Flag those who are already ≥ 6 months as at today
        df['eligible_today'] = df['ARTStartDate2'].apply(lambda d: date_diff_in_months2(d, today) >= 6)

        #drop irrelevant columns and extract actual VL eligible from dataframe
        df = df.drop(['end_date','ARTStartDate2'], axis=1)
        df = df[df['durationOnART'] >= 6]

        # Get the current date
        #today = pd.Timestamp('today')
        today = pd.to_datetime(endDate)
        last_30_days = today - pd.Timedelta(days=29)
        next_30_days = today + pd.Timedelta(days=29)
        
        #function to calculate current age and mirror excel datedif function
        def calculate_age_vectorized(dob_series, ref_date=None):
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
        
        #print(repr(df.loc[df['DOB'].str.contains('1976')]['DOB'].iloc[0]))
        # Clean DOB once
        #df['DOB'] = pd.to_datetime(df['DOB'].astype(str).str.strip(), errors='coerce')

        #df['Age'] = calculate_age_vectorized(df['DOB'], ref_date=end_date)
        #df['Current_Age'] = calculate_age_vectorized(df['DOB'], ref_date=end_date)
        df['DOB'] = pd.to_datetime(df['DOB'].astype(str).str.strip(), errors='coerce')
        df['Current_Age'] = calculate_age_vectorized2(df['DOB'], ref_date=endDate)
        df['Age'] = calculate_age_vectorized2(df['DOB'], ref_date=endDate)

        # Get the last day of the first quarter in the last one year
        last_year = today - pd.DateOffset(years=1)
        first_quarter_last_year = pd.to_datetime(last_year) + pd.tseries.offsets.QuarterEnd(0)
        
        six_months_ago = today - pd.DateOffset(months=6)
        end_of_quarter_last_6_months = pd.to_datetime(six_months_ago) + pd.tseries.offsets.QuarterEnd(0)

        print(first_quarter_last_year)     
        
        #convert VL dates to datetime
        df['DateResultReceivedFacility'] = pd.to_datetime(df['DateResultReceivedFacility'])
        df['LastDateOfSampleCollection'] = pd.to_datetime(df['LastDateOfSampleCollection'])
        df['Pharmacy_LastPickupdate'] = pd.to_datetime(df['Pharmacy_LastPickupdate'])
        df['NextAppt'] = pd.to_datetime(df['NextAppt'])

        #3rd 95 columns integration
        df['validVlResult'] = df.apply(lambda row: 'Valid Result' if (((row['Age'] >= 15 and row['DateResultReceivedFacility'] > first_quarter_last_year) or (row['Age'] < 15 and row['durationOfVlResult'] <= 6)) and ((row['Age'] >= 15 and row['LastDateOfSampleCollection'] > first_quarter_last_year) or (row['Age'] < 15 and row['durationOfSC'] <= 6))) else 'Invalid Result', axis=1)
        df['validVlSampleCollection'] = df.apply(lambda row: 'Valid SC' if ((row['Age'] >= 15 and row['LastDateOfSampleCollection'] > first_quarter_last_year) or (row['Age'] < 15 and row['durationOfSC'] <= 6)) else 'Invalid SC', axis=1)
        #df['validVlResult'] = df.apply(lambda row: 'Valid Result' if (row['DateResultReceivedFacility'] > first_quarter_last_year and row['LastDateOfSampleCollection'] > first_quarter_last_year) else 'Invalid Result', axis=1)
        #df['validVlSampleCollection'] = df.apply(lambda row: 'Valid SC' if row['LastDateOfSampleCollection'] > first_quarter_last_year else 'Invalid SC', axis=1)
        df['vlSCGap'] = df.apply(lambda row: 'SC Gap' if row['validVlSampleCollection'] == 'Invalid SC' else 'Not SC Gap', axis=1)
        df['vlWKMissedSC'] = df.apply(lambda row: 'vlWKMissedSC' if ((row['vlSCGap'] == 'SC Gap') and (row['Pharmacy_LastPickupdate2'].isocalendar().week == currentWeek) and row['eligible_today']) else 'NotvlWKMissedSC', axis=1)
        df['PendingResult'] = df.apply(lambda row: 'Pending' if ((row['validVlSampleCollection'] == 'Valid SC') & (row['validVlResult'] == 'Invalid Result')) else 'Not pending', axis=1)    
        df['last30daysmissedSC'] = df.apply(lambda row: 'Missed SC' if ((row['vlSCGap'] == 'SC Gap') & (row['Pharmacy_LastPickupdate'] >= last_30_days) & (row['Pharmacy_LastPickupdate'] < today)) else 'Not Missed SC', axis=1)  
        df['expNext30daysdueforSC'] = df.apply(lambda row: 'due for SC' if ((row['vlSCGap'] == 'SC Gap') & (row['NextAppt'] >= today) & (row['NextAppt'] < next_30_days)) else 'Not due for SC', axis=1)  
        #df['Suppression'] = df.apply(lambda row: 'Suppressed' if ((row['validVlResult'] == 'Valid Result') & (row['CurrentViralLoad2'] < 1000)) else 'Not Suppressed', axis=1)
        df['Suppression'] = df.apply(lambda row: 'Suppressed' if ((row['validVlResult'] == 'Valid Result') & (row['CurrentViralLoad'] < 1000)) else ('Unsuppressed' if ((row['validVlResult'] == 'Valid Result') & (row['CurrentViralLoad'] > 1000)) else 'Invalid Result'), axis=1)
        #df.to_excel("3rd95.xlsx")
        
        df_sc_Gap = process_Linelist(df, 'vlSCGap', 'SC Gap', columns_to_select, sort_by=['LGA', 'FacilityName', 'CaseManager'])
        df_pending_results = process_Linelist(df, 'PendingResult', 'Pending', columns_to_select, sort_by=['LGA', 'FacilityName', 'CaseManager'])
        df_last30daysmissedSC  = process_Linelist(df, 'last30daysmissedSC', 'Missed SC', columns_to_select, sort_by=['LGA', 'FacilityName', 'CaseManager'])
        df_expNext30daysdueforSC = process_Linelist(df, 'expNext30daysdueforSC', 'due for SC', columns_to_select, sort_by=['LGA', 'FacilityName', 'CaseManager'])
        df_Suppression = process_Linelist(df, 'Suppression', 'Unsuppressed', columns_to_select, sort_by=['LGA', 'FacilityName', 'CaseManager'])  
        df_vlWKMissedSC = process_Linelist(df, 'vlWKMissedSC', 'vlWKMissedSC', columns_to_select, sort_by=['LGA', 'FacilityName', 'CaseManager'])   
        
        df_active_Eligible = df[df['CurrentARTStatus']=="Active"]

        df_active_Eligible['vlEligible'] = df_active_Eligible['CurrentARTStatus'].apply(lambda x: 1 if x == "Active" else 0)
        df_active_Eligible['validVlResult_valid'] = df_active_Eligible['validVlResult'].apply(lambda x: 1 if x == "Valid Result" else 0)
        df_active_Eligible['validVlSampleCollection'] = df_active_Eligible['validVlSampleCollection'].apply(lambda x: 1 if x == "Valid SC" else 0)
        df_active_Eligible['vlSCGap'] = df_active_Eligible['vlSCGap'].apply(lambda x: 1 if x == "SC Gap" else 0)
        df_active_Eligible['PendingResult'] = df_active_Eligible['PendingResult'].apply(lambda x: 1 if x == "Pending" else 0)
        df_active_Eligible['last30daysmissedSC'] = df_active_Eligible['last30daysmissedSC'].apply(lambda x: 1 if x == "Missed SC" else 0)
        df_active_Eligible['expNext30daysdueforSC'] = df_active_Eligible['expNext30daysdueforSC'].apply(lambda x: 1 if x == "due for SC" else 0)
        df_active_Eligible['Suppressed'] = df_active_Eligible['Suppression'].apply(lambda x: 1 if x == "Suppressed" else 0)
        df_active_Eligible['vlWKMissedSC'] = df_active_Eligible['vlWKMissedSC'].apply(lambda x: 1 if x == "vlWKMissedSC" else 0)

        #result = df_active_Eligible.groupby(['LGA','FacilityName','CaseManager'])[['vlEligible', 'validVlResult_valid', 'validVlSampleCollection','vlSCGap', 'PendingResult']].sum().reset_index()
        result = df_active_Eligible.groupby(['LGA','FacilityName','CaseManager'])[['vlEligible', 'validVlResult_valid', 'validVlSampleCollection','vlSCGap', 'PendingResult','last30daysmissedSC','expNext30daysdueforSC','Suppressed','vlWKMissedSC']].sum().reset_index()

        result['vl_result_rate'] = ((result['validVlResult_valid'] / result['vlEligible'])).round(4)
        result['sample_collection_rate'] = ((result['validVlSampleCollection'] / result['vlEligible'])).round(4)
        result['suppression_rate'] = ((result['Suppressed'] / result['validVlResult_valid'])).round(4)
        
        result = result[['LGA','FacilityName','CaseManager','vlEligible','validVlResult_valid','Suppressed','vl_result_rate','suppression_rate','validVlSampleCollection','sample_collection_rate','vlSCGap','PendingResult','last30daysmissedSC','expNext30daysdueforSC','vlWKMissedSC']]

        result = result.rename(columns={'validVlSampleCollection': 'Valid VL Samples',
                                        'validVlResult_valid': 'Valid VL Results',
                                        'vlEligible': 'Eligible for VL',
                                        'sample_collection_rate': '%VL Sample Collection Rate',
                                        'vl_result_rate': '%VL Coverage',
                                        'suppression_rate': '%VL Suppression Rate',
                                        'PendingResult': 'Pending VL Results',
                                        'vlSCGap': 'VL Sample Collection Gap',
                                        'last30daysmissedSC': 'Last 30 days Missed VL SC',
                                        'expNext30daysdueforSC': 'Expected Next 30 days due for VL SC',
                                        'vlWKMissedSC': 'Weekly VL SC Missed Oppurtunity',
                                        'Suppression': 'Suppressed',})
        
        #format and export
        sdate = endDate.strftime("%d-%m-%Y")

        # List of dataframes and their corresponding sheet names
        dataframes = {
            "SC GAP": df_sc_Gap,
            "PENDING RESULT": df_pending_results,
            "LAST 30 DAYS MISSED SC": df_last30daysmissedSC,
            "EXP NEXT 30 DAYS DUE FOR SC": df_expNext30daysdueforSC,
            "UNSUPPRESSED RESULTS": df_Suppression,
            "WK SC Missed Oppurtunity": df_vlWKMissedSC,
            "3RD 95 SUMMARY": result,
            #"Sheet3": df3,
            # Add more dataframes and sheet names as needed
        }
        
        # Build row_masks for all sheets except the summary
        row_masks_dict = {}

        for sheet_name, df in dataframes.items():
            if sheet_name != "3RD 95 SUMMARY":
                masks = {}

                masks["VL SC"] = sc_gap_mask(
                    df,
                    endDate,
                    age_col="Current_Age"
                )

                masks["Initiate TPT"] = tpt_gap_mask(df)

                # Future additions
                # masks["Biometrics"] = biometrics_mask(df)
                # masks["EAC"] = eac_mask(df)

                row_masks_dict[sheet_name] = masks
        
        # Example DataFrames

        # Dynamic numeric and percentage column configuration
        column_config = {
            "3RD 95 SUMMARY": {
                "numeric_cols": [3,4,5,8,10,11,12,13,14],

                "percent_formulas": {
                    "%VL Coverage": "=E{subtotal_row}/D{subtotal_row}",
                    "%VL Suppression Rate": "=F{subtotal_row}/E{subtotal_row}",
                    "%VL Sample Collection Rate": "=I{subtotal_row}/D{subtotal_row}"
                },

                # NEW (merge A:C)
                "merge_columns": (0, 2),

                # NEW title override
                "title": "3RD 95 PERFORMANCE REPORT – {period}"
            }
        }

        #filename = export_3rd95_analysis(dataframes, formatted_period=sdate, column_config=column_config)

        #return filename
    
        # Write each dataframe to a different sheet
        filename = export_to_excel_with_formatting(
            dataframes,
            sdate,
            summaryName="3RD 95 SUMMARY",
            column_widths={'A:A': 20, 'B:B': 35, 'C:C': 35,},
            row_masks=row_masks_dict,  # << pass mask here
            column_config=column_config
        )
        return filename