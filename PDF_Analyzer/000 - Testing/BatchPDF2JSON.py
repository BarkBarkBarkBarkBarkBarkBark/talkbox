# # the following script doesnt correctly iterate the first page context against each new PDF. The combined markdown of all first pages is passed as system prompt context in each iteration, which i assume would cause token bloat and clipping. pdf2JSON works wonderfully, and probably a new main.py could be made that iterates it against each document in a directory. 

# # Updated Script: Integrated cleaned-up JSON schema into LLM prompt
# import os
# import re
# import base64
# import requests
# import pdfplumber
# from collections import defaultdict
# from pdf2image import convert_from_path
# from pathlib import Path

# from dotenv import load_dotenv


# load_dotenv()


# api_key = os.getenv('OPENAI_KEY')

# def first_page_to_markdown(pdf_path):
#     """
#     Extracts the first page text from the PDF and converts it to markdown format.
#     """
#     with pdfplumber.open(pdf_path) as pdf:
#         first_page = pdf.pages[0]
#         text = first_page.extract_text()

#         if not text.strip():
#             print("Warning: No text found on the first page.")
#             return "# First Page Overview\n\n_No text found on the first page._"

#         markdown = f"# First Page Overview\n\n```\n{text.strip()}\n```"
        
#     document_name = Path(pdf_path).stem
#     print(document_name)
    
#     return markdown

# # Main function to get the first page context
# def get_first_page_context(pdf_path):
#     """
#     Processes the first page of the PDF and returns its markdown content.
#     """
#     print(f"Processing the first page of {pdf_path}...")
#     return first_page_to_markdown(pdf_path)


# # Function to encode an image to Base64
# def encode_image(image_path):
#     with open(image_path, "rb") as image_file:
#         return base64.b64encode(image_file.read()).decode('utf-8')

# # Function to extract text from a PDF using pdfplumber
# def extract_text_from_pdf(pdf_path):
#     with pdfplumber.open(pdf_path) as pdf:
#         text = ""
#         for page in pdf.pages:
#             text += page.extract_text() + "\n"
#     return text

# # Function to parse data from extracted text (now accepts parsing logic as an argument)
# def parse_data(text, parsing_logic):
#     return parsing_logic(text)

# # Example parsing logic function (can be replaced or passed dynamically)
# def permit_parsing_logic(text):
#     data = []
#     sections = text.split("\n\n")  # Split by blank lines for sections
#     current_record = defaultdict(lambda: None)

#     for section in sections:
#         if "Parcel Number" in section:
#             match = re.search(r"Parcel Number:\s+([\d]+)", section)
#             if match:
#                 current_record["ParcelNumber"] = match.group(1)
#         if "Permit Number" in section:
#             match = re.search(r"Permit Number:\s+([\w-]+)", section)
#             if match:
#                 current_record["PermitNumber"] = match.group(1)
#         if "Permit Type" in section:
#             match = re.search(r"Permit Type:\s+([\w\s]+)", section)
#             if match:
#                 current_record["PermitType"] = match.group(1)
#         if "Status" in section:
#             match = re.search(r"Status:\s+([\w]+)", section)
#             if match:
#                 current_record["Status"] = match.group(1)
#         if "Issue Date" in section:
#             match = re.search(r"Issue Date:\s+([\d/]+)", section)
#             if match:
#                 current_record["IssueDate"] = match.group(1)
#         if "Finaled Date" in section:
#             match = re.search(r"Finaled Date:\s+([\d/]+)", section)
#             if match:
#                 current_record["FinaledDate"] = match.group(1)
#         if "Valuation" in section:
#             match = re.search(r"Valuation:\s+\$([\d,\.]+)", section)
#             if match:
#                 current_record["Valuation"] = match.group(1)
#         if "Total Cost" in section:
#             match = re.search(r"Total Cost:\s+\$([\d,\.]+)", section)
#             if match:
#                 current_record["TotalCost"] = match.group(1)
#         if "Address" in section:
#             match = re.search(r"Address:\s+([\w\s,]+)", section)
#             if match:
#                 current_record["Address"] = match.group(1)
#         if "Description" in section:
#             match = re.search(r"Description:\s+(.+)", section)
#             if match:
#                 current_record["Description"] = match.group(1)
#         if any(current_record.values()):  # Save record if populated
#             data.append(dict(current_record))
#             current_record.clear()

#     return data

# # Function to process a single PDF file
# def process_pdf(pdf_path, output_dir):
#     images = convert_from_path(pdf_path, dpi=200,
#                                poppler_path="/opt/homebrew/opt/poppler/bin")  # Adjust DPI for quality
#     image_paths = []
#     for i, image in enumerate(images):
#         image_path = os.path.join(output_dir, f"{Path(pdf_path).stem}_page_{i + 1}.jpg")
#         image.save(image_path, "JPEG")
#         image_paths.append(image_path)
#     return image_paths

# # Function to send an image to the OpenAI API
# def analyze_image(image_path, page_number):
#     base64_image = encode_image(image_path)
#     document_name = Path(image_path).name  # Extract the file name from the image path
#     # Define the example schema
#     example_schema = {
#         "ParcelNumber": "677029027",
#         "PermitNumber": "2933-B-0-0",
#         "PermitType": "Building",
#         "Status": "Finaled",
#         "IssueDate": "12/16/2019",
#         "FinaledDate": "01/05/2023",
#         "Valuation": "$278,814.00",
#         "TotalCost": "$5,954.33",
#         "Address": "469 Dryden St, Thousand Oaks, CA 91360",
#         "Description": "Addition and remodel of existing single-family dwelling.",
#         "DocumentName": document_name,  # Use the extracted file name
#         "PageNumber": page_number
#     }
#     prompt_text = (
#         f"Please analyze the attached image and extract **all possible information** in as much detail as possible. "
#         f"Use the following JSON structure for your output:\n"
#         f"{{\n"
#         f"  \"ParcelNumber\": \"String\",\n"
#         f"  \"PermitNumber\": \"String\",\n"
#         f"  \"PermitType\": \"String\",\n"
#         f"  \"Status\": \"String\",\n"
#         f"  \"IssueDate\": \"String\",\n"
#         f"  \"FinaledDate\": \"String\",\n"
#         f"  \"Valuation\": \"String\",\n"
#         f"  \"TotalCost\": \"String\",\n"
#         f"  \"Address\": \"String\",\n"
#         f"  \"Description\": \"String\",\n"
#         f"  \"DocumentName\": \"{document_name}\",\n"  # Include the file name in the prompt
#         f"  \"PageNumber\": {page_number}\n"
#         f"}}\n\n"
#         f"Here is an example of how the data should be structured:\n{example_schema}\n\n"
#         f"Please don't include the example schema in the JSON output, only data extracted from the image. "
#         f"Please don't include any commentary at the beginning or end of the JSON output document. "
#         f"Please ensure that the output document is valid JSON, with appropriate opening and closing braces. "
#         f"Please ensure that the output document doesn't begin with a newline character, or any characters that aren't valid JSON. "
#         f"The first page of this multipage document has been extracted to markdown, please use it to reference heading structure if you are unsure:\n{first_page_context}\n\n"
#         f"IMPORTANT: Ensure completeness and do not omit any information, even if it seems minor. "
#         f"If any part is unclear or incomplete, iterate and refine the response until every detail is captured. "
#         f"The output file needs to be pure JSON, with no code block indicators or other formatting. Do not output code, provide plain text JSON. "
#         f"Ensure there are square brackets at the beginning and end of the output document, it needs to be a valid JSON object. "
#         f"Data is represented in multiple rows, so it is possible that data is truncated. Please return a null string for missing data. If you are unsure, please return a null string."
#     )
#     payload = {
#         "model": "gpt-4o",
#         "messages": [
#             {
#                 "role": "user",
#                 "content": [
#                     {"type": "text", "text": prompt_text},
#                     {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
#                 ]
#             }
#         ],
#         "max_tokens": 4000
#     }
#     response = requests.post("https://api.openai.com/v1/chat/completions", headers={
#         "Content-Type": "application/json",
#         "Authorization": f"Bearer {api_key}"
#     }, json=payload)

#     if response.status_code == 200:
#         return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
#     else:
#         return f"Error: {response.status_code}, {response.text}"

# def list_pdf_files(directory):
#     """
#     Lists all PDF files in the given directory.
#     """
#     return [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith('.pdf')]

# # Main function to process all PDFs in a directory
# def process_directory(pdf_dir, output_dir, parsing_logic):
#     os.makedirs(output_dir, exist_ok=True)

#     pdf_files = list_pdf_files(pdf_dir)
#     for pdf_path in pdf_files:
#         print(f"Processing {pdf_path}...")
#         # Extract text from PDF
#         text = extract_text_from_pdf(pdf_path)
#         parsed_data = parse_data(text, parsing_logic)

#         for record in parsed_data:
#             print(f"Parsed Record: {record}")

#         # Convert PDF pages to images
#         image_paths = process_pdf(pdf_path, output_dir)

#         for i, image_path in enumerate(image_paths):
#             print(f"Analyzing {image_path}...")
#             result = analyze_image(image_path, i + 1)  # Pass the correct page number

#             # Save the result for each page
#             output_file = os.path.join(output_dir, f"{Path(image_path).stem}_analysis.json")
#             with open(output_file, "w") as f:
#                 f.write(result)

#             print(f"Analysis saved to {output_file}")

# # Example usage
# if __name__ == "__main__":
#     pdf_dir = input("PDF Directory: ")
#     output_dir = input("Output Directory: ")  # Replace with your output directory
#     for pdf_path in list_pdf_files(pdf_dir):
#         first_page_context = get_first_page_context(pdf_path)
#         print("First Page Context:\n")
#         print(first_page_context)
#     process_directory(pdf_dir, output_dir, permit_parsing_logic)
