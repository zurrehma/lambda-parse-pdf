import argparse
import os
import pdfplumber
import re
from datetime import datetime
import boto3
from botocore.config import Config
import fitz  # PyMuPDF
import usaddress
import mysql.connector
import pytz

# Function to insert data into DynamoDB
mysql_host=''
mysql_user=''
mysql_password=''
mysql_database=''
dynamo_table_name = 'commerce_hub_packing_slips'
s3 = boto3.client('s3')
def insert_into_dynamodb(data):
    if "order_date_pst" in data:
        data.pop("order_date_pst")
    if "preferred_arrival_date_pst" in data:
        data.pop("preferred_arrival_date_pst")
    dynamodb = boto3.resource('dynamodb')
    table_name = dynamo_table_name
    table = dynamodb.Table(table_name)

    try:
        response = table.put_item(Item=data)
        print("Data inserted successfully into DynamoDB:", response)
    except Exception as e:
        print("Error inserting data into DynamoDB:", e)

# Function to insert data into MySQL RDS
def insert_into_mysql(data):
    rds_data={}
    rds_table_keys=["order_year", "hash", "po_number", "order_number", "order_id", "so_number", "order_date", "order_date_str", "preferred_arrival_date", "preferred_arrival_date_str", "ship_via", "quantity", "costco_sku", 
                    "vendor_ref", "description", "ship_to_name", "ship_to_first_name", "ship_to_last_name", "ship_to_middle_name",
                    "ship_to_addr1", "ship_to_addr2", "ship_to_attention", "ship_to_city", "ship_to_state", "ship_to_zip", 
                    "ship_to_country", "ship_to_phone", "ship_to_email", "bill_to_name", "bill_to_first_name", 
                    "bill_to_last_name", "bill_to_middle_name", "bill_to_addr1", "bill_to_addr2", "bill_to_attention", "bill_to_city", "bill_to_state",
                    "bill_to_zip", "bill_to_country", "bill_to_phone", "bill_to_email"]
    data_keys=["order_year", "key", "purchase_order", "customer_order", "order_id", "so_number", "order_date_pst", "customer_order_date", "preferred_arrival_date_pst", "preferred_arrival_date", "ship_via", "qty", "costco_item", 
               "vendor_ref", "description", "ship_to_name", "ship_to_first_name", "ship_to_last_name", "ship_to_middle_name",
               "ship_to_addr", "ship_to_addr2", "ship_to_compony", "ship_to_city", "ship_to_state", "ship_to_zip_code", 
               "ship_to_country", "ship_to_phone", "ship_to_email", "sold_to_name", "sold_to_first_name", "sold_to_last_name", 
               "sold_to_middle_name", "sold_to_addr", "sold_to_addr2", "sold_to_compony", "sold_to_city", "sold_to_state", 
               "sold_to_zip_code", "sold_to_country", "sold_to_phone", "sold_to_email"]

    for index, value in enumerate(data_keys):
        if value in data:
            rds_data[rds_table_keys[index]] = data[value]
        else:
            rds_data[rds_table_keys[index]] = "null"
    print("rds_data: ", rds_data)
    try:
        connection = mysql.connector.connect(
            host=mysql_host,
            user=mysql_user,
            password=mysql_password,
            database=mysql_database
        )
        cursor = connection.cursor()
        sql = """
            INSERT INTO commerce_hub_packing_slips (
                order_year, hash, po_number, order_number, order_id, so_number, order_date, order_date_str, 
                preferred_arrival_date, preferred_arrival_date_str, ship_via, quantity, costco_sku,
                vendor_ref, description, ship_to_name, ship_to_first_name, ship_to_last_name,
                ship_to_middle_name, ship_to_addr1, ship_to_addr2, ship_to_attention, ship_to_city,
                ship_to_state, ship_to_zip, ship_to_country, ship_to_phone, ship_to_email,
                bill_to_name, bill_to_first_name, bill_to_last_name, bill_to_middle_name,
                bill_to_addr1, bill_to_addr2, bill_to_attention, bill_to_city, bill_to_state,
                bill_to_zip, bill_to_country, bill_to_phone, bill_to_email
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        cursor.execute(sql, (
            rds_data['order_year'], rds_data["hash"], rds_data['po_number'], rds_data['order_number'], rds_data['order_id'], rds_data['so_number'], rds_data['order_date'], rds_data['order_date_str'], rds_data['preferred_arrival_date'], rds_data['preferred_arrival_date_str'],
            rds_data['ship_via'], rds_data['quantity'], rds_data['costco_sku'], rds_data['vendor_ref'],
            rds_data['description'], rds_data['ship_to_name'], rds_data['ship_to_first_name'],
            rds_data['ship_to_last_name'], rds_data['ship_to_middle_name'], rds_data['ship_to_addr1'],
            rds_data['ship_to_addr2'], rds_data['ship_to_attention'], rds_data['ship_to_city'],
            rds_data['ship_to_state'], rds_data['ship_to_zip'], rds_data['ship_to_country'],
            rds_data['ship_to_phone'], rds_data['ship_to_email'], rds_data['bill_to_name'],
            rds_data['bill_to_first_name'], rds_data['bill_to_last_name'], rds_data['bill_to_middle_name'],
            rds_data['bill_to_addr1'], rds_data['bill_to_addr2'], rds_data['bill_to_attention'],
            rds_data['bill_to_city'], rds_data['bill_to_state'], rds_data['bill_to_zip'],
            rds_data['bill_to_country'], rds_data['bill_to_phone'], rds_data['bill_to_email']
        ))
        connection.commit()
        print("Data inserted successfully into MySQL RDS")
    except Exception as e:
        print("Error inserting data into MySQL RDS:", e)
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def extract_all_ship_to_info(all_ship_to_details, data):
    lines = all_ship_to_details.split('\n')
    # Step 1: Extract name and contact details
    name = lines.pop(0).strip()

    # Iterate over lines in reverse order
    for line in reversed(lines):
        # Check if the line contains an email or phone number
        if re.match(r'\S+@\S+', line):
            email = line
            lines.remove(line)
        elif re.match(r'\d{1,}-\d{1,}-\d{1,}', line):
            phone = line
            lines.remove(line)

    #Remaining lines are likely the address (potentially with the company name)
    address_lines = ' '.join(lines)
    
    #Parse address using usaddress
    address_dict, address_type = usaddress.tag(address_lines)
    print("SHIP TO DETAILS:")
    # Print results
    if name:
        data["ship_to_name"]=name
        print(f"Name: {name}")
        match = re.match(r'(?P<first_name>\w+)\s*(?P<middle_name>\w*)\s+(?P<last_name>\w+)', name)
        if match:
            if match.group('first_name'):
                data["ship_to_first_name"] = match.group('first_name')
            if match.group('middle_name'):
                data["ship_to_middle_name"] = match.group('middle_name')
            if match.group('last_name'):
                data["ship_to_last_name"] = match.group('last_name')
    if 'Recipient' in address_dict:
        print(f"Company: {address_dict['Recipient']}")
        data["ship_to_compony"]=address_dict['Recipient']
        address_lines = address_lines.replace(address_dict['Recipient'], '').strip()
    if address_lines:
        print(f"Address: {address_lines}")
        data["ship_to_addr"]=address_lines
    if 'StreetName' in address_dict:
        print(f"City: {address_dict['PlaceName']}")
        print(f"State: {address_dict['StateName']}")
        print(f"ZIP Code: {address_dict['ZipCode']}")
        data["ship_to_city"]=address_dict['PlaceName']
        data["ship_to_state"]=address_dict['StateName']
        data["ship_to_zip_code"]=address_dict['ZipCode']
    if 'CountryName' in address_dict:
        print(f"Country: {address_dict['CountryName']}")
        data["ship_to_country_name"]=address_dict['CountryName']
    if 'phone' in locals():
        print(f"Phone: {phone}")
        data["ship_to_phone"]=phone
    if 'email' in locals():
        print(f"Email: {email}")
        data["ship_to_email"]=email

    return data

def extract_all_sold_to_info(all_sold_to_details, data):
    lines = all_sold_to_details.split('\n')
    # Step 1: Extract name and contact details
    name = lines.pop(0).strip()

    # Iterate over lines in reverse order
    for line in reversed(lines):
        # Check if the line contains an email or phone number
        if re.match(r'\S+@\S+', line):
            email = line
            lines.remove(line)
        elif re.match(r'\d{1,}-\d{1,}-\d{1,}', line):
            phone = line
            lines.remove(line)

    #Remaining lines are likely the address (potentially with the company name)
    address_lines = ' '.join(lines)
    
    #Parse address using usaddress
    address_dict, address_type = usaddress.tag(address_lines)

    # Print results
    print("SOLD TO DETAILS:")
    if name:
        data["sold_to_name"]=name
        print(f"Name: {name}")
        match = re.match(r'(?P<first_name>\w+)\s*(?P<middle_name>\w*)\s+(?P<last_name>\w+)', name)
        if match:
            if match.group('first_name'):
                data["sold_to_first_name"] = match.group('first_name')
            if match.group('middle_name'):
                data["sold_to_middle_name"] = match.group('middle_name')
            if match.group('last_name'):
                data["sold_to_last_name"] = match.group('last_name')
    if 'Recipient' in address_dict:
        print(f"Company: {address_dict['Recipient']}")
        data["sold_to_compony"]=address_dict['Recipient']
        address_lines = address_lines.replace(address_dict['Recipient'], '').strip()
    if address_lines:
        print(f"Address: {address_lines}")
        data["sold_to_addr"]=address_lines
    if 'StreetName' in address_dict:
        print(f"City: {address_dict['PlaceName']}")
        print(f"State: {address_dict['StateName']}")
        print(f"ZIP Code: {address_dict['ZipCode']}")
        data["sold_to_city"]=address_dict['PlaceName']
        data["sold_to_state"]=address_dict['StateName']
        data["sold_to_zip_code"]=address_dict['ZipCode']
    if 'CountryName' in address_dict:
        print(f"Country: {address_dict['CountryName']}")
        data["sold_to_country_name"]=address_dict['CountryName']
    if 'phone' in locals():
        print(f"Phone: {phone}")
        data["sold_to_phone"]=phone
    if 'email' in locals():
        print(f"Email: {email}")
        data["sold_to_email"]=email
        

    return data

def read_all_ship_to_info(pdf_path, index):
    doc = fitz.open(pdf_path)
    ship_to_data = ''
    sold_to_data = ''

    for i, page in enumerate(doc):
        if i == index: 
            pattern = re.compile(r"SHIP TO:(?P<ship_to>[\s\S]+?)SOLD TO:", re.DOTALL)

            match = pattern.search(page.get_text())

            if match:
                ship_to_data = match.group("ship_to").strip()
            else:
                print("<ship_to>: No match found.")

            pattern = re.compile(r"SOLD TO:(?P<sold_to>[\s\S]+?)PURCHASE ORDER", re.DOTALL)

            match = pattern.search(page.get_text())

            if match:
                sold_to_data = match.group("sold_to").strip()
            else:
                print("<sold_to>: No match found.")
    doc.close()
    return ship_to_data, sold_to_data

def save_pages_as_pdfs(pdf_path, output_directory, bucket):
    table1_keys = ['purchase_order', 'customer_order', 'customer_order_date', 'preferred_arrival_date', 'ship_via']
    table2_keys = ['qty', 'costco_item', 'vendor_ref', 'description']
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            data = {}
            ship_to_data, sold_to_data = read_all_ship_to_info(pdf_path, i)
            data = extract_all_ship_to_info(ship_to_data, data)
            data = extract_all_sold_to_info(sold_to_data, data)
            # page = pdf.pages
            # for page in pdf.pages:
            tables = page.find_tables()
            if len(tables) != 0:
                if len(tables) >= 1:
                    if len(tables[0].rows) > 1:
                            subscriptable=tables[0].extract(x_tolerance = 5)
                            for idx, value in enumerate(subscriptable[1]):
                                if value != '':
                                    data[table1_keys[idx]] = value
                if len(tables) >= 2:
                    if len(tables[1].rows) > 1:
                            subscriptable=tables[1].extract(x_tolerance = 5)
                            for idx, value in enumerate(subscriptable[1]):
                                if value != '':
                                    data[table2_keys[idx]] = value
            print(data)
            date_time_obj = datetime.strptime(data["customer_order_date"].replace('\n', '').replace(' EST', '').strip(), '%m/%d/%Y %I:%M %p')
            data["order_year"]=date_time_obj.year
            target_time_zone = pytz.timezone('America/Los_Angeles')
            order_date_pst = date_time_obj.astimezone(target_time_zone)
            data["order_date_pst"]=order_date_pst
            year = date_time_obj.year
            month = date_time_obj.month
            cleaned_purchase_order = re.sub(r'[^\w\s]', '_', data["purchase_order"])
            cleaned_date = re.sub(r'[^\w\s]', '_', data["customer_order_date"].replace('\n', '').replace(' EST', '').strip())
            output_file = os.path.join(output_directory, f"{cleaned_purchase_order}_{year}.pdf")
            data["key"]=f"{cleaned_purchase_order}_{year}{month}"
            insert_into_mysql(data)
            insert_into_dynamodb(data)
            page_pdf_paths = []
            doc = fitz.open(pdf_path)
            page = doc[i]
            output_pdf = fitz.open()
            output_pdf.insert_pdf(doc, from_page=i, to_page=i)
            output_pdf.save(output_file)
            s3.upload_file(output_file, bucket, f'archive/{os.path.basename(output_file)}')
            doc.close()

# Lambda_handler
def lambda_handler(event, context):
    global mysql_host, mysql_user, mysql_password, mysql_database, dynamo_table_name
    # Get the uploaded file details from the S3 event
    mysql_host = os.environ.get('MYSQL_HOST')
    mysql_user = os.environ.get('MYSQL_USER')
    mysql_password = os.environ.get('MYSQL_PASSWORD')
    mysql_database = os.environ.get('MYSQL_DATABASE')
    dynamo_table_name = os.environ.get('DYNAMO_TABLE_NAME')
    if not mysql_host or not mysql_user or not mysql_password or not mysql_database or not dynamo_table_name:
        print("Error: Required environment variables are missing.")
    else:

        bucket = event['Records'][0]['s3']['bucket']['name']
        key = event['Records'][0]['s3']['object']['key']
    
        # Download the PDF file from S3 'new' directory to Lambda's /tmp directory
        download_path = f'/tmp/{os.path.basename(key)}'
        s3.download_file(bucket, key, download_path)

        # Process individual pages and save as PDFs
        output_directory = '/tmp/output_pdfs/'
        os.makedirs(output_directory, exist_ok=True)
        save_pages_as_pdfs(download_path, output_directory, bucket)

        # Delete the original PDF file from the 'new' directory in S3
        s3.delete_object(Bucket=bucket, Key=key)
    