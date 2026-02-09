# Import OS module for file access
import os
import logging

# Import SentenceTransformer for semantic search
from sentence_transformers import SentenceTransformer, util

# Set up logging
logger = logging.getLogger(__name__)

# Global variables for model, embeddings, and text sections
MODEL = None
SECTION_EMBEDDINGS = None
SECTIONS = None

# Function to get the most relevant answer from the knowledge base using semantic search
def get_kb_answer(query: str) -> str:
    global MODEL, SECTION_EMBEDDINGS, SECTIONS
    
    logger.info(f"get_kb_answer called with query: {query}")

    # Lazy-load model and knowledge base only on first use
    if MODEL is None:
        from tqdm import tqdm  # For progress bar during embedding generation
        logger.info("Initializing knowledge base...")
        print("Initializing knowledge base...")

        # Read knowledge base content from the file
        kb_path = os.path.join(os.path.dirname(__file__), "KnowledgeBase.md")
        logger.info(f"Reading knowledge base from: {kb_path}")
        
        try:
            with open(kb_path, "r", encoding="utf-8") as f:
                KB_TEXT = f.read()
            logger.info(f"Knowledge base loaded successfully. Text length: {len(KB_TEXT)}")
        except Exception as e:
            logger.error(f"Failed to read knowledge base file: {e}")
            return "I'm sorry, I couldn't access the hotel information right now."

        # Split the KB text into sections separated by double newlines
        SECTIONS = KB_TEXT.split("\n\n")
        logger.info(f"Knowledge base split into {len(SECTIONS)} sections")

        # Load pre-trained sentence transformer model for embeddings
        logger.info("Loading sentence transformer model...")
        MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Sentence transformer model loaded successfully")

        # Generate embeddings for each section of the KB
        logger.info("Generating embeddings for knowledge base sections...")
        SECTION_EMBEDDINGS = MODEL.encode(SECTIONS, convert_to_tensor=True, show_progress_bar=True)
        logger.info("Embeddings generated successfully")

    # Encode the user's query into a semantic embedding
    logger.info("Encoding user query into embedding")
    query_embedding = MODEL.encode(query, convert_to_tensor=True)

    # Perform semantic search to find the closest matching section
    logger.info("Performing semantic search")
    hits = util.semantic_search(query_embedding, SECTION_EMBEDDINGS, top_k=1)

    # If no results found, return fallback message
    if not hits or not hits[0]:
        logger.warning("No matching sections found in knowledge base")
        return "I'm sorry, I couldn't find an answer for that."

    # Extract the best match using corpus_id
    best_match = hits[0][0]
    logger.info(f"Best match found with score: {best_match['score']}, corpus_id: {best_match['corpus_id']}")

    # Return the matching section from the knowledge base
    answer = SECTIONS[best_match["corpus_id"]]
    logger.info(f"Returning answer of length: {len(answer)}")
    return answer
