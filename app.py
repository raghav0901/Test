import dash
from dash import Dash, dcc, html, Input, Output, State
import pandas as pd
import urllib.parse
from flask import Flask
from flask_caching import Cache
from sqlalchemy import create_engine
import dash_bootstrap_components as dbc
from mitosheet.mito_dash.v1 import Spreadsheet, activate_mito, mito_callback
from dash.dependencies import ALL
 
# -----------------------------------------------------------------------------
# Initialize Flask + Dash app, activate Mito
# -----------------------------------------------------------------------------
server = Flask(__name__)
cache = Cache(server, config={'CACHE_TYPE': 'simple'})
app = Dash(__name__, server=server, external_stylesheets=[dbc.themes.BOOTSTRAP])
activate_mito(app)  # Must be called before layout using Spreadsheet
 
# -----------------------------------------------------------------------------
# Load full DataFrame once at startup and store in cache
# -----------------------------------------------------------------------------
conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
"SERVER=sacafpedvdba01.database.windows.net;"
    "DATABASE=sebfpeqc;"
    "UID=raghav.kapoor;"
    "PWD=K1zuXa1B82VESMe0xDq4i71AybBhjawrzUSx/xkiVPQ=;"
    "Encrypt=yes;"
    "TrustServerCertificate=no;"
)
params = urllib.parse.quote_plus(conn_str)
azure_connection_string = f"mssql+pyodbc:///?odbc_connect={params}"
azure_engine = create_engine(azure_connection_string)
 
try:
    print("sql connecting")
except Exception as e:
    print("Warning: could not load from DB, using sample data. Error:", e)
 


@server.route("/hello")
def hello():
    return "Hello, Flask + Dash is running!"
# -----------------------------------------------------------------------------
# mito_callback: capture edits and merge into cache
# (Uncomment and adjust if you want to persist edits back to master_df)
# -----------------------------------------------------------------------------
# @mito_callback(
#     Output('dummy-output', 'children'),
#     Input({'type': 'spreadsheet', 'id': ALL}, 'spreadsheet_result'),
#     # Note: Using ALL pattern if multiple spreadsheets might exist; adapt if needed.
#     State('Carrier-dropdown', 'value'),
#     State('application-dropdown', 'value'),
#     State('Status-dropdown', 'value')
# )
# def handle_mito(spreadsheet_result_list, selected_carrier, selected_app, selected_stat):
#     """
#     Called whenever the user edits *any* Spreadsheet created (pattern-matching id). Merge edits into master_df.
#     spreadsheet_result_list is a list; filter out None and find which one fired.
#     """
#     # Find the non-None spreadsheet_result in the list
#     spreadsheet_result = None
#     for res in spreadsheet_result_list:
#         if res is not None:
#             spreadsheet_result = res
#             break
#     if spreadsheet_result is None:
#         return None
#
#     df_edited = spreadsheet_result.dfs()[0]
#
#     # Merge edits back into master_df by ID, similar to your original logic
#     df_master = cache.get('master_df')
#     if df_master is None:
#         df_master = df_edited.copy()
#     else:
#         # If filters were applied when rendering sheet, update only those rows
#         if selected_carrier or selected_app or selected_stat:
#             df_master_indexed = df_master.set_index('ID')
#             df_edited_indexed = df_edited.set_index('ID')
#             for idx in df_edited_indexed.index:
#                 if idx in df_master_indexed.index:
#                     df_master_indexed.loc[idx, :] = df_edited_indexed.loc[idx, :]
#             df_merged = df_master_indexed.reset_index()
#         else:
#             # No filter: sheet shows full data; replace master entirely
#             df_merged = df_edited.copy()
#         df_master = df_merged
#
#     cache.set('master_df', df_master)
#     print("handle_mito: merged edits; new master_df shape:", df_master.shape)
#     return None
 
# -----------------------------------------------------------------------------
# Run server
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    app.server.run(debug=True,port=8000,host='0.0.0.0')

 






