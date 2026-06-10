# 🎈 Pointer

Pointer is an agentic database selector. 

The Pointer database is a table of objects containing collection names, descriptions, and few shot examples.



In this case, there 6 databases;
   doctor, 
   therapist, 
   medical clinic, 
   mental health clinic, 
   providers, 
   general resources

a near text querey of the pointer database returns the collection name, which is passed to the next call.



to host on your machine, instead of streamlit, create .streamlit/secrets.toml using template included in repo

WEAVIATE_URL = "asdfaqsdgaf" - find the weaviate keys in Confluence

WEAVIATE_API_KEY = "asdadzf" - find the weaviate keys in Confluence

OPENAI_API_KEY = "ASFSFGCE" - use your own or text me

### How to run it on your own machine

1. Install the requirements

   ```
   $ pip install -r requirements.txt
   ```

2. Run the app

   ```
   $ streamlit run streamlit_app.py
   ```
