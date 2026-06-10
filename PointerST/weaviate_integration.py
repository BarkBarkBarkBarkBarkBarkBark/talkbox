# weaviate_integration.py


def weaviate_process(user_query):
    # Import libraries
    from dotenv import load_dotenv
    import weaviate.classes as wvc
    import os
    load_dotenv()

    # Best practice: store your credentials in environment variables
    wcd_url = os.environ["WEAVIATE_URL"]
    wcd_api_key = os.environ["WEAVIATE_API_KEY"]
    openai_api_key = os.environ["OPENAI_API_KEY"]

    import weaviate
    from weaviate.classes.init import Auth



    # Establish the Weaviate client connection
    client = weaviate.connect_to_weaviate_cloud(
        cluster_url=wcd_url,
        auth_credentials=wvc.init.Auth.api_key(wcd_api_key),
        headers={"X-OpenAI-Api-Key": openai_api_key}
    )

    try:
        # Initial query to get the database name
        collection_name = "Pointer"
        questions = client.collections.get(collection_name)

        response = questions.query.near_text(
            query=user_query,  # Use user_query instead of input()
            limit=6
        )

        # Extract the database name from the response properties
        database_name = response.objects[0].properties.get("database_name")
        
        # Use the extracted database name in a subsequent call
        if database_name:
            next_query_response = client.collections.get(database_name).query.near_text(
                query=user_query,  # Use the same user query
                limit=20
            )
            
            # Collect the properties of each object
            results = []

            
            for obj in next_query_response.objects[:20]:
                results.append(obj.properties)
            
            import random
            random.shuffle(results)
            results = results[:20]

            return results
        else:
            return ["Database name not found in the response."]
    finally:
        client.close()  # Ensure the client is closed gracefully
