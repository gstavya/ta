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

st.title("📄 TA Grader – Google Sheets Auto-Grader")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "openid",
    "email"
]

if st.button("Authenticate with Google"):
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', scopes=SCOPES)
    # Use run_console for environments without a local browser
    creds = flow.run_console()
    
    st.session_state["creds"] = creds
    user_email = creds.id_token.get("email") if creds.id_token else "Unknown"
    st.write(f"Authenticated as {user_email}")


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

    # Retrieve credentials from session state
    creds = st.session_state.get("creds")
    if not creds:
        st.error("Please authenticate first by clicking the 'Authenticate with Google' button.")
    else:
        try:
            from googleapiclient.discovery import build
            service = build("sheets", "v4", credentials=creds)
            body = {"values": [[val] for val in update_values]}  # Ensure 2D list format

            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body=body,
            ).execute()

            st.success("✅ Successfully uploaded to Google Sheets!")
        except Exception as error:
            st.error(f"❌ An error occurred: {error}")

