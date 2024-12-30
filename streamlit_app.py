import streamlit as st
import pdfplumber
import pandas as pd
import io
import base64
import re
import pdf2image
import pytesseract
from PIL import Image
import numpy as np

def extract_text_from_image(image):
    """Extract text from image using OCR"""
    # Increase image resolution for better OCR
    image = image.convert('L')  # Convert to grayscale
    # Apply threshold to make text more clear
    threshold = 200
    image = image.point(lambda p: p > threshold and 255)
    # Extract text using OCR
    custom_config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(image, config=custom_config)
    return text

def parse_transaction_line(line):
    """Parse a single line of transaction"""
    # Match date pattern (DD/MM/YY or DD/MM/YYYY)
    date_pattern = r'(\d{2}/\d{2}/(?:\d{2}|\d{4}))'
    # Match amount pattern (numbers with optional decimals and commas)
    amount_pattern = r'((?:Rs\.?|₹)?\s*[\d,]+\.?\d{0,2})'
    
    date_match = re.search(date_pattern, line)
    amount_match = re.search(amount_pattern, line)
    
    if date_match and amount_match:
        date = date_match.group(1)
        amount = amount_match.group(1)
        # Description is everything between date and amount
        description = line[date_match.end():amount_match.start()].strip()
        return [date, description, amount]
    return None

def extract_from_scanned_pdf(pdf_file):
    """Extract data from scanned PDF using OCR"""
    all_data = []
    
    try:
        # Convert PDF to images
        images = pdf2image.convert_from_bytes(pdf_file.read())
        
        for image in images:
            # Extract text from image
            text = extract_text_from_image(image)
            lines = text.split('\n')
            
            for line in lines:
                # Clean the line
                line = ' '.join(line.split()).strip()
                if line:
                    # Try to parse transaction
                    transaction = parse_transaction_line(line)
                    if transaction:
                        all_data.append(transaction)
    
        if not all_data:
            return None
            
        # Create DataFrame
        df = pd.DataFrame(all_data, columns=['Date', 'Description', 'Amount'])
        return df
    
    except Exception as e:
        st.error(f"Error in OCR processing: {str(e)}")
        return None

def process_credit_card_bill(df):
    """Process the extracted data"""
    if df is None or df.empty:
        return None
        
    # Remove any empty rows
    df = df.dropna(how='all')
    
    # Clean up date format
    try:
        df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
        # If above fails, try with 2-digit year
        mask = df['Date'].isna()
        df.loc[mask, 'Date'] = pd.to_datetime(df.loc[mask, 'Date'], format='%d/%m/%y', errors='coerce')
        df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
    except:
        pass
    
    # Clean up amount format
    df['Amount'] = df['Amount'].replace(r'[^\d.-]', '', regex=True)
    df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
    
    # Remove rows where date or amount is invalid
    df = df.dropna(subset=['Date', 'Amount'])
    
    return df

def get_download_link(df, format_type):
    """Generate a download link for the processed file"""
    if format_type == 'Excel':
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        excel_data = output.getvalue()
        b64 = base64.b64encode(excel_data).decode()
        return f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="processed_bill.xlsx">Download Excel File</a>'
    else:
        csv = df.to_csv(index=False)
        b64 = base64.b64encode(csv.encode()).decode()
        return f'<a href="data:file/csv;base64,{b64}" download="processed_bill.csv">Download CSV File</a>'

def main():
    st.set_page_config(page_title="Credit Card Bill Processor", page_icon="💳")
    
    st.title("Credit Card Bill Processor")
    st.write("Convert your credit card bill PDF to Excel/CSV")
    
    # File upload
    uploaded_file = st.file_uploader("Upload your credit card bill (PDF)", type=['pdf'])
    
    # Format selection
    format_type = st.radio("Select output format:", ('Excel', 'CSV'))
    
    if uploaded_file is not None:
        try:
            with st.spinner('Processing PDF... This may take a minute for scanned documents...'):
                # Try OCR extraction for scanned PDFs
                df = extract_from_scanned_pdf(uploaded_file)
                
                if df is not None and not df.empty:
                    df = process_credit_card_bill(df)
                    
                    if df is not None and not df.empty:
                        # Show preview
                        st.subheader("Preview of extracted data:")
                        st.dataframe(df.head())
                        
                        # Download button
                        st.markdown(get_download_link(df, format_type), unsafe_allow_html=True)
                        
                        # Display statistics
                        st.subheader("Summary Statistics:")
                        num_transactions = len(df)
                        st.write(f"Total number of transactions: {num_transactions}")
                        
                        if 'Amount' in df.columns:
                            total_amount = df['Amount'].sum()
                            st.write(f"Total amount: ₹{total_amount:,.2f}")
                    else:
                        st.error("Could not process the extracted data. Please check if the PDF contains valid transaction data.")
                else:
                    st.error("No transaction data found in the PDF. Please make sure you've uploaded a valid credit card statement.")
                    
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
            st.write("Please make sure you've uploaded a valid PDF file with transaction data.")

if __name__ == '__main__':
    main()
