import streamlit as st
import pdfplumber
import pandas as pd
import io
import base64

def extract_table_from_pdf(pdf_file):
    """Extract tables from PDF and convert to DataFrame"""
    all_tables = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                # Clean up the table data
                cleaned_table = [[cell.strip() if cell else '' for cell in row] for row in table]
                all_tables.extend(cleaned_table)
    
    if not all_tables:
        return None
        
    # Convert to DataFrame
    df = pd.DataFrame(all_tables[1:], columns=all_tables[0])
    return df

def process_credit_card_bill(df):
    """Process the extracted data specifically for credit card bills"""
    if df is None:
        return None
        
    # Remove any empty rows
    df = df.dropna(how='all')
    
    # Remove any duplicate rows
    df = df.drop_duplicates()
    
    # Try to convert date columns to datetime
    date_columns = df.columns[df.columns.str.contains('date', case=False)]
    for col in date_columns:
        try:
            df[col] = pd.to_datetime(df[col])
        except:
            pass
    
    # Try to convert amount columns to numeric
    amount_columns = df.columns[df.columns.str.contains('amount|price|cost', case=False)]
    for col in amount_columns:
        df[col] = df[col].replace('[\$,]', '', regex=True)
        df[col] = pd.to_numeric(df[col], errors='ignore')
    
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
                    
                    # Show preview
                    st.subheader("Preview of extracted data:")
                    st.dataframe(df.head())
                    
                    # Download button
                    st.markdown(get_download_link(df, format_type), unsafe_allow_html=True)
                    
                    # Display some basic statistics
                    st.subheader("Summary Statistics:")
                    num_transactions = len(df)
                    st.write(f"Total number of transactions: {num_transactions}")
                    
                    # If there's an amount column, show total
                    amount_cols = df.columns[df.columns.str.contains('amount|price|cost', case=False)]
                    if not amount_cols.empty:
                        total_amount = df[amount_cols[0]].sum()
                        st.write(f"Total amount: ${total_amount:,.2f}")
                else:
                    st.error("No tables found in the PDF. Please make sure the PDF contains tabular data.")
                    
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
            st.write("Please make sure you've uploaded a valid PDF file with tabular data.")

if __name__ == '__main__':
    main()
