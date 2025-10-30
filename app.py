import os
import time
import functools
import logging
from logging.handlers import TimedRotatingFileHandler

import dash
from dash import Dash, dcc, html, Input, Output, State
import pandas as pd
import urllib.parse
from flask import Flask, request, jsonify
from flask_caching import Cache
from sqlalchemy import create_engine
import dash_bootstrap_components as dbc
from mitosheet.mito_dash.v1 import Spreadsheet, activate_mito, mito_callback
from dash.dependencies import ALL
from flask_cors import CORS

# -----------------------
# Logging setup
# -----------------------
def setup_logging(log_dir="logs", log_file="app.log", level=logging.INFO,
                  when="midnight", backupCount=7, use_json=False):
    """
    Create a root logger: console + rotating file.
    log_dir: relative path (default 'logs') so you don't need root permissions.
    """
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file)

    logger = logging.getLogger()
    logger.setLevel(level)

    # Avoid duplicate handlers on re-import
    if any(isinstance(h, TimedRotatingFileHandler) and getattr(h, "baseFilename", "") == os.path.abspath(log_path)
           for h in logger.handlers):
        # already configured
        return logger

    # Formatter
    fmt = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    formatter = logging.Formatter(fmt)

    # Console handler (stdout)
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # Timed rotating file handler (daily)
    fh = TimedRotatingFileHandler(log_path, when=when, backupCount=backupCount, utc=True)
    fh.setLevel(level)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Reduce verbose werkzeug logs unless you want them
    logging.getLogger('werkzeug').setLevel(logging.INFO)

    return logger

def register_flask_request_logging(flask_app: Flask, logger=None):
    logger = logger or logging.getLogger(__name__)

    @flask_app.before_request
    def _log_request_start():
        try:
            logger.info("REQ %s %s from=%s ua=%s", request.method, request.path, request.remote_addr, request.user_agent)
        except Exception:
            logger.info("REQ %s %s (could not log all request metadata)", request.method, request.path)

    @flask_app.errorhandler(Exception)
    def handle_unexpected_error(error):
        try:
            logger.exception("Unhandled exception while processing request %s %s", request.method, request.path)
        except Exception:
            logger.exception("Unhandled exception in request (error logging failed)")
        return "Internal Server Error", 500

# Optional decorator for logging general python function calls (not used on Dash callbacks here)
def log_call(logger=None):
    logger = logger or logging.getLogger(__name__)
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                logger.info("CALL %s args=%s kwargs=%s", fn.__name__, args, kwargs)
            except Exception:
                logger.info("CALL %s (args could not be stringified)", fn.__name__)
            start = time.time()
            try:
                result = fn(*args, **kwargs)
                duration = time.time() - start
                logger.info("RETURN %s duration=%.4fs", fn.__name__, duration)
                return result
            except Exception:
                logger.exception("EXCEPTION in %s", fn.__name__)
                raise
        return wrapper
    return decorator

# -----------------------
# Initialize Flask + Dash app, activate Mito
# -----------------------
serverr = Flask(__name__)
CORS(serverr)
cache = Cache(serverr, config={'CACHE_TYPE': 'simple'})
app = Dash(__name__, server=serverr, external_stylesheets=[dbc.themes.BOOTSTRAP],
           routes_pathname_prefix='/dash/', requests_pathname_prefix='/dash/')
activate_mito(app)  # Must be called before layout using Spreadsheet

# Setup logger now (writes to ./logs/app.log by default)
logger = setup_logging(log_dir="logs", log_file="app.log", level=logging.INFO)
register_flask_request_logging(serverr, logger=logger)

server = app.server

guid = None
@serverr.route('/incoming', methods=['POST','GET'])
def api_filter():
    payload = request.get_json() or {}
    global guid
    guid = payload.get('guid')
    logger.info("Received filter request with guid: %s payload_keys=%s", guid, list(payload.keys()))
    return jsonify({'status': 'ok'}), 200

# -----------------------
# Load full DataFrame once at startup and store in cache
# -----------------------
# NOTE: Be careful: avoid logging secrets (DB password) — do NOT log connection string in plaintext
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
    logger.info("Attempting to load DataFrame from DB via stored procedure Census_Eng")
    full_df = pd.read_sql("SET NOCOUNT ON; EXEC Census_Eng", azure_engine.raw_connection())
    if 'BirthDate' in full_df.columns:
        full_df['BirthDate'] = pd.to_datetime(full_df['BirthDate'], format='%Y-%m-%d', errors='coerce')
    logger.info("Loaded full_df from DB with shape %s", full_df.shape)
except Exception as e:
    logger.exception("Warning: could not load from DB, using sample data. Error: %s", e)
    full_df = pd.DataFrame({
        'PlanSponsor': ['X', 'Y', 'X', 'Z'],
        'Carrier': ['A', 'A', 'B', 'B'],
        'Value': [10, 20, 30, 40],
        'MemberStatus': ['Active', 'Inactive', 'Active', 'Inactive']
    })

# Ensure unique ID column exists for merging edits
if 'ID' not in full_df.columns:
    full_df = full_df.reset_index(drop=False).rename(columns={'index': 'ID'})
# Store initial DataFrame in cache
cache.set('master_df', full_df)
logger.info("Stored master_df in cache; shape=%s", full_df.shape)

# -----------------------
# Build dropdown options from cached DataFrame
# -----------------------
df0 = cache.get('master_df')
carrier_options = [{'label': x, 'value': x} for x in sorted(df0['Carrier'].dropna().unique())]
app_options = [{'label': x, 'value': x} for x in sorted(df0['PlanSponsor'].dropna().unique())]
stat_options = [{'label': x, 'value': x} for x in sorted(df0['MemberStatus'].dropna().unique())]

# -----------------------
# Globals for Spreadsheet IDs
# -----------------------
sheet_counter = 0  # will increment each time Execute is clicked, to give new id

# -----------------------
# Layout: dropdowns, Execute button, and placeholder Div for Spreadsheet
# -----------------------
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

# -----------------------
# Callback: triggered only by Execute button click. Filters are States.
# -----------------------
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
        return html.Div()  # empty

    start = time.time()
    try:
        logger.info("on_execute called: n_clicks=%s carrier=%s app=%s status=%s", n_clicks, selected_carrier, selected_app, selected_stat)

        df_master = cache.get('master_df')
        if df_master is None:
            df_master = full_df.copy()
            cache.set('master_df', df_master)
            logger.info("Repopulated master_df from full_df; shape=%s", df_master.shape)

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

        duration = time.time() - start
        logger.info("on_execute returning spreadsheet id=%s rows=%s duration=%.3fs", sheet_counter, len(dff), duration)
        return spread

    except Exception:
        logger.exception("Exception in on_execute")
        # Return something safe to user
        return html.Div("Error loading data (check server logs).")

# -----------------------
# mito_callback: capture edits and merge into cache
# (Uncomment and adjust if you want to persist edits back to master_df)
# -----------------------
# @mito_callback(
#     Output('dummy-output', 'children'),
#     Input({'type': 'spreadsheet', 'id': ALL}, 'spreadsheet_result'),
#     State('Carrier-dropdown', 'value'),
#     State('application-dropdown', 'value'),
#     State('Status-dropdown', 'value')
# )
# def handle_mito(spreadsheet_result_list, selected_carrier, selected_app, selected_stat):
#     try:
#         logger.info("handle_mito called; looking for spreadsheet result among %s", len(spreadsheet_result_list))
#         spreadsheet_result = None
#         for res in spreadsheet_result_list:
#             if res is not None:
#                 spreadsheet_result = res
#                 break
#         if spreadsheet_result is None:
#             logger.info("handle_mito: no spreadsheet_result found")
#             return None
#
#         df_edited = spreadsheet_result.dfs()[0]
#         logger.info("handle_mito: edited rows=%s", len(df_edited))
#
#         df_master = cache.get('master_df')
#         if df_master is None:
#             df_master = df_edited.copy()
#             logger.info("handle_mito: no master_df in cache, using edited as master")
#         else:
#             if selected_carrier or selected_app or selected_stat:
#                 df_master_indexed = df_master.set_index('ID')
#                 df_edited_indexed = df_edited.set_index('ID')
#                 for idx in df_edited_indexed.index:
#                     if idx in df_master_indexed.index:
#                         df_master_indexed.loc[idx, :] = df_edited_indexed.loc[idx, :]
#                 df_merged = df_master_indexed.reset_index()
#             else:
#                 df_merged = df_edited.copy()
#             df_master = df_merged
#
#         cache.set('master_df', df_master)
#         logger.info("handle_mito: merged edits; new master_df shape: %s", df_master.shape)
#     except Exception:
#         logger.exception("Exception in handle_mito")
#     return None

# -----------------------
# Run server
# -----------------------
if __name__ == '__main__':
    logger.info("Starting Flask server (debug=%s)", True)
    server.run(debug=True, port=8000, host='0.0.0.0')
