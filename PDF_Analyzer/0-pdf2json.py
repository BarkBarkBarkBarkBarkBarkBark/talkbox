# Updated Script: Integrated cleaned-up JSON schema into LLM prompt
import os
import re
import base64
import requests
import pdfplumber
from collections import defaultdict
from pdf2image import convert_from_path
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

api_key = os.getenv('OPENAI_KEY')

def first_page_to_markdown(pdf_path):
    """
    Extracts the first page text from the PDF and converts it to markdown format.
    """
    with pdfplumber.open(pdf_path) as pdf:
        first_page = pdf.pages[0]
        text = first_page.extract_text()

        if not text.strip():
            print("Warning: No text found on the first page.")
            return "# First Page Overview\n\n_No text found on the first page._"

        markdown = f"# First Page Overview\n\n```\n{text.strip()}\n```"
        
    document_name = Path(pdf_path).stem
    print(document_name)
    
    return markdown

def get_county_input():
    # Prompt the user to enter the county name
    county_name = input("Please enter the county name: ")
    return county_name

# Main function to get the first page context
def get_first_page_context(pdf_path):
    """
    Processes the first page of the PDF and returns its markdown content.
    """
    print(f"Processing the first page of {pdf_path}...")
    return first_page_to_markdown(pdf_path)


# Function to encode an image to Base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Function to extract text from a PDF using pdfplumber
def extract_text_from_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

# Function to parse data from extracted text (now accepts parsing logic as an argument)
def parse_data(text, parsing_logic):
    return parsing_logic(text)

# Example parsing logic function (can be replaced or passed dynamically)
def permit_parsing_logic(text):
    data = []
    sections = text.split("\n\n")  # Split by blank lines for sections
    current_record = defaultdict(lambda: None)

    for section in sections:
        if "Parcel Number" in section:
            match = re.search(r"Parcel Number:\s+([\d]+)", section)
            if match:
                current_record["ParcelNumber"] = match.group(1)
        if "Permit Number" in section:
            match = re.search(r"Permit Number:\s+([\w-]+)", section)
            if match:
                current_record["PermitNumber"] = match.group(1)
        if "Permit Type" in section:
            match = re.search(r"Permit Type:\s+([\w\s]+)", section)
            if match:
                current_record["PermitType"] = match.group(1)
        if "Status" in section:
            match = re.search(r"Status:\s+([\w]+)", section)
            if match:
                current_record["Status"] = match.group(1)
        if "Issue Date" in section:
            match = re.search(r"Issue Date:\s+([\d/]+)", section)
            if match:
                current_record["IssueDate"] = match.group(1)
        if "Finaled Date" in section:
            match = re.search(r"Finaled Date:\s+([\d/]+)", section)
            if match:
                current_record["FinaledDate"] = match.group(1)
        if "Valuation" in section:
            match = re.search(r"Valuation:\s+\$([\d,\.]+)", section)
            if match:
                current_record["Valuation"] = match.group(1)
        if "Total Cost" in section:
            match = re.search(r"Total Cost:\s+\$([\d,\.]+)", section)
            if match:
                current_record["TotalCost"] = match.group(1)
        if "Address" in section:
            match = re.search(r"Address:\s+([\w\s,]+)", section)
            if match:
                current_record["Address"] = match.group(1)
        if "Description" in section:
            match = re.search(r"Description:\s+(.+)", section)
            if match:
                current_record["Description"] = match.group(1)
        if any(current_record.values()):  # Save record if populated
            data.append(dict(current_record))
            current_record.clear()

    return data

# Function to process a single PDF file
def process_pdf(pdf_path, output_dir):
    images = convert_from_path(pdf_path, dpi=200,
                               poppler_path="/opt/homebrew/opt/poppler/bin")  # Adjust DPI for quality
    image_paths = []
    for i, image in enumerate(images):
        image_path = os.path.join(output_dir, f"{Path(pdf_path).stem}_page_{i + 1}.jpg")
        image.save(image_path, "JPEG")
        image_paths.append(image_path)
    return image_paths

# Function to send an image to the OpenAI API
def analyze_image(image_path, document_name, page_number, county_name, first_page_context):
    base64_image = encode_image(image_path)
    document_name = Path(image_path).name
    schema = {
        "permitSchema": {
            "ParcelNumber": "String",
            "PermitNumber": "String",
            "PermitType": "String",
            "Status": "String",
            "IssueDate": "String",
            "FinaledDate": "String",
            "Valuation": "String",
            "TotalCost": "String",
            "Address": "String",
            "Description": "String",
            "DocumentName": "String",
            "PageNumber": "Integer",
            "County": "String"
        },
        "exampleData": [
            {
                "ParcelNumber": "677029027",
                "PermitNumber": "2933-B-0-0",
                "PermitType": "Building",
                "Status": "Finaled",
                "IssueDate": "12/16/2019",
                "FinaledDate": "01/05/2023",
                "Valuation": "$278,814.00",
                "TotalCost": "$5,954.33",
                "Address": "469 Dryden St, Thousand Oaks, CA 91360",
                "Description": "Addition and remodel of existing single-family dwelling.",
                "DocumentName": document_name,
                "PageNumber": page_number,
                "County": county_name
            }
        ]
    }
    prompt_text = (
    f"Analyze the attached image and extract all possible details. Use this JSON structure for each entry:\n"
    f"{{\n"
    f"  \"ParcelNumber\": \"String\",\n"
    f"  \"PermitNumber\": \"String\",\n"
    f"  \"PermitType\": \"String\",\n"
    f"  \"Status\": \"String\",\n"
    f"  \"IssueDate\": \"String\",\n"
    f"  \"FinaledDate\": \"String\",\n"
    f"  \"Valuation\": \"String\",\n"
    f"  \"TotalCost\": \"String\",\n"
    f"  \"Address\": \"String\",\n"
    f"  \"Description\": \"String\",\n"
    f"  \"DocumentName\": \"String\",\n"
    f"  \"PageNumber\": \"Integer\",\n"
    f"  \"County\": \"String\"\n"
    f"}}\n\n"
    f"Example:\n{schema}\n\n"
    f"The document name is {document_name}.\n"
    f"Return valid JSON without extra text or code blocks. Start with '[' and end with ']'. "
    f"If data is missing or unclear, use null. Include all details. "
    f"please do not infer data, especially permit number. If there is data but no permit number, do not attempt to infer the permit number for context on the page, simply return nuill"
    f"First page reference:\n{first_page_context}"
    )
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }
        ],
        "max_tokens": 5000
    }
    response = requests.post("https://api.openai.com/v1/chat/completions", headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }, json=payload)

    if response.status_code == 200:
        return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    else:
        return f"Error: {response.status_code}, {response.text}"

# Main function to process a single PDF
def main(pdf_path, output_dir, parsing_logic, county_name):
    os.makedirs(output_dir, exist_ok=True)

    print(f"Processing {pdf_path}...")
    # Extract text from PDF
    text = extract_text_from_pdf(pdf_path)
    parsed_data = parse_data(text, parsing_logic)

    for record in parsed_data:
        print(f"Parsed Record: {record}")

    # Convert PDF pages to images
    image_paths = process_pdf(pdf_path, output_dir)

    for i, image_path in enumerate(image_paths):
        print(f"Analyzing {image_path}...")
        result = analyze_image(image_path, Path(pdf_path).name, i + 1, county_name)

        # Save the result for each page
        output_file = os.path.join(output_dir, f"{Path(image_path).stem}_analysis.json")
        with open(output_file, "w") as f:
            f.write(result)

        print(f"Analysis saved to {output_file}")

# Example usage
if __name__ == "__main__":
    pdf_path = input("PDF Path: ")
    output_dir = input("Output Directory: ")  # Replace with your output directory
    county_name = get_county_input()  # Get the county name once
    first_page_context = get_first_page_context(pdf_path)
    print("First Page Context:\n")
    print(first_page_context)
    main(pdf_path, output_dir, permit_parsing_logic, county_name)
