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
    "TrustServerCertificate=yes;"
)
params = urllib.parse.quote_plus(conn_str)
azure_connection_string = f"mssql+pyodbc:///?odbc_connect={params}"
azure_engine = create_engine(azure_connection_string)
 
try:
    full_df = pd.DataFrame({
        'PlanSponsor': ['X', 'Y', 'X', 'Z'],
        'Carrier': ['A', 'A', 'B', 'B'],
        'Value': [10, 20, 30, 40],
        # If you refer to 'MemberStatus' or others in filters, ensure columns exist in sample:
        'MemberStatus': ['Active', 'Inactive', 'Active', 'Inactive']
    })
except Exception as e:
    print("Warning: could not load from DB, using sample data. Error:", e)
    full_df = pd.DataFrame({
        'PlanSponsor': ['X', 'Y', 'X', 'Z'],
        'Carrier': ['A', 'A', 'B', 'B'],
        'Value': [10, 20, 30, 40],
        # If you refer to 'MemberStatus' or others in filters, ensure columns exist in sample:
        'MemberStatus': ['Active', 'Inactive', 'Active', 'Inactive']
    })
 
# Ensure unique ID column exists for merging edits
if 'ID' not in full_df.columns:
    full_df = full_df.reset_index(drop=False).rename(columns={'index': 'ID'})
# Store initial DataFrame in cache
cache.set('master_df', full_df)
 
# -----------------------------------------------------------------------------
# Build dropdown options from cached DataFrame
# -----------------------------------------------------------------------------
df0 = cache.get('master_df')
carrier_options = [{'label': x, 'value': x} for x in sorted(df0['Carrier'].dropna().unique())]
app_options = [{'label': x, 'value': x} for x in sorted(df0['PlanSponsor'].dropna().unique())]
stat_options = [{'label': x, 'value': x} for x in sorted(df0['MemberStatus'].dropna().unique())]
 
# -----------------------------------------------------------------------------
# Globals for Spreadsheet IDs
# -----------------------------------------------------------------------------
sheet_counter = 0  # will increment each time Execute is clicked, to give new id
 
# -----------------------------------------------------------------------------
# Layout: dropdowns, Execute button, and placeholder Div for Spreadsheet
# -----------------------------------------------------------------------------
app.layout = dbc.Container([
    # Filter dropdowns
    dbc.Row([
        dbc.Col(
            dcc.Dropdown(
                id='Carrier-dropdown',
                options=carrier_options,
                placeholder="Select Carrier",
                clearable=True
            ),
            md=4
        ),
        dbc.Col(
            dcc.Dropdown(
                id='application-dropdown',
                options=app_options,
                placeholder="Select Application",
                clearable=True
            ),
            md=4
        ),
        dbc.Col(
            dcc.Dropdown(
                id='Status-dropdown',
                options=stat_options,
                placeholder="Select Status",
                clearable=True
            ),
            md=4
        )
    ], className="mb-4"),
 
    # Execute button row
    dbc.Row([
        dbc.Col(
            dbc.Button("Execute", id='execute-button', color='primary', n_clicks=0),
            width='auto'
        ),
    ], className="mb-4"),
 
    # Placeholder for the Spreadsheet; initially empty
    dbc.Row(
        dbc.Col(
            html.Div(id='sheet-wrapper'),
            width=12
        ),
        className="mb-4"
    ),
 
    # Dummy output for mito_callback (if you choose to hook edits)
    html.Div(id='dummy-output', style={'display': 'none'})
], fluid=True, className="p-4")
 
# -----------------------------------------------------------------------------
# Callback: triggered only by Execute button click. Filters are States.
# -----------------------------------------------------------------------------
@app.callback(
    Output('sheet-wrapper', 'children'),
    Input('execute-button', 'n_clicks'),
    State('Carrier-dropdown', 'value'),
    State('application-dropdown', 'value'),
    State('Status-dropdown', 'value'),
    prevent_initial_call=False  # we handle n_clicks==0 inside
)
def on_execute(n_clicks, selected_carrier, selected_app, selected_stat):
    """
    When Execute button is clicked (n_clicks>=1), fetch the master DataFrame from cache, apply filters,
    and return a new Spreadsheet with the filtered data. On initial load (n_clicks is None or 0),
    return an empty Div or placeholder.
    """
    global sheet_counter
 
    # If button has never been clicked (n_clicks is None or 0), do not render the Spreadsheet
    if not n_clicks:
        # Optionally, you can return a message like:
        # return html.Div("Click 'Execute' to load data.")
        return html.Div()  # empty
 
    # Button has been clicked at least once: apply filters
    df_master = cache.get('master_df')
    if df_master is None:
        df_master = full_df.copy()
        cache.set('master_df', df_master)
 
    dff = df_master.copy()
    if selected_carrier:
        dff = dff[dff['Carrier'] == selected_carrier]
    if selected_app:
        dff = dff[dff['PlanSponsor'] == selected_app]
    if selected_stat:
        dff = dff[dff['MemberStatus'] == selected_stat]
 
    # Increment sheet_counter to give a fresh id each time
    sheet_counter += 1
    sheet_id = {'type': 'spreadsheet', 'id': sheet_counter}
    # Create and return the Spreadsheet component
    spread = Spreadsheet(dff, id=sheet_id)
    return spread
 
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
 