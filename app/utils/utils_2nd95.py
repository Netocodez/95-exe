import pandas as pd
import numpy as np

def compute_appointment_and_iit_dates(df):
    df['Pharmacy_LastPickupdate2'] = pd.to_datetime(df['Pharmacy_LastPickupdate'], errors='coerce')
    df['Duration'] = pd.to_numeric(df['DaysOfARVRefill'], errors='coerce')
    df['NextAppt'] = df['Pharmacy_LastPickupdate2'] + pd.to_timedelta(df['Duration'], unit='D')
    df['IITDate2'] = df['NextAppt'] + pd.Timedelta(days=29)
    return df

def classify_iit_Appt_status(df, endDate):
    today = pd.to_datetime(endDate)
    currentyear = today.year
    previousyear = today.year - 1
    sevenDaysIIT = today + pd.Timedelta(days=7)
    currentWeekYear = f"{today.isocalendar().week}_{today.year}"
    currentWeek = today.isocalendar().week

    # Ensure datetime formats
    df['IITDate2'] = pd.to_datetime(df['IITDate2'], errors='coerce')
    df['NextAppt'] = pd.to_datetime(df['NextAppt'], errors='coerce')
    df['Outcomes_Date'] = pd.to_datetime(df['Outcomes_Date'], errors='coerce')
    
    # === Current Year Definite Losses ===
    mask = (
        df['Outcomes_Date'].notna() &
        (df['Outcomes_Date'].dt.year == currentyear) &
        (df['Outcomes_Date'] <= today) &
        df['CurrentARTStatus'].isin(["Death", "Transferred out", "Discontinued Care"])
    )
    df['CurrentYearLosses'] = np.where(mask, 'CurrentYearLosses', 'notCurrentYearLosses')

    # === Current Week Definite Losses === (calendar year aligned)
    mask = (
        df['Outcomes_Date'].notna() &
        (df['Outcomes_Date'].dt.year == currentyear) &
        (df['Outcomes_Date'].dt.isocalendar().week == currentWeek) &
        (df['Outcomes_Date'] <= today) &
        df['CurrentARTStatus'].isin(["Death", "Transferred out", "Discontinued Care"])
    )
    df['CurrentWeekLosses'] = np.where(mask, 'CurrentWeekLosses', 'notCurrentWeekLosses')

    # === Current Year IIT ===
    mask = (
        df['IITDate2'].notna() &
        (df['IITDate2'].dt.year == currentyear) &
        (df['IITDate2'] <= today) &
        df['CurrentARTStatus'].isin(['LTFU', 'Lost to followup'])
    )
    df['CurrentYearIIT'] = np.where(mask, 'CurrentYearIIT', 'notCurrentYearIIT')

    # === Current Week IIT === (calendar year aligned)
    mask = (
        df['IITDate2'].notna() &
        (df['IITDate2'].dt.year == currentyear) &
        (df['IITDate2'].dt.isocalendar().week == currentWeek) &
        (df['IITDate2'] <= today) &
        df['CurrentARTStatus'].isin(['LTFU', 'Lost to followup'])
    )
    df['CurrentWeekIIT'] = np.where(mask, 'CurrentWeekIIT', 'notCurrentWeekIIT')

    # === Previous Year IIT ===
    mask = (
        df['IITDate2'].notna() &
        (df['IITDate2'].dt.year == previousyear) &
        (df['IITDate2'] <= today) &
        df['CurrentARTStatus'].isin(['LTFU', 'Lost to followup'])
    )
    df['previousyearIIT'] = np.where(mask, 'previousyearIIT', 'notpreviousyearIIT')

    # === Imminent IIT ===
    mask = (
        df['NextAppt'].notna() &
        (df['NextAppt'] <= today) &
        (df['CurrentARTStatus'] == 'Active')
    )
    df['ImminentIIT'] = np.where(mask, 'ImminentIIT', 'notImminentIIT')

    # === Seven Days IIT ===
    mask = (
        df['IITDate2'].notna() &
        (df['IITDate2'] <= sevenDaysIIT) &
        (df['CurrentARTStatus'] == 'Active')
    )
    df['sevendaysIIT'] = np.where(mask, 'sevendaysIIT', 'notsevenDaysIIT')

    # === Current Month Expected === (no helper column)
    mask = (
        df['NextAppt'].notna() &
        (df['NextAppt'].dt.month == today.month) &
        (df['NextAppt'].dt.year == today.year) &
        (df['CurrentARTStatus'] == 'Active')
    )
    df['currentmonthexpected'] = np.where(mask, 'currentmonthexpected', 'notcurrentmonthexpected')

    # === Baseline-related checks ===
    baseline_columns = {
        'BaselineNextAppt_week_year',
        'BaselineCurrentARTStatus',
        'BaselinePharmacy_LastPickupdate',
        'BaselineNextAppt',
    }
    if baseline_columns.issubset(df.columns):
        df['BaselineNextAppt'] = pd.to_datetime(df['BaselineNextAppt'], errors='coerce').fillna(pd.to_datetime('1900'))

        mask = (
            (df['BaselineNextAppt_week_year'] == currentWeekYear) &
            (df['CurrentARTStatus'] == 'Active') &
            (df['BaselineCurrentARTStatus'] == 'Active')
        )
        df['currentweekexpected'] = np.where(mask, 'currentweekexpected', 'notcurrentweekexpected')

        mask = (
            (df['currentweekexpected'] == 'currentweekexpected') &
            (df['Pharmacy_LastPickupdate2'] > df['BaselinePharmacy_LastPickupdate']) &
            (df['NextAppt'] > df['BaselineNextAppt'])
        )
        df['weeklyexpectedrefilled'] = np.where(mask, 'weeklyexpectedrefilled', 'notweeklyexpectedrefilled')

        mask = (
            (df['BaselineNextAppt_week_year'] == currentWeekYear) &
            (df['CurrentARTStatus'] == 'Active') &
            (df['BaselineCurrentARTStatus'] == 'Active') &
            (df['weeklyexpectedrefilled'] == 'notweeklyexpectedrefilled')
        )
        df['pendingweeklyrefill'] = np.where(mask, 'pendingweeklyrefill', 'notpendingweeklyrefill')

    return df


def trackBiometrics(df, endDate):
    # Convert endDate to datetime
    today = pd.to_datetime(endDate)
    current_year = today.year
    current_week = today.isocalendar().week

    # Ensure datetime formats for relevant columns
    df['NextAppt'] = pd.to_datetime(df['NextAppt'], errors='coerce')
    #df['Pharmacy_LastPickupdate2'] = pd.to_datetime(df['Pharmacy_LastPickupdate'], errors='coerce', dayfirst=True)
    df['LastDateOfSampleCollection2'] = pd.to_datetime(df['LastDateOfSampleCollection'], errors='coerce', dayfirst=True).fillna('1900-01-01')


    # === Captured Biometrics ===
    mask_captured = (df['PBS_Capturee'] == "Yes") & (df['CurrentARTStatus'] == 'Active')
    df['CapturedBiometrics'] = np.where(mask_captured, 'CapturedBiometrics', 'notCapturedBiometrics')

    # === Biometrics gap ===
    mask_gap = (df['PBS_Capturee'] == "No") & (df['CurrentARTStatus'] == 'Active')
    df['BiometricsGap'] = np.where(mask_gap, 'BiometricsGap', 'notBiometricsGap')

    # === Weekly Missed Biometrics ===
    mask_weekly = (
        (df['PBS_Capturee'] == "No") &
        (df['CurrentARTStatus'] == 'Active') &
        (
            # Either pharmacy refill OR sample collection happened in current week/year
            ((df['Pharmacy_LastPickupdate2'].notna()) &
            (df['Pharmacy_LastPickupdate2'].dt.isocalendar().week == current_week) &
            (df['Pharmacy_LastPickupdate2'].dt.year == current_year)) |
            ((df['LastDateOfSampleCollection2'].notna()) &
            (df['LastDateOfSampleCollection2'].dt.isocalendar().week == current_week) &
            (df['LastDateOfSampleCollection2'].dt.year == current_year))
        )
    )

    df['WKMissedBiometrics'] = np.where(mask_weekly, 'WKMissedBiometrics', 'notWKMissedBiometrics')


    return df 


def trackTPT(df, endDate):
    # Convert endDate to datetime
    today = pd.to_datetime(endDate)
    current_year = today.year
    current_week = today.isocalendar().week

    # Ensure datetime formats
    df['NextAppt'] = pd.to_datetime(df['NextAppt'], errors='coerce')
    df['Pharmacy_LastPickupdate2'] = pd.to_datetime(
        df['Pharmacy_LastPickupdate'], errors='coerce', dayfirst=True
    )
    df['LastDateOfSampleCollection2'] = pd.to_datetime(
        df['LastDateOfSampleCollection'], errors='coerce', dayfirst=True
    )
    
    df['PBS_Capture_Date2'] = pd.to_datetime(
        df['PBS_Capture_Date'], errors='coerce', dayfirst=True
    )

    # === Eligible for TPT ===
    mask_TPTEligible = (
        (df['Current_TB_Status'] == "No signs or symptoms of disease") &
        (df['CurrentARTStatus'] == 'Active')
    )
    df['TPTEligible'] = np.where(mask_TPTEligible, 'TPTEligible', 'notTPTEligible')

    # === On TPT ===
    mask_OnTPT = (
        mask_TPTEligible &
        (
            df['First_TPT_Pickupdate'].notna() |
            df['Current_TPT_Received'].notna()
        )
    )
    df['OnTPT'] = np.where(mask_OnTPT, 'OnTPT', 'notOnTPT')

    # === TPT Gap ===
    mask_TPTGap = (
        mask_TPTEligible &
        df['First_TPT_Pickupdate'].isna() &
        df['Current_TPT_Received'].isna()
    )
    df['TPTGap'] = np.where(mask_TPTGap, 'TPTGap', 'notTPTGap')

    # === Weekly Missed TPT ===
    mask_weekly_Missed_TPT = (
        mask_TPTEligible &
        # No TPT dispensed
        df['First_TPT_Pickupdate'].isna() &
        df['Current_TPT_Received'].isna() &
        (
            # Pharmacy refill this week
            (
                df['Pharmacy_LastPickupdate2'].notna() &
                (df['Pharmacy_LastPickupdate2'].dt.isocalendar().week == current_week) &
                (df['Pharmacy_LastPickupdate2'].dt.year == current_year)
            )
            |
            # Biometrics captured this week
            (
                df['PBS_Capture_Date2'].notna() &
                (df['PBS_Capture_Date2'].dt.isocalendar().week == current_week) &
                (df['PBS_Capture_Date2'].dt.year == current_year)
            )
            |
            # VL sample collected this week
            (
                df['LastDateOfSampleCollection2'].notna() &
                (df['LastDateOfSampleCollection2'].dt.isocalendar().week == current_week) &
                (df['LastDateOfSampleCollection2'].dt.year == current_year)
            )
        )
    )

    df['WKMissedTPT'] = np.where(
        mask_weekly_Missed_TPT,
        'WKMissedTPT',
        'notWKMissedTPT'
    )

    return df


def integrate_baseline_data(df, dfbaseline):
    
    #Bring in Values from baseline ART line list
    df['BaselineCurrentARTStatus']=df['uuid'].map(dfbaseline.set_index('uuid')['CurrentARTStatus'])
    df['BaselinePharmacy_LastPickupdate']=df['uuid'].map(dfbaseline.set_index('uuid')['Pharmacy_LastPickupdate'])
    df['BaselineDaysOfARVRefill']=df['uuid'].map(dfbaseline.set_index('uuid')['DaysOfARVRefill'])
    
    #Calculate Next Appointment for Added baseline columns
    df['BaselinePharmacy_LastPickupdate'] = pd.to_datetime(df['BaselinePharmacy_LastPickupdate'], errors='coerce', dayfirst=True).fillna(pd.to_datetime('1900'))
    df['BaselineDaysOfARVRefill'] = pd.to_numeric(df['BaselineDaysOfARVRefill'], errors='coerce')
    df['BaselineDaysOfARVRefill'] = df['BaselineDaysOfARVRefill'].apply(lambda x: 0 if pd.notnull(x) and x > 180 else x)
    df['BaselineNextAppt'] = df['BaselinePharmacy_LastPickupdate'] + pd.to_timedelta(df['BaselineDaysOfARVRefill'], unit='D') 
    
    #Create week year columns for baseline last pickup date and baseline next appointment
    df['BaselinePharmacy_LastPickupdate_week_year'] = df['BaselinePharmacy_LastPickupdate'].dt.isocalendar().week.astype(str) + '_' + df['BaselinePharmacy_LastPickupdate'].dt.year.astype(str)
    #df['BaselineNextAppt_week_year'] = df['BaselineNextAppt'].dt.isocalendar().week.astype(str) + '_' + df['BaselineNextAppt'].dt.year.astype(int).astype(str)
    df['BaselineNextAppt_week_year'] = df['BaselineNextAppt'].apply(
            lambda x: f"{x.isocalendar().week}_{x.year}" if pd.notna(x) else ""
        )
        
    return df


