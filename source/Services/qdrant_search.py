from Database.sqlDB import embedding_model, qdrant_client 
import json
from Models.gpt4omini import query_model
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch





# List of all collections to search from
collections = ["careers", "servicesoffereds", "directorsinfo"]


# Load cross-encoder model for re-ranking
cross_encoder_model = AutoModelForSequenceClassification.from_pretrained("cross-encoder/ms-marco-MiniLM-L-6-v2")
cross_encoder_tokenizer = AutoTokenizer.from_pretrained("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerank(query: str, results: list):
    pairs = [(query, r.payload.get("text", "")) for r in results]

    inputs = cross_encoder_tokenizer(
        pairs,
        padding=True,
        truncation=True,
        return_tensors="pt"
    )

    with torch.no_grad():
        logits = cross_encoder_model(**inputs).logits
        scores = logits.squeeze(-1).tolist()

    reranked = []
    for res, score in zip(results, scores):
        reranked.append({
            "score": res.score,
            "re_rank_score": score,
            "payload": res.payload,
            "id": res.id
        })

    reranked = sorted(reranked, key=lambda x: x["re_rank_score"], reverse=True)
    return reranked[:5]


def qdrant_search(query: str):
    # Step 1: Encode the query
    query_vector = embedding_model.encode(query).tolist()

    # Step 2: Search all collections
    all_results = []
    for collection in collections:
        try:
            search_results = qdrant_client.search(
                collection_name=collection,
                query_vector=query_vector,
                limit=5,
                with_payload=True
            )
            for result in search_results:
                result.payload["__collection"] = collection  # Tag collection name
                all_results.append(result)
        except Exception as e:
            print(f"⚠️ Error querying collection '{collection}': {e}")

    # Step 3: Sort by score and get top 5 overall
    #top_results = sorted(all_results, key=lambda x: x.score, reverse=True)[:5]
    #db_result = [res.payload for res in top_results]

    # Step 3: Re-rank top N (e.g., 15) results for better quality
    top_pre_rerank = sorted(all_results, key=lambda x: x.score, reverse=True)[:15]
    final_results = rerank(query, top_pre_rerank)


    # 3. Ask the model to summarize the search results
    explanation_prompt = f"""
    You are GrootBot, an AI-assistant for Groot Software Solutions.
    You are given a list of search results from a database. Your task is to generate a short(under 200-characters-short), readable answer in natural language based on the result.
    - For any query related to careers or job openings, refer to the 'Careers' table in the database.
    - For any query related to founders or directors, refer to the 'directorsinfo' table in the database.
    - Positions available in the company are listed under the 'CareerTitle' column in the 'Careers' table.
    - Each job description is detailed in the 'ShortDescription' column of the 'Careers' table.
    In case user queries about services offered, ask user to visit our website at https://grootsoftwares.com/services.
    In case of an error or no results or if user wants to submit a resume ask user to email at hr@grootsoftwares.com".
    Question: {query}

    Results:
    {json.dumps(final_results, indent=2)}

    Generate a very-short, readable answer in natural language based on the result.
    """

    #final_response = query_model(explanation_prompt)

    return {
        #"question": query,
        #"response": 
        #final_response.content.strip()
        explanation_prompt
    }
