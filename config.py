# Configuration for the Visual Agent
MODEL_LLM_VISION = "llama3.2-vision"  # or "openbmb/minicpm-v2.6"
BACKEND_TYPE = "ollama"  # "ollama" or "vllm"
VLLM_API_URL = "http://localhost:8000/v1"

# Additional configuration for rendering characters
GENERATE_TEXT_PROMPT = """You are an AI visual agent designed to help users by generating and displaying text in the selection area. 
Format your response as a string of visible characters, ensuring they appear within the selection area.
Make sure each character is clearly separated and easy to read."""