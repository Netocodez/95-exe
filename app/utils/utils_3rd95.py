from io import BytesIO
from datetime import datetime
import pandas as pd

from utils.paths import OUTPUTS

def export_3rd95_analysis(dataframes_dict, formatted_period, column_config=None):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    workbook = writer.book

    # --- Formats ---
    header_format = workbook.add_format({
        "bold": True, "text_wrap": True, "valign": "bottom",
        "fg_color": "#D7E4BC", "border": 1
    })
    row_band_format = workbook.add_format({'bg_color': '#F9F9F9'})
    percentage_format = workbook.add_format({'num_format': '0.00%'})
    grand_total_format = workbook.add_format({
        "bold": True, "text_wrap": True, "valign": "vcenter",
        "fg_color": "#C6EFCE", "font_color": "#006100",
        "border": 2, "font_size": 12
    })
    grand_total_percentage_format = workbook.add_format({
        "bold": True, "valign": "vcenter",
        "fg_color": "#C6EFCE", "font_color": "#006100",
        "border": 2, "num_format": "0.00%", "font_size": 12
    })
    title_format = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center'})

    def col_idx_to_excel(col_idx):
        div, mod = divmod(col_idx, 26)
        return chr(65 + mod) if div == 0 else chr(64 + div) + chr(65 + mod)

    # Strip datetime to date
    for df in dataframes_dict.values():
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.date

    # --- Process each sheet ---
    for sheet_name, df in dataframes_dict.items():

        worksheet = workbook.add_worksheet(sheet_name)
        writer.sheets[sheet_name] = worksheet

        # Write header
        for col_num, value in enumerate(df.columns):
            worksheet.write(0, col_num, value, header_format)

        # Write data
        df.to_excel(writer, sheet_name=sheet_name, startrow=1, header=False, index=False)

        # Sheets with banding + hide G
        if sheet_name in ["SC GAP", "PENDING RESULT", "LAST 30 DAYS MISSED SC",
                          "EXP NEXT 30 DAYS DUE FOR SC", "UNSUPPRESSED RESULTS"]:
            worksheet.conditional_format(1, 0, len(df), len(df.columns) - 1,
                                         {'type': 'formula', 'criteria': 'MOD(ROW(),2)=0', 'format': row_band_format})
            column_ranges = {'O:AG': 10, 'J:M': 12, 'N:N': 40, 'E:F': 15}
            for col_range, width in column_ranges.items():
                worksheet.set_column(col_range, width)
            worksheet.set_column('G:G', None, None, {'hidden': True})

        # ---------------- 3RD 95 SUMMARY ----------------
        if sheet_name == "3RD 95 SUMMARY":

            cfg = column_config.get(sheet_name, {}) if column_config else {}

            # --------------------------------------------
            # 1️⃣ GET CONFIGURABLE TITLE  (NEW)
            # --------------------------------------------
            title_text = cfg.get(
                "title",
                f"3RD 95 SUMMARY AS AT {formatted_period}"  # default
            )
            # Replace {period} if used in title
            title_text = title_text.replace("{period}", formatted_period)

            # --------------------------------------------
            # 2️⃣ GET CONFIGURABLE MERGE RANGE (NEW)
            # --------------------------------------------
            merge_start, merge_end = cfg.get("merge_columns", (0, 2))  # default A:C

            # Merge title row
            worksheet.merge_range(0, 0, 0, len(df.columns) - 1, title_text, title_format)

            # Rewrite header below title
            for col_num, value in enumerate(df.columns):
                worksheet.write(1, col_num, value, header_format)

            df.to_excel(writer, sheet_name=sheet_name, startrow=2, header=False, index=False)

            numeric_cols = cfg.get("numeric_cols", [3,4,5,8,10,11,12,13,14])

            percent_formulas = cfg.get("percent_formulas", {
                "%VL Sample Collection Rate": "=I{subtotal_row}/D{subtotal_row}",
                "%VL Coverage": "=E{subtotal_row}/D{subtotal_row}",
                "%VL Suppression Rate": "=F{subtotal_row}/E{subtotal_row}"
            })

            # Apply 3-color scales to percentage columns
            for col_name in percent_formulas:
                if col_name in df.columns:
                    col_idx = df.columns.get_loc(col_name)
                    worksheet.set_column(col_idx, col_idx, None, percentage_format)
                    worksheet.conditional_format(2, col_idx, len(df)+2, col_idx, {
                        'type': '3_color_scale',
                        'min_color': '#F8696B',
                        'mid_color': '#FFEB84',
                        'max_color': '#63BE7B'
                    })

            worksheet.conditional_format(2, 0, len(df)+1, len(df.columns)-1,
                                         {'type': 'formula','criteria':'MOD(ROW(),2)=0','format':row_band_format})

            worksheet.hide_gridlines(2)

            # Column widths
            col_widths = {'A:A':20,'B:B':35,'C:C':25}
            for col_range, width in col_widths.items():
                worksheet.set_column(col_range, width)

            # Subtotals per facility
            facility_col = 1
            start_row = 2
            current_row = start_row
            subtotal_rows = []

            while current_row <= len(df)+start_row-1:
                facility_name = df.iloc[current_row - start_row, facility_col]
                last_row = current_row

                while last_row <= len(df)+start_row-1 and df.iloc[last_row - start_row, facility_col] == facility_name:
                    last_row += 1

                subtotal_row = last_row
                subtotal_rows.append(subtotal_row+1)

                # -----------------------------------------------------------
                # SUBTOTAL MERGE — USE CONFIGURABLE RANGE  (NEW)
                # -----------------------------------------------------------
                worksheet.merge_range(
                    subtotal_row, merge_start,
                    subtotal_row, merge_end,
                    f"Subtotal – {facility_name}", header_format
                )

                # Numeric subtotal formulas
                for col in numeric_cols:
                    col_letter = col_idx_to_excel(col)
                    worksheet.write_formula(
                        subtotal_row, col,
                        f"=SUM({col_letter}{current_row+1}:{col_letter}{last_row})",
                        header_format
                    )

                # Percentage subtotal
                for col_name, formula in percent_formulas.items():
                    if col_name in df.columns:
                        col_idx = df.columns.get_loc(col_name)
                        formula_str = formula.replace("{subtotal_row}", str(subtotal_row+1))
                        worksheet.write_formula(subtotal_row, col_idx, formula_str, percentage_format)

                current_row = subtotal_row + 1

            # -----------------------------------------------------------
            # GRAND TOTAL ROW
            # -----------------------------------------------------------
            grand_total_row = current_row

            worksheet.merge_range(
                grand_total_row, merge_start,
                grand_total_row, merge_end,
                "GRAND TOTAL",
                grand_total_format
            )

            for col in numeric_cols:
                col_letter = col_idx_to_excel(col)
                subtotal_cells = ",".join([f"{col_letter}{r}" for r in subtotal_rows])
                worksheet.write_formula(
                    grand_total_row, col,
                    f"=SUM({subtotal_cells})",
                    grand_total_format
                )

            for col_name, formula in percent_formulas.items():
                if col_name in df.columns:
                    col_idx = df.columns.get_loc(col_name)
                    formula_str = formula.replace("{subtotal_row}", str(grand_total_row+1))
                    worksheet.write_formula(grand_total_row, col_idx, formula_str, grand_total_percentage_format)

    writer.close()
    output.seek(0)

    filename = f"3RD_95_ANALYSIS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    with open(OUTPUTS / filename, "wb") as f:
        f.write(output.getbuffer())

    return filename