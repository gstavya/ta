import google.auth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from langchain_community.tools.gmail.utils import get_gmail_credentials
import re
import pandas as pd
import streamlit as st
import os
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import json

st.title("📄 TA Grader – Google Sheets Auto-Grader")

# The SCOPES variable defines what level of access you need. Modify as needed based on your requirements.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Function to get the Google OAuth credentials (This is to be used when authenticating users)
def get_credentials():
    # OAuth flow to generate the credentials
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'  # Desktop clients use this redirect URI
    auth_url, _ = flow.authorization_url(prompt='consent')
    return flow, auth_url

# Function to extract the spreadsheet ID from the Google Sheets URL
def extract_sheet_id(sheet_url):
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", sheet_url)
    return match.group(1) if match else None

# Streamlit Input UI for OAuth
def authenticate_user():
    flow, auth_url = get_credentials()

    # Show the authorization URL in the Streamlit app
    st.write("Please click the link below to authorize the app:")
    st.markdown(f"[Authorize the app]({auth_url})", unsafe_allow_html=True)

    # Get the authorization code from the user
    auth_code = st.text_input("Enter the authorization code here:")

    # If the user enters the code, fetch the token
    if auth_code:
        try:
            flow.fetch_token(code=auth_code)
            creds = flow.credentials
            st.success("Authentication successful!")
            return creds
        except Exception as e:
            st.error(f"❌ An error occurred: {e}")  # Print out the error for debugging
            return None
    return None

# Load Spreadsheet and Process Data
spreadsheet_file = st.file_uploader("📂 Upload Google Sheets (CSV format)", type=["csv"])
text_file = st.file_uploader("📜 Upload Activity File (TXT format)", type=["txt"])
sheet_url = st.text_input("🔗 Enter Google Sheets Link:")

# Authenticate the user
creds = authenticate_user()

if creds:
    # User authentication is successful, proceed with the process
    if sheet_url:
        spreadsheet_id = extract_sheet_id(sheet_url)
        if not spreadsheet_id:
            st.error("❌ Invalid Google Sheets URL. Please check the link.")

    # --- Process and Preview Uploaded Spreadsheet ---
    if spreadsheet_file and text_file and sheet_url:
        df = pd.read_csv(spreadsheet_file)
        text_content = text_file.read().decode("utf-8")

        st.write("### Preview of Uploaded Spreadsheet:")
        st.dataframe(df.head())

        # --- Select Column to Edit ---
        column_to_edit = st.selectbox("✏️ Select column to update:", df.columns)

        if st.button("🔍 Check Names and Update Preview"):
            update = ["TRUE" if name_in_text(name, text_content) else "FALSE" for name in df['Unnamed: 2']]
            df[column_to_edit] = update  
            st.session_state["updated_df"] = df  # Store in session state for persistence
            st.session_state["update_values"] = update  # Store update values

            st.write("### Updated Spreadsheet Preview:")
            st.dataframe(df)

    # --- Upload to Google Sheets ---
    if "updated_df" in st.session_state and st.button("🚀 Upload to Google Sheets"):
        df = st.session_state["updated_df"]
        update_values = st.session_state["update_values"]

        # Determine range dynamically based on selected column
        col_index = df.columns.get_loc(column_to_edit)
        column_letter = chr(ord('A') + col_index)  # Convert index to column letter
        range_name = f"{column_letter}2:{column_letter}{len(df) + 1}"  # Adjust range dynamically

        # Build the Google Sheets service with authenticated credentials
        try:
            service = build("sheets", "v4", credentials=creds)
            body = {"values": [[val] for val in update_values]}  # Ensure 2D list format

            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body=body,
            ).execute()

            st.success("✅ Successfully uploaded to Google Sheets!")  # Feedback on success
        except HttpError as error:
            st.error(f"❌ An error occurred: {error}")

# --- Helper Function ---
def name_in_text(name, text_content):
    pattern = r'\b' + re.escape(name) + r'\b'
    return bool(re.search(pattern, text_content, re.IGNORECASE))
