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
import webbrowser

st.title("📄 TA Grader – Google Sheets Auto-Grader")

import os
import pickle
import streamlit as st
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.auth import exceptions

# The SCOPES variable defines what level of access you need. 
# Modify as needed based on your requirements.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def authenticate_user():
    """Authenticate the user with Google and store the token.json file as JSON"""
    
    creds = None
    # The file token.json stores the user's access and refresh tokens.
    if os.path.exists('token.json'):
        with open('token.json', 'r') as token:
            creds_data = json.load(token)
            creds = Credentials.from_authorized_user_info(creds_data, SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except exceptions.GoogleAuthError as error:
                st.error(f"Error during token refresh: {error}")
                return None
        else:
            # Run the OAuth flow to get the credentials
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secrets.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run as a JSON file
        creds_data = creds.to_json()
        with open('token.json', 'w') as token:
            json.dump(creds_data, token)

    # Return authenticated Google API service (example with Google Drive)
    try:
        service = build('drive', 'v3', credentials=creds)
        return service
    except exceptions.HttpError as error:
        st.error(f"An error occurred: {error}")
        return None

def main():
    st.title('Google Authentication Example')

    # Button to authenticate the user
    if st.button('Authenticate with Google'):
        service = authenticate_user()
        if service:
            st.success("Authentication successful!")
            # Example: List files in Google Drive (can be replaced with your own API call)
            results = service.files().list(pageSize=10, fields="files(id, name)").execute()
            files = results.get('files', [])
            if not files:
                st.write('No files found.')
            for file in files:
                st.write(f"File ID: {file['id']} | Name: {file['name']}")
        else:
            st.error("Authentication failed!")

main()

# --- Function: Extract Google Sheets ID from Link ---
def extract_sheet_id(sheet_url):
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", sheet_url)
    return match.group(1) if match else None

# --- File Uploaders ---
spreadsheet_file = st.file_uploader("📂 Upload Google Sheets (CSV format)", type=["csv"])
text_file = st.file_uploader("📜 Upload Activity File (TXT format)", type=["txt"])
sheet_url = st.text_input("🔗 Enter Google Sheets Link:")

if sheet_url:
    spreadsheet_id = extract_sheet_id(sheet_url)
    if not spreadsheet_id:
        st.error("❌ Invalid Google Sheets URL. Please check the link.")

def name_in_text(name, text_content):
    pattern = r'\b' + re.escape(name) + r'\b'
    return bool(re.search(pattern, text_content, re.IGNORECASE))

# --- Load Spreadsheet ---
if spreadsheet_file and text_file and sheet_url:
    df = pd.read_csv(spreadsheet_file)
    text_content = text_file.read().decode("utf-8")

    st.write("### Preview of Uploaded Spreadsheet:")
    st.dataframe(df.head())

    # --- Select Column to Edit ---
    column_to_edit = st.selectbox("✏️ Select column to update:", df.columns)

    if st.button("🔍 Check Names and Update Preview"):
        update = ["TRUE" if name_in_text(name, text_content) else "FALSE" for name in df['Unnamed: 2']]
        print(df['Unnamed: 2'])
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

    credentials = get_gmail_credentials(
        token_file="token.json",
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
        client_secrets_file="credentials.json",
    )

    try:
        service = build("sheets", "v4", credentials=credentials)
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
