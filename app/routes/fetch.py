from flask import Blueprint, request, jsonify, send_file
import os
import traceback

from ..utils.file_loader import load_file, is_allowed_file, DATE_COLUMNS, NUMERIC_COLUMNS
from ..utils.emr_processor import appendLamisData, ensureLGAState, emr_df, parse_any_date
from ..utils.third95 import third95, third95CMG
from ..utils.second95 import second95, Second95R, Second95RCMG, second95CMG
from utils.paths import OUTPUTS

import pandas as pd

bp = Blueprint('fetch', __name__)

@bp.route('/fetch', methods=['POST'])
def fetch_data():
    try:
        file1 = request.files.get("file1")
        file2 = request.files.get("file2")
        file3 = request.files.get("file3")
        end_date = request.form.get("endDate")

        if not file1 or not is_allowed_file(file1.filename):
            return jsonify({"message": "Upload a valid ART Line List file"}), 400

        df = load_file(file1)
        df = ensureLGAState(df, emr_df)
        
        # Always apply date/numeric formatting
        for col in DATE_COLUMNS:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
                #df[col] = parse_any_date(df[col])
                
        for col in NUMERIC_COLUMNS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # === CASE 1: Only file1 ===
        if not file2 and not file3:
            output_filename = third95(df, end_date)

        # === CASE 2: file1 + file2 ===
        elif file2 and is_allowed_file(file2.filename) and not file3:
            #df_baseline = load_file(file2)
            #df = df.merge(df_baseline[['uuid', 'CurrentARTStatus']], on='uuid', how='left', suffixes=('', '_baseline'))
            #df['ARTStatus_PreviousQuarter'] = df['CurrentARTStatus_baseline']
            output_filename = third95(df, end_date)

        # === CASE 3: file1 + file3 ===
        elif file3 and is_allowed_file(file3.filename) and not file2:
            df_cmg = load_file(file3)
            if 'uuid' in df_cmg.columns and 'CASE MANAGER' in df_cmg.columns:
                df_cmg = df_cmg[['uuid', 'CASE MANAGER']]
                df = df.merge(df_cmg, on='uuid', how='left')
                df['CaseManager'] = df['CASE MANAGER'].fillna('Unassigned')
            else:
                return jsonify({"message": "File3 must contain 'uuid' and 'CASE MANAGER' columns"}), 400
            output_filename = third95CMG(df, end_date)

        # === CASE 4: file1 + file2 + file3 ===
        elif file2 and is_allowed_file(file2.filename) and file3 and is_allowed_file(file3.filename):
            #df_baseline = load_file(file2)
            #df = df.merge(df_baseline[['uuid', 'CurrentARTStatus']], on='uuid', how='left', suffixes=('', '_baseline'))
            #df['ARTStatus_PreviousQuarter'] = df['CurrentARTStatus_baseline']
            #df.to_excel('dfbaseline.xlsx', index=False)  # Debugging line to check df structure

            df_cmg = load_file(file3)
            if 'uuid' in df_cmg.columns and 'CASE MANAGER' in df_cmg.columns:
                df_cmg = df_cmg[['uuid', 'CASE MANAGER']]
                df = df.merge(df_cmg, on='uuid', how='left')
                df['CaseManager'] = df['CASE MANAGER'].fillna('Unassigned')
            else:
                return jsonify({"message": "File3 must contain 'uuid' and 'CASE MANAGER' columns"}), 400

            output_filename = third95CMG(df, end_date)

        # === Unsupported or partial case ===
        else:
            return jsonify({"message": "Invalid or unsupported combination of files"}), 400

        return jsonify({
            "message": "3RD 95 Analysis completed successfully.",
            "download_url": f"/download/{output_filename}"
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"message": f"Error: {str(e)}"}), 500
    
    
@bp.route('/fetch2nd95', methods=['POST'])
def fetch_second95():
    try:
        file1 = request.files.get("file1")
        file2 = request.files.get("file2")
        file3 = request.files.get("file3")
        end_date = request.form.get("endDate")

        if not file1 or not is_allowed_file(file1.filename):
            return jsonify({"message": "Upload a valid ART Line List file"}), 400

        df = load_file(file1)
        df = ensureLGAState(df, emr_df)

        # Format date/numeric columns
        for col in DATE_COLUMNS:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
                #df[col] = parse_any_date(df[col])
        for col in NUMERIC_COLUMNS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Run the 2ND 95 processing
        if not file2 and not file3:
            output_filename = second95(df, end_date)
            
        # === CASE 2: file1 + file2 ===
        elif file2 and is_allowed_file(file2.filename) and not file3:
            dfbaseline = load_file(file2)
            output_filename = Second95R(df, dfbaseline, end_date)
            
        # === CASE 3: file1 + file3 ===
        elif file3 and is_allowed_file(file3.filename) and not file2:
            df_cmg = load_file(file3)
            if 'uuid' in df_cmg.columns and 'CASE MANAGER' in df_cmg.columns:
                df_cmg = df_cmg[['uuid', 'CASE MANAGER']]
                df['CaseManager'] = df['uuid'].map(df_cmg.set_index('uuid')['CASE MANAGER']).fillna('Unassigned')
            else:
                return jsonify({"message": "File3 must contain 'uuid' and 'CASE MANAGER' columns"}), 400
            output_filename = second95CMG(df, end_date)
            
        # === CASE 4: file1 + file2 + file3 ===
        elif file2 and is_allowed_file(file2.filename) and file3 and is_allowed_file(file3.filename):
            df_baseline = load_file(file2)

            df_cmg = load_file(file3)
            if 'uuid' in df_cmg.columns and 'CASE MANAGER' in df_cmg.columns:
                df_cmg = df_cmg[['uuid', 'CASE MANAGER']]
                df['CaseManager'] = df['uuid'].map(df_cmg.set_index('uuid')['CASE MANAGER']).fillna('Unassigned')
            else:
                return jsonify({"message": "File3 must contain 'uuid' and 'CASE MANAGER' columns"}), 400

            output_filename = Second95RCMG(df, df_baseline, end_date)

        # === Unsupported or partial case ===
        else:
            return jsonify({"message": "Invalid or unsupported combination of files"}), 400

        return jsonify({
            "message": "2ND 95 Analysis completed successfully.",
            "download_url": f"/download/{output_filename}"
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"message": f"Error: {str(e)}"}), 500



#@bp.route('/download/<filename>')
#def download_file(filename):
    #output_dir = os.path.join(os.path.dirname(__file__), "..", "outputs")
    #path = os.path.abspath(os.path.join(output_dir, filename))

    #if os.path.exists(path):
        #return send_file(path, as_attachment=True)

    #return jsonify({"error": "File not found"}), 404

@bp.route('/download/<filename>')
def download_file(filename):
    path = OUTPUTS / filename

    if path.exists():
        return send_file(path, as_attachment=True)

    return jsonify({"error": "File not found"}), 404

