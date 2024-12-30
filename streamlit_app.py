import streamlit as st
import pdfplumber
import pandas as pd
import io
import base64
import re

def clean_text(text):
    """Clean and standardize text from PDF"""
    if text:
        return ' '.join(text.split()).strip()
    return ''

def extract_table_from_pdf(pdf_file):
    """Extract tables from PDF with improved handling for ICICI format"""
    all_data = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            # First try to extract tables normally
            tables = page.extract_tables()
            
            if not tables:
                # If no tables found, try to extract text and parse it
                text = page.extract_text()
                lines = text.split('\n')
                
                # Process text line by line
                for line in lines:
                    # Clean the line
                    line = clean_text(line)
                    
                    # Skip empty lines and headers
                    if not line or 'Date' in line or 'Transaction Details' in line:
                        continue
                    
                    # Try to match date patterns and transaction details
                    date_match = re.search(r'\d{2}/\d{2}/\d{2,4}', line)
                    if date_match:
                        # Split the line into components
                        parts = re.split(r'\s{2,}', line)
                        if len(parts) >= 2:
                            date = date_match.group(0)
                            # Find amount (looking for numbers with decimal points)
                            amount = re.search(r'[\d,]+\.\d{2}', line)
                            amount = amount.group(0) if amount else ''
                            # Everything else is the description
                            description = ' '.join(parts[1:-1]) if len(parts) > 2 else parts[1]
                            
                            all_data.append([date, description, amount])
            else:
                # Process structured tables
                for table in tables:
                    for row in table:
                        # Clean and filter row data
                        cleaned_row = [clean_text(str(cell)) for cell in row if cell]
                        if cleaned_row and any(cleaned_row):
                            # Check if row contains date
                            if any(re.search(r'\d{2}/\d{2}/\d{2,4}', cell) for cell in cleaned_row):
                                all_data.append(cleaned_row)
    
    if not all_data:
        return None
        
    # Create DataFrame with appropriate columns
    columns = ['Date', 'Description', 'Amount']
    df = pd.DataFrame(all_data)
    
    # Ensure we have the right number of columns
    if len(df.columns) > len(columns):
        # Combine extra columns into description
        df = df.iloc[:, :len(columns)]
    elif len(df.columns) < len(columns):
        # Add missing columns
        for i in range(len(df.columns), len(columns)):
            df[i] = ''
            
    df.columns = columns
    return df

def process_credit_card_bill(df):
    """Process the extracted data with improved handling"""
    if df is None:
        return None
        
    # Remove any empty rows
    df = df.dropna(how='all')
    
    # Remove any duplicate rows
    df = df.drop_duplicates()
    
    # Clean up date format
    try:
        df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
        df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
    except:
        pass
    
    # Clean up amount format
    df['Amount'] = df['Amount'].replace('[\$,]', '', regex=True)
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
            with st.spinner('Processing PDF...'):
                # Process the PDF
                df = extract_table_from_pdf(uploaded_file)
                
                if df is not None:
                    df = process_credit_card_bill(df)
                    
                    if df is not None and not df.empty:
                        # Show preview
                        st.subheader("Preview of extracted data:")
                        st.dataframe(df.head())
                        
                        # Download button
                        st.markdown(get_download_link(df, format_type), unsafe_allow_html=True)
                        
                        # Display some basic statistics
                        st.subheader("Summary Statistics:")
                        num_transactions = len(df)
                        st.write(f"Total number of transactions: {num_transactions}")
                        
                        if 'Amount' in df.columns:
                            total_amount = df['Amount'].sum()
                            st.write(f"Total amount: ₹{total_amount:,.2f}")
                    else:
                        st.error("Could not process the data after extraction. Please check if the PDF contains valid transaction data.")
                else:
                    st.error("No transaction data found in the PDF. Please make sure you've uploaded a valid credit card statement.")
                    
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
            st.write("Please make sure you've uploaded a valid PDF file with transaction data.")

if __name__ == '__main__':
    main()
